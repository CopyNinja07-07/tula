# TULA: Toll Uncertainty and Liability Assessment

*Tulā* (तुला) is the balance scale. Before an AI punishes someone, it should weigh the evidence. TULA is that scale.

TULA is an AI safety layer for automatic billing, with barrier-free tolling as the first testbed and no tie to one country. For every vehicle it decides **charge**, **hold**, or **send to a human**, and it keeps the wrong-charge rate under a target that can be proven with conformal risk control. It also sizes that promise to the number of human reviewers available, and keeps it while the system learns from its own past decisions. It is being built for the Meta Global AI Developer Hackathon (26 Oct to 4 Nov 2026, Indie track, solo), and it continues whether or not the application is accepted.

**Status (25 Oct 2026):** working build. The risk controller (per group, two modes), evidence check, human review budget, the learning-from-disputes loop and the benchmark simulator run end to end on simulated traffic. Reader A (open plate OCR) is measured on 1,684 real Indian plates; Reader B (Muse Spark) is built and waits for API access. Design and early results: [docs/WHITEPAPER.md](docs/WHITEPAPER.md) ([PDF](docs/TULA-Whitepaper.pdf)).

## Quickstart

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt   # needs Python 3.10+
cp .env.example .env        # then paste your own Meta Model API key into .env
PYTHONPATH=src .venv/bin/python -m tula.read_plate data/samples/synthetic_plate.png
PYTHONPATH=src .venv/bin/python -m tula.simulate                 # simulated FASTag, registry and passages
PYTHONPATH=src .venv/bin/python -m tula.reader_a                 # Reader A (open OCR) on 1,684 labelled Indian plates
PYTHONPATH=src .venv/bin/python -m tula.evaluate                 # full simulated benchmark, prints the results table
PYTHONPATH=src .venv/bin/python -m tula.audit                    # human review budget vs promised wrong-charge rate
PYTHONPATH=src .venv/bin/python -m tula.feedback                 # recursive loop: learning from disputes, naive vs TULA
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests   # offline tests, no key needed
```

The read prints as JSON (plate text, confidence, plate style, state, vehicle type, make, colour, image issues) and a receipt is saved in `experiments/receipts/`. The sample plate is drawn by `tools/make_sample_plate.py` and belongs to no real vehicle.

## Pipeline

1. **SAM 3.1** cuts the plate and the vehicle out of the camera frame.
2. Two independent readers: a specialist plate OCR model, and **Muse Spark**, which reads the plate and returns vehicle type, make and colour as structured output.
3. **Evidence check**: the reads are compared with the vehicle linked to the FASTag and its registry record.
4. **Risk controller**: conformal risk control with a cut-off for each group (plate style, state, day/night, weather).
5. **Outcome**: charge, hold or human review, with an evidence note written by Muse Spark.
6. **Red team**: cloned plates, tag swaps and edited images.
7. **Review budget**: the strictest promise that fits the reviewers available.
8. **Recursive loop**: recalibrate from a small random audit, never from disputes alone.

## Layout

| Folder | What goes there |
| --- | --- |
| `src/tula/` | Pipeline code |
| `data/raw/` | Downloaded public plate datasets (not committed) |
| `data/synthetic/` | Simulated FASTag, registry and billing layers |
| `experiments/` | Runs, metrics and receipts |
| `docs/` | Project brief, whitepaper, figures, demo script |
| `tests/` | Offline tests |
| `tools/` | Small helper scripts |

## Datasets

- Foggy-Hazy License Plates (Mendeley, CC BY 4.0): https://data.mendeley.com/datasets/p3jr4555tf
- Indian number plates with text (Hugging Face): https://huggingface.co/datasets/zenitsu09/indian-number-plate
- Indian License Plates with Labels (Kaggle, boxes only): https://www.kaggle.com/datasets/kedarsai/indian-license-plates-with-labels
- A second country's public plate set (to choose)

Datasets are downloaded into `data/raw/` and never committed. The Indian Licence Plate Dataset in the wild (arXiv 2111.06054) is not public.

## Metrics

Wrong-charge rate (bounded), automation rate, human review load, worst-group gap, the believed-vs-true error gap when learning from disputes, and guarantee survival under attack.

Owner: Suryansh Pratap Singh
