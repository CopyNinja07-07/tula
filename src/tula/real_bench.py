"""TULA on real photos: real plate reads, simulated tag and registry.

Every passage is built around one real photo and the two real reads of it:
  Reader A  open-source plate OCR on the SAM 3.1 plate crop (foggy, clear) or
            on the dataset's own crop (indian)
  Reader B  Meta's Muse Glimmer 30B on the full photo (plate, type, make, colour)
The FASTag, registry and scenario (clean, missing tag, swapped tag, cloned
plate, wrong class) are simulated, because no public data links tags,
registrations and bills.

Assumptions, stated so they can be argued with:
  * A dense registry: a plate read that is not the car's own plate belongs to
    some other owner (India has about 350 million registered vehicles, so most
    near-miss plate strings exist). A misread that is billed is a wrong charge.
  * The registered make, colour and type of a car come from Muse Glimmer's read
    of the clear version of the same scene (foggy and clear sets). For the
    indian set there is no second photo, so they come from the same read and the
    vehicle checks are only informative for clones there.

Groups are the photo sets (foggy, clear, indian). Calibration uses one passage
per photo; test passages use photos never seen in calibration. The split is
repeated many times and the mean wrong-charge rate is reported, which is what
the conformal guarantee is about.

    PYTHONPATH=src python -m tula.real_bench --alpha 0.05 --splits 50
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

from tula.crc import CHARGE, HOLD, REVIEW, GroupController
from tula.evidence import LearnedScore, check
from tula.simulate import COLOURS, MAKES, TOLL_CLASSES, Vehicle

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "experiments" / "results"
MANIFEST = ROOT / "data" / "raw" / "kaggle_bundle" / "manifest.csv"
SCENARIOS = {"clean": 0.80, "tag_missing": 0.08, "tag_swap": 0.05, "cloned_plate": 0.04, "wrong_class": 0.03}
TYPE_TO_CLASS = {"car": "car_jeep_van", "suv": "car_jeep_van", "van": "car_jeep_van",
                 "three_wheeler": "car_jeep_van", "two_wheeler": "car_jeep_van",
                 "bus": "bus_truck", "truck": "bus_truck"}
BRANDS = sorted({m for ms in MAKES.values() for m in ms} | {"Renault", "Nissan", "Volkswagen", "Skoda", "Ford",
                                                          "Chevrolet", "Bajaj", "Hero", "TVS", "Royal Enfield"})


def clean(s) -> str:
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


UNKNOWN = ("unknown", "not ", "unclear", "cannot", "can't", "none", "n/a", "identifiable")


def is_unknown(v) -> bool:
    return not v or any(w in str(v).lower() for w in UNKNOWN)


def norm_colour(c) -> str | None:
    """None means the reader could not tell; that is never counted as a mismatch."""
    if is_unknown(c):
        return None
    c = str(c).lower()
    for k in ("white", "silver", "grey", "gray", "black", "red", "blue"):
        if k in c:
            return "grey" if k == "gray" else k
    return "other"


def norm_make(m) -> str | None:
    if is_unknown(m):
        return None
    m = str(m).lower()
    if "suzuki" in m or "maruti" in m:
        return "Maruti Suzuki"
    for b in BRANDS:
        if b.lower().split()[0] in m:
            return b
    return "other"


def norm_type(t) -> str:
    return t if t in TYPE_TO_CLASS else "car"


# ---------------------------------------------------------------- photos

def load_photos(glimmer_path: Path) -> list[dict]:
    """One dict per labelled photo with both real reads."""
    manifest = [r for r in csv.DictReader(open(MANIFEST)) if r["unreadable"] != "True"]
    a_sam = {r["file"]: r for r in csv.DictReader(open(RES / "reader_a_sam31_reads.csv"))}
    a_zen = {r["id"]: r for r in csv.DictReader(open(RES / "reader_a_zenitsu_reads.csv"))}
    glim = {}
    for line in open(glimmer_path):
        g = json.loads(line)
        if g.get("read"):
            glim[g["file"]] = g["read"]
    photos = []
    for r in manifest:
        if r["set"] == "indian":
            z = a_zen.get(r["id"])
            ra = {"plate_text": clean(z["read"]) or None, "plate_confidence": float(z["confidence"] or 0)} if z else None
        else:
            z = a_sam.get(r["file"])
            ra = {"plate_text": clean(z["read"]) or None, "plate_confidence": float(z["confidence"] or 0)} if z else None
        g = glim.get(r["file"])
        if ra is None or g is None:
            continue
        readable = g.get("plate_readable", True)
        rb = {"plate_text": clean(g.get("plate_text")) if readable else None,
              "plate_confidence": float(g.get("plate_confidence") or 0) if readable else 0.0,
              "vehicle_type": norm_type(g.get("vehicle_type")), "make": norm_make(g.get("make")),
              "colour": norm_colour(g.get("colour"))}
        photos.append({"set": r["set"], "file": r["file"], "scene": f"{r['set'] if r['set'] == 'indian' else 'mendeley'}:{r['id']}",
                       "truth": clean(r["truth"]), "a": ra, "b": rb})
    # registry attributes: Glimmer on the clear photo of the same scene when there is one
    clear_attr = {p["scene"]: p["b"] for p in photos if p["set"] == "clear"}
    for p in photos:
        p["reg"] = clear_attr.get(p["scene"], p["b"])
    return photos


# ---------------------------------------------------------------- registry and passages

class Registry(dict):
    """plate -> Vehicle. Unknown plates belong to some other owner (dense registry)."""

    def __init__(self, rng: random.Random):
        super().__init__()
        self.rng = rng
        self.n = 0

    def add(self, plate, vtype, make, colour) -> Vehicle:
        cls = TYPE_TO_CLASS[vtype]
        v = Vehicle(vehicle_id=f"R{self.n:06d}", plate=plate, state=plate[:2], plate_style="unknown",
                    toll_class=cls, vehicle_type=vtype, make=make, colour=colour,
                    tag_id=f"TAG{self.n:08d}", tag_class=cls)
        self.n += 1
        self[plate] = v
        return v

    def get(self, plate, default=None):
        if plate in self:
            return self[plate]
        if not plate:
            return default
        vtype = self.rng.choice(["car", "car", "suv", "van", "truck"])
        return self.add(plate, vtype, self.rng.choice(MAKES[vtype]), self.rng.choice(list(COLOURS)))


def passage(photo: dict, reg: Registry, by_tag: dict, rng: random.Random, mix: dict | None = None) -> dict:
    """Simulate one toll passage around a real photo and fuse the real reads."""
    truth = photo["truth"]
    r = photo["reg"]
    car = reg.get(truth) if truth in reg else reg.add(truth, r["vehicle_type"], r["make"], r["colour"])
    by_tag[car.tag_id] = car
    mix = mix or SCENARIOS
    scenario = rng.choices(list(mix), list(mix.values()))[0]
    tag_read, tag_class = car.tag_id, car.tag_class
    actual = car  # the car physically passing
    if scenario == "tag_missing":
        tag_read, tag_class = None, None
    elif scenario == "tag_swap":
        other = reg.get(truth[:-1] + str((int(truth[-1]) + 1) % 10) if truth[-1:].isdigit() else truth + "X")
        by_tag[other.tag_id] = other
        tag_read, tag_class = other.tag_id, other.tag_class
    elif scenario in ("cloned_plate", "lookalike_clone"):
        # The car in the photo shows a plate registered to a different vehicle (the victim).
        # A look-alike clone copies a plate from a car of the same type, make and colour,
        # so nothing in one photo can tell them apart.
        if scenario == "lookalike_clone":
            victim = Vehicle(**{**car.__dict__, "vehicle_id": car.vehicle_id + "v"})
        else:
            vtype = rng.choice([t for t in ("car", "suv", "van", "truck") if t != r["vehicle_type"]] or ["car"])
            victim = Vehicle(**{**car.__dict__, "vehicle_id": car.vehicle_id + "v", "vehicle_type": vtype,
                                "make": rng.choice([m for m in MAKES[vtype] if m != r["make"]] or MAKES[vtype]),
                                "colour": rng.choice([c for c in COLOURS if c != r["colour"]]),
                                "toll_class": TYPE_TO_CLASS[vtype], "tag_class": TYPE_TO_CLASS[vtype]})
        reg_c = Registry(rng)
        reg_c.update(reg)
        reg_c[truth] = victim
        actual = Vehicle(**{**car.__dict__, "vehicle_id": car.vehicle_id + "c", "plate": "CLONE"})
        tag_read, tag_class = None, None
        reg = reg_c
    elif scenario == "wrong_class":
        tag_class = rng.choice([c for c in TOLL_CLASSES if c != car.toll_class])

    correct_account = actual.vehicle_id
    correct_fee = TOLL_CLASSES[actual.toll_class]["fee"]
    out = {"photo": photo, "scenario": scenario, "group": photo["set"]}
    for name, use_a, use_b in (("fused", True, True), ("ocr", True, False), ("vlm", False, True)):
        ev = check(photo["a"], photo["b"], tag_read, tag_class, by_tag, reg, use_a, use_b)
        wrong = ev.target is not None and (ev.target != correct_account or ev.fee != correct_fee)
        out[name] = (ev.score, wrong, ev.target is not None)
        out[name + "_signals"] = ev.signals
    # today's biller: trust the tag, else Reader A's plate read; never asks a human
    if tag_read is not None:
        naive = by_tag[tag_read]
        fee = TOLL_CLASSES[tag_class]["fee"]
    else:
        naive = reg.get(photo["a"]["plate_text"]) if photo["a"]["plate_text"] else None
        fee = TOLL_CLASSES[naive.toll_class]["fee"] if naive else None
    out["naive"] = naive is not None and (naive.vehicle_id != correct_account or fee != correct_fee)
    out["naive_charged"] = naive is not None
    out["a_conf"] = photo["a"]["plate_confidence"]
    out["b_conf"] = photo["b"]["plate_confidence"]
    return out


# ---------------------------------------------------------------- one split

def split_scenes(photos, rng):
    scenes = sorted({p["scene"] for p in photos})
    rng.shuffle(scenes)
    n = len(scenes)
    part = {s: ("fit" if i < 0.2 * n else "cal" if i < 0.6 * n else "test") for i, s in enumerate(scenes)}
    return {k: [p for p in photos if part[p["scene"]] == k] for k in ("fit", "cal", "test")}


def run_split(photos, alpha, delta, seed, test_repeats=5) -> dict:
    rng = random.Random(seed)
    parts = split_scenes(photos, rng)
    reg, by_tag = Registry(rng), {}
    fit = [passage(p, reg, by_tag, rng) for p in parts["fit"] for _ in range(3)]
    cal = [passage(p, reg, by_tag, rng) for p in parts["cal"]]
    test = [passage(p, reg, by_tag, rng) for p in parts["test"] for _ in range(test_repeats)]

    def summary(decisions, cases, wrong_of):
        per = defaultdict(lambda: [0, 0, 0])  # n, charged, wrong
        for d, c in zip(decisions, cases):
            g = per[c["group"]]
            g[0] += 1
            if d == CHARGE:
                g[1] += 1
                g[2] += wrong_of(c)
        n = sum(g[0] for g in per.values())
        return {"wrong": sum(g[2] for g in per.values()) / n, "auto": sum(g[1] for g in per.values()) / n,
                "review": sum(d == REVIEW for d in decisions) / n,
                "groups": {k: {"wrong": g[2] / g[0], "auto": g[1] / g[0]} for k, g in per.items()}}

    res = {}
    res["Today's biller (trust tag, else plate)"] = summary(
        [CHARGE if c["naive_charged"] else REVIEW for c in test], test, lambda c: c["naive"])
    res["One threshold: Reader A >= 0.9"] = summary(
        [CHARGE if c["ocr"][2] and c["a_conf"] >= 0.9 else REVIEW for c in test], test, lambda c: c["ocr"][1])
    res["One threshold: Glimmer >= 0.9"] = summary(
        [CHARGE if c["vlm"][2] and c["b_conf"] >= 0.9 else REVIEW for c in test], test, lambda c: c["vlm"][1])
    res["Fused score, fixed cut-off 0.3"] = summary(
        [CHARGE if c["fused"][0] <= 0.3 else REVIEW for c in test], test, lambda c: c["fused"][1])

    for key in ("ocr", "vlm", "fused"):
        model = LearnedScore().fit([c[key + "_signals"] for c in fit], [c[key][1] for c in fit])
        for c in cal + test:
            c[key + "_l"] = (model.score(c[key + "_signals"], c[key][2]), c[key][1], c[key][2])
    for key, label, d in (("ocr_l", "Reader A only + controller", None),
                          ("vlm_l", "Glimmer only + controller", None),
                          ("fused_l", "TULA (both readers + controller)", None),
                          ("fused_l", f"TULA, {1 - delta:.0%} confidence mode", delta)):
        ctl = GroupController(alpha, delta=d).fit([c["group"] for c in cal], [c[key][0] for c in cal],
                                                  [c[key][1] for c in cal])
        res[label] = summary([ctl.decide(c["group"], c[key][0]) for c in test], test, lambda c, k=key: c[k][1])
    return {"sizes": {k: len(v) for k, v in parts.items()}, "results": res}


def demo_cases(photos, alpha, seed=0) -> list[dict]:
    """Test passages of one split with TULA's decision and today's biller's, for the demo page."""
    rng = random.Random(seed)
    parts = split_scenes(photos, rng)
    reg, by_tag = Registry(rng), {}
    fit = [passage(p, reg, by_tag, rng) for p in parts["fit"] for _ in range(3)]
    cal = [passage(p, reg, by_tag, rng) for p in parts["cal"]]
    test = [passage(p, reg, by_tag, rng) for p in parts["test"]]
    model = LearnedScore().fit([c["fused_signals"] for c in fit], [c["fused"][1] for c in fit])
    for c in cal + test:
        c["fused_l"] = (model.score(c["fused_signals"], c["fused"][2]), c["fused"][1], c["fused"][2])
    ctl = GroupController(alpha).fit([c["group"] for c in cal], [c["fused_l"][0] for c in cal],
                                     [c["fused_l"][1] for c in cal])
    out = []
    for c in test:
        out.append({**c, "decision": ctl.decide(c["group"], c["fused_l"][0]),
                    "certified": ctl.certified(c["group"]), "tau": ctl.taus.get(c["group"])})
    return out


