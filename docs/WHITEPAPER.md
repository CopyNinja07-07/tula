# TULA: A Risk-Controlled Safety Layer for Automatic Billing

**Toll Uncertainty and Liability Assessment**
Suryansh Pratap Singh · Design paper, October 2026

> **Status.** This is a design paper. Nothing described here has been built or run yet. Every experiment in Section 6 is planned, and every claim about performance is a hypothesis stated so that it can fail. Where a result will go, the paper says so.

---

## Abstract

Barrier-free tolling bills a vehicle with no person checking the bill. A camera reads the plate, a reader picks up the FASTag, and a fee follows. When the plate is misread, or the tag belongs to another car, a real owner gets a penalty. Today's systems guard against this with one confidence threshold on the plate read. That threshold trades automation against mistakes, but it cannot say how often a wrong charge will happen, and it says nothing about night, rain, or an attacker with a cloned plate.

TULA is a safety layer that sits between the camera and the bill. It fuses independent evidence into one disagreement score, then decides to **charge**, **hold**, or **send to a human**. A conformal risk controller sets the charge cut-off so that the expected wrong-charge rate stays below a target, calibrated separately for each group of traffic (plate style, state, day or night, weather). A group too small to certify is never charged automatically. We also state how far the guarantee can fall when an attacker controls a fraction of the traffic, and we plan to measure that fall directly.

The name is Sanskrit. *Tulā* (तुला) is the balance scale. The system weighs the evidence before it punishes anyone.

---

## 1. Problem

India has started Multi-Lane Free Flow (MLFF) tolling, with the first plaza live on NH-48 in May 2026 and bids out for 104 more. A misread there becomes an e-notice, and the fee doubles after 72 hours. The same design is in use in Ireland, Norway, Chile, Australia, Canada and several US states.

The errors are small in rate and large in count:

- India refunded about 12.55 lakh faulty FASTag deductions in 2024, roughly 0.03% of transactions, and that was with toll booths still in place.
- A New York State audit found about 36,000 wrong charges at one Thruway exit in three weeks, roughly a 5% error rate.
- Dublin's M50 logged 14,280 plate misreads in about 87 million passages.

Three things are missing from current systems:

1. **No stated error rate.** A confidence threshold has no known wrong-charge rate, per plate type or per state.
2. **No attack accounting.** Printed stickers, cloned plates and swapped tags are documented. No deployed system reports how much damage they can do.
3. **No safe default for rare groups.** A model that is accurate on average can be wrong far more often on hand-painted plates, two-line plates, fog or night. The average hides the group that gets hurt.

## 2. The idea in one picture

```
 camera frame ──► SAM 3.1 crops: plate crop + vehicle crop
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
   Reader A: plate OCR          Reader B: vision-language model
   (sees plate crop only)       (sees vehicle crop + registry record,
                                 never Reader A's answer)
          │                            │
          └─────────────┬──────────────┘
                        ▼
        Evidence check against FASTag + registry
        (plate, class, make, colour)
                        ▼
              one disagreement score s
                        ▼
        Risk controller (per-group cut-off τ_g)
          ├── s ≤ τ_g and group certified ──► CHARGE
          ├── borderline ───────────────────► HOLD (next camera, next plaza)
          └── otherwise ────────────────────► HUMAN REVIEW + evidence note
```

## 3. Method

### 3.1 Readers that cannot copy each other

Two readers are only useful if their mistakes differ. If the second reader sees the first reader's answer, it tends to agree with it, and the disagreement signal disappears. TULA applies the need-to-know rule from our earlier work on agent context (ZeroBleed): each reader receives only the inputs it needs, and the evidence check is ordinary code that sees both outputs.

- **Reader A** is a small specialist OCR model. It sees the plate crop and nothing else.
- **Reader B** is a vision-language model (Muse Spark). It reads the plate again from its own crop, and it returns vehicle class, make and colour as structured output. It is shown the registry record and asked whether the image is consistent with it. It is never shown Reader A's answer.

Language models invent plausible plates. Asking Reader B to check against a fixed registry record, and logging when it cannot, keeps an invented plate from becoming evidence.

### 3.2 The disagreement score

The evidence check turns the outputs into a handful of signals: whether the two plate reads match, edit distance between them, whether the registry vehicle matches the observed class, make and colour, and whether the FASTag is the one linked to that plate. A small scoring function combines them into one number `s ∈ [0, 1]`, where higher means more disagreement. The scoring function is deliberately simple, because the safety claim comes from calibration, not from the score. A better score gives more automation. A worse score gives more holds. Neither breaks the bound.

