"""Type definitions for PP-DocLayout."""

from typing import Literal, TypedDict, NotRequired

# ============== Actions ==============
TranslateAction = Literal["translate", "keep", "skip"]

# ============== Block Labels ==============
BlockLabel = Literal[
    # Main content
    "abstract",
    "text",
    "paragraph_title",
    "doc_title",
    # Visual elements
    "image",
    "chart",
    "table",
    "figure_title",
    # Formulas
    "display_formula",
    "inline_formula",
    "formula_number",
    # References & notes
    "reference_content",
    "footnote",
    "vision_footnote",
    # Noise / metadata
    "aside_text",
    "header",
    "footer",
    "number",
    "content",
]

# ============== Block Types ==============
class Block(TypedDict):
    """Single block from PaddleOCR-VL parsing result."""
    block_label: BlockLabel
    block_content: str
    block_bbox: list[int]  # [x1, y1, x2, y2]
    block_id: int
    block_order: int | None
    group_id: int
    block_polygon_points: list[list[float]]


class ModelSettings(TypedDict):
    """Model configuration from PaddleOCR-VL."""
    use_doc_preprocessor: bool
    use_layout_detection: bool
    use_chart_recognition: bool
    use_seal_recognition: bool
    use_ocr_for_image_block: bool
    format_block_content: bool
    merge_layout_blocks: bool
    markdown_ignore_labels: list[str]
    return_layout_polygon_points: bool


class PageData(TypedDict):
    """Complete page data from PaddleOCR-VL."""
    input_path: str
    page_index: int
    page_count: int
    width: int
    height: int
    model_settings: ModelSettings
    parsing_res_list: list[Block]
    # layout_det_res is optional, may be present or not
    layout_det_res: NotRequired[dict]


class ProjectData(TypedDict):
    """All pages for a project."""
    pages: list[PageData]
    project_name: str


# ============== Translation Related ==============
class TranslateRequest(TypedDict):
    """Request for translation."""
    text: str
    label: BlockLabel


class TranslateResult(TypedDict):
    """Result of translation."""
    original: str
    translated: str | None  # None if kept or skipped
    action: TranslateAction
    label: BlockLabel
