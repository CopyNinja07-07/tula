"""Checks for the real-photo benchmark plumbing and the evidence note (no model needed)."""
import random

from tula.note import evidence_note
from tula.real_bench import Registry, norm_colour, norm_make, passage


def photo(truth="MH12AB1234", a=None, b=None):
    reads = {"plate_text": truth, "plate_confidence": 0.95}
    seen = {"plate_text": truth, "plate_confidence": 0.95, "vehicle_type": "car", "make": "Hyundai", "colour": "white"}
    p = {"set": "clear", "file": "clear/1.jpg", "scene": "m:1", "truth": truth,
         "a": a or reads, "b": b or seen}
    p["reg"] = p["b"]
    return p


def run(scenario, **kw):
    rng = random.Random(0)
    return passage(photo(**kw), Registry(rng), {}, rng, {scenario: 1.0})


def test_clean_correct_reads_are_not_wrong():
    c = run("clean")
    assert c["fused"][1] is False and c["naive"] is False


def test_swapped_tag_bills_someone_else_naively():
    c = run("tag_swap")
    assert c["naive"] is True and c["fused_signals"]["tag_mismatch"] > 0
    assert c["fused_signals"]["readers_vs_tag"] == 1.0  # one-digit-off tag still flagged


def test_clone_is_flagged_by_vehicle_checks():
    c = run("cloned_plate")
    sig = c["fused_signals"]
    assert c["fused"][1] is True  # charging would bill the victim
    assert sig["type_mismatch"] or sig["make_mismatch"] or sig["colour_mismatch"]


def test_lookalike_clone_leaves_no_vehicle_signal():
    c = run("lookalike_clone")
    sig = c["fused_signals"]
    assert c["fused"][1] is True
    assert not (sig["type_mismatch"] or sig["make_mismatch"] or sig["colour_mismatch"])


def test_misread_plate_with_no_tag_is_a_wrong_charge():
    wrong = {"plate_text": "MH12AB1284", "plate_confidence": 0.97}
    c = run("tag_missing", a=wrong, b={**wrong, "vehicle_type": "car", "make": "Hyundai", "colour": "white"})
    assert c["fused"][1] is True and c["naive"] is True


def test_normalisers():
    assert norm_colour("Pearl White") == "white" and norm_colour("dark gray") == "grey"
    assert norm_make("Maruti Suzuki Swift Dzire") == "Maruti Suzuki"


def test_note_states_uncertified_group():
    note = evidence_note("hold", {"no_tag": 1.0}, "AB", None, None, "foggy", certified=False)
    assert note.startswith("Held") and "foggy" in note and "No FASTag" in note