def attack_curve(photos, alpha, eps_list=(0.0, 0.05, 0.1, 0.2, 0.3), splits=20,
                 kind=("cloned_plate", "tag_swap")) -> list[dict]:
    """Calibrate on normal traffic, then let attackers take a share eps of test traffic.

    The bound from Section 3.5 says the wrong-charge rate stays under alpha + eps
    (expected over calibration sets). We measure how much of that room is used.
    """
    out = []
    for eps in eps_list:
        rows = []
        for seed in range(splits):
            rng = random.Random(1000 + seed)
            parts = split_scenes(photos, rng)
            reg, by_tag = Registry(rng), {}
            fit = [passage(p, reg, by_tag, rng) for p in parts["fit"] for _ in range(3)]
            cal = [passage(p, reg, by_tag, rng) for p in parts["cal"]]
            base = {k: v * (1 - eps) for k, v in SCENARIOS.items()}
            for k in kind:
                base[k] = base.get(k, 0) + eps / len(kind)
            test = [passage(p, reg, by_tag, rng, base) for p in parts["test"] for _ in range(5)]
            model = LearnedScore().fit([c["fused_signals"] for c in fit], [c["fused"][1] for c in fit])
            for c in cal + test:
                c["s"] = model.score(c["fused_signals"], c["fused"][2])
            ctl = GroupController(alpha).fit([c["group"] for c in cal], [c["s"] for c in cal],
                                              [c["fused"][1] for c in cal])
            dec = [ctl.decide(c["group"], c["s"]) for c in test]
            n = len(test)
            rows.append({"wrong": sum(d == CHARGE and c["fused"][1] for d, c in zip(dec, test)) / n,
                         "auto": sum(d == CHARGE for d in dec) / n,
                         "naive": sum(c["naive"] for c in test) / n})
        out.append({"eps": eps, "kind": list(kind), "bound": alpha + eps,
                    "tula_wrong": st.mean(r["wrong"] for r in rows), "tula_auto": st.mean(r["auto"] for r in rows),
                    "naive_wrong": st.mean(r["naive"] for r in rows)})
    return out


