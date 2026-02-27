"""Tests for batch_processor module."""

from pp_doclayout.core.batch_processor import (
    estimate_tokens,
    get_translatable_blocks,
    group_blocks_by_size,
    create_batches,
    BatchProcessor,
    BatchSize,
)


def test_estimate_tokens():
    """Test token estimation."""
    short_text = "Hello world"
    long_text = "This is a longer text for testing token estimation with more words."

    short_count = estimate_tokens(short_text)
    long_count = estimate_tokens(long_text)

    assert short_count > 0
    assert long_count > short_count


def test_get_translatable_blocks():
    """Test get_translatable_blocks filters correctly."""
    blocks = [
        {"block_label": "text", "block_content": "This is a longer text that should be translated properly."},
        {"block_label": "paragraph_title", "block_content": "Introduction"},
        {"block_label": "abstract", "block_content": "Abstract content."},
        {"block_label": "number", "block_content": "123"},
    ]

    translatable = get_translatable_blocks(blocks)

    # Should translate text and abstract
    assert len(translatable) == 2
    assert translatable[0][1]["block_label"] == "text"
    assert translatable[1][1]["block_label"] == "abstract"


def test_group_blocks_by_size():
    """Test group_blocks_by_size categorizes correctly."""
    # Create a very long text for large block
    long_text = "This is a very long text block that contains many words " * 100

    blocks = [
        {"block_label": "text", "block_content": "Short"},
        {"block_label": "abstract", "block_content": "Medium length text here."},
        {"block_label": "text", "block_content": long_text},
    ]

    indexed = [(i, b) for i, b in enumerate(blocks)]
    groups = group_blocks_by_size(indexed)

    assert "small" in groups
    assert "medium" in groups
    assert "large" in groups
    assert len(groups["small"]) > 0
    assert len(groups["large"]) > 0


def test_create_batches():
    """Test create_batches splits correctly."""
    items = [(i, {"block_label": "text"}) for i in range(10)]
    batches = create_batches(items, batch_size=3)

    assert len(batches) == 4  # 10 / 3 = 3.33 -> 4 batches
    assert len(batches[0]) == 3
    assert len(batches[3]) == 1  # Last batch has 1 item


def test_batch_processor_initialization():
    """Test BatchProcessor initialization."""
    batch_sizes = BatchSize(small=8, medium=4, large=2)
    processor = BatchProcessor(batch_sizes=batch_sizes)

    assert processor.batch_sizes.small == 8
    assert processor.batch_sizes.medium == 4
    assert processor.batch_sizes.large == 2


def test_batch_processor_default_initialization():
    """Test BatchProcessor with default batch sizes."""
    processor = BatchProcessor()

    assert processor.batch_sizes.small == 16
    assert processor.batch_sizes.medium == 8
    assert processor.batch_sizes.large == 4


def test_batch_processor_empty_blocks():
    """Test BatchProcessor handles empty blocks."""
    processor = BatchProcessor()

    class MockTranslator:
        def translate(self, text: str) -> str:
            return text

    results = processor.process_document([], MockTranslator())
    assert results == []


def test_batch_processor_no_translatable_blocks():
    """Test BatchProcessor handles no translatable blocks."""
    processor = BatchProcessor()

    blocks = [
        {"block_label": "number", "block_content": "123"},
        {"block_label": "footer", "block_content": "Page 1"},
    ]

    class MockTranslator:
        def translate(self, text: str) -> str:
            return text

    results = processor.process_document(blocks, MockTranslator())
    assert results == []
