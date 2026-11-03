# TULA: A Risk-Controlled Safety Layer for Automatic Billing

**Toll Uncertainty and Liability Assessment**

Suryansh Pratap Singh · Working paper, version 3, 4 November 2026

> **Status.** The full pipeline runs on real photos: Meta SAM 3.1 finds the plate and the vehicle, an open-source plate OCR (Reader A) and Meta Muse Glimmer 30B (Reader B) read them, and the evidence check, risk controller and red team run on those real reads. The FASTag, registry and billing layers are still **simulated**. Sections 7.1, 7.3 and 7.4 use simulated readers; Sections 7.2, 7.5 and 7.6 use real photos and real reads. Every hypothesis is stated so that it can fail.

---

## Abstract

Barrier-free tolling bills a vehicle with no person checking the bill. A camera reads the plate, a reader picks up the tag, and a fee follows. When the plate is misread, or the tag belongs to another car, a real owner gets a penalty. Today's systems guard against this with one confidence threshold. That threshold cannot say how often a wrong charge will happen, it says nothing about night, rain or an attacker with a cloned plate, and it gives no safe way to improve the system after deployment.

TULA is a safety layer that sits between the camera and the bill. It fuses independent evidence into one disagreement score, then decides to **charge**, **hold**, or **send to a human**. A conformal risk controller sets the charge cut-off so that the wrong-charge rate stays below a stated target, calibrated separately for each group of traffic (plate style, region, day or night, weather). A group too small to certify is never charged automatically. TULA also answers two questions a deployed system faces: **how strict a promise can it make for a given number of human reviewers**, and **how can it keep learning from its own decisions** when the only feedback is disputes from the people it charged. On 1,050 real plate photos read by Meta SAM 3.1 and Meta Muse Glimmer 30B, with simulated tags and registry, TULA kept wrong charges under a 5% promise in every group (clear, fog, Indian set) while charging 86% of traffic automatically; today's tag-first biller was wrong on 17%, and a single confidence threshold broke the promise in clear weather. We also show, in simulation, that a system which learns from disputes slides to about 2.5 times its promised wrong-charge rate while believing it is on target, and that a small random audit keeps the promise. The design is not specific to India: the same layer applies to any automatic penalty (tolls, e-challans, fraud flags), in any country.

The name is Sanskrit. *Tulā* (तुला) is the balance scale. The system weighs the evidence before it punishes anyone.

---

## 1. Problem

Free-flow tolling is used in Ireland, Norway, Chile, Australia, Canada, the Czech Republic and several US states, and India started Multi-Lane Free Flow (MLFF) tolling in May 2026, with the first plaza on NH-48 and bids out for 104 more. In India a misread becomes an e-notice, and the fee doubles after 72 hours.

The errors are small in rate and large in count:

- India refunded about 12.55 lakh faulty FASTag deductions in 2024, roughly 0.03% of transactions, and that was with toll booths still in place.
- A New York State audit found about 36,000 wrong charges at one Thruway exit in three weeks, roughly a 5% error rate.
- Dublin's M50 logged 14,280 plate misreads in about 87 million passages.

Four things are missing from current systems:

1. **No stated error rate.** A confidence threshold has no known wrong-charge rate, per plate type or per region.
2. **No attack accounting.** Printed stickers, cloned plates and swapped tags are documented. No deployed system reports how much damage they can do.
3. **No safe default for rare groups.** A model that is accurate on average can be wrong far more often on hand-painted plates, two-line plates, fog or night.
4. **No safe way to learn after deployment.** The only feedback is disputes, and only people who were charged can dispute. Learning from that feedback teaches the system that its unnoticed mistakes were correct.

## 2. The idea in one picture

```
 camera frame ──► SAM 3.1 (text prompts "license plate", "vehicle"): plate crop + vehicle box
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
   Reader A: plate OCR          Reader B: Muse Glimmer 30B (vision-language)
   (plate crop only)            (whole photo; never Reader A's answer)
          │                            │
          └─────────────┬──────────────┘
                        ▼
        Evidence check against tag + registry
        (plate, class, make, colour)  →  one disagreement score s
                        ▼
        Risk controller (per-group cut-off τ_g, sized to the review budget)
          ├── s ≤ τ_g and group certified ──► CHARGE
          ├── borderline ───────────────────► HOLD (next camera, next plaza)
          └── otherwise ────────────────────► HUMAN REVIEW + evidence note
                        ▼
        Random audit of a small share of ALL traffic
          └──► recalibrates τ_g each round (never learns from disputes alone)
```