def budget_table(photos, alphas=(0.01, 0.02, 0.03, 0.05, 0.075, 0.10), splits=20) -> list[dict]:
    """Stricter promise -> more passages for humans. One row per promise alpha."""
    out = []
    for alpha in alphas:
        rows = []
        for seed in range(splits):
            r = run_split(photos, alpha, 0.1, 2000 + seed, test_repeats=3)["results"]["TULA (both readers + controller)"]
            rows.append(r)
        groups = rows[0]["groups"]
        out.append({"alpha": alpha, "wrong": st.mean(r["wrong"] for r in rows),
                    "auto": st.mean(r["auto"] for r in rows),
                    "human": 1 - st.mean(r["auto"] for r in rows),
                    "group_auto": {g: st.mean(r["groups"][g]["auto"] for r in rows) for g in groups}})
    return out


def reader_independence(photos) -> dict:
    """Do the two readers make mistakes on the same photos?"""
    a = [p["a"]["plate_text"] != p["truth"] for p in photos]
    b = [p["b"]["plate_text"] != p["truth"] for p in photos]
    both = sum(x and y for x, y in zip(a, b))
    n = len(photos)
    pa, pb = sum(a) / n, sum(b) / n
    return {"photos": n, "a_wrong": round(pa, 3), "b_wrong": round(pb, 3), "both_wrong": round(both / n, 3),
            "both_wrong_if_independent": round(pa * pb, 3),
            "either_right": round(1 - both / n, 3)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--delta", type=float, default=0.1)
    ap.add_argument("--splits", type=int, default=50)
    ap.add_argument("--glimmer", default=str(RES / "glimmer_reads.jsonl"))
    args = ap.parse_args(argv)
    photos = load_photos(Path(args.glimmer))
    runs = [run_split(photos, args.alpha, args.delta, seed) for seed in range(args.splits)]
    methods = list(runs[0]["results"])
    groups = sorted({g for r in runs for g in r["results"][methods[0]]["groups"]})
    table = {}
    for m in methods:
        w = [r["results"][m]["wrong"] for r in runs]
        table[m] = {
            "wrong_mean": st.mean(w), "wrong_sd": st.pstdev(w),
            "auto_mean": st.mean(r["results"][m]["auto"] for r in runs),
            "review_mean": st.mean(r["results"][m]["review"] for r in runs),
            "group_wrong": {g: st.mean(r["results"][m]["groups"].get(g, {"wrong": 0})["wrong"] for r in runs)
                            for g in groups},
            "group_auto": {g: st.mean(r["results"][m]["groups"].get(g, {"auto": 0})["auto"] for r in runs)
                           for g in groups},
        }
    report = {"alpha": args.alpha, "delta": args.delta, "splits": args.splits, "photos": len(photos),
              "photos_by_set": {g: sum(p["set"] == g for p in photos) for g in groups},
              "split_sizes": runs[0]["sizes"], "scenarios": SCENARIOS,
              "independence": {g: reader_independence([p for p in photos if p["set"] == g]) for g in groups},
              "table": table}
    report["budget"] = budget_table(photos)
    report["attacks"] = attack_curve(photos, args.alpha)
    report["lookalike"] = attack_curve(photos, args.alpha, eps_list=(0.05, 0.1), kind=("lookalike_clone",))
    out = RES / f"real_bench_alpha{args.alpha}.json"
    out.write_text(json.dumps(report, indent=2))
    lines = [f"Real photos: {len(photos)} ({report['photos_by_set']}), alpha = {args.alpha:.0%}, "
             f"{args.splits} random splits (mean over splits)", "",
             "| Method | Wrong charges | Charged automatically | Sent to human | "
             + " | ".join(f"Wrong: {g}" for g in groups) + " |",
             "|---|---|---|---|" + "---|" * len(groups)]
    for m, t in table.items():
        lines.append(f"| {m} | {t['wrong_mean']:.2%} (±{t['wrong_sd']:.2%}) | {t['auto_mean']:.1%} | "
                     f"{t['review_mean']:.1%} | " + " | ".join(f"{t['group_wrong'][g]:.2%}" for g in groups) + " |")
    lines += ["", "Reader independence (share of photos each reader gets wrong):", ""]
    for g, d in report["independence"].items():
        lines.append(f"- {g}: A wrong {d['a_wrong']:.0%}, Glimmer wrong {d['b_wrong']:.0%}, both wrong "
                     f"{d['both_wrong']:.0%} (if independent: {d['both_wrong_if_independent']:.0%})")
    lines += ["", "Review budget: stricter promise, more work for humans (held or reviewed):", "",
              "| Promise | Wrong charges | Charged automatically | Held or reviewed | "
              + " | ".join(f"Auto: {g}" for g in groups) + " |", "|---|---|---|---|" + "---|" * len(groups)]
    for b in report["budget"]:
        lines.append(f"| {b['alpha']:.1%} | {b['wrong']:.2%} | {b['auto']:.1%} | {b['human']:.1%} | "
                     + " | ".join(f"{b['group_auto'].get(g, 0):.0%}" for g in groups) + " |")
    lines += ["", "Red team: attackers take a share of traffic after calibration (clones + swapped tags):", "",
              "| Attacker share | Bound (promise + share) | TULA wrong charges | TULA charged automatically | Today's biller wrong |",
              "|---|---|---|---|---|"]
    for a in report["attacks"] + report["lookalike"]:
        tag = " (look-alike clones)" if "lookalike_clone" in a["kind"] else ""
        lines.append(f"| {a['eps']:.0%}{tag} | {a['bound']:.0%} | {a['tula_wrong']:.2%} | {a['tula_auto']:.1%} | {a['naive_wrong']:.2%} |")
    md = "\n".join(lines)
    out.with_suffix(".md").write_text("# TULA on real photos\n\n" + md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
