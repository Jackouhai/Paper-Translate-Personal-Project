from vllm import LLM, SamplingParams

from .base import BaseTranslator


class HYMTTranslator(BaseTranslator):
    def __init__(
        self,
        model_id: str = "tencent/HY-MT1.5-1.8B",
        base_url: str | None = None,
    ):
        self.model_id = model_id
        self.base_url = base_url
        self._client = None

        if base_url is None:
            self._llm = LLM(
                model=model_id,
                dtype="bf16",
                max_model_len=4096,
                gpu_memory_utilization=0.9,
                enforce_eager=True,
                trust_remote_code=True,
            )
            self._sampling_params = SamplingParams(
                max_tokens=2048,
                temperature=0,
            )
        else:
            from openai import OpenAI

            self._client = OpenAI(base_url=base_url, api_key="unused")

    def translate(
        self, text: str, source_lang: str = "en", target_lang: str = "vi"
    ) -> str:
        if not text or not text.strip():
            return ""

        if self._client:
            messages = [
                {
                    "role": "user",
                    "content": f"Translate the following segment into {target_lang}, without additional explanation.\n\n{text}",
                }
            ]
            try:
                resp = self._client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"Translation error: {e}")
                return text
        else:
            messages = [
                {
                    "role": "user",
                    "content": f"Translate the following segment into {target_lang}, without additional explanation.\n\n{text}",
                }
            ]
            try:
                outputs = self._llm.chat(
                    messages=[messages],
                    sampling_params=self._sampling_params,
                )
                return outputs[0].outputs[0].text.strip()
            except Exception as e:
                print(f"Translation error: {e}")
                return text

    @classmethod
    def load(cls, **kwargs) -> "HYMTTranslator":
        return cls(**kwargs)


_instance: HYMTTranslator | None = None


def get_translator(**kwargs) -> HYMTTranslator:
    global _instance
    if _instance is None:
        _instance = HYMTTranslator.load(**kwargs)
    elif kwargs:
        _instance = HYMTTranslator.load(**kwargs)
    return _instance
