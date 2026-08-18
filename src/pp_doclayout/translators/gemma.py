import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

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
        max_concurrent_requests: int | None = None,
        backend: str | None = None,
        transformers_model_name: str | None = None,
    ):
        from ..config import settings

        self.base_url = base_url or settings.vllm_base_url
        self.model_name = model_name or settings.vllm_model_name
        self.context_window = settings.vllm_context_window
        self.chat_template_reserve = settings.vllm_chat_template_reserve
        self.max_input_tokens = settings.translation_max_input_tokens
        self.max_concurrent_requests = max_concurrent_requests or settings.max_concurrent_requests
        self.retry_attempts = settings.vllm_retry_attempts
        self.backend = (backend or settings.translation_backend).lower()
        if self.backend not in {"auto", "vllm", "transformers"}:
            raise ValueError("backend must be 'auto', 'vllm', or 'transformers'")
        self.transformers_model_name = (
            transformers_model_name or settings.transformers_model_name
        )

        self.client = OpenAI(base_url=self.base_url, api_key="unused")
        self._transformers_tokenizer = None
        self._transformers_model = None
        self._transformers_device = None
        self._transformers_lock = Lock()

    @property
    def allows_transformers_fallback(self) -> bool:
        return self.backend in {"auto", "transformers"}

    def _translation_messages(
        self, text: str, source_lang: str, target_lang: str
    ) -> list[dict[str, str]]:
        """Build the TranslateGemma chat input used by both backends."""
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
        return [{"role": "user", "content": f"<<<custom>>>{translation_prompt}"}]

    @staticmethod
    def _transformers_messages(
        text: str, source_lang: str, target_lang: str
    ) -> list[dict[str, str]]:
        """Use the delimiter format from the original notebook engine."""
        return [
            {
                "role": "user",
                "content": (
                    f"<<<source>>>{source_lang}<<<target>>>{target_lang}"
                    f"<<<text>>>{text}"
                ),
            }
        ]

    def _load_transformers(self):
        """Lazy-load one local Hugging Face model for notebook/Colab use."""
        if self._transformers_model is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        logger.info(
            "Loading Transformers fallback model %s on %s",
            self.transformers_model_name,
            device,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            self.transformers_model_name,
            trust_remote_code=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            self.transformers_model_name,
            torch_dtype=dtype,
            trust_remote_code=True,
        )
        model.to(device)
        model.eval()
        self._transformers_tokenizer = tokenizer
        self._transformers_model = model
        self._transformers_device = device

    def _translate_with_transformers(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        request_max_tokens: int,
    ) -> str:
        """Generate locally. The lock also prevents duplicate model loading."""
        import torch

        with self._transformers_lock:
            self._load_transformers()
            tokenizer = self._transformers_tokenizer
            model = self._transformers_model
            messages = self._transformers_messages(
                text, source_lang, target_lang
            )
            inputs = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            ).to(self._transformers_device)
            input_length = inputs["input_ids"].shape[-1]
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=request_max_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            generated = output[0, input_length:]
            translation = tokenizer.decode(
                generated,
                skip_special_tokens=True,
            ).strip()
            return translation or text

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

        messages = self._translation_messages(text, source_lang, target_lang)
        request_max_tokens = self._get_max_tokens_for_text(text)
        backend = getattr(self, "backend", "vllm")
        if backend == "transformers":
            try:
                return self._translate_with_transformers(
                    text, source_lang, target_lang, request_max_tokens
                )
            except Exception as exc:
                logger.error("Transformers translation failed: %s", exc)
                return text

        last_error = None
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
                last_error = exc
                if attempt >= self.retry_attempts:
                    logger.warning(
                        "Gemma translation failed after %d attempts: %s",
                        self.retry_attempts + 1,
                        exc
                    )
                    break
                time.sleep(0.5 * (attempt + 1))

        if backend == "auto":
            logger.info("Falling back to the local Transformers backend")
            try:
                return self._translate_with_transformers(
                    text, source_lang, target_lang, request_max_tokens
                )
            except Exception as exc:
                logger.error("Transformers fallback failed: %s", exc)

        logger.error(
            "Gemma translation failed after %d attempts: %s",
            self.retry_attempts + 1,
            last_error,
        )
        return text

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
