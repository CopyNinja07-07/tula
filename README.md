# TULA

**Before an AI fines someone, it should weigh the evidence.** *Tulā* (तुला) is Sanskrit for the balance scale.

TULA is a safety layer for AI systems that bill or fine people automatically. Its first testbed is barrier-free toll billing in India, where a camera reads your number plate and a bill follows with no barrier and no person checking. For every vehicle TULA decides **charge**, **hold**, or **send to a human**, and it keeps the wrong-charge rate under a stated promise, separately for each kind of traffic (fog, clear, plate type).

Built solo for the Meta Global AI Developer Hackathon 2026 (Indie track) with **Meta SAM 3.1** and **Meta Muse Glimmer 30B**, both running on open weights.

**[Demo page](docs/demo/index.html)** · **[Whitepaper](docs/WHITEPAPER.md)** · **[Results](experiments/results/)**

## The problem

India started Multi-Lane Free Flow tolling on NH-48 in 2026, with more than 100 plazas planned. A misread plate becomes an e-notice for someone else, and the fee doubles after 72 hours. Similar systems elsewhere already bill the wrong people: a New York audit found about 36,000 wrong charges at one exit in three weeks, and in October 2026 a Nebraska couple got a $500 toll bill from a misread plate. Today's systems charge when one confidence score passes one threshold, so nobody can say how often an innocent driver is billed, in fog, at night, or when someone clones a plate.

## What TULA does

```
camera frame
   │  SAM 3.1 (Meta) finds the plate and the vehicle
   ▼
Reader A: open plate OCR        Reader B: Muse Glimmer 30B (Meta)
(plate crop only)               (whole photo: plate, type, make, colour)
   │       the readers never see each other's answer       │
   └──────────────────────┬──────────────────────────────────┘
                          ▼
     Evidence check against the FASTag and the registered vehicle
                → one doubt score
                          ▼
     Risk controller: conformal risk control, one cut-off per group
        ├── low doubt, group certified  → CHARGE
        ├── borderline                  → HOLD (wait for the next camera)
        └── otherwise                   → HUMAN REVIEW + evidence note
```

- **Conformal risk control** (Angelopoulos et al., 2022) picks each cut-off so the expected wrong-charge rate stays under the promise α.
- **No certificate, no automatic charge:** a group with too little checked data is never charged automatically.
- **Review budget:** for a given number of reviewers, TULA reports the strictest promise it can keep.
- **Learning after launch:** TULA recalibrates from a small random audit, never from disputes alone, because "nobody complained" is not the same as "correct".

## Results on real photos

1,050 labelled photos in three groups: 232 clear, the same 232 scenes in fog, and 586 Indian-set photos. Promise: at most 5% wrong charges per group. Mean of 200 random splits. Full tables: [`experiments/results/`](experiments/results/).

**TULA keeps the promise in every group, and today's biller does not:**

| Method | Wrong charges | Charged automatically | Wrong: clear | Wrong: fog | Wrong: Indian set |
|---|---|---|---|---|---|
| Today's biller (trust the tag, else the plate) | 17.0% | 100% | 14.1% | 18.9% | 17.4% |
| One threshold: Muse Glimmer ≥ 90% sure | 6.7% | 52% | **12.2%** | 0.1% | **7.0%** |
| One threshold: open plate OCR ≥ 90% sure | 3.7% | 28% | **8.4%** | 2.5% | 2.3% |
| **TULA** | **4.3%** | **86%** | 3.6% | 4.0% | 4.6% |
| TULA, 90%-confidence mode | 2.5% | 79% | 1.5% | 1.9% | 3.1% |

A single threshold that is safe in fog is unsafe in clear weather: Glimmer is careful in fog and over-confident in clear light. TULA sets a separate cut-off per group, so it does not need to know this in advance.

**Readers** (exact plate reads against hand labels):

| Photos | SAM 3.1 found the plate | Open plate OCR | Muse Glimmer | Glimmer said "cannot read" |
|---|---|---|---|---|
| Clear | 248 / 248 | 70.7% | **90.9%** | 0% |
| Fog (same scenes) | 247 / 248 | 14.7% | **37.1%** | 55% |
| Indian set | – | 32.4% | **68.0%** | 16% |

