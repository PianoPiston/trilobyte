# Stoa challenge: solution options

Junction challenge: answer natural-language questions about construction drawings and BIM models, accurately and verifiably, with the location in the drawing that supports each answer.

## What the data looks like

Source: `junction-dataset` (about 12 GB, about 14,000 drawings, 127,044 questions). Only some sources have questions.

| Source | Drawings | Questions | Notes |
|---|---|---|---|
| cubicasa5k | 4,788 PNG | 85,514, all counts | Real Finnish plans, often scanned and hand-marked. About 18 questions per drawing. Questions appear in English and Finnish with the same answer, so deduplicate before scoring. |
| swiss_dwellings | 1,040 floors, each as PNG, PDF and DXF | 37,584 (25,568 counts, 12,016 areas) | Clean synthetic renders with printed room labels and areas. About 36 questions per floor. The printed areas may let a model read answers without understanding the plan. |
| ifc_models | 533 IFC, plus rendered PNG, PDF and SVG | 3,062 (areas, counts, volumes, lengths) | Floor plans rendered from open BIM models. PNGs are very large (about 7,500 × 4,200 px). |
| ifc_bench | 30 IFC | 820 (free text) | Full BIM models. |
| opening_design | 678 PDF, 271 DWG, 48 IFC, 9 DXF | 64 | Real US architecture sheets. Mostly not floor plans. |
| habs, finna, europeana, wikimedia | about 6,500 images | none | No questions. Usable only as extra unlabelled material. |

Scoring (from the dataset README): counts must be exact. Areas, lengths and volumes must be within 2%. Text answers are free-form.

Licences: NC, SA and ND terms apply per file. Keep the credit when showing drawings. Use for non-commercial purposes only.

## Option A: direct vision-language model answers

Send each drawing (tiled at high resolution) and the question to a multimodal model. Ask for a structured answer with the page, a bounding box for the evidence, and a confidence score.

- **Pros:** fastest to build. Handles any question wording and any language. Works on every format that can be rendered to an image.
- **Cons:** counting dense plans is unreliable, and models tend to miscount. Outlines are imprecise, so areas will often miss the 2% tolerance.
- **Best for:** a baseline, text questions, and the opening_design and ifc_bench questions.

## Option B: room segmentation, then deterministic counting and area

Train or fine-tune a room segmentation model on cubicasa5k. Then count and measure from the masks, using the scale from the drawing.

- **Pros:** gives exact counts and areas, plus a mask as evidence for each answer, which fits the "show where it came from" requirement.
- **Cons:** the published CubiCasa baseline reaches roughly 57.5% mean room IoU, so it needs fine-tuning. Scale detection is an extra problem, and swiss and cubicasa drawings differ in style.
- **Best for:** count and area questions on floor plans, which make up most of the data.

## Option C: promptable segmentation plus a vision-language model

Use a general-purpose segmentation model (SAM-family) with point or box prompts to outline each room. Use a vision-language model to label each region and answer the question.

- **Pros:** more general than a floor-plan-specific model, so it may transfer better to the Swiss, US and museum drawings.
- **Cons:** needs prompts for each room. Faint walls can cause over-segmentation. I have not checked which current segmentation model versions are available, so verify this first.
- **Best for:** a generalisation test, or fallback when Option B fails on a source.

## Option D: parse vector and BIM files directly

Read geometry and metadata from DXF, IFC and SVG files instead of images.

- **Pros:** exact answers, fully verifiable, no vision error. IFC models carry typed elements, so counts are direct queries.
- **Cons:** covers only the sources that have vector or BIM files with questions: ifc_models, ifc_bench, and the Swiss DXF files. It does not help the PNG-only cubicasa5k set.
- **Best for:** IFC and DXF questions, where it can reach near-perfect scores.

## Option E: hybrid routing (recommended)

Route each question by file format:

1. **IFC or DXF available:** use deterministic parsing (Option D).
2. **PNG or PDF floor plan, count or area question:** room segmentation (Option B), with a vision-language model for labels and text questions.
3. **Everything else (text questions, unusual sheets):** vision-language model (Option A), with the evidence region shown.

Every answer should return: the value, the source file and page, an evidence region (mask, box or IFC element ID), the method used, and a confidence score. Treat low-confidence answers as "unknown" rather than guessing, because wrong answers can cost more than no answer under exact-match scoring.

## Evaluation plan

- Split by drawing, not by question. Otherwise the same plan appears in train and test.
- Deduplicate cubicasa5k questions across English and Finnish before scoring.
- Report accuracy separately per source and per question type: exact match for counts, within 2% for areas, lengths and volumes.
- Report precision and false-positive rate, since the challenge asks for honest measurement rather than just a working demo.
- Evaluate cubicasa5k and swiss_dwellings separately, because printed labels make swiss_dwellings easier.

## Deployment

- Hostinger VPS (KVM 2, 2 vCPU, 8 GB RAM) per team. A GPU is not included, so model choice matters: a small segmentation model on CPU, with heavier work sent to a hosted model through the Hostinger AI Router.
- Expose a simple API plus a small UI that shows the drawing with the evidence region highlighted.
- Check that the chosen model fits the VPS memory before committing. I have not verified the Hostinger AI Router's model list or pricing.

## Open questions

- Which room segmentation weights can we legally use for a non-commercial hackathon entry?
- Does cubicasa5k include SVG room polygons for area ground truth? Not yet confirmed.
- Which vision-language model gives the best counting accuracy on dense plans? Needs a small benchmark on about 200 questions.
