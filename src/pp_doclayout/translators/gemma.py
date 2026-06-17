import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

from .base import BaseTranslator

class GemmaTranslator(BaseTranslator):
    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        max_tokens: int | None = None,
        max_concurrent_requests: int | None = None
    ):
        from ..config import settings

        self.base_url = base_url or settings.vllm_base_url
        self.model_name = model_name or settings.vllm_model_name
        self.max_tokens = max_tokens or settings.vllm_max_tokens
        self.max_concurrent_requests = max_concurrent_requests or settings.max_concurrent_requests
        self.min_output_tokens = settings.vllm_min_output_tokens
        self.output_token_multiplier = settings.vllm_output_token_multiplier
        self.retry_attempts = settings.vllm_retry_attempts

        self.client = OpenAI(base_url=self.base_url, api_key="unused")

    def _get_max_tokens_for_text(self, text: str) -> int:
        """Estimate tokens length for request

        Args:
            text (str): input text

        Returns:
            int: tokens length
        """
        estimated_input_tokens = max(1, len(text.split()) * 2)
        estimated_output_tokens = int(estimated_input_tokens * self.output_token_multiplier)
        request_max_tokens = max(self.min_output_tokens, estimated_output_tokens)
        return min(self.max_tokens, request_max_tokens)

    def translate(
        self, text: str, source_lang: str = "en", target_lang: str = "vi"
    ) -> str:
        if not text or not text.strip():
            return ""

        messages = [
            {
                "role": "user",
                "content": f"<<<source>>>{source_lang}<<<target>>>{target_lang}<<<text>>>{text}",
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
            except Exception as e:
                if attempt >= self.retry_attempts:
                    print(f"Gemma translation error: {e}")
                    return text
                time.sleep(0.5 * (attempt + 1))

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str = "en",
        target_lang: str = "vi",
    ) -> list[str | None]:
        """Translate multiple texts using concurrent requests.

        vLLM will automatically batch these requests
        via continuous batching.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translations (None if failed for a
            particular text)
        """
        if not texts:
            return []

        # Use ThreadPoolExecutor for concurrent requests
        max_workers = min(self.max_concurrent_requests, len(texts))
        print(
            f"Translating {len(texts)} blocks with "
            f"{max_workers} concurrent requests"
        )
        results = [None] * len(texts)

        def translate_one(idx: int, text: str) -> tuple[int, str]:
            """Translate a single text."""
            translated = self.translate(text, source_lang, target_lang)
            return (idx, translated)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(translate_one, i, text): i for i, text in enumerate(texts) if text and text.strip()
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
