from pp_doclayout.policies.translation_policy import should_translate


def test_paragraph_title_is_kept_by_default():
    assert should_translate("paragraph_title", "Related Work") == "keep"


def test_paragraph_title_is_translated_when_enabled():
    assert (
        should_translate(
            "paragraph_title",
            "Related Work",
            translate_titles=True,
        )
        == "translate"
    )


def test_table_of_contents_title_is_skipped():
    assert should_translate("paragraph_title", "Contents") == "skip"


def test_document_title_is_kept():
    assert should_translate("doc_title", "Paper title") == "keep"
