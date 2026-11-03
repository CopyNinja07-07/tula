"""Draw the animated SVGs used by the README and the website.

Everything is plain SVG with SMIL and CSS animation: no GIFs, no JavaScript,
so GitHub renders it inline. Numbers are read from experiments/results, so the
pictures can never drift from the measured results.

Run: PYTHONPATH=src .venv/bin/python tools/make_art.py
Writes docs/assets/*.svg
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"
OUT = ROOT / "docs" / "assets"

# Palette: highway-sign green, brass of a market scale, verdict colours.
FONTS = ROOT / "docs" / "assets" / "fonts"


def _font(name: str, file: str) -> str:
    """Embed a font as base64 so the SVG renders the same everywhere, GitHub included."""
    import base64
    data = base64.b64encode((FONTS / file).read_bytes()).decode()
    return f'@font-face{{font-family:"{name}";src:url(data:font/woff2;base64,{data}) format("woff2");font-weight:100 900}}'


# Palette: night road, lit by an emerald-to-lime gradient; amber and rose for hold and review.
STYLE = ("<style>" + _font("TulaDisplay", "bricolage-grotesque.woff2") + _font("TulaMono", "geist-mono.woff2") + """
  :root{--bg:#06100c;--ink:#ecf6f0;--muted:#93a99d;--line:#1d3329;--brass:#bef264;
        --charge:#34d399;--hold:#fbbf24;--review:#fb7185;--sign:#10b981;--panel:#0f1d17;--plate:#ecece4}
  @media (prefers-color-scheme: light){:root{--bg:#f4f8f5;--ink:#0a1711;--muted:#4b5f54;--line:#d5e3da;--brass:#65a30d;
        --charge:#059669;--hold:#b45309;--review:#be123c;--sign:#047857;--panel:#ffffff;--plate:#fbfbf5}}
  text{font-family:TulaMono,ui-monospace,"SF Mono",Menlo,monospace;fill:var(--ink)}
  .sans{font-family:TulaDisplay,system-ui,-apple-system,"Segoe UI",sans-serif}
  .muted{fill:var(--muted)} .bg{fill:var(--bg)} .panel{fill:var(--panel);stroke:var(--line)}
  .ink{stroke:var(--ink)} .brass{fill:url(#tg)} .sbrass{stroke:url(#tg)}
  .charge{fill:var(--charge)} .hold{fill:var(--hold)} .review{fill:var(--review)} .sign{fill:url(#tg)}
</style>""")
GRAD = ('<defs><linearGradient id="tg" x1="0" y1="0" x2="1" y2="0.3">'
        '<stop offset="0" stop-color="#10b981"/><stop offset="0.5" stop-color="#6ee7b7"/><stop offset="1" stop-color="#bef264"/>'
        '</linearGradient><radialGradient id="glow" cx="0.5" cy="0" r="0.9">'
        '<stop offset="0" stop-color="#10b981" stop-opacity="0.22"/><stop offset="1" stop-color="#10b981" stop-opacity="0"/>'
        '</radialGradient></defs>')


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{STYLE}{GRAD}'
            f'<rect class="bg" width="{w}" height="{h}" rx="14"/><rect width="{w}" height="{h}" rx="14" fill="url(#glow)"/>{body}</svg>')


def kt(times, total):
    return ";".join(f"{t / total:.4f}" for t in times)


# ------------------------------------------------------------------ 1. the scale

def scale_svg() -> str:
    """Tula = balance scale. Evidence drops into the pans and the verdict follows."""
    T = 15.0
    cx, cy, arm, chain = 450, 92, 190, 120
    # (time, beam angle in degrees); negative tips the left pan down.
    beat = [(0, 0), (1.4, 0), (2.2, -9), (4.2, -9), (4.8, 0), (6.4, 0), (7.2, 9), (9.2, 9),
            (9.8, 0), (11.4, 0), (11.8, 2.5), (12.2, -2.5), (12.6, 1.5), (13.0, -1), (13.4, 0), (15, 0)]
    times = [t for t, _ in beat]
    keys = kt(times, T)
    ang = ";".join(f"{a} {cx} {cy}" for _, a in beat)
    # Pans hang vertically: they follow the beam ends, they do not rotate.
    left = ";".join(f"{-arm * (1 - math.cos(math.radians(a))):.1f} {-arm * math.sin(math.radians(a)):.1f}" for _, a in beat)
    right = ";".join(f"{arm * (1 - math.cos(math.radians(a))):.1f} {arm * math.sin(math.radians(a)):.1f}" for _, a in beat)

    def pan(x, offsets):
        return (f'<g><animateTransform attributeName="transform" type="translate" dur="{T}s" repeatCount="indefinite" '
                f'keyTimes="{keys}" values="{offsets}" calcMode="spline" '
                f'keySplines="{";".join(["0.45 0 0.25 1"] * (len(beat) - 1))}"/>'
                f'<line x1="{x}" y1="{cy}" x2="{x - 62}" y2="{cy + chain}" class="sbrass" stroke-width="1.5"/>'
                f'<line x1="{x}" y1="{cy}" x2="{x + 62}" y2="{cy + chain}" class="sbrass" stroke-width="1.5"/>'
                f'<path d="M{x - 78} {cy + chain} Q{x} {cy + chain + 46} {x + 78} {cy + chain} Z" class="brass" opacity="0.92"/>'
                f'{{CHIPS}}</g>')

    def chip(x, y, text, cls, t_in, t_out):
        # drop in from above, stay, fade out
        a, b, c, d = t_in / T, (t_in + 0.6) / T, t_out / T, (t_out + 0.4) / T
        return (f'<g opacity="0"><animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
                f'keyTimes="0;{a:.4f};{b:.4f};{c:.4f};{d:.4f};1" values="0;0;1;1;0;0"/>'
                f'<animateTransform attributeName="transform" type="translate" dur="{T}s" repeatCount="indefinite" '
                f'keyTimes="0;{a:.4f};{b:.4f};1" values="0 -70;0 -70;0 0;0 0"/>'
                f'<rect x="{x - 74}" y="{y}" width="148" height="24" rx="5" class="{cls}"/>'
                f'<text x="{x}" y="{y + 16.5}" text-anchor="middle" font-size="12" style="fill:#fff">{text}</text></g>')

    lx, rx = cx - arm, cx + arm
    py = cy + chain - 30
    left_chips = (chip(lx, py - 28, "A reads MH12AB1234", "charge", 0.8, 4.3)
                  + chip(lx, py, "B reads MH12AB1234", "charge", 1.1, 4.3))
    right_chips = (chip(rx, py - 28, "FASTag ≠ plate seen", "review", 5.8, 9.3)
                   + chip(rx, py, "colour ≠ registry", "review", 6.1, 9.3))
    hold_chips = (chip(lx, py, "A: could not read", "hold", 10.8, 14.2)
                  + chip(rx, py, "B: fog, unsure", "hold", 10.8, 14.2))

    def verdict(text, cls, t_in, t_out):
        a, b, c, d = t_in / T, (t_in + 0.3) / T, t_out / T, (t_out + 0.3) / T
        return (f'<g opacity="0"><animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
                f'keyTimes="0;{a:.4f};{b:.4f};{c:.4f};{d:.4f};1" values="0;0;1;1;0;0"/>'
                f'<rect x="{cx - 92}" y="300" width="184" height="40" rx="6" class="{cls}"/>'
                f'<text x="{cx}" y="327" text-anchor="middle" font-size="20" font-weight="700" '
                f'style="fill:#fff;letter-spacing:4px" class="sans">{text}</text></g>')

    beam = (f'<g><animateTransform attributeName="transform" type="rotate" dur="{T}s" repeatCount="indefinite" '
            f'keyTimes="{keys}" values="{ang}" calcMode="spline" '
            f'keySplines="{";".join(["0.45 0 0.25 1"] * (len(beat) - 1))}"/>'
            f'<rect x="{cx - arm - 6}" y="{cy - 5}" width="{2 * arm + 12}" height="10" rx="5" class="brass"/>'
            f'<polygon points="{cx - 10},{cy - 26} {cx + 10},{cy - 26} {cx},{cy - 6}" class="brass"/></g>')
    body = (
        f'<text x="40" y="52" font-size="30" font-weight="800" class="sans" style="letter-spacing:6px">TULA</text>'
        f'<text x="40" y="76" font-size="13" class="muted sans">तुला · the balance scale</text>'
        f'<text x="860" y="52" text-anchor="end" font-size="13" class="muted">weigh the evidence</text>'
        f'<text x="860" y="72" text-anchor="end" font-size="13" class="muted">before anyone is fined</text>'
        f'<rect x="{cx - 4}" y="{cy}" width="8" height="190" class="brass"/>'
        f'<path d="M{cx - 70} 292 Q{cx} 270 {cx + 70} 292 Z" class="brass"/>'
        f'<text x="{lx}" y="{cy + chain + 72}" text-anchor="middle" font-size="12" class="muted">evidence it is right</text>'
        f'<text x="{rx}" y="{cy + chain + 72}" text-anchor="middle" font-size="12" class="muted">evidence of doubt</text>'
        + pan(lx, left).replace("{CHIPS}", left_chips + hold_chips[: hold_chips.index("</g>") + 4])
        + pan(rx, right).replace("{CHIPS}", right_chips + hold_chips[hold_chips.index("</g>") + 4:])
        + beam
        + f'<circle cx="{cx}" cy="{cy}" r="7" class="brass"/>'
        + verdict("CHARGE", "charge", 2.4, 4.4) + verdict("REVIEW", "review", 7.4, 9.4) + verdict("HOLD", "hold", 12.0, 14.4)
    )
    return svg(900, 360, body, "TULA weighs evidence: agreeing reads tip the scale to charge, contradictions to review, fog to hold")


# ------------------------------------------------------------------ 2. the pipeline

def pipeline_svg() -> str:
    T = 9.0
    road = ('<line x1="20" y1="250" x2="300" y2="250" class="ink" stroke-width="2"/>'
            '<line x1="20" y1="270" x2="300" y2="270" class="ink" stroke-width="1" stroke-dasharray="14 10" opacity="0.4"/>'
            # gantry
            '<rect x="180" y="70" width="8" height="180" class="sign"/><rect x="150" y="66" width="110" height="10" rx="2" class="sign"/>'
            '<rect x="226" y="76" width="26" height="16" rx="3" class="sign"/><circle cx="239" cy="96" r="4" class="sign"/>')
    car = (f'<defs><clipPath id="roadclip"><rect x="10" y="0" width="300" height="312"/></clipPath></defs>'
           f'<g clip-path="url(#roadclip)"><g><animateTransform attributeName="transform" type="translate" dur="{T}s" repeatCount="indefinite" '
           f'keyTimes="0;0.15;0.3;0.42;1" values="-160 0;120 0;120 0;400 0;400 0"/>'
           '<rect x="0" y="200" width="110" height="34" rx="10" class="panel" stroke-width="2"/>'
           '<path d="M18 200 L34 176 L82 176 L98 200 Z" class="panel" stroke-width="2"/>'
           '<circle cx="26" cy="236" r="11" class="ink" style="fill:var(--ink)"/><circle cx="86" cy="236" r="11" style="fill:var(--ink)"/>'
           '<rect x="96" y="210" width="20" height="12" rx="2" style="fill:var(--plate);stroke:var(--ink)"/></g></g>')
    flash = (f'<polygon points="239,100 300,240 330,240" style="fill:var(--brass)" opacity="0">'
             f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" keyTimes="0;0.2;0.22;0.27;1" values="0;0;0.45;0;0"/></polygon>')
    # SAM box snapping onto the plate while the car waits
    sam = (f'<rect x="230" y="204" width="32" height="24" rx="2" fill="none" stroke="#28dc78" stroke-width="2.5" opacity="0">'
           f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" keyTimes="0;0.21;0.23;0.3;0.31;1" values="0;0;1;1;0;0"/></rect>')

    nodes = [  # x, y, w, label, sub, appear time
        (380, 40, 170, "SAM 3.1", "finds plate + vehicle", 2.0),
        (600, 10, 270, "Reader A · open plate OCR", "sees the plate crop only", 2.6),
        (600, 92, 270, "Reader B · Muse Glimmer 30B", "whole photo: plate, make, colour", 2.6),
        (380, 178, 170, "Evidence check", "vs FASTag + registry", 3.6),
        (600, 178, 270, "Risk controller", "conformal cut-off τ per group", 4.4),
    ]

    def node(x, y, w, label, sub, t):
        a = t / T
        return (f'<g opacity="0.25"><animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
                f'keyTimes="0;{a:.3f};{a + 0.03:.3f};0.95;1" values="0.25;0.25;1;1;0.25"/>'
                f'<rect x="{x}" y="{y}" width="{w}" height="62" rx="8" class="panel" stroke-width="1.5"/>'
                f'<text x="{x + 14}" y="{y + 26}" font-size="14" font-weight="700" class="sans">{label}</text>'
                f'<text x="{x + 14}" y="{y + 46}" font-size="11.5" class="muted">{sub}</text></g>')

    def packet(path, t, colour="var(--brass)"):
        a = t / T
        return (f'<circle r="5" style="fill:{colour}" opacity="0"><animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
                f'keyTimes="0;{a:.3f};{a + 0.005:.3f};{a + 0.07:.3f};{a + 0.075:.3f};1" values="0;0;1;1;0;0"/>'
                f'<animateMotion dur="{T}s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;{a:.3f};{a + 0.07:.3f};1" '
                f'calcMode="linear" path="{path}"/></circle>')

    wires = [("M300 150 C340 150 340 71 380 71", 1.7), ("M550 71 C575 71 575 41 600 41", 2.3),
             ("M550 71 C575 71 575 123 600 123", 2.3), ("M600 41 C572 41 578 196 550 196", 3.0),
             ("M600 123 C576 123 576 204 550 204", 3.0), ("M550 222 L600 222", 4.0)]
    wire_draw = "".join(f'<path d="{p}" fill="none" class="ink" stroke-width="1.2" stroke-dasharray="4 5" opacity="0.35"/>' for p, _ in wires)
    packets = "".join(packet(p, t) for p, t in wires)

    def decision(text, cls, t_in, t_out, y):
        a, b, c, d = t_in / T, (t_in + 0.2) / T, t_out / T, (t_out + 0.2) / T
        return (f'<g opacity="0"><animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
                f'keyTimes="0;{a:.3f};{b:.3f};{c:.3f};{d:.3f};1" values="0;0;1;1;0;0"/>'
                f'<rect x="600" y="{y}" width="270" height="44" rx="8" class="{cls}"/>'
                f'<text x="735" y="{y + 28}" text-anchor="middle" font-size="16" font-weight="800" class="sans" '
                f'style="fill:#fff;letter-spacing:3px">{text}</text></g>')

    body = (road + flash + car + sam + wire_draw + "".join(node(*n) for n in nodes) + packets
            + decision("CHARGE · HOLD · REVIEW", "sign", 4.8, 8.6, 256)
            + '<text x="20" y="300" font-size="11.5" class="muted">frame → boxes → two blind readers → doubt score → decision + reason</text>')
    return svg(900, 312, body, "TULA pipeline: camera frame, SAM 3.1, two independent readers, evidence check, risk controller, decision")


# ------------------------------------------------------------------ 3. verdict per group

def verdict_svg() -> str:
    r = json.loads((RES / "real_bench_alpha0.05.json").read_text())
    t = r["table"]
    rows = [("Today's biller", "Today's biller (trust tag, else plate)", "var(--muted)"),
            ("One threshold (Glimmer ≥ 0.9)", "One threshold: Glimmer >= 0.9", "var(--hold)"),
            ("TULA", "TULA (both readers + controller)", "url(#tg)")]
    groups = [("clear", "Clear"), ("foggy", "Fog"), ("indian", "Indian set")]
    alpha = r["alpha"]
    x0, scale_w, top = 250, 540, 78
    mx = 0.22
    px = lambda v: x0 + v / mx * scale_w
    out = [f'<text x="30" y="36" font-size="16" font-weight="800" class="sans">Wrong charges per group · promise ≤ {alpha:.0%}</text>',
           f'<text x="30" y="56" font-size="11.5" class="muted">1,050 real photos · mean of {r["splits"]} random splits</text>']
    for k in range(0, 21, 5):  # gridlines
        x = px(k / 100)
        out.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{top + 3 * 110 - 20}" class="ink" stroke-width="0.6" opacity="0.15"/>'
                   f'<text x="{x}" y="{top + 3 * 110 - 4}" text-anchor="middle" font-size="11" class="muted">{k}%</text>')
    delay = 0.0
    for gi, (g, gname) in enumerate(groups):
        y = top + gi * 110
        out.append(f'<text x="30" y="{y - 6}" font-size="13" font-weight="700" class="sans">{gname}</text>')
        for ri, (label, key, colour) in enumerate(rows):
            v = t[key]["group_wrong"][g]
            yy = y + ri * 28
            w = px(v) - x0
            over = v > alpha
            out.append(
                f'<rect x="{x0}" y="{yy}" width="0" height="20" rx="3" style="fill:{colour}">'
                f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{delay:.2f}s" dur="0.9s" fill="freeze" '
                f'calcMode="spline" keyTimes="0;1" keySplines="0.2 0.8 0.2 1"/></rect>'
                f'<text x="{x0 - 8}" y="{yy + 14.5}" text-anchor="end" font-size="11" class="muted">{label}</text>'
                f'<text x="{px(v) + 8:.1f}" y="{yy + 14.5}" font-size="12" font-weight="700" opacity="0" '
                f'style="fill:{"var(--review)" if over else "var(--ink)"}">{v:.1%}{" · over" if over else ""}'
                f'<animate attributeName="opacity" from="0" to="1" begin="{delay + 0.8:.2f}s" dur="0.3s" fill="freeze"/></text>')
            delay += 0.18
    ax = px(alpha)
    out.append(f'<line x1="{ax}" y1="{top - 14}" x2="{ax}" y2="{top + 3 * 110 - 22}" style="stroke:var(--review)" stroke-width="2" stroke-dasharray="6 4">'
               f'<animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1.2s" repeatCount="indefinite"/></line>'
               f'<text x="{ax + 6}" y="{top - 16}" font-size="11.5" style="fill:var(--review)">promise {alpha:.0%}</text>')
    return svg(900, top + 3 * 110 + 14, "".join(out), "Wrong charges per group: today's biller and a single threshold break the 5% promise, TULA stays under it")


# ------------------------------------------------------------------ 4. red team

def redteam_svg() -> str:
    r = json.loads((RES / "real_bench_alpha0.05.json").read_text())
    pts = r["attacks"]
    W, H, x0, y0, pw, ph = 900, 360, 80, 300, 760, 240
    X = lambda e: x0 + e / 0.30 * pw
    Y = lambda v: y0 - v / 0.45 * ph

    def line(key, style, dur, begin):
        d = "M" + " L".join(f"{X(p['eps']):.1f} {Y(p[key]):.1f}" for p in pts)
        length = 1400
        return (f'<path d="{d}" fill="none" style="{style}" stroke-width="3" stroke-linejoin="round" '
                f'stroke-dasharray="{length}" stroke-dashoffset="{length}">'
                f'<animate attributeName="stroke-dashoffset" from="{length}" to="0" begin="{begin}s" dur="{dur}s" fill="freeze"/></path>'
                + "".join(f'<circle cx="{X(p["eps"]):.1f}" cy="{Y(p[key]):.1f}" r="4" style="{style.replace("stroke", "fill")}" opacity="0">'
                          f'<animate attributeName="opacity" to="1" begin="{begin + dur:.1f}s" dur="0.3s" fill="freeze"/></circle>' for p in pts))

    out = ['<text x="30" y="36" font-size="16" font-weight="800" class="sans">Red team: attackers take a share of traffic after calibration</text>',
           '<text x="30" y="56" font-size="11.5" class="muted">cloned plates + swapped FASTags · the bound is promise + attacker share</text>']
    for v in range(0, 46, 15):
        out.append(f'<line x1="{x0}" y1="{Y(v / 100):.1f}" x2="{x0 + pw}" y2="{Y(v / 100):.1f}" class="ink" stroke-width="0.6" opacity="0.15"/>'
                   f'<text x="{x0 - 10}" y="{Y(v / 100) + 4:.1f}" text-anchor="end" font-size="11" class="muted">{v}%</text>')
    for e in (0, 0.05, 0.1, 0.2, 0.3):
        out.append(f'<text x="{X(e):.1f}" y="{y0 + 20}" text-anchor="middle" font-size="11" class="muted">{e:.0%}</text>')
    out.append(f'<text x="{x0 + pw / 2}" y="{y0 + 42}" text-anchor="middle" font-size="11.5" class="muted">attacker share of traffic</text>')
    # the allowed region under the bound
    poly = " ".join(f"{X(p['eps']):.1f},{Y(p['bound']):.1f}" for p in pts) + f" {X(0.3):.1f},{y0} {X(0):.1f},{y0}"
    out.append(f'<polygon points="{poly}" style="fill:var(--brass)" opacity="0.08"/>')
    out.append(line("bound", "stroke:var(--brass)", 1.2, 0.2))
    out.append(line("naive_wrong", "stroke:var(--muted)", 1.4, 0.8))
    out.append(line("tula_wrong", "stroke:var(--charge)", 1.4, 1.6))
    last = pts[-1]
    out.append(f'<text x="{X(0.3) - 6:.1f}" y="{Y(last["naive_wrong"]) - 10:.1f}" text-anchor="end" font-size="12" class="muted">today\'s biller {last["naive_wrong"]:.0%}</text>'
               f'<text x="{X(0.3) - 6:.1f}" y="{Y(last["bound"]) - 10:.1f}" text-anchor="end" font-size="12" style="fill:var(--brass)">bound {last["bound"]:.0%}</text>'
               f'<text x="{X(0.3) - 6:.1f}" y="{Y(last["tula_wrong"]) + 22:.1f}" text-anchor="end" font-size="12" font-weight="700" style="fill:var(--charge)">TULA {last["tula_wrong"]:.1%}</text>')
    return svg(W, H + 20, "".join(out), "Red team: TULA's wrong charges stay under the bound as attackers grow; today's biller does not")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("scale", scale_svg), ("pipeline", pipeline_svg), ("verdict", verdict_svg), ("redteam", redteam_svg)):
        (OUT / f"{name}.svg").write_text(fn())
        print("wrote", OUT / f"{name}.svg")


if __name__ == "__main__":
    main()
