# TULA handoff (read this first)

Written 2 Nov 2026 for a fresh Claude on Suryansh's new Claude Pro account. It holds everything needed to finish TULA without the old chats.

## 1. Who and what

- **Owner:** Suryansh Pratap Singh (GitHub `CopyNinja07-07`). Solo project.
- **TULA** = Toll Uncertainty and Liability Assessment. Tulā (तुला) is the balance scale.
- **Pitch:** "Before an AI punishes someone, it should weigh the evidence. TULA is that scale."
- **What it is:** an AI safety layer for any AI that punishes people automatically (tolls, e-challans, fraud flags). First testbed: barrier-free toll billing in India (NHAI's camera + FASTag free-flow tolling, where a wrong read becomes a fine that doubles after 72 hours).
- **Where the idea came from (1 Nov):** Suryansh saw FASTag slowing toll lanes while US free-flow tolls just read the car and bill it, and went looking for the AI safety gap in that.
- **Event:** Meta Global AI Developer Hackathon (Cerebral Valley + Meta), Indie track. **Accepted on 26 Oct 2026.**
- **Goal for now:** ship it as a strong, finished hackathon and resume project. A solo paper may come later, after a proper prior-work search.

## 2. Deadline

- **Submit by 4 Nov, 9:00 PM ET = 5 Nov, 6:30 AM IST.** Aim to submit on the evening of 4 Nov IST, not at the last minute.
- Form: cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit
- Judging: Impact 30%, Use of Meta AI tooling 25%, Technical depth 20%, Demo 25%. Meta tooling is a quarter of the score, so Muse Spark and SAM 3.1 must really run.

## 3. Where everything lives

| What | Where |
| --- | --- |
| Code (main copy) | Mac: `~/Desktop/Meta AI Hackathon/TULA` |
| GitHub (public) | https://github.com/CopyNinja07-07/tula |
| Papers and datasets | Mac: `~/Desktop/Meta AI Hackathon/research` (keep every source here, organised) |
| Whitepaper | `docs/WHITEPAPER.md` and `docs/TULA-Whitepaper.pdf` (rebuild PDF with `tools/make_whitepaper_pdf.py`) |
| Project brief | `docs/TULA_project_brief.md` |
| Foggy plate labels | `label_foggy.html` (in `tools/label_page.html` / the data folder) saves `labels.csv` to `~/Downloads` |
| Datasets | `data/raw/` (never committed) |
| Results | `experiments/results/` |
| Design blueprint | https://claude.ai/artifact/JusUMwS43g65brXWY3kacS (old account; may not open from the new one) |

The Mac copy may be ahead of GitHub. The last GitHub commit seen on 2 Nov is "Add Vietnamese plates as the second country". Run `git status` and `git log` on the Mac before anything else.

## 4. Pipeline

1. **SAM 3.1** cuts the plate and the vehicle out of the camera frame.
2. **Two independent plate readers:** Reader A = open plate OCR model; Reader B = **Muse Spark** (Meta Model API, base URL `https://api.meta.ai/v1`), which reads the plate and returns vehicle type, make and colour as JSON.
3. **Evidence check:** reads are compared with the FASTag-linked vehicle and its registry record (both simulated).
4. **Risk controller:** conformal risk control (Angelopoulos et al., arXiv 2208.02814) with a cut-off per group (plate style, state, day/night, weather), so the wrong-charge rate stays under a target.
5. **Outcome:** charge, hold, or human review, with an evidence note written by Muse Spark.
6. **Red team:** cloned plates, tag swaps, edited or sticker images; report how much of the guarantee survives.
7. **Review budget:** the strictest promise that fits the number of human reviewers.
8. **Recursive loop:** recalibrate from a small random audit, never from disputes alone (naive learning from disputes breaks the guarantee).

Code map (`src/tula/`): `muse.py` (Muse Spark reader), `read_plate.py`, `reader_a.py`, `readers_sim.py`, `simulate.py` (FASTag, registry, passages, simple attacks), `evidence.py`, `crc.py` (risk controller), `audit.py` (review budget), `feedback.py` (recursive loop), `evaluate.py` (results table). Tests in `tests/`.

## 5. Done vs remaining

**Done**
- Muse Spark reader code (`muse.py`), not yet run on real photos.
- Simulated FASTag, registry and billing layers.
- Risk controller, per group, two modes, tested.
- Human review budget (`audit.py`) and recursive dispute loop (`feedback.py`), on simulated traffic.
- Reader A measured on real plates: **31% exact on 1,684 Indian plates vs 97% on 2,921 Vietnamese plates.** (Caveat: the model may have seen Vietnamese plates in training.)
- Whitepaper v2 and README.
- Accepted to the hackathon.

**Remaining, in priority order**
1. **Credits and key (Suryansh does this himself):** claim the $150 Meta Model API credits from the acceptance email, then paste the key into `TULA/.env`. Claude never sees, prints or handles the key.
2. **Run Reader B (Muse Spark)** on the real Indian and foggy plates. Compare with Reader A.
3. **Add SAM 3.1 crops** in front of both readers (new step; not built yet).
4. **Finish the hand-labelled foggy plates.** Suryansh had done about 250 by 1 Nov; 400 to 500 is enough. Use what exists if time runs short.
5. **Final run:** feed real reads into the evidence check, risk controller, review budget and recursive loop. Save the numbers in `experiments/results/`. Baselines: single threshold, OCR only, Muse Spark only, fused without the risk controller.
6. **Red team run:** cloned plates and tag swaps on the real-read pipeline; survival curve.
7. **Small demo page:** one image in, charge / hold / review out with the evidence note.
8. **Update whitepaper and README** with real results; push to GitHub.
9. **Demo video (2 to 3 min) and short writeup**, then submit.

Cut list if time runs out (drop in this order): demo page polish, adaptive attacks, SAM 3.1 (say "planned" honestly), extra foggy labels. Never drop: Muse Spark on real plates, final numbers, video, submission.

## 6. Day-by-day plan to the deadline (IST)

| Day | Work | Done when |
| --- | --- | --- |
| **3 Nov (Tue), morning** | Suryansh: credits + key in `.env`. Claude: reconnect to Mac, check git state, one Muse Spark call on a sample plate | One real Muse Spark JSON read |
| **3 Nov, afternoon** | Muse Spark on all labelled Indian and foggy plates; SAM 3.1 crops added | Reader A vs Reader B table on real photos |
| **3 Nov, evening** | Final run: evidence check, risk controller, review budget, recursive loop, red team on real reads | All numbers saved in `experiments/results/` |
| **4 Nov (Wed), morning** | Demo page; whitepaper + README updated; push | Repo public, runs from README |
| **4 Nov, afternoon** | Record and edit demo video; write submission text | Video and writeup ready |
| **4 Nov, by 10 PM IST** | Submit the form (repo, video, writeup, whitepaper) | Submitted, about 8 hours early |

## 7. How Suryansh likes to work

- **Simple English.** Explain like he is new to the topic. Short replies.
- **Check prior work before calling anything novel.** Novelty is NOT verified. Say "to our knowledge" at most, and frame TULA as "a safety layer applied to a real case", not "a new invention". Each piece already exists (ANPR, conformal risk control, abstention, human review, clone-plate detection).
- **Never handle API keys.** He pastes keys into `.env` himself. Never print `.env`.
- **No Claude co-author lines in git commits.** No `Co-Authored-By` trailers, ever.
- **Save every dataset and paper** in `Meta AI Hackathon/research`. After the hackathon he will ask for a 60 to 70 page book-style explanation of the project, so keep sources organised.
- Demo videos: fast, connected, edited-looking, pitch language.
- Only public data; no real people's plates from his own footage.
- Prioritise finishing. Do work that can be undone without asking, and say what you did.

## 8. Ready-to-paste first prompt for the new account

Paste this into Claude Code (connected to the Mac, opened in the TULA folder):

```
Hi Claude. I'm Suryansh. I'm continuing my solo hackathon project TULA from another Claude account. 
Please read HANDOFF.md in this folder first (~/Desktop/Meta AI Hackathon/TULA/HANDOFF.md), 
then docs/TULA_project_brief.md and docs/WHITEPAPER.md.

Rules: explain in simple English, never ask for or print my API keys (I paste them into .env myself), 
don't call anything novel without checking prior work, and no Claude co-author lines in git commits.

Deadline: submit by 5 Nov 6:30 AM IST; I want to submit by 4 Nov 10 PM IST.
Start by checking git status and what's ahead of GitHub, then tell me in 5 lines where we are 
and what you'll do today following the day-by-day plan in HANDOFF.md. Then start on the next step.
```

If the new account uses a Claude project instead, upload HANDOFF.md, the brief and the whitepaper PDF as project files and paste the same prompt.
