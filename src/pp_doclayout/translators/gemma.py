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

    @classmethod
    def load(cls, **kwargs) -> "GemmaTranslator":
        return cls(**kwargs)


_instance: GemmaTranslator | None = None


def get_translator(**kwargs) -> GemmaTranslator:
    global _instance
    if _instance is None:
        _instance = GemmaTranslator.load(**kwargs)
    return _instance