### 3.3 The risk controller

Define the loss for one passage and a cut-off `τ`:

```
L(τ) = 1[ vehicle is charged  AND  charge is wrong ]       charged means s ≤ τ
```

`L` is bounded by 1 and never decreases as `τ` grows, because a higher cut-off charges more cars. This is the setting of conformal risk control (Angelopoulos et al., 2022). With `n` calibration passages and empirical risk `R̂_n(τ)`, choose

```
τ̂ = sup { τ :  n/(n+1) · R̂_n(τ) + 1/(n+1)  ≤  α }
```

Then, if test passages are exchangeable with the calibration passages, `E[L(τ̂)] ≤ α`. The target `α` is the wrong-charge rate we promise, for example 1 in 10,000.

### 3.4 Per-group cut-offs, and when to refuse

The bound above holds on average over all traffic. A group that is rare or hard can carry far more than `α` while the average still looks fine. TULA calibrates one cut-off `τ̂_g` for each group `g` (plate style, state, day or night, weather), so the bound holds inside each group (Section 3.3 applied to the calibration passages of `g`).

This has a hard floor. Because of the `1/(n+1)` term, a group with `n_g` calibration passages can only certify a target `α` if `n_g ≥ 1/α − 1`. For `α = 10⁻⁴` that is about **10,000 passages per group**. Wrong charges are themselves rare, so a real calibration set holds few of them.

So TULA adopts a rule we call **no certificate, no automatic charge**: a group without enough calibration data to certify `α` is never charged automatically. Its passages are held or reviewed, and the group is reported as uncertified. The system gets less automatic where it knows least, which is the safe direction. The price is more human review for rare groups, and we measure that price (Section 6).

To reach realistic error rates without waiting for real wrong charges, the benchmark injects errors (tag swaps, cloned plates, misreads) and re-weights them back to realistic frequencies during calibration.

### 3.5 What an attacker can take away

Conformal guarantees assume exchangeability. A cloned plate or a sticker attack breaks it on purpose. We do not claim the guarantee survives an attack unchanged. We state what it becomes.

**Proposition.** Let `P` be the calibration distribution and `Q` the test distribution, and let `TV(P, Q) = ε`. For any loss bounded in `[0, 1]`, `E_Q[L(τ̂)] ≤ E_P[L(τ̂)] + ε ≤ α + ε`.

*Proof sketch.* For a function `f` with values in `[0, 1]`, `|E_Q f − E_P f| ≤ TV(P, Q)`. Apply it to `f = L(τ̂)` with `τ̂` fixed after calibration. ∎

The reading is plain. If an attacker controls a fraction `ε` of the traffic, the wrong-charge rate is at most `α + ε`. This bound is loose, because an attacker's traffic is not chosen at random, but it is a number we can publish and test. The plan is to measure the real rate under each attack, plot how far below `α + ε` it stays, and report where the controller fails.

### 3.6 Explanations that serve a real decision

For every hold and review, Muse Spark writes a short note from the structured evidence, for example: "Plate reads match, but the vehicle type and colour do not match the registered vehicle." The note goes to the reviewer and, if the driver disputes, to the driver. Disputes also produce labels, but only for charged cars, which biases the labels. We treat that selective-labels problem as open and out of scope.

## 4. What is new, and what is not

To our knowledge, based on 15 targeted searches across arXiv, USPTO, IEEE DataPort and vendor material, the building blocks exist separately and the combination does not. We have not found a paper, patent or product that bounds the wrong-charge rate in automatic billing. This is a first pass and we will keep trying to break the claim.

| Piece | Closest existing work | Status in TULA |
|---|---|---|
| Confidence thresholds before manual review | USPTO 10019640, 8768753 | Replaced by a calibrated cut-off with a stated rate |
| Uncertainty in plate reading | Benchmarking probabilistic LPR (2023) | Reused as an input signal, not claimed |
| VLMs reading plates | LP-LLM, BLPR | Reused; checked against a registry record |
| Clone-plate detection | UK False Plate Classifier | Not claimed as new |
| Attacks on plate readers | GRAPHITE, SPAR | Used as the attack set |
| Conformal risk control | Angelopoulos et al., 2022 | The core tool, not claimed |
| Group-wise conformal guarantees | Group-conditional CRC; Conformal Fairness | Applied for the first time to billing, to our knowledge |
| Deferral to humans | DeCCaF; learning to defer | Used for the review path |
| Reader independence by input isolation | none found for plate reading | Our design choice, tested in Section 6 |
| No-certificate-no-charge rule for small groups | none found | Our design choice |
| Guarantee stated under attacker-controlled traffic | Robust conformal prediction (pixel noise only) | New measurement for physical attacks |
| Open benchmark pairing tag, plate, class and billing | none found | Released with the project |

