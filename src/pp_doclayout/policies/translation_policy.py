from typing import Literal

TranslateAction = Literal["translate", "keep", "skip"]

NO_TRANSLATE_LABELS = frozenset(
    [
        "doc_title",
        "paragraph_title",
        "reference_content",
        "footnote",
        "vision_footnote",
        "table",
        "image",
        "chart",
        "display_formula",
        "formula_number",
    ]
)

SKIP_LABELS = frozenset(["aside_text", "header", "footer", "number", "content"])

TRANSLATE_LABELS = frozenset(["abstract", "text", "figure_title", "table_caption"])


def should_translate(label: str, content: str) -> TranslateAction:
    if label in SKIP_LABELS:
        return "skip"
    
    content_lower = content.strip().lower()
    words = content_lower.split()
    if label == "paragraph_title" and "contents" in words and (len(content_lower) < 50 or len(words) < 4):
        return "skip"
    
    if label in NO_TRANSLATE_LABELS:
        return "keep"
    
    if label in TRANSLATE_LABELS:
        if len(words) < 6 and label == "text" and "@" not in content:
            return "keep"
        if "@" in content:
            return "keep"
        return "translate"

    return "keep"
