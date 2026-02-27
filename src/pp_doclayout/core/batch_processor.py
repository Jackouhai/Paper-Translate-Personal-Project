"""Batch processing for efficient translation."""

import tiktoken
from typing import TYPE_CHECKING, NamedTuple

from ..policies.translation_policy import should_translate
from ..types import Block, TranslateAction, TranslateResult

if TYPE_CHECKING:
    from ..translators.base import BaseTranslator


class TokenCount(NamedTuple):
    """Token count for a block."""
    count: int
    block_idx: int


class BatchSize(NamedTuple):
    """Batch size configuration."""
    small: int  # < 100 tokens
    medium: int  # 100-500 tokens
    large: int  # > 500 tokens


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """Estimate token count for text.

    Args:
        text: Text to estimate
        model: Model to use for tokenizer (default: gpt-4)

    Returns:
        Estimated token count
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to rough estimate: ~4 chars per token
        return len(text) // 4


def get_translatable_blocks(blocks: list[Block]) -> list[tuple[int, Block]]:
    """Filter blocks that should be translated.

    Args:
        blocks: List of all blocks

    Returns:
        List of (original_index, block) for blocks that should be translated
    """
    translatable = []
    for idx, block in enumerate(blocks):
        content = block.get("block_content", "").strip()
        label = block.get("block_label", "")
        action = should_translate(label, content)
        if action == "translate":
            translatable.append((idx, block))
    return translatable


def group_blocks_by_size(
    indexed_blocks: list[tuple[int, Block]],
    small_threshold: int = 100,
    medium_threshold: int = 500,
) -> dict[str, list[tuple[int, Block]]]:
    """Group blocks by estimated token count.

    Args:
        indexed_blocks: List of (index, block)
        small_threshold: Token threshold for small blocks
        medium_threshold: Token threshold for medium blocks

    Returns:
        Dict with keys 'small', 'medium', 'large'
    """
    groups = {"small": [], "medium": [], "large": []}

    for idx, block in indexed_blocks:
        content = block.get("block_content", "")
        token_count = estimate_tokens(content)

        if token_count < small_threshold:
            groups["small"].append((idx, block))
        elif token_count < medium_threshold:
            groups["medium"].append((idx, block))
        else:
            groups["large"].append((idx, block))

    return groups


def create_batches(
    items: list[tuple[int, Block]],
    batch_size: int,
) -> list[list[tuple[int, Block]]]:
    """Split items into batches of given size.

    Args:
        items: List of (index, block)
        batch_size: Maximum items per batch

    Returns:
        List of batches
    """
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i : i + batch_size])
    return batches


class BatchProcessor:
    """Process blocks in batches for efficient translation."""

    def __init__(
        self,
        batch_sizes: BatchSize | None = None,
        small_threshold: int = 100,
        medium_threshold: int = 500,
    ):
        """Initialize BatchProcessor.

        Args:
            batch_sizes: Batch sizes for each group
            small_threshold: Token threshold for small blocks
            medium_threshold: Token threshold for medium blocks
        """
        self.batch_sizes = batch_sizes or BatchSize(small=16, medium=8, large=4)
        self.small_threshold = small_threshold
        self.medium_threshold = medium_threshold

    def process_document(
        self,
        blocks: list[Block],
        translator: "BaseTranslator",
    ) -> list[TranslateResult]:
        """Process all blocks in a document.

        Args:
            blocks: List of blocks to process
            translator: Translator instance

        Returns:
            List of translation results
        """
        # Get translatable blocks
        translatable = get_translatable_blocks(blocks)

        if not translatable:
            return []

        # Group by token count
        grouped = group_blocks_by_size(
            translatable, self.small_threshold, self.medium_threshold
        )

        # Create batches
        batches = []
        for size_name in ["small", "medium", "large"]:
            batch_size = getattr(self.batch_sizes, size_name)
            items = grouped[size_name]
            if items:
                batches.extend(create_batches(items, batch_size))

        # Translate batches
        all_results = []
        for batch in batches:
            texts = [block.get("block_content", "") for _, block in batch]
            translations = self._translate_batch(texts, translator)

            # Map results back to blocks
            for (_, block), translated in zip(batch, translations):
                result: TranslateResult = {
                    "original": block.get("block_content", ""),
                    "translated": translated,
                    "action": "translate",
                    "label": block.get("block_label", ""),
                }
                all_results.append(result)

        return all_results

    def _translate_batch(
        self,
        texts: list[str],
        translator: "BaseTranslator",
    ) -> list[str | None]:
        """Translate a batch of texts.

        Args:
            texts: List of texts to translate
            translator: Translator instance

        Returns:
            List of translations (None if failed)
        """
        # Check if translator supports batch translation
        if hasattr(translator, "translate_batch"):
            return translator.translate_batch(texts)

        # Fallback to sequential translation
        return [translator.translate(text) for text in texts]
