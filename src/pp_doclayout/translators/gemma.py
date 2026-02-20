from openai import OpenAI

from .base import BaseTranslator


class GemmaTranslator(BaseTranslator):
    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        max_tokens: int | None = None,
    ):
        from ..config import settings

        self.base_url = base_url or settings.vllm_base_url
        self.model_name = model_name or settings.vllm_model_name
        self.max_tokens = max_tokens or settings.vllm_max_tokens

        self.client = OpenAI(base_url=self.base_url, api_key="unused")

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

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0,
            )
            content = response.choices[0].message.content
            return content.strip() if content else text
        except Exception as e:
            print(f"Gemma translation error: {e}")
            return text

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str = "en",
        target_lang: str = "vi",
    ) -> list[str | None]:
        """Translate multiple texts in a single batch request.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translations (None if failed for a particular text)
        """
        if not texts:
            return []

        # Filter empty texts
        non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
        if not non_empty:
            return [None] * len(texts)

        # Prepare batch messages
        messages = [
            {
                "role": "user",
                "content": "\n".join(
                    f"[{idx}] <<<source>>>{source_lang}<<<target>>>{target_lang}<<<text>>>{text}"
                    for idx, (_, text) in enumerate(non_empty)
                ),
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens * len(non_empty),
                temperature=0,
            )
            content = response.choices[0].message.content
            if not content:
                return [None] * len(texts)

            # Parse batch response
            results = [None] * len(texts)

            # Try to parse responses like "[1] Translation 1\n[2] Translation 2..."
            for idx, (orig_idx, _) in enumerate(non_empty):
                pattern = f"\\[{idx}\\]"
                if pattern in content:
                    start = content.find(pattern)
                    next_idx = idx + 1
                    next_pattern = f"\\[{next_idx}\\]" if next_idx < len(non_empty) else None
                    end = content.find(next_pattern) if next_pattern else len(content)
                    translated = content[start + len(pattern) : end].strip()
                    results[orig_idx] = translated if translated else texts[orig_idx]

            # Fill None with original text
            for i in range(len(results)):
                if results[i] is None and texts[i]:
                    results[i] = texts[i]

            return results

        except Exception as e:
            print(f"Gemma batch translation error: {e}")
            return [t if t else None for t in texts]

    @classmethod
    def load(cls, **kwargs) -> "GemmaTranslator":
        return cls(**kwargs)


_instance: GemmaTranslator | None = None


def get_translator(**kwargs) -> GemmaTranslator:
    global _instance
    if _instance is None:
        _instance = GemmaTranslator.load(**kwargs)
    return _instance
