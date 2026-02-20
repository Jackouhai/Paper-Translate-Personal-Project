from openai import OpenAI


class TranslationEngineGemma:
    def __init__(
        self,
        base_url="http://127.0.0.1:8001/v1",
        model_name="Infomaniak-AI/vllm-translategemma-4b-it",
    ):
        self.client = OpenAI(base_url=base_url, api_key="unused")
        self.model_name = model_name
        print(f"TranslateGemma client ready -> {base_url} (model: {model_name})")

    def translate(self, text, source_lang="en", target_lang="vi"):
        if not text or not text.strip():
            return ""

        # Infomaniak delimiter format
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
                max_tokens=2048,
                temperature=0,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Gemma Translation error: {str(e)}")
            return text


# Singleton instance
_engine = None


def get_translator():
    global _engine
    if _engine is None:
        _engine = TranslationEngineGemma()
    return _engine
