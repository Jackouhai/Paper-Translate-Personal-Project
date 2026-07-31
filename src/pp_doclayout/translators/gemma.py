import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

from .base import BaseTranslator

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES = {
    "en": "English",
    "vi": "Vietnamese",
}


class GemmaTranslator(BaseTranslator):
    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        max_concurrent_requests: int | None = None
    ):
        from ..config import settings

        self.base_url = base_url or settings.vllm_base_url
        self.model_name = model_name or settings.vllm_model_name
        self.context_window = settings.vllm_context_window
        self.chat_template_reserve = settings.vllm_chat_template_reserve
        self.max_input_tokens = settings.translation_max_input_tokens
        self.max_concurrent_requests = max_concurrent_requests or settings.max_concurrent_requests
        self.retry_attempts = settings.vllm_retry_attempts

        self.client = OpenAI(base_url=self.base_url, api_key="unused")

    def _get_max_tokens_for_text(self, text: str) -> int:
        """Estimate tokens length for request

        Args:
            text (str): input text

        Returns:
            int: tokens length
        """
        estimated_source_tokens = max(1, len(text.split()) * 2)
        estimated_prompt_tokens = (
            estimated_source_tokens + self.chat_template_reserve
        )

        if estimated_prompt_tokens > self.max_input_tokens:
            raise ValueError(
                "Translation block exceeds TranslateGemma's 2048 token input limit"
            )
        available_output_tokens = (
            self.context_window - estimated_prompt_tokens
        )

        return (available_output_tokens)

    def translate(
        self, text: str, source_lang: str = "en", target_lang: str = "vi"
    ) -> str:
        if not text or not text.strip():
            return ""

        source_language = _LANGUAGE_NAMES.get(source_lang, source_lang)
        target_language = _LANGUAGE_NAMES.get(target_lang, target_lang)
        translation_prompt = (
            f"You are a professional {source_language} ({source_lang}) to "
            f"{target_language} ({target_lang}) translator research paper. Your goal is to "
            f"accurately convey the meaning and nuances of the original "
            f"{source_language} text while adhering to {target_language} grammar, "
            "vocabulary, and cultural sensitivities. Warning: Do not use Arabic laguange. The following text is an "
            "excerpt from a technical academic research paper. Produce only the "
            f"{target_language} translation, without any additional explanations "
            f"or commentary. Please translate the following {source_language} "
            f"text into {target_language}:\n\n{text}"
        )

        messages = [
            {
                "role": "user",
                "content": f"<<<custom>>>{translation_prompt}",
            }
        ]

        request_max_tokens = self._get_max_tokens_for_text(text)
        for attempt in range(self.retry_attempts + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=request_max_tokens,
                    temperature=0,
                )
                content = response.choices[0].message.content
                return content.strip() if content else text
            except Exception as exc:
                if attempt >= self.retry_attempts:
                    logger.error(
                        "Gemma translation failed after %d attempts: %s",
                        self.retry_attempts + 1,
                        exc
                    )
                    return text
                time.sleep(0.5 * (attempt + 1))

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str = "en",
        target_lang: str = "vi",
    ) -> list[str]:
        """Translate multiple texts using concurrent requests.

        vLLM will automatically batch these requests
        via continuous batching.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translations. Blank inputs produce empty strings.
        """
        if not texts:
            return []

        # Use ThreadPoolExecutor for concurrent requests
        max_workers = min(self.max_concurrent_requests, len(texts))
        logger.info(
            "Translating %d blocks with %d concurrent requests",
            len(texts),
            max_workers,
        )
        results = [""] * len(texts)

        def translate_one(idx: int, text: str) -> tuple[int, str]:
            """Translate a single text."""
            translated = self.translate(text, source_lang, target_lang)
            return (idx, translated)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(translate_one, i, text): i
                for i, text in enumerate(texts)
                if text and text.strip()
            }

            for future in as_completed(futures):
                idx, translated = future.result()
                results[idx] = translated
        return results

    @classmethod
    def load(cls, **kwargs) -> "GemmaTranslator":
        return cls(**kwargs)


_instance: GemmaTranslator | None = None


def get_translator(**kwargs) -> GemmaTranslator:
    global _instance
    if _instance is None:
        _instance = GemmaTranslator.load(**kwargs)
    return _instance
