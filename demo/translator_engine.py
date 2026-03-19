from vllm import LLM, SamplingParams


class TranslationEngine:
    def __init__(self, model_id="tencent/HY-MT1.5-1.8B"):
        print(f"Loading HY-MT model {model_id} (vLLM offline)...")
        self.llm = LLM(
            model=model_id,
            dtype="bfloat16",
            max_model_len=4096,
            gpu_memory_utilization=0.9,
            enforce_eager=True,
            trust_remote_code=True,
        )
        self.sampling_params = SamplingParams(
            max_tokens=2048,
            temperature=0,
        )

    def translate(self, text, target_lang="vi"):
        if not text or not text.strip():
            return ""

        messages = [
            {
                "role": "user",
                "content": f"Translate the following segment into {target_lang}, without additional explanation.\n\n{text}",
            }
        ]

        try:
            outputs = self.llm.chat(
                messages=[messages],
                sampling_params=self.sampling_params,
            )
            return outputs[0].outputs[0].text.strip()
        except Exception as e:
            print(f"Translation error: {str(e)}")
            return text


_engine = None


def get_translator():
    global _engine
    if _engine is None:
        _engine = TranslationEngine()
    return _engine