## 3. Method

### 3.1 Readers that cannot copy each other

Two readers are only useful if their mistakes differ. If the second reader sees the first reader's answer, it tends to agree with it and the disagreement signal disappears. TULA applies the need-to-know rule from our earlier work on agent context (ZeroBleed): each reader receives only the inputs it needs, and the evidence check is ordinary code that sees both outputs.

- **Plate finder.** Meta's SAM 3.1 (official weights, converted to MLX, running on a laptop) is prompted with "license plate" and "vehicle". On the 248 hand-labelled foggy photos it found the plate in 247; the open detector used in version 2 found 207.
- **Reader A** is a small specialist OCR model (the open-source fast-plate-ocr model `cct-s-v2-global`). It sees the SAM 3.1 plate crop and nothing else. It is a stand-in, not the reader any toll operator uses.
- **Reader B** is Meta's open-weight Muse Glimmer 30B (official 4-bit GGUF, served with llama.cpp on two T4 GPUs, reasoning strength "low", Meta's recommended sampling with a fixed seed). It reads the whole photo and returns plate text, confidence, plate style, state, vehicle type, make, colour and image problems as JSON. It is told never to guess and to mark the plate unreadable instead. It is never shown Reader A's answer. A hosted alternative (Muse Spark through the Meta Model API) is in the code for operators with an API account.

Using open weights for both Meta models means an operator can run TULA at the plaza without sending photos of people's cars to a cloud service.

Language models can invent plausible plates. Reader B's plate is never trusted on its own: it only adds or removes doubt, and the cut-off is calibrated on outcomes, so a reader that invents plates costs automation, not safety.

### 3.2 The disagreement score