The safest wording is "to our knowledge, the first", and only after we repeat the search before release.

## 5. Threat model

- **Cloned plate.** The right plate on the wrong vehicle. Reader A and Reader B can both agree, so the vehicle check against the registry carries the decision.
- **Swapped tag.** A tag moved to a different car. The class, make and colour check should catch it.
- **Sticker or edited image.** Printed patterns that mislead plate readers. Plan: a transfer attack on Reader A first, with an adaptive attack on the full pipeline if time allows.
- **Out of scope for now.** Collusion between reviewers, tampering with the registry itself, and attacks on the camera hardware.

## 6. Planned evaluation

**Benchmark.** A semi-synthetic set: real plate images with simulated tag, registry and billing layers on top.

| Layer | Source |
|---|---|
| Real Indian plates | Indian Licence Plate Dataset in the wild (16,192 images, 21,683 plates) |
| Hard Indian plates | IEEE DataPort Indian LPR set (hand-painted fonts, two-line plates, worn paint) |
| Bad weather | Foggy-Hazy License Plates (1,001 images) |
| Night and rain | Augmented copies, labelled as synthetic |
| FASTag, registry, billing | Simulated, with realistic tag misreads, swaps, clones and wrong classes |

Only public datasets are used. No real person's plate from our own footage.

**Baselines.** One confidence threshold (today's practice), OCR alone, Muse Spark alone, and the fused system without the risk controller.

**Metrics.** Wrong-charge rate (the promised number), automation rate, human review load, the gap between the best and worst group, and how much of the guarantee survives each attack.

**Hypotheses, each of which can fail.**

1. On the test split, the controller keeps the wrong-charge rate at or below `α` in every certified group, while the single-threshold baseline exceeds `α` in at least one group.
2. The fused system gives a higher automation rate than OCR alone at the same wrong-charge rate.
3. Isolating the readers' inputs (Section 3.1) lowers the correlation of their errors compared with showing Reader B the OCR answer.
4. Under a cloned-plate attack on a fraction `ε` of traffic, the measured wrong-charge rate stays under `α + ε`, and we report where it does not.
5. Shifting the calibration data away from test conditions (for example, calibrating on day and testing on night) breaks the guarantee, and the group-wise controller recovers it only when the group is calibrated.

A failed hypothesis is a result, and the paper will report it that way.

## 7. Limits and ethics

- **The guarantee is conditional.** It holds when calibration traffic looks like real traffic. Section 3.5 and hypothesis 5 are there to show how it fails.
- **Rare groups cost review time.** No certificate, no automatic charge means more human work where data is thin. That is a deliberate trade.
- **Simulated layers are simulated.** The FASTag and registry layers are our model of reality, so results measure the method, not an operator's real error rates.
- **A human stays in the loop.** TULA reduces wrong charges and never removes the reviewer.
- **Privacy.** Public datasets only, and nothing in the repo identifies a real vehicle owner.
- **Reuse beyond tolling.** The same layer applies to any automatic penalty (e-challans, fraud flags). Those are future work, and the tolling results should not be assumed to carry over.

## References

- Angelopoulos, Bates, Fisch, Lei, Schuster. *Conformal Risk Control.* arXiv:2208.02814.
- *Group-conditional conformal risk control.* arXiv:2406.17819.
- Gendler et al. *Adversarially Robust Conformal Prediction.* ICLR 2022.
- *Lip-RCP.* ICML 2025.
- *DeCCaF: Deferral under Cost and Capacity Constraints Framework.* arXiv:2403.06906.
- *LP-LLM.* arXiv:2601.09116 · *BLPR.* arXiv:2604.09927.
- *Benchmarking probabilistic license plate recognition.* arXiv:2302.01427.
- Attacks on plate readers: *GRAPHITE.* arXiv:2002.07088 · *SPAR.* arXiv:2604.02457.
- *Indian Licence Plate Dataset in the wild.* arXiv:2111.06054.
- Liu et al. *Lost in the Middle.* 2024.
- Problem data: Indian FASTag refund figures (2024), New York State Comptroller Thruway audit (2025), RTE report on M50 plate misreads (2023), NHAI MLFF launch on NH-48 (2026).
