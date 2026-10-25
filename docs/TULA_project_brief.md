# TULA project brief (for the Claude project)

## What TULA is
TULA = Toll Uncertainty and Liability Assessment. Tulā (तुला) is Sanskrit for the balance scale. Pitch line: "Before an AI punishes someone, it should weigh the evidence. TULA is that scale."

A solo AI safety project by Suryansh Pratap Singh for the Meta Global AI Developer Hackathon (Cerebral Valley + Meta), Indie track. It is a safety layer for any AI that punishes people automatically (tolls, e-challans, fraud flags), with barrier-free toll billing as the first testbed. The work continues even if the hackathon application is not accepted.

Blueprint (full design, novelty table, plan): https://claude.ai/artifact/JusUMwS43g65brXWY3kacS
Code folder on the Mac: ~/Desktop/Meta AI Hackathon/TULA

## The problem
India's NHAI is rolling out Multi-Lane Free Flow (MLFF) tolling: ANPR cameras plus FASTag, with no human checking the bill. If the tag fails, the owner gets an e-notice and the fee doubles after 72 hours. India refunded 12.55 lakh faulty FASTag deductions in 2024. A New York audit found about 36,000 wrong charges at one Thruway exit in three weeks. Cloned plates, swapped tags and stickers that fool plate readers make it worse. Today's systems use one confidence threshold, so nobody can state or prove a wrong-charge rate.

## The system
1. SAM 3.1 cuts the plate and the vehicle out of the frame.
2. Two independent readers: a specialist plate OCR model, and Muse Spark (Meta Model API), which reads the plate and returns vehicle type, make and colour as structured JSON.
3. Evidence check: reads are compared with the FASTag-linked vehicle and its registry record (simulated).
4. Risk controller: conformal risk control (Angelopoulos et al., arXiv 2208.02814) with a cut-off per group (plate style, state, day/night, weather) so the wrong-charge rate stays under a target.
5. Outcome: charge, hold, or human review, with an evidence note written by Muse Spark.
6. Red team: cloned plates, tag swaps, edited or sticker-style images; report how much of the guarantee survives.

## Novelty claim (keep it honest)
Each piece exists alone: confidence thresholds in toll patents, probabilistic LPR, VLM plate readers (LP-LLM, BLPR), clone-plate detection (UK False Plate Classifier; NOT claimed as new), plate-reader attacks (GRAPHITE, SPAR), robust conformal prediction (Gendler ICLR 2022, Lip-RCP ICML 2025). No work found that combines them into billing with a provable, group-wise wrong-charge bound tested under attack, plus an open benchmark pairing tag reads, plates and billing outcomes. Say "to our knowledge"; re-run the search before claiming.

## Data
Semi-synthetic benchmark: real plates from Indian Licence Plate Dataset in the wild (arXiv 2111.06054, 16,192 images), IEEE DataPort Indian LPR set, Foggy-Hazy plates (Mendeley, 1,001 images), augmented night/rain copies, plus simulated FASTag, registry and billing layers. Public data only; no real people's plates from own footage.

Metrics: wrong-charge rate (bounded), automation rate, human review load, worst-group gap, guarantee survival under attack. Baselines: single threshold, OCR only, Muse Spark only, fused without the risk controller.

## Hackathon facts
- Build window: 26 Oct to 4 Nov 2026. Submit by 4 Nov, 9:00 PM ET (5 Nov, 6:30 AM IST) at cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit.
- Judging: Impact 30%, Use of Meta AI tooling 25%, Technical depth 20%, Demo 25%.
- $150 Meta Model API credits per accepted participant (claim form in the acceptance email). Meta Model API base URL: https://api.meta.ai/v1. Models: Muse Spark, Muse Image, SAM 3.1, open-weight models (also on Modal, Baseten, Fireworks), Muse Code.
- Application submitted 24 Oct; status Pending; acceptance emails by 26 Oct, 9:00 AM ET.
- If not accepted: build anyway with Meta's open-weight models and other public tools.

## Solo 10-day plan
| Days | Goal | Done when |
| --- | --- | --- |
| 26 Oct | Kickoff, credits, API working, download datasets | One Muse Spark call returns a plate read as JSON |
| 27-28 Oct | Simulated tag and registry layer; SAM 3.1 crops; OCR reader | Every image has a crop, a read and a tag record |
| 29-30 Oct | Muse Spark second reader; evidence check and disagreement score | Baselines measured |
| 31 Oct-1 Nov | Conformal risk controller with per-group cut-offs | Wrong-charge rate under target per group |
| 2 Nov | Red team: cloned plates, tag swaps | Survival curve |
| 3 Nov | Dashboard and evidence note | Live clip in, decision out |
| 4 Nov | README, demo video, submit | Submitted early |

## How Suryansh likes to work
- Plain, simple English; explain like he is new to the topic.
- Every project should be genuinely novel; check prior work before claiming anything.
- Never print or handle API keys; he pastes keys into .env himself.
- No Claude co-author lines in git commits.
- Demo videos: fast, connected, edited-looking, pitch language.