The evidence check decides who would be billed (the tag's account, or the registry match for the plate when there is no tag) and turns the evidence into signals: plate disagreement between the readers, mismatch between the tag's registered plate and the read, both readers agreeing exactly on a plate that is not the tag's, vehicle type against the billed toll class, colour and make against the registry (only when the reader could tell; "unknown" is never counted against the driver), low reader confidence, and a missing tag. These are combined into one number `s ∈ [0, 1]`, higher meaning more doubt.

Two scores are supported: a hand-set weighted sum, and a logistic regression fitted on a separate split of the data. Fitting the score is allowed because the cut-off is calibrated on different passages afterwards. The safety claim comes from calibration, not from the score: a better score gives more automation, a worse score gives more holds, and neither breaks the bound.

### 3.3 The risk controller

Define the loss for one passage and a cut-off `τ`:

```
L(τ) = 1[ vehicle is charged  AND  charge is wrong ]       charged means s ≤ τ
```

"Wrong" means the bill goes to the wrong account or for the wrong amount. `L` is bounded by 1 and never decreases as `τ` grows. This is the setting of conformal risk control (Angelopoulos et al., 2022). With `n` calibration passages and empirical risk `R̂_n(τ)`, choose

```
τ̂ = sup { τ :  n/(n+1) · R̂_n(τ) + 1/(n+1)  ≤  α }
```

Then, if test passages are exchangeable with the calibration passages, `E[L(τ̂)] ≤ α`. The target `α` is the wrong-charge rate we promise.

That bound holds **on average over calibration sets**. A single deployment wants more: the promise should hold for *this* calibration set with high probability. TULA therefore also offers a high-probability mode in the style of Learn-then-Test: it picks the largest `τ` whose one-sided Clopper-Pearson upper bound on the wrong-charge rate stays below `α` at confidence `1 − δ` (we use `δ = 0.1`). Both modes are implemented and tested; the tests check that the average risk stays under `α` in the first mode and that the bound is exceeded in at most a `δ` share of trials in the second.

### 3.4 Per-group cut-offs, and when to refuse

The bound above holds over all traffic. A group that is rare or hard can carry far more than `α` while the average still looks fine. TULA calibrates one cut-off `τ̂_g` for each group `g` (plate style, region, day or night, weather), so the bound holds inside each group.

This has a hard floor. Because of the `1/(n+1)` term, a group with `n_g` calibration passages can only certify `α` if `n_g ≥ 1/α − 1`. For `α = 10⁻⁴` that is about **10,000 passages per group**.

So TULA adopts a rule we call **no certificate, no automatic charge**: a group without enough calibration data to certify `α` is never charged automatically. Its passages are held or reviewed, and the group is reported as uncertified. In our simulation the uncertified groups were exactly the hardest ones (hand-painted plates in fog or at night, two-line plates at night in fog): the system gets less automatic where it knows least.

To reach realistic error rates without waiting for real wrong charges, the benchmark injects errors (tag swaps, cloned plates, misreads) at higher-than-real rates. Re-weighting them back to realistic frequencies is planned, not built.

### 3.5 What an attacker can take away

Conformal guarantees assume exchangeability. A cloned plate or a sticker attack breaks it on purpose. We do not claim the guarantee survives an attack unchanged. We state what it becomes.

**Proposition.** Let `P` be the calibration distribution and `Q` the test distribution, and let `TV(P, Q) = ε`. For any loss bounded in `[0, 1]`, `E_Q[L(τ̂)] ≤ E_P[L(τ̂)] + ε ≤ α + ε`.

*Proof sketch.* For a function `f` with values in `[0, 1]`, `|E_Q f − E_P f| ≤ TV(P, Q)`. Apply it to `f = L(τ̂)` with `τ̂` fixed after calibration. ∎

If an attacker controls a fraction `ε` of the traffic, the wrong-charge rate is at most `α + ε`. The bound is loose, but it is a number we can publish and test.

### 3.6 The human review budget

Every hold or review costs something. An operator has a fixed number of reviewers, so the real question is: **with reviewers for a share `b` of traffic, what is the strictest promise `α` TULA can make?** TULA sweeps `α`, measures the share of traffic sent to humans at each level, and reports for each budget the smallest `α` whose review load fits. If the review queue still overflows (for example during a surge), passages are triaged by expected harm, doubt times fee. The highest-harm passages go to humans first, the rest wait on hold, and nothing over budget is ever charged. This turns the three-way trade-off between wrong charges, automation and human work into one table an operator can read (Section 7.3).

### 3.7 Learning from its own decisions safely (the recursive loop)

After deployment a billing system receives feedback only through disputes, and disputes are **selective labels**: only charged people can dispute, and many wrongly charged people never do. A cloned-plate victim may not notice a small toll at all. A system that recalibrates on this feedback treats "no dispute" as "correct". Its estimated error falls, its cut-off loosens, it charges more, and the loop repeats. Attackers add pressure: when cloned plates get through, cloning spreads.

TULA never recalibrates on disputes alone. Each round, a small **uniform random audit** of all traffic (charged, held and reviewed alike) is checked by humans. Those audited passages are a random sample of real traffic, so they are exchangeable with future traffic in a stationary period, and the bound of Section 3.3 still applies to cut-offs calibrated on them. The audit also gives an unbiased estimate of the live wrong-charge rate, so the system knows its real number instead of the dispute-based one. Disputes are still handled as complaints and refunds. They are simply not used as calibration labels.

The limit is drift. Audits from older rounds describe older traffic, so when the attack mix changes quickly the bound can lag by a round. Section 7.4 shows this happening once, and the audit catching it.

### 3.8 Explanations that serve a real decision

For every passage TULA writes a short note from the structured evidence, for example: "Sent to a human reviewer. Both readers agree on the plate. No FASTag was read. The make, colour seen in the photo do not match the registered vehicle (possible cloned plate or swapped tag)." The note goes to the reviewer and, if the driver disputes, to the driver. It is written by plain code from the measured signals, not by a language model, so it cannot state anything the pipeline did not measure.

## 4. What is new, and what is not

Based on 15 targeted searches on 24 October, a re-check of every cited paper on 25 October, and six more searches on 3 November, the building blocks exist separately. We have not found a paper, patent or product that applies conformal risk control to plate reading or toll billing: deployed systems use one confidence threshold (for example, E-470 in Colorado sends reads under 94% confidence to manual review). The November search also found close work we had missed, and two rows below were downgraded because of it: choosing an error level from a reviewer budget is already done in security-alert triage and clinical deferral, and Gibbs, Han, Tibshirani and Zrnic (October 2026) give distribution-free error control with a minimum of expert audits. What we did not find is the dispute (selective-label) failure in billing measured against an audit fix, or any of this tested on real plate photos. This is still not a full literature review.

| Piece | Closest existing work | Status in TULA |
|---|---|---|
| Confidence thresholds before manual review | USPTO 10019640, 8768753 | Replaced by a calibrated cut-off with a stated rate |
| Uncertainty in plate reading | Benchmarking probabilistic LPR (2023) | Reused as an input signal, not claimed |
| VLMs reading plates | LP-LLM; BLPR (confidence-driven VLM fallback) | Reused; checked against a registry record |
| Clone-plate detection by make/model vs registry | UK False Plate Classifier; make-model classifiers (arXiv 1809.00953) | Not claimed as new |
| Attacks on plate readers | GRAPHITE; street-legal adversarial plate rim (SPAR) | Used as the attack set |
| Conformal risk control | Angelopoulos et al., 2022 | The core tool, not claimed |
| Conditional / adaptive risk control | Automatically Adaptive CRC (arXiv 2406.17819) | Related; TULA uses explicit groups and a refusal rule |
| Robust conformal prediction | Gendler et al. ICLR 2022; Lip-RCP (arXiv 2506.05434) | Pixel-noise robustness; TULA's bound is about attacker-controlled traffic |
| Deferral to humans under workload limits | DeCCaF (arXiv 2403.06906); cost-sensitive conformal abstention with a review-rate cap (arXiv 2607.27143); dual-threshold conformal deferral for alert triage (MDPI Electronics 15(18), 2026) | Applied, not new: TULA reads the strictest promise off the reviewer budget the same way |
| Error control with a minimum of expert audits | Gibbs, Han, Tibshirani, Zrnic, *Reliable AI-Assisted Decisions via Selective Auditing* (October 2026) | Closest work to Section 3.7; TULA adds the dispute-feedback failure in billing |
| AI control with an audit budget | Ctrl-Z (arXiv 2504.10374) | Evaluation style borrowed for billing |
| Selective labels from human decisions | Lakkaraju et al., 2017 | The problem behind Section 3.7 |
| Reader independence by input isolation | none found for plate reading | Design choice |
| No-certificate-no-charge rule for small groups | Follows from the 1/(n+1) term; per-group (Mondrian) conformal methods | Design rule, not a contribution |
| Conformal risk control in toll billing, tested on real plate photos | none found | Applied here, to our knowledge for the first time |
| Dispute-label recalibration vs random-audit recalibration in billing | none found for billing | Measured here in simulation |
| Open benchmark pairing tag, plate, class and billing | none found | Released with the project (photos linked, not redistributed) |

The claim we make is narrow: these known tools, combined and measured for automatic toll billing, on real photos.

## 5. Threat model

- **Cloned plate.** The right plate on the wrong vehicle. Both readers can agree, so the vehicle check against the registry carries the decision.
- **Swapped tag.** A tag moved to a different car. The plate-vs-tag and class checks should catch it.
- **Wrong class.** A tag registered under a cheaper toll class. The vehicle-type check should catch it.
- **Sticker or edited image.** Printed patterns that mislead plate readers. Plan: a transfer attack on Reader A first, then an adaptive attack on the full pipeline.
- **Adaptive attackers over time.** Attackers copy what works. The recursive-loop experiment lets cloning grow with its success.
- **Out of scope for now.** Collusion between reviewers, tampering with the registry itself, and attacks on the camera hardware.

## 6. Evaluation

**Data.** Public data only, from more than one source, so the method is not tied to one country's plates.

| Layer | Source | Status |
|---|---|---|
| Indian plates with plate text | Hugging Face `zenitsu09/indian-number-plate` (1,684 unique photos, 965 plates; licence not stated) | Downloaded, used for Reader A |
| Foggy and hazy Indian plates | Foggy-Hazy License Plates, Mendeley (1,001 photos with clear versions, CC BY 4.0) | 248 photos hand-labelled for TULA (232 readable, 16 unreadable), each paired with its clear version; labels released |
| Plate locations | Kaggle "Indian License Plates with Labels" (2,083 photos, boxes only) | Downloaded |
| Vietnamese plates with text | Hugging Face `sonnetechnology/license-plate-text-recognition-full` (8,823 photos, CC BY 4.0; 2,921 clean single-line plate labels used) | Downloaded, used for Reader A |
| Tag, registry, billing | Simulated, with tag misreads, swaps, clones and wrong classes | Built |

The Indian Licence Plate Dataset in the wild (16,192 images), named in version 1, is not public: its authors write that it cannot be released "because of legalities involved in making Indian Road data public". IEEE DataPort's Indian LPR set needs a paid subscription.

**Baselines.** Today's biller (trust the tag, else the plate), one confidence threshold per reader, the fused score with a fixed cut-off, each reader alone with the controller.

**Metrics.** Wrong-charge rate (the promised number), automation rate, hold rate, human review load, worst-group rate, groups over the target, the believed-vs-true gap in the recursive loop, and how much of the guarantee survives each attack.

**Hypotheses, each of which can fail.**

1. The controller keeps the wrong-charge rate at or below `α` in every certified group, while the single-threshold baseline exceeds `α` in at least one group.
2. The fused system gives a higher automation rate than OCR alone at the same wrong-charge rate.
3. Isolating the readers' inputs lowers the correlation of their errors compared with showing Reader B the OCR answer.
4. Under a cloned-plate attack on a fraction `ε` of traffic, the measured wrong-charge rate stays under `α + ε`.
5. Calibrating on day and testing on night breaks the guarantee, and the group-wise controller recovers it only when the group is calibrated.
6. A system that recalibrates on dispute labels exceeds its promise and under-estimates its own error; random-audit recalibration keeps the promise.
7. Reader confidence alone is not a safe charging signal on real Indian plates: some reads the model is very sure of are wrong.

## 7. Early results

Sections 7.1, 7.3 and 7.4 use one seed and **simulated** readers with assumed error rates, so they test the method, not real plates. Sections 7.2, 7.5 and 7.6 use real photos and real reads; 7.6 is the mean over 200 random splits.

### 7.1 The controller on simulated traffic (hypotheses 1 and 2)

120,000 passages over 20,000 vehicles, split into fit, calibration and test; 24 groups; target `α = 0.5%` per group. Planted problems (tag swaps, clones, wrong classes, missing tags) are about 10% of traffic, far above real life.

| Method | Wrong-charge rate | Charged automatically | Worst group | Groups over α |
|---|---|---|---|---|
| Today's biller (trust the tag) | 6.19% | 100% | 7.39% | 24/24 |
| One confidence threshold (0.9) | 4.23% | 67.6% | 5.48% | 12/24 |
| Fused score, fixed cut-off | 1.29% | 90.5% | 2.01% | 15/24 |
| OCR only + controller | 0.44% | 29.3% | 0.90% | 7/24 |
| Muse only + controller | 0.47% | 89.2% | 1.14% | 6/24 |
| TULA (fused + controller) | 0.44% | 89.5% | 1.04% | 7/24 |
| **TULA, 90%-confidence mode** | **0.30%** | **83.8%** | **0.61%** | **1/24** |

Hypothesis 1 holds in the high-probability mode. In the average-case mode, single test splits still land over `α` in several groups, which is what an in-expectation bound allows. Hypothesis 2 is mixed: fusion beats OCR alone by far (89% vs 29% automation), but in simulation it is no better than Reader B alone, because the simulated Reader B already carries the vehicle checks. Real readers will decide this.

### 7.2 Reader A on real photos (hypothesis 7)

fast-plate-ocr `cct-s-v2-global` on 1,684 labelled Indian plate photos: **31% exact reads**, 22.5% character error rate (49% exact on crops 200 px or wider, 13% on crops under 100 px). Of the 313 reads it was at least 90% sure of, **69 were wrong (22%)**. A billing system that trusts that confidence would charge the wrong person on those plates. This supports hypothesis 7 and is the direct case for calibrating on outcomes instead of trusting confidence.

The same model on 2,921 Vietnamese plates (real photos): **96.9% exact reads**, 0.7% character error rate, and only 24 of 2,825 confident reads wrong (0.8%). One "global" plate reader is three times more accurate in one country than in another. A single worldwide threshold would therefore be far less safe for Indian drivers than for Vietnamese ones, which is the case for calibrating per region. Caveat: the model may have seen Vietnamese plates in training, so part of the gap may be training-data overlap rather than plate difficulty; we have not checked its training data yet.

### 7.3 The human review budget (Section 3.6)

| Reviewers can check | Strictest promise that fits | Wrong charges (test) | Charged automatically |
|---|---|---|---|
| 2% of traffic | 1.50% | 1.24% | 91.5% |
| 5% of traffic | 0.75% | 0.59% | 87.6% |
| 10% of traffic | 0.30% | 0.18% | 74.1% |
| 20% of traffic | 0.20% | 0.10% | 50.8% |

Stricter promises cost both reviewers and automation, and the table makes that price explicit.

### 7.4 Learning from disputes (Section 3.7, hypothesis 6)

Promise `α = 1%`, six rounds of 30,000 passages, wrong charges disputed with probability 0.3 (clones) to 0.7 (wrong class); cloning grows with its success against the naive system.

| Round | Clone rate | Naive: true | Naive: believes | TULA: true | TULA: believes |
|---|---|---|---|---|---|
| 1 | 2.0% | 0.46% | 0.24% | 0.46% | 0.11% |
| 2 | 2.5% | 2.28% | 1.17% | 0.55% | 0.75% |
| 3 | 6.6% | 2.54% | 1.21% | 0.68% | 0.46% |
| 4 | 12.6% | 2.84% | 1.22% | 1.11% | 1.11% |
| 5 | 15.0% | 2.71% | 1.09% | 1.21% | 1.20% |
| 6 | 15.0% | 2.49% | 1.08% | 1.00% | 0.88% |

The naive system settles at 2.5–2.8%, more than twice its promise, while believing it is near 1.1–1.2%. TULA, recalibrating on a 3% random audit, stays close to its promise and knows its real number. In rounds 4 and 5, when cloning grew fastest, TULA went over its promise (1.11% and 1.21%); its own audit measured the rise almost exactly (1.11% and 1.20%), and it was back to 1.00% in round 6. That is the drift limit of Section 3.7, measured: recalibration lags a fast-growing attack by about a round, but it never loses track of the true rate.

### 7.5 Meta SAM 3.1 and Muse Glimmer on real photos

**Finding the plate.** SAM 3.1 (MLX build on a 16 GB Apple M5 laptop), prompted with the text "license plate", found a plate in 247 of 248 foggy photos (median score 0.94) and in all 248 clear versions. The detector used before found 207 of 248.

**Reading it.** Muse Glimmer 30B ran from Meta's official 4-bit GGUF in llama.cpp on two free Kaggle T4 GPUs, with reasoning set to low and Meta's recommended sampling. It read 1,096 photos in about 7 hours with no failed calls. Truth is the hand labels (foggy, clear) and the dataset labels (Indian set); photos the labeller marked unreadable are left out.

| Set | Photos | Reader A exact | Glimmer exact | Glimmer said "cannot read" | Reader A sure (≥90%) but wrong | Glimmer sure (≥90%) but wrong |
|---|---|---|---|---|---|---|
| Clear | 232 | 70.7% | **90.9%** | 0% | 17 of 152 (11%) | 21 of 226 (9%) |
| Foggy (same scenes) | 232 | 14.7% | **37.1%** | 54.7% | 17 of 36 (47%) | 0 of 2 |
| Indian set | 586 / 600 | 32.4% | **68.0%** | 16.3% | 20 of 101 (20%) | 37 of 332 (11%) |

Three things stand out. Glimmer reads far better than the open-source OCR on every set. In fog it mostly says it cannot read instead of guessing, which is the behaviour a billing system needs. But on clear photos it is still at least 90% sure of 21 wrong reads, so its confidence alone is not a safe charging signal either (hypothesis 7 holds for both readers).

**Label check.** Where both readers agree with each other but not with the hand label, the label may be a typing slip. 20 of 232 labels are flagged this way (`experiments/results/label_suspects.csv`), for example `WBO6F5977` where both readers say `WB06F5977`. The labels are left unchanged, so every reader is scored against the same human labels; the flagged list is released for checking.

### 7.6 TULA on real photos (hypotheses 1, 2, 4)

**Set-up.** 1,050 labelled photos in three groups (232 clear, 232 foggy versions of the same scenes, 586 Indian-set photos), each with both real reads. The FASTag, registry and scenario on each passage are simulated: 80% clean, 8% missing tag, 5% swapped tag, 4% cloned plate, 3% tag in the wrong class. The registry is dense, so a misread plate always bills somebody else. The registered make and colour come from Glimmer's read of the clear photo of the same scene. Scenes are split 20% (fit the learned score) / 40% (calibrate) / 40% (test), so a foggy photo and its clear twin never sit on both sides. Every number is the mean over 200 random splits. Promise `α = 5%` per group. Code: `src/tula/real_bench.py`; output: `experiments/results/real_bench_alpha0.05.md`.

| Method | Wrong charges | Charged automatically | Wrong: clear | Wrong: foggy | Wrong: Indian |
|---|---|---|---|---|---|
| Today's biller (trust the tag, else the plate) | 17.00% | 100% | 14.14% | 18.88% | 17.38% |
| One threshold: Reader A ≥ 0.9 | 3.70% | 27.5% | **8.41%** | 2.46% | 2.33% |
| One threshold: Glimmer ≥ 0.9 | 6.65% | 52.2% | **12.23%** | 0.11% | **7.03%** |
| Fused score, fixed cut-off 0.3 | 2.64% | 56.9% | 2.29% | 0.19% | 3.75% |
| Reader A only + controller | 4.51% | 47.8% | 4.16% | 4.53% | 4.65% |
| Glimmer only + controller | 4.17% | 84.6% | 3.52% | 3.96% | 4.50% |
| **TULA (both readers + controller)** | **4.26%** | **85.8%** | 3.61% | 3.95% | 4.64% |
| TULA, 90%-confidence mode | 2.50% | 79.3% | 1.47% | 1.89% | 3.14% |

**Hypothesis 1 holds on real reads.** TULA stays under 5% in every group while charging 86% of traffic automatically. A single confidence threshold breaks the promise in the clear group with either reader (8.4% and 12.2%) and in the Indian group with Glimmer (7.0%): the threshold that is safe in fog is unsafe in clear weather, because Glimmer is careful in fog and over-confident in clear light. The fixed cut-off happens to land under 5% here, but at 57% automation and with no way to know that in advance.

**Hypothesis 2 is mixed, as in simulation.** Fusion beats the open-source OCR alone by a wide margin (86% vs 48% charged automatically at the same promise). It is barely better than Glimmer alone (86% vs 85%). On these photos the second reader adds little, because the two readers fail on the same photos: on clear photos both are wrong on 9%, three times what independent errors would give (3%). Independent readers help only as far as their errors are independent, and that should be measured, not assumed.

**One fix made during this evaluation.** The first run found a gap: a swapped tag whose plate differed from the real one by one character looked like a small misread and was charged. The evidence check now adds a signal when both readers agree exactly on a plate that is not the tag's. The fix was chosen by reasoning about the case, not tuned on test numbers, and the weights of the learned score are fit only on the fit split. All tables in this paper were re-run after the change.

**Review budget on real photos.** Stricter promises cost automation, most of all in the groups with the least clean data:

| Promise | Wrong charges | Charged automatically | Held or reviewed | Auto: clear | Auto: foggy | Auto: Indian |
|---|---|---|---|---|---|---|
| 1% | 0.53% | 30.2% | 69.8% | 21% | 14% | 41% |
| 2% | 1.28% | 63.3% | 36.7% | 82% | 59% | 58% |
| 3% | 2.31% | 78.2% | 21.8% | 86% | 76% | 76% |
| 5% | 4.40% | 85.7% | 14.3% | 89% | 84% | 85% |
| 10% | 9.57% | 93.8% | 6.2% | 95% | 91% | 95% |

**Red team (hypothesis 4 holds).** The controller is calibrated on normal traffic, then attackers (cloned plates and swapped tags) take a share `ε` of test traffic. Wrong charges stay under the bound `α + ε` at every level, and TULA uses well under half of the extra room an attacker is allowed:

| Attacker share | Bound | TULA wrong charges | TULA charged automatically | Today's biller wrong |
|---|---|---|---|---|
| 0% | 5% | 4.79% | 86.4% | 17.03% |
| 10% | 15% | 8.10% | 81.7% | 25.18% |
| 30% | 35% | 14.63% | 71.7% | 41.98% |
| 10%, look-alike clones only | 15% | 8.24% | 82.1% | 24.94% |

Look-alike clones (a copied plate on a car of the same type, make and colour) leave no trace in one photo, so TULA cannot catch them; they still stay inside the bound, because the bound does not depend on catching them. Catching them needs evidence across plazas (a car seen in two places at once), which is future work.

**What these results do not show.** The photos and reads are real; the tags, registry and scenario mix are not. The Indian set's plates come from one public dataset with unknown collection conditions. Reader A is an open-source plate reader used as a stand-in; it is not the system any Indian toll operator uses. Hypotheses 3 (isolated vs shared reader inputs) and 5 (day vs night shift) are not tested on real photos yet.

## 8. Limits and ethics

- **The guarantee is conditional.** It holds when calibration traffic looks like real traffic. Sections 3.5 and 3.7 and hypothesis 5 are there to show how it fails.
- **Simulated parts are simulated.** The tag, registry and billing layers, the simulated readers' error rates and the dispute probabilities are our assumptions. Results on them measure the method, not an operator's real error rates.
- **Rare groups cost review time.** No certificate, no automatic charge means more human work where data is thin. That is a deliberate trade.
- **A human stays in the loop.** TULA reduces wrong charges and never removes the reviewer.
- **Privacy.** Public datasets only. Nothing in the repository identifies a vehicle owner, and raw datasets are not redistributed.
- **Reuse beyond tolling.** The same layer applies to any automatic penalty (e-challans, fraud flags) in any country. Those are future work, and the tolling results should not be assumed to carry over.

## References

- Angelopoulos, Bates, Fisch, Lei, Schuster. *Conformal Risk Control.* arXiv:2208.02814.
- *Automatically Adaptive Conformal Risk Control.* arXiv:2406.17819.
- Gendler, Weng, Daniel, Romano. *Adversarially Robust Conformal Prediction.* ICLR 2022.
- *Efficient Robust Conformal Prediction via Lipschitz-Bounded Networks* (Lip-RCP). ICML 2025, arXiv:2506.05434.
- *Cost-Sensitive Learning to Defer to Multiple Experts with Workload Constraints* (DeCCaF). arXiv:2403.06906.
- *Ctrl-Z: Controlling AI Agents via Resampling.* arXiv:2504.10374.
- Lakkaraju, Kleinberg, Leskovec, Ludwig, Mullainathan. *The Selective Labels Problem.* KDD 2017.
- *LP-LLM.* arXiv:2601.09116 · *BLPR.* arXiv:2604.09927.
- *Benchmarking Probabilistic Deep Learning Methods for License Plate Recognition.* arXiv:2302.01427.
- Attacks on plate readers: *GRAPHITE.* arXiv:2002.07088 · *Street-Legal Physical-World Adversarial Rim for License Plates.* arXiv:2604.02457.
- *Deep Learning Based Vehicle Make-Model Classification.* arXiv:1809.00953.
- *Indian Licence Plate Dataset in the wild.* arXiv:2111.06054 (dataset not public).
- Liu et al. *Lost in the Middle.* arXiv:2307.03172.
- Gibbs, Han, Tibshirani, Zrnic. *Reliable AI-Assisted Decisions via Selective Auditing.* arXiv, October 2026.
- *Cost-Sensitive Conformal Prediction and Human-in-the-Loop Abstention for Imbalanced High-Stakes Decision Support.* arXiv:2607.27143.
- *Dual-Threshold Conformal Deferral for Trustworthy Security Alert Triage.* Electronics 15(18):4084, 2026.
- Meta. *SAM 3.1* (facebook/sam3.1; MLX conversion mlx-community/sam3.1-bf16) and *Muse Glimmer 30B* (meta-models/Muse-Glimmer-30B-GGUF, Apache 2.0), 2026.
- Toll misread cases: WOWT (15 Oct 2026, North Texas Tollway Authority); KKTV (2 Sep 2026, E-470 Colorado).
- Problem data: Indian FASTag refund figures (2024), New York State Comptroller Thruway audit (2025), RTE report on M50 plate misreads (2023), NHAI MLFF launch on NH-48 (2026).
