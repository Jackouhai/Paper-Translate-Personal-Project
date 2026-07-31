import logging
from unittest.mock import MagicMock

import pytest

from pp_doclayout.translators.gemma import GemmaTranslator


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


def test_translate_sends_research_paper_context_prompt():
    translator = object.__new__(GemmaTranslator)
    translator.model_name = "test-model"
    translator.retry_attempts = 0
    translator._get_max_tokens_for_text = lambda text: 512
    translator.client = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = "Ban dich"
    translator.client.chat.completions.create.return_value = response

    result = translator.translate("Source passage")

    assert result == "Ban dich"
    request = translator.client.chat.completions.create.call_args.kwargs
    messages = request["messages"]
    assert messages[0]["role"] == "user"

    prompt = messages[0]["content"]
    assert prompt.startswith("<<<custom>>>")
    assert "professional English (en) to Vietnamese (vi) translator" in prompt
    assert "technical academic research paper" in prompt
    assert "Warning: Do not use Arabic laguange." in prompt
    assert prompt.endswith("Vietnamese:\n\nSource passage")


def _translator_for_token_budget():
    translator = object.__new__(GemmaTranslator)
    translator.context_window = 4096
    translator.max_input_tokens = 2048
    translator.chat_template_reserve = 256
    return translator


def test_max_tokens_respects_context_budget():
    translator = _translator_for_token_budget()

    result = translator._get_max_tokens_for_text("word " * 820)

    assert result == 2200


def test_max_tokens_rejects_blocks():
    translator = _translator_for_token_budget()

    with pytest.raises(ValueError, match="2048 token input limit"):
        translator._get_max_tokens_for_text("word " * 1000)
