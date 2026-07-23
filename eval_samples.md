# Evaluation Sample Candidates

## Selected PDFs

| ID | File | Layout | Features | Notes |
|----|------|--------|----------|-------|
| sample_01 | `input/2210.17323v2.pdf` | pending manual review | 16 pages; text, abstract, headings, footnotes | Parsed: 16/16 pages |
| sample_02 | `input/2306.00978v6.pdf` | pending manual review | 15 pages; text, figures, captions, footnotes | Parsed: 15/15 pages |
| sample_03 | `input/2602.15763v2.pdf` | pending manual review | 40 pages; text, chart, formulas, captions | Parsed: 40/40 pages; PDF export verified after page-break fix |
| sample_04 | `input/2606.13392v2.pdf` | pending manual review | 30 pages; text, images, captions | Parsed: 30/30 pages |

## Feature Labels

- one_column
- two_column
- formula
- table
- figure
- chart
- references
- dense_text

## Week 2 Status

- All four current input PDFs have complete per-page parse JSON.
- Feature summaries above come from detected block labels, not final manual scoring.
- Column layout, clipping, OCR quality, translation quality, and formula preservation still require manual review.
- Record failures per sample instead of treating one successful end-to-end run as coverage for the whole dataset.

## Manual Review Checklist

For every sample, record:

- one-column, two-column, or mixed layout;
- OCR omissions and incorrect block labels;
- translated text clipping or unreadably small font;
- table, image, chart, and formula preservation;
- HTML page count and PDF page count;
- server/model configuration used for the run;
- reproducible error messages and affected page numbers.
