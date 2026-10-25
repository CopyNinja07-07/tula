# TULA: Toll Uncertainty and Liability Assessment

*Tulā* (तुला) is the balance scale. Before an AI punishes someone, it should weigh the evidence. TULA is that scale.

TULA is an AI safety layer for automated toll billing. For every vehicle it decides **charge**, **hold**, or **send to a human**, and it keeps the wrong-charge rate under a target that can be proven with conformal risk control. It is being built for the Meta Global AI Developer Hackathon (26 Oct to 4 Nov 2026, Indie track, solo), and it continues whether or not the application is accepted.

Blueprint: https://claude.ai/artifact/JusUMwS43g65brXWY3kacS

## Pipeline

1. **SAM 3.1** cuts the plate and the vehicle out of the camera frame.
2. Two independent readers: a specialist plate OCR model, and **Muse Spark**, which reads the plate and returns vehicle type, make and colour as structured output.
3. **Evidence check**: the reads are compared with the vehicle linked to the FASTag and its registry record.
4. **Risk controller**: conformal risk control with a cut-off for each group (plate style, state, day/night, weather).
5. **Outcome**: charge, hold or human review, with an evidence note written by Muse Spark.
6. **Red team**: cloned plates, tag swaps and edited images.

## Layout

| Folder | What goes there |
| --- | --- |
| `src/tula/` | Pipeline code |
| `data/raw/` | Downloaded public plate datasets (not committed) |
| `data/synthetic/` | Simulated FASTag, registry and billing layers |
| `experiments/` | Runs, metrics and receipts |
| `docs/` | Project brief, write-up, figures, demo script |

## Datasets

- Indian Licence Plate Dataset in the wild: https://arxiv.org/abs/2111.06054
- Indian LPR (IEEE DataPort): https://ieee-dataport.org/documents/indian-license-plate-recognition-dataset-yolo-ocr
- Foggy-Hazy License Plates (Mendeley): https://data.mendeley.com/datasets/p3jr4555tf

## Metrics

Wrong-charge rate (bounded), automation rate, human review load, worst-group gap, and guarantee survival under attack.
