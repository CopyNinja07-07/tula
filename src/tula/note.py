"""Evidence note: a short plain-English reason for every hold or review.

Built from the evidence signals by plain code, so it can only state facts the
pipeline measured (no model can add a plate or a claim that is not there).
"""
from __future__ import annotations

DECISION_TEXT = {
    "charge": "Charged automatically.",
    "hold": "Held: not charged yet. Waiting for the next camera or plaza.",
    "review": "Sent to a human reviewer. Nobody is charged until they decide.",
}


def evidence_note(decision: str, signals: dict, read_a: str | None, read_b: str | None,
                  billed_plate: str | None, group: str, certified: bool, image_issues=None) -> str:
    parts = []
    if read_a and read_b:
        parts.append("Both readers agree on the plate." if read_a == read_b
                     else f"The two readers disagree: {read_a} vs {read_b}.")
    elif read_a or read_b:
        parts.append(f"Only one reader could read the plate ({read_a or read_b}).")
    else:
        parts.append("Neither reader could read the plate.")
    if signals.get("no_tag"):
        parts.append("No FASTag was read, so billing would rely on the plate alone.")
    if signals.get("readers_vs_tag") and billed_plate:
        parts.append(f"Both readers agree on the plate, but the FASTag belongs to {billed_plate} (possible swapped tag).")
    elif signals.get("tag_mismatch", 0) > 0.2 and billed_plate:
        parts.append(f"The FASTag belongs to {billed_plate}, which does not match the plate seen.")
    mism = [k for k, name in (("type_mismatch", "vehicle type"), ("make_mismatch", "make"),
                              ("colour_mismatch", "colour")) if signals.get(k)]
    if mism:
        names = {"type_mismatch": "vehicle type", "make_mismatch": "make", "colour_mismatch": "colour"}
        parts.append("The " + ", ".join(names[m] for m in mism)
                     + " seen in the photo do not match the registered vehicle (possible cloned plate or swapped tag).")
    if signals.get("low_confidence", 0) > 0.3:
        parts.append("A reader was unsure of its read.")
    if image_issues:
        parts.append("Image problems: " + ", ".join(image_issues[:3]) + ".")
    if not certified:
        parts.append(f"The '{group}' group has too little checked data to promise a wrong-charge rate, "
                     "so TULA never charges it automatically.")
    return DECISION_TEXT[decision] + " " + " ".join(parts)
