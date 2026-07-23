from pp_doclayout.translators.gemma import GemmaTranslator
import logging
from unittest.mock import MagicMock

def test_translate_batch_preserves_blank_inputs():
    translator = object.__new__(GemmaTranslator)
    translator.max_concurrent_requests = 4
    translator.translate = (
        lambda text, source_lang="en", target_lang="vi":
        "" if not text.strip() else f"vi:{text}"
    )

    result = translator.translate_batch(
        ["hello", "", "   ", "world"]
    )

    assert result == [
        "vi:hello",
        "",
        "",
        "vi:world",
    ]

def test_translate_logs_error_after_final_retry(caplog):
    translator = object.__new__(GemmaTranslator)
    translator.model_name = "test-model"
    translator.retry_attempts = 0
    translator._get_max_tokens_for_text = lambda text: 512
    translator.client = MagicMock()
    translator.client.chat.completions.create.side_effect = RuntimeError(
        "server unavailable"
    )

    with caplog.at_level(
        logging.ERROR,
        logger="pp_doclayout.translators.gemma",
    ):
        result = translator.translate("Hello")

    assert result == "Hello"
    assert "Gemma translation failed after 1 attempts" in caplog.text
    assert "server unavailable" in caplog.text