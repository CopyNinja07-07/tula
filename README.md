<div align="center">

<img src="docs/assets/scale.svg" alt="Animated balance scale: two agreeing plate reads tip it to CHARGE, a FASTag that contradicts the plate tips it to REVIEW, fog leaves it level and the passage is HELD" width="100%">

# TULA · तुला

### An AI should weigh the evidence before it fines anyone.

TULA checks automatic toll bills before they are sent, and keeps a written promise on how many go to the wrong person.

[![Meta SAM 3.1](https://img.shields.io/badge/Meta-SAM%203.1-10b981?style=flat-square&labelColor=06100c)](#how-metas-models-are-used)
[![Muse Glimmer 30B](https://img.shields.io/badge/Meta-Muse%20Glimmer%2030B-6ee7b7?style=flat-square&labelColor=06100c)](#how-metas-models-are-used)
[![Track](https://img.shields.io/badge/Indie%20track-Build%20for%20Your%20World-bef264?style=flat-square&labelColor=06100c)](#built-during-the-hackathon)
[![Tests](https://img.shields.io/badge/tests-25%20passing-10b981?style=flat-square&labelColor=06100c)](tests/)
[![License: MIT](https://img.shields.io/badge/license-MIT-93a99d?style=flat-square&labelColor=06100c)](LICENSE)

**[🌐 Website](https://copyninja07-07.github.io/tula/)** · **[🎚️ Try it yourself](https://copyninja07-07.github.io/tula/#try)** · **[🚗 Toll desk](https://copyninja07-07.github.io/tula/demo/)** · **[📄 Whitepaper](docs/WHITEPAPER.md)** · **[📊 Every number](experiments/results/)**

</div>

---

## Built during the hackathon

TULA was built solo for the **Meta Global AI Developer Hackathon 2026** (26 October to 4 November), **Indie track**, theme **Build for Your World**, by Suryansh Pratap Singh. The idea came on 22 October, and the first design notes and simulated benchmark were committed on 25 October, while applying. Everything that uses Meta's models was built during the hackathon: SAM 3.1 on the photos, the Muse Glimmer reads, the hand labels, the real-photo benchmark, the red team and the website. The [commit history](https://github.com/CopyNinja07-07/tula/commits/main) shows the dates.

## For judges: a three-minute tour

| | What to open | What you will see |
|---|---|---|
| 1 | **[The website](https://copyninja07-07.github.io/tula/)**, top to bottom | The problem, how TULA works in four steps, and the results on 1,050 real photos |
| 2 | **[Try it yourself](https://copyninja07-07.github.io/tula/#try)** | Move the slider to choose how many wrong bills you accept. TULA recalculates its decision line for each kind of photo, live, on the real scores. Then try the "90% sure" rule and watch it break in clear weather |
| 3 | **[The toll desk](https://copyninja07-07.github.io/tula/demo/)** | Click real cars: the photo with SAM 3.1's boxes, both readers' answers, the evidence, TULA's decision and its written reason |
| 4 | **Reproduce the numbers** (no GPU, no API key, about 2 minutes) | `pip install -r requirements.txt` then `PYTHONPATH=src python -m tula.real_bench --alpha 0.05`. The model reads are saved in `experiments/results/`, so every table can be rebuilt on a laptop |

---

## The problem

India is moving to **barrier-free tolling** (Multi-Lane Free Flow, started on NH-48 in 2026). Cars drive under a camera gantry at full speed and a bill follows automatically. Nobody checks that bill before it is sent.

- **One wrong digit bills a stranger.** Read `MH12AB1234` as `MH12AB1284` and someone who was never there gets the notice. In India an unpaid toll notice doubles after 72 hours.
- **It already happens elsewhere.** A New York State audit found about 36,000 wrong charges at one exit in three weeks. Swapped FASTags and cloned plates cause the same harm on purpose.
- **Today's rule cannot say how often.** Billers trust the FASTag, else charge when the plate reader says it is "90% sure". Being sure is not being right, and nobody can tell a driver how often that rule bills an innocent person, in fog or under attack.

## Why I started

At a FASTag plaza the car still slows down and waits for the tag to be read, while in other countries cars pass under a gantry at full speed. The question was: what would it take for India to stop waiting **safely**? Removing the barrier is easy. Knowing, and limiting, how often the camera bills the wrong person is the hard part. That is an AI safety question: an automated system is about to penalise people, and it should be able to state and keep a limit on its own mistakes.

## What TULA does

TULA sits between the camera and the bill. For every passing car it decides one of three things:

| Decision | When | What happens |
|---|---|---|
| **Charge** | the evidence is strong enough for this kind of photo | billed automatically |
| **Hold** | the evidence is close | not billed yet; wait for the next camera or plaza |
| **Send to a person** | the evidence is weak or contradicts itself | a reviewer decides, with TULA's written reason in front of them |

And it keeps a promise you choose, for example **at most 5 wrong bills in every 100**, separately for fog, clear weather and each kind of plate.

## How it works

<img src="docs/assets/pipeline.svg" alt="Animated pipeline: a car passes the gantry, SAM 3.1 boxes the plate, two blind readers read it, the evidence check and the risk controller produce charge, hold or review" width="100%">

1. **Find.** Meta **SAM 3.1** finds the number plate and the vehicle in the photo from two text prompts, `"license plate"` and `"vehicle"`.
2. **Read, twice.** Two readers read the plate without seeing each other's answer: an open-source plate OCR on the plate crop, and Meta **Muse Glimmer 30B** on the whole photo, which also reports the car's make, colour and type.
3. **Check.** Plain code compares both reads with the FASTag and the registered vehicle: do the readers agree, does the tag belong to this plate, does the car look like the one on record? Each contradiction is a signal, and a small model fitted on separate data turns the signals into one **doubt score** from 0 to 1.
4. **Decide, with a promise.** Using past cars whose right answer is known, TULA draws a line on the doubt score for each group of traffic: the highest doubt it can accept while keeping the promise. Cars below the line are charged; the rest are held or reviewed. A group with too little checked data is never charged automatically.

<details>
<summary><b>The rule behind step 4</b> (conformal risk control)</summary>

For group `g` with `n_g` checked passages, scores `s_i`, and `wrong_i = 1` if charging passage `i` would bill the wrong account or amount:

$$
\tau_g \;=\; \max\Big\{\tau \;:\; \frac{\#\{i : s_i \le \tau,\ \text{wrong}_i\} + 1}{n_g + 1} \;\le\; \alpha \Big\}
\quad\Longrightarrow\quad
\mathbb{E}\big[\text{wrong-charge rate}_g\big] \le \alpha
$$

This is conformal risk control (Angelopoulos et al., 2022), applied per group. It holds for any doubt score, so a better score only buys more automation, never a broken promise. A second mode uses a Clopper-Pearson bound so the promise holds with at least 90% probability on each calibration set, not just on average. Code: [`src/tula/crc.py`](src/tula/crc.py). The website runs the same rule, ported line for line to JavaScript.

</details>

## How Meta's models are used

| Model | What it does in TULA | How it runs |
|---|---|---|
| **SAM 3.1** | Finds the plate and the vehicle from text prompts. One model gives both crops, with no plate-detector training. Found a plate in **247 of 248 foggy photos** (median score 0.94); the detector used before found 207 | MLX build (`mlx-community/sam3.1-bf16`) on a 16 GB Apple M5 MacBook, about 3 s per photo. [`src/tula/sam_crop.py`](src/tula/sam_crop.py) |
| **Muse Glimmer 30B** | The second, independent reader. Returns JSON with plate, confidence, vehicle type, make, colour and image problems. The vehicle fields are what catch a cloned plate on the wrong car. It says "cannot read" instead of guessing in fog | Meta's official 4-bit GGUF in llama.cpp, compiled for CUDA, split across **two free Kaggle T4 GPUs**. 1,096 photos in about 7 hours, zero failed calls. [`kaggle/glimmer_reader/`](kaggle/glimmer_reader/) |

**Why Meta's models matter here.** A plate reader alone cannot tell a cloned plate from the real car, because both show the same plate. Glimmer reads the car itself, which gives TULA independent evidence to check against the registry. SAM 3.1 finds plates in fog where a standard detector misses them, so fewer cars fall back to "no evidence". Because both are **open weights**, a toll operator can run the whole system at the plaza without sending photos of people's cars to a cloud API.

**What it took.** Glimmer's hidden reasoning used up the whole token budget on the first runs; the API switch to turn it off was ignored, so the fix was Glimmer's own `Reasoning strength: low` line in the system prompt plus a larger budget. Building llama.cpp on Kaggle's CUDA 13 needed a manual link to the GPU driver library. Both are documented in [`glimmer_reader.py`](kaggle/glimmer_reader/glimmer_reader.py). A hosted path through the Meta Model API (Muse Spark) is in [`src/tula/muse.py`](src/tula/muse.py) for operators who prefer an API.

## Results on 1,050 real photos

<img src="docs/assets/verdict.svg" alt="Wrong charges per group: today's biller 14 to 19 percent, one Glimmer threshold 12.2 percent in clear and 7.0 percent on the Indian set, TULA 3.6 to 4.6 percent, all under the 5 percent promise" width="100%">

232 clear photos, the **same 232 scenes in fog** (plate text hand-labelled for TULA), and 586 photos from an Indian plate dataset. Promise: at most 5% wrong bills per group. Scenes are split into fit / calibration / test so no scene is seen twice; numbers are the mean of **200 random splits**.

| Method | Wrong bills | Charged straight away | Clear | Fog | Indian set |
|---|---:|---:|---:|---:|---:|
| Today's rule (trust the tag, else the plate) | 17.0% | 100% | 14.1% | 18.9% | 17.4% |
| Charge if Glimmer is ≥ 90% sure | 6.7% | 52% | **12.2%** ✗ | 0.1% | **7.0%** ✗ |
| Charge if the open OCR is ≥ 90% sure | 3.7% | 28% | **8.4%** ✗ | 2.5% | 2.3% |
| Glimmer alone + TULA's rule | 4.2% | 85% | 3.5% | 4.0% | 4.5% |
| **TULA** | **4.3%** | **86%** | 3.6% ✓ | 4.0% ✓ | 4.6% ✓ |
| TULA, kept with 90% certainty | 2.5% | 79% | 1.5% | 1.9% | 3.1% |

**The key finding:** a rule that is safe in fog is unsafe in clear light. Glimmer refuses to guess in fog (it said "cannot read" on 55% of foggy photos) and is over-confident when it can see (21 wrong reads at ≥ 90% confidence on clear photos). One global threshold cannot know that; a line per group does not need to.

<details>
<summary><b>How well each reader reads</b></summary>

| Photos | SAM 3.1 found the plate | Open plate OCR, exact | Muse Glimmer 30B, exact | Glimmer said "cannot read" |
|---|---:|---:|---:|---:|
| Clear | 248 / 248 | 70.7% | **90.9%** | 0% |
| Fog, same scenes | 247 / 248 | 14.7% | **37.1%** | 54.7% |
| Indian set | – | 32.4% | **68.0%** | 16.3% |

</details>

<details>
<summary><b>What a stricter promise costs</b> (review budget)</summary>

| Promise | Wrong bills | Charged straight away | Held or reviewed |
|---:|---:|---:|---:|
| 1% | 0.53% | 30% | 70% |
| 2% | 1.28% | 63% | 37% |
| 3% | 2.31% | 78% | 22% |
| 5% | 4.40% | 86% | 14% |
| 10% | 9.57% | 94% | 6% |

</details>

### We also attacked it

<img src="docs/assets/redteam.svg" alt="As attackers take up to 30 percent of traffic after calibration, TULA's wrong charges stay under the bound of promise plus attacker share, while today's biller climbs to 42 percent" width="100%">

After TULA had drawn its lines, cloned plates and swapped FASTags took up to 30% of traffic. Theory allows wrong bills to rise to promise + attacker share even if no attack is caught. TULA used about a third of that room at every level; today's rule reached 42%. **Look-alike clones** (a copied plate on a car of the same make and colour) cannot be seen in one photo; they still stay inside the bound, and catching them needs evidence across plazas.

## What is real and what is simulated

| Real | Simulated |
|---|---|
| The photos (public datasets) | The FASTag on each car |
| 248 foggy photos hand-labelled for TULA ([labels](data/labels/foggy_labels.csv)) | The vehicle registry |
| SAM 3.1's boxes, both readers' answers | The mix of swapped tags, cloned plates and wrong classes |

No public data links tags, registrations and bills, so those parts are simulated with stated assumptions ([`src/tula/real_bench.py`](src/tula/real_bench.py)). Other limits:

- The open-source plate reader is a stand-in. It is not the system any Indian toll operator uses.
- The two readers fail on the same photos three times more often than chance on clear photos, so on this data TULA is only slightly better than Glimmer alone with the same rule.
- 20 of the 232 hand labels look like typing slips (both readers agree on something else). They are [listed](experiments/results/label_suspects.csv) and left unchanged.
- The promise assumes new traffic looks like the checked traffic. The [whitepaper](docs/WHITEPAPER.md) shows where that breaks and how a small random audit, never disputes alone, repairs it.

## Run it yourself

```bash
git clone https://github.com/CopyNinja07-07/tula && cd tula
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m pytest -q                              # 25 offline tests
PYTHONPATH=src .venv/bin/python -m tula.real_bench --alpha 0.05 --splits 200
python3 -m http.server -d docs 8000                                       # the website at localhost:8000
```

<details>
<summary><b>Regenerate the model reads, the website data and the art</b></summary>

The photos are not redistributed; download them into `data/raw/` (see [Data](#data-and-credits)) and build the bundle with `tools/make_kaggle_bundle.py`.

| Step | Command (`PYTHONPATH=src .venv/bin/python …`) | Runs on |
|---|---|---|
| SAM 3.1 boxes | `tools/run_sam_bundle.py` | Apple Silicon (MLX), about 3 s per photo |
| Open OCR on SAM crops | `tools/reader_a_on_sam.py` | CPU |
| Muse Glimmer reads | `kaggle/glimmer_reader/` then `kaggle kernels push --accelerator NvidiaTeslaT4` | 2× T4, about 7 h for 1,096 photos |
| Reader comparison | `tools/compare_readers.py` | CPU |
| Website data | `tools/export_lab.py`, `tools/make_demo.py` | CPU |
| Animated SVGs | `tools/make_art.py` (drawn from the result files) | CPU |
| Simulated benchmark, review budget, dispute loop | `-m tula.evaluate`, `-m tula.audit`, `-m tula.feedback` | CPU |

</details>

## Repository map

```
src/tula/        crc.py (the promise) · evidence.py (checks, doubt score) · note.py (written reasons)
                 real_bench.py (real photos) · sam_crop.py (SAM 3.1) · reader_a.py · muse.py
                 simulate.py · evaluate.py · audit.py (review budget) · feedback.py (dispute loop)
kaggle/          Muse Glimmer reader for free Kaggle GPUs
tools/           one script per pipeline step, plus the website and art builders
experiments/     results/: every number quoted anywhere
data/labels/     hand labels for the foggy photos
docs/            website (index.html, demo/), animated SVGs, fonts, whitepaper and PDF
tests/           25 offline tests
```

## Data and credits

| Source | Use | Licence |
|---|---|---|
| [Foggy-Hazy License Plates](https://data.mendeley.com/datasets/p3jr4555tf) (Mendeley) | 248 foggy photos and their clear versions; plate text [hand-labelled for TULA](data/labels/foggy_labels.csv) | CC BY 4.0 |
| [zenitsu09/indian-number-plate](https://huggingface.co/datasets/zenitsu09/indian-number-plate) | Indian plates with text (reads only; photos not shown) | Not stated by the uploader |
| [sonnetechnology/license-plate-text-recognition-full](https://huggingface.co/datasets/sonnetechnology/license-plate-text-recognition-full) | Vietnamese plates, a second country for the OCR check | CC BY 4.0 |

Models: Meta SAM 3.1 and Muse Glimmer 30B under Meta's licences (not redistributed); [fast-plate-ocr](https://github.com/ankandrew/fast-plate-ocr) as the open-source reader. Fonts: Bricolage Grotesque, Geist and Noto Serif Devanagari (SIL OFL). The website's toll desk shows small thumbnails of 19 CC BY photos, with credit.

**Prior work.** Every building block exists already: plate OCR, vision-language plate readers, conformal risk control, deferral to humans under a budget, audit-based error control (Gibbs, Han, Tibshirani and Zrnic, 2026). To our knowledge they have not been combined and measured for toll billing. Section 4 of the [whitepaper](docs/WHITEPAPER.md) says which parts are new and which are not.

**Licence.** [MIT](LICENSE).

<div align="center"><sub>Suryansh Pratap Singh · <a href="https://github.com/CopyNinja07-07">GitHub</a> · <i>tulā</i> is Sanskrit for the balance scale</sub></div>
