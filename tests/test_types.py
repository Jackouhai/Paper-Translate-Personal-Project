"""Tests for types module."""

from pp_doclayout.types import (
    TranslateAction,
    BlockLabel,
    Block,
    PageData,
    ModelSettings,
    TranslateRequest,
    TranslateResult,
)


def test_translate_action_values():
    """Test TranslateAction has correct literal values."""
    assert TranslateAction.__args__ == ("translate", "keep", "skip")


def test_block_label_values():
    """Test BlockLabel includes all expected labels."""
    # Sample of expected labels
    expected = ["text", "abstract", "image", "table", "display_formula"]
    for label in expected:
        assert label in BlockLabel.__args__


def test_block_typeddict():
    """Test Block TypedDict can be instantiated."""
    block: Block = {
        "block_label": "text",
        "block_content": "Test content",
        "block_bbox": [100, 200, 300, 400],
        "block_id": 0,
        "block_order": 1,
        "group_id": 0,
        "block_polygon_points": [[100.0, 200.0], [300.0, 400.0]],
    }
    assert block["block_label"] == "text"
    assert block["block_content"] == "Test content"


def test_page_data_typeddict():
    """Test PageData TypedDict can be instantiated."""
    page: PageData = {
        "input_path": "/path/to/file.pdf",
        "page_index": 0,
        "page_count": 10,
        "width": 800,
        "height": 1200,
        "model_settings": {
            "use_layout_detection": True,
            "merge_layout_blocks": True,
            "markdown_ignore_labels": [],
            "return_layout_polygon_points": True,
            "use_doc_preprocessor": False,
            "use_chart_recognition": False,
            "use_seal_recognition": False,
            "use_ocr_for_image_block": False,
            "format_block_content": False,
        },
        "parsing_res_list": [
            {
                "block_label": "text",
                "block_content": "Test",
                "block_bbox": [0, 0, 100, 100],
                "block_id": 0,
                "block_order": None,
                "group_id": 0,
                "block_polygon_points": [[0.0, 0.0], [100.0, 100.0]],
            }
        ],
    }
    assert page["page_index"] == 0
    assert page["page_count"] == 10


def test_model_settings_typeddict():
    """Test ModelSettings TypedDict can be instantiated."""
    settings: ModelSettings = {
        "use_layout_detection": True,
        "merge_layout_blocks": True,
        "markdown_ignore_labels": ["number", "footer"],
        "return_layout_polygon_points": True,
        "use_doc_preprocessor": False,
        "use_chart_recognition": False,
        "use_seal_recognition": False,
        "use_ocr_for_image_block": False,
        "format_block_content": False,
    }
    assert settings["use_layout_detection"] is True


def test_translate_request_typeddict():
    """Test TranslateRequest TypedDict can be instantiated."""
    request: TranslateRequest = {
        "text": "Hello world",
        "label": "text",
    }
    assert request["text"] == "Hello world"
    assert request["label"] == "text"


def test_translate_result_typeddict():
    """Test TranslateResult TypedDict can be instantiated."""
    result: TranslateResult = {
        "original": "Hello world",
        "translated": "Xin chào thế giới",
        "action": "translate",
        "label": "text",
    }
    assert result["original"] == "Hello world"
    assert result["translated"] == "Xin chào thế giới"
    assert result["action"] == "translate"


def test_translate_result_keep_action():
    """Test TranslateResult with keep action."""
    result: TranslateResult = {
        "original": "Introduction",
        "translated": None,
        "action": "keep",
        "label": "paragraph_title",
    }
    assert result["action"] == "keep"
    assert result["translated"] is None


def test_translate_result_skip_action():
    """Test TranslateResult with skip action."""
    result: TranslateResult = {
        "original": "123",
        "translated": None,
        "action": "skip",
        "label": "number",
    }
    assert result["action"] == "skip"
    assert result["translated"] is None
