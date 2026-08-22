from pp_doclayout.core.renderer import render_page_blocks


def test_render_page_blocks_normalizes_markdown_title_wrapper(tmp_path):
    page = {
        "width": 100,
        "height": 100,
        "parsing_res_list": [
            {
                "block_id": 1,
                "block_label": "paragraph_title",
                "block_content": "**Tóm tắt**",
                "block_bbox": [0, 0, 100, 20],
            },
        ],
    }

    html = render_page_blocks(page, imgs_dir=tmp_path, output_dir=tmp_path)

    assert "<h2 class=\"block paragraph_title auto-fit\"" in html
    assert ">Tóm tắt</h2>" in html
    assert "**Tóm tắt**" not in html


def test_render_page_blocks_omits_skipped_labels(tmp_path):
    page = {
        "width": 100,
        "height": 100,
        "parsing_res_list": [
            {
                "block_id": 1,
                "block_label": "text",
                "block_content": "Visible content",
                "block_bbox": [0, 0, 50, 20],
            },
            {
                "block_id": 2,
                "block_label": "aside_text",
                "block_content": "arXiv metadata",
                "block_bbox": [0, 20, 20, 80],
            },
        ],
    }

    html = render_page_blocks(page, imgs_dir=tmp_path, output_dir=tmp_path)

    assert "Visible content" in html
    assert "arXiv metadata" not in html
    assert "aside_text" not in html
