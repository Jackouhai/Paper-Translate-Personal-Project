from typing import Literal

TranslateAction = Literal["translate", "keep", "skip"]

NO_TRANSLATE_LABELS = frozenset(
    [
        "doc_title",
        "reference_content",
        "footnote",
        "vision_footnote",
        "table",
        "image",
        "chart",
        "display_formula",
        "inline_formula",
        "formula_number",
        "number"
    ]
)

SKIP_LABELS = frozenset(["aside_text", "header", "footer", "content"])

TRANSLATE_LABELS = frozenset(["abstract", "text", "figure_title"])


def should_translate(
    label: str,
    content: str,
    *,
    translate_titles: bool = False,
) -> TranslateAction:
    if label in SKIP_LABELS:
        return "skip"

    content_lower = content.strip().lower()
    words = content_lower.split()
    if (
        label == "paragraph_title"
        and "contents" in words
        and (len(content_lower) < 50 or len(words) < 4)
    ):
        return "skip"

    if label == "paragraph_title":
        return "translate" if translate_titles else "keep"

    if label in NO_TRANSLATE_LABELS:
        return "keep"

    if label in TRANSLATE_LABELS:
        return "translate"

    return "keep"