**Red team:** with attackers (cloned plates, swapped tags) taking up to 30% of traffic after calibration, TULA's wrong charges stay under the bound of promise + attacker share (14.6% at 30%, bound 35%; today's biller: 42%).

**Review budget:** a 2% promise still charges 63% automatically; a 1% promise only 30%. That is how many reviewers a stricter promise costs.

**Also found:** the two readers fail on the same photos more often than chance (both wrong on 9% of clear photos, vs 3% if independent), so on these photos TULA is only slightly better than Glimmer alone with the same controller (86% vs 85% automatic). 20 of the 232 hand labels look like typing slips ([list](experiments/results/label_suspects.csv)); they are left unchanged.

What these numbers are and are not:
- The plate photos and both readers' answers are real. The FASTag, registry and scenarios (missing tag, swapped tag, cloned plate, wrong class) are simulated, because no public data links tags, registrations and bills.
- Reader A is an open-source plate reader used as a stand-in. It is not the system any Indian toll operator uses.
- Look-alike clones (a copied plate on the same make, model and colour) cannot be caught from one photo; the red team measures how much they cost.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m pytest -q                       # offline tests
PYTHONPATH=src .venv/bin/python -m tula.evaluate                   # simulated benchmark
PYTHONPATH=src .venv/bin/python -m tula.real_bench --alpha 0.05    # real photos (needs the reads below)
```

Reads on real photos:

| Step | Command | Where it runs |
|---|---|---|
| SAM 3.1 plate and vehicle boxes | `PYTHONPATH=src .venv/bin/python tools/run_sam_bundle.py` | Apple Silicon Mac (MLX), about 3 s per photo |
| Reader A on SAM crops | `PYTHONPATH=src .venv/bin/python tools/reader_a_on_sam.py` | CPU |
| Muse Glimmer reads | `kaggle/glimmer_reader/` (push with `kaggle kernels push --accelerator NvidiaTeslaT4`) | 2× T4 GPU on Kaggle, llama.cpp, Meta's official 4-bit GGUF |
| Compare readers | `PYTHONPATH=src .venv/bin/python tools/compare_readers.py` | CPU |
| Demo data | `PYTHONPATH=src .venv/bin/python tools/make_demo.py` | CPU |

`src/tula/muse.py` is an optional Reader B through the hosted Meta Model API (Muse Spark), for anyone with an API key in `.env`.

## Data

| Data | Use | Licence |
|---|---|---|
| [Foggy-Hazy License Plates](https://data.mendeley.com/datasets/p3jr4555tf) (Mendeley), 248 photos plus their clear versions | Fog vs clear on the same scenes. Plate text hand-labelled for TULA: [`data/labels/foggy_labels.csv`](data/labels/foggy_labels.csv) | CC BY 4.0 |
| [zenitsu09/indian-number-plate](https://huggingface.co/datasets/zenitsu09/indian-number-plate) (Hugging Face) | Indian plates with text | Not stated by the uploader |
| [sonnetechnology/license-plate-text-recognition-full](https://huggingface.co/datasets/sonnetechnology/license-plate-text-recognition-full) (Hugging Face) | Second country (Vietnam) for Reader A | CC BY 4.0 |

Full photo sets are not redistributed here; download them into `data/raw/`. The demo page carries small thumbnails of 29 photos, with credit.

## Layout

| Folder | Contents |
|---|---|
| `src/tula/` | Pipeline: SAM 3.1 crops, readers, evidence check, risk controller, review budget, audit loop, benchmarks |
| `kaggle/glimmer_reader/` | Muse Glimmer reader that runs on Kaggle GPUs |
| `tools/` | Scripts that run each step on the photo set and build the demo |
| `experiments/results/` | Every number in this README and the whitepaper |
| `data/labels/` | Hand-made plate labels for the foggy photos |
| `docs/` | Whitepaper and demo page |
| `tests/` | Offline tests |

## Prior work

Each building block exists already: plate OCR, vision-language plate readers (LP-LLM, BLPR), conformal risk control, deferral to humans under a budget, audit-based error control (Gibbs, Han, Tibshirani and Zrnic, 2026), clone-plate checks against the registry. To our knowledge they have not been combined and measured for toll billing. See Section 4 of the whitepaper.

Suryansh Pratap Singh · [GitHub](https://github.com/CopyNinja07-07)
