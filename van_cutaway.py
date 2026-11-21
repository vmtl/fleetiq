"""FleetIQ interactive engineering-style van cutaway.

A normalized schematic, not vehicle-specific service documentation.
Colors describe the share of distinct NHTSA complaints mentioning a broad
system. They are NOT part failure probabilities.
"""
from __future__ import annotations

import html
import json

COLORS = {"none": "#71859e", "low": "#11edc1", "moderate": "#f7dc65",
          "elevated": "#ff9e4a", "high": "#ff496f"}
SYSTEMS = [
    "Engine / cooling", "Powertrain / transmission", "Fuel system",
    "Electrical / electronics", "Brakes", "Steering", "Suspension",
    "Wheels / tires", "Body / structure", "Safety / driver assistance",
    "Visibility / lighting", "Interior / comfort", "Other / unspecified",
]


def band(share, count):
    if count <= 0:
        return "No reports", COLORS["none"]
    if share >= 30:
        return "High share", COLORS["high"]
    if share >= 15:
        return "Elevated share", COLORS["elevated"]
    if share >= 5:
        return "Moderate share", COLORS["moderate"]
    return "Lower share", COLORS["low"]


def render_cutaway(lookup, total, vehicle, detailed=False, evidence_rows=None):
    """Return self-contained clickable technical SVG suitable for Streamlit HTML."""
    payload = {}
    for system in SYSTEMS:
        item = lookup.get(system, {})
        count = int(item.get("complaints", 0))
        share = float(item.get("share_pct", 0.0))
        label, color = band(share, count)
        payload[system] = {"count": count, "share": round(share, 1),
                           "status": label, "color": color}
    evidence_rows = evidence_rows or {}
    safe_evidence = {
        system: [
            {"model_year": str(item.get("model_year", ""))[:8],
             "component": str(item.get("component", ""))[:120],
             "description": str(item.get("description", ""))[:300]}
            for item in evidence_rows.get(system, [])[:3]
        ] for system in SYSTEMS
    }

    def part(system, body):
        color = payload[system]["color"]
        return (
            '<g class="hotspot" role="button" tabindex="0" data-system="'
            + html.escape(system, quote=True)
            + '" style="--heat:' + color + '">' + body + '</g>'
        )

    # Full-size cargo van elevation: wheelbase 758 of 1100 length, tire diameter
    # 138 of ~480 height, a realistic relationship unlike the old oversized wheels.
    shell = part("Body / structure", """
      <path class="exterior" d="M65 469 L142 469 A83 83 0 0 1 308 469
         L900 469 A83 83 0 0 1 1066 469 L1123 469
         Q1153 468 1153 438 L1148 394
         Q1144 364 1110 350 L1009 334 L959 316
         Q946 304 938 290 L835 173
         Q801 130 752 128 Q550 119 330 125
         L115 128 Q65 129 65 179Z"/>
      <path class="roof-highlight" d="M90 145 Q330 136 745 141 Q789 143 820 177"/>
      <path class="body-divider" d="M96 171 V439 M390 163 V439 M708 160 V442"/>
      <path class="body-divider" d="M401 206 H710 M404 216 V441"/>
      <path class="lower-sill" d="M90 445 H143 M307 447 H900 M1068 446 H1130"/>
      <path class="door" d="M411 233 H684 V432 H411Z"/>
      <path class="door-track" d="M393 219 H707"/>
      <path class="handle" d="M624 260 H653 M868 353 H892"/>
      <path class="window" d="M766 175 Q784 174 802 195
          L925 322 L926 334 H755 V191Z"/>
      <path class="window-line" d="M801 196 L797 333 M755 338 V441"/>
      <path class="mirror" d="M929 316 L948 310 L960 324 L949 343 L931 340Z"/>
      <path class="arch" d="M142 469 A83 83 0 0 1 308 469
          M900 469 A83 83 0 0 1 1066 469"/>
      <path class="body-detail" d="M79 393 H137 M313 396 H708 M96 192 H373"/>
    """)

    chassis = """
      <g pointer-events="none" opacity=".74">
        <path d="M319 457 H892" stroke="#82a7bf" stroke-width="6"/>
        <path d="M320 466 H896" stroke="#3c5d79" stroke-width="3"/>
        <path d="M210 456 H333 M892 456 H998" stroke="#4f7594" stroke-width="4"/>
        <path d="M92 519 H1137" stroke="#527997" stroke-width="1.4" opacity=".38"/>
      </g>"""
    pieces = []

    pieces.append(part("Interior / comfort", """
       <path class="part-body" d="M788 371 L795 307 Q800 294 814 295
          H827 Q836 300 830 319 L821 369 H841 V389 H779Z"/>
       <path class="part-detail" d="M794 369 H831 M805 388 V414"/>
       <path class="part-body" d="M694 375 H733 L740 386 H692Z"/>
    """))
    pieces.append(part("Safety / driver assistance", """
       <path class="part-body" d="M843 337 H871 V357 H843Z"/>
       <path class="part-detail" d="M849 345 H865 M857 340 V352"/>
    """))
    pieces.append(part("Fuel system", """
       <rect class="part-body" x="480" y="420" width="117" height="32" rx="7"/>
       <path class="part-detail" d="M490 432 H586 M490 441 H581"/>
       <path class="part-outline" d="M492 420 L480 391 L448 390"/>
       <circle class="part-body" cx="448" cy="390" r="5"/>
    """))
    pieces.append(part("Electrical / electronics", """
       <rect class="part-body" x="861" y="355" width="47" height="36" rx="4"/>
       <path class="part-detail" d="M872 365 H897 M872 372 H897 M872 379 H897"/>
       <path class="part-outline" d="M886 355 Q906 337 929 342"/>
       <circle class="metal" cx="869" cy="361" r="2.5"/>
    """))
    pieces.append(part("Powertrain / transmission", """
       <path class="part-body" d="M825 413 L844 399 H901
          L921 409 V434 L900 444 H845 L827 434Z"/>
       <path class="part-detail" d="M849 402 V443 M866 401 V442 M882 402 V443"/>
       <path class="part-outline" d="M828 424 L754 428 L723 442 H672"/>
       <circle class="part-body" cx="753" cy="429" r="7"/>
    """))
    pieces.append(part("Engine / cooling", """
       <path class="part-body" d="M926 377 H1013 L1030 388
           V426 L1016 441 H934 L919 428 V390Z"/>
       <path class="part-body" d="M935 365 H1017 V383 H935Z"/>
       <path class="part-detail" d="M946 371 H1006 M949 390 V428
           M964 389 V431 M980 389 V431 M995 390 V428 M1011 394 V425"/>
       <circle class="part-outline" cx="1009" cy="416" r="12"/>
       <circle class="part-detail" cx="1009" cy="416" r="4"/>
       <path class="part-outline" d="M1006 368 Q1024 356 1050 360"/>
    """))
    # Radiator is a separate clickable geometry, same broad NHTSA category.
    pieces.append(part("Engine / cooling", """
       <rect class="part-body" x="1061" y="364" width="20" height="66" rx="2"/>
       <path class="part-detail" d="M1065 370 V423 M1070 370 V423 M1075 370 V423"/>
       <path class="part-outline" d="M1061 377 Q1046 369 1032 385
            M1061 419 Q1042 428 1031 418"/>
    """))
    pieces.append(part("Steering", """
       <circle class="part-outline" cx="874" cy="309" r="17"/>
       <path class="part-outline" d="M874 309 L906 388 L933 395"/>
       <path class="part-outline" d="M933 447 H1032"/>
    """))

    for x in (225, 983):
        pieces.append(part("Suspension", f"""
           <path class="part-outline" d="M{x-33} 400 L{x-13} 394
                L{x+18} 394 L{x+34} 406"/>
           <path class="part-outline" d="M{x-8} 356 V391"/>
           <path class="part-outline" d="M{x-14} 363
                q28 -2 0 6 q28 4 0 8 q28 4 0 8 q28 4 0 8"/>
           <path class="part-outline" d="M{x-18} 356 H{x+17}"/>
        """))
        pieces.append(part("Wheels / tires", f"""
           <circle cx="{x}" cy="469" r="69" class="tire"/>
           <circle cx="{x}" cy="469" r="53" class="rim"/>
           <circle cx="{x}" cy="469" r="39" class="wheel-inner"/>
           <circle cx="{x}" cy="469" r="9" class="hub"/>
           <path class="spoke" d="M{x} 431 V507 M{x-38} 469 H{x+38}
                M{x-27} 442 L{x+27} 496 M{x+27} 442 L{x-27} 496"/>
        """))
        pieces.append(part("Brakes", f"""
           <circle cx="{x}" cy="469" r="30" class="brake-rotor"/>
           <path class="part-body" d="M{x+23} 443 Q{x+47} 444 {x+49} 466
                L{x+38} 480 L{x+29} 474 L{x+32} 460Z"/>
           <path class="part-detail" d="M{x+35} 455 L{x+43} 458"/>
        """))
    pieces.append(part("Visibility / lighting", """
       <path class="part-body" d="M1110 359 Q1135 365 1140 379
           L1113 382 L1103 371Z"/>
       <path class="part-body" d="M65 369 H76 V405 H65Z"/>
    """))
    pieces.append(part("Other / unspecified", """
       <circle class="part-body" cx="126" cy="287" r="13"/>
       <path class="part-detail" d="M126 277 V289 M126 294 V297"/>
    """))

    callouts = """<g class="callouts" pointer-events="none">
        <path d="M984 374 L988 342 L1050 342" class="leader"/>
        <text x="1050" y="337" text-anchor="end">ENGINE</text>
        <path d="M870 414 L839 391 L803 391" class="leader"/>
        <text x="800" y="386" text-anchor="end">GEARBOX</text>
        <path d="M1071 376 L1099 346" class="leader"/>
        <text x="1105" y="344">RADIATOR</text>
        <path d="M226 377 L275 365 L300 365" class="leader"/>
        <text x="303" y="361">STRUT</text>
        <path d="M1020 455 L1056 492" class="leader"/>
        <text x="1059" y="505">CALIPER</text>
      </g>""" if detailed else ""

    data_json = json.dumps({"stats": payload, "evidence": safe_evidence},
                           ensure_ascii=True).replace("<", "\\u003c")
    name = html.escape(str(vehicle), quote=True)
    mode = "expanded" if detailed else "compact"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 565" '
        'role="img" aria-label="Proportional cargo van technical engineering cutaway">'
        '<defs><linearGradient id="drawing-bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop stop-color="#162d48"/><stop offset="1" stop-color="#09182a"/>'
        '</linearGradient><filter id="soft-glow" x="-30%" y="-30%" '
        'width="160%" height="160%"><feGaussianBlur in="SourceGraphic" '
        'stdDeviation="1.3" result="haze"/><feMerge><feMergeNode in="haze"/>'
        '<feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        '<rect x="13" y="12" width="1174" height="535" rx="17" '
        'fill="url(#drawing-bg)" opacity=".48"/>'
        '<path d="M47 540 H1154" stroke="#537e9e" stroke-width="1" opacity=".35"/>'
        '<text x="68" y="67" fill="#9bb4ca" font-size="17" letter-spacing="1.6">'
        'CARGO VAN · TECHNICAL SIDE ELEVATION · FRONT →</text>'
        + shell + chassis + "".join(pieces) + callouts + '</svg>'
    )
    legend = "".join(
        '<span><i class="dot" style="background:' + color + '"></i>'
        + html.escape(label) + '</span>'
        for label, color in [
            ("Lower share", COLORS["low"]), ("Moderate", COLORS["moderate"]),
            ("Elevated", COLORS["elevated"]), ("High share", COLORS["high"]),
            ("No reports", COLORS["none"]),
        ]
    )

    style = """
    <style>
      *{box-sizing:border-box}html,body{margin:0;padding:0;background:transparent;
        color:#e5f2ff;font:13px/1.42 system-ui,Segoe UI,Arial,sans-serif}
      .frame{display:flex;flex-direction:column;min-width:0;
        border:1px solid rgba(119,199,239,.25);border-radius:16px;overflow:hidden;
        background:linear-gradient(135deg,rgba(26,50,79,.65),rgba(8,18,36,.62))}
      .frame.compact{height:430px}.frame.expanded{height:875px}
      .top{display:flex;align-items:center;justify-content:space-between;gap:8px;
        padding:12px 15px 3px;flex-shrink:0}
      .name{font-size:14px;font-weight:700}.context{font-size:10px;color:#b0c5d9}
      svg{display:block;width:100%;height:0;min-height:0;
        flex:1 1 auto;overflow:hidden}
      .exterior{fill:rgba(121,165,198,.085);stroke:#9fcae7;stroke-width:3.2}
      .roof-highlight,.window-line,.body-detail{fill:none;stroke:#9fc8e3;
        stroke-width:1.6;opacity:.65}
      .body-divider,.door-track{fill:none;stroke:#97bbd2;stroke-width:1.4;opacity:.36}
      .door{fill:rgba(94,149,186,.035);stroke:#9bbfd9;stroke-width:1.7;opacity:.54}
      .lower-sill,.arch{fill:none;stroke:#b0d6ed;stroke-width:3;opacity:.8}
      .window{fill:rgba(74,147,191,.17);stroke:#a8d5ed;stroke-width:2.5}
      .mirror{fill:rgba(132,180,211,.32);stroke:#b8dbee;stroke-width:2}
      .handle{fill:none;stroke:#d1e9f7;stroke-width:4;stroke-linecap:round;opacity:.7}
      .part-body{fill:var(--heat);fill-opacity:.38;stroke:var(--heat);stroke-width:2.4}
      .part-outline{fill:none;stroke:var(--heat);stroke-width:2.6;
        stroke-linecap:round;stroke-linejoin:round}
      .part-detail{fill:none;stroke:#203951;stroke-width:2;opacity:.85;stroke-linecap:round}
      .metal{fill:#9eb7c9}.tire{fill:#0a1527;stroke:var(--heat);stroke-width:6}
      .rim{fill:#40546a;stroke:#8da9bf;stroke-width:2.6}
      .wheel-inner{fill:rgba(44,68,91,.86);stroke:#bad2e0;stroke-width:1.8}
      .hub{fill:#c8dce7;stroke:#42627d;stroke-width:2}
      .spoke{stroke:var(--heat);stroke-width:3;opacity:.65}
      .brake-rotor{fill:none;stroke:var(--heat);stroke-width:3.2;opacity:.8}
      .callouts text{font:bold 11px Arial;letter-spacing:.5px;fill:#dceffa}
      .leader{fill:none;stroke:#9dbfda;stroke-width:1.2;opacity:.8}
      .hotspot{cursor:pointer;outline:none;transition:filter .12s}
      .hotspot:hover,.hotspot.active,.hotspot:focus-visible{filter:url(#soft-glow)}
      .hotspot.active .part-body{fill-opacity:.67}
      .frame.compact .part-detail{opacity:.25}
      .frame.compact .body-detail{opacity:.35}
      .frame.compact .door-track{opacity:.2}
      .details{display:flex;flex-wrap:wrap;align-items:center;gap:8px;
        flex-shrink:0;min-height:42px;padding:8px 12px;
        border-top:1px solid rgba(119,199,239,.17)}
      .selected{font-weight:700;color:#f3faff}
      .pill{padding:3px 7px;border-radius:40px;border:1px solid rgba(154,210,244,.28);
        background:rgba(27,48,77,.42);color:#d7e9fa;font-size:11px}
      .legend{display:flex;flex-wrap:wrap;gap:9px;padding:2px 12px 10px}
      .legend span{color:#adc6dc;font-size:10px}
      .dot{display:inline-block;width:8px;height:8px;margin-right:4px;border-radius:50%}
      .evidence{margin-top:5px;padding:11px 14px;border-top:1px solid rgba(134,197,233,.2);
        overflow-y:auto;flex:1 1 auto;min-height:0}
      .evidence h4{font-size:12px;margin:0 0 7px;color:#dbeaf8}
      .evidence-card{padding:9px;margin:7px 0;border-radius:9px;
        background:rgba(37,66,96,.36);border:1px solid rgba(150,205,233,.13)}
      .evidence-card b{display:block;font-size:11px;color:#b7d5e9}
      .evidence-card p{margin:5px 0 0;color:#d3e1ee;font-size:11px}
      .empty-evidence{color:#b4cbde;font-size:11px}
    </style>"""
    javascript = """
    <script>
    const DATA = __DATA__;
    const areas = Array.from(document.querySelectorAll('.hotspot'));
    const picked = document.getElementById('picked');
    const count = document.getElementById('count');
    const share = document.getElementById('share');
    const status = document.getElementById('status');
    function activate(el) {
      areas.forEach(a => a.classList.remove('active'));
      el.classList.add('active');
      const d = DATA.stats[el.dataset.system];
      picked.textContent = el.dataset.system;
      count.textContent = d.count.toLocaleString() + ' complaint(s)';
      share.textContent = d.share.toFixed(1) + "% of this vehicle's complaints";
      status.textContent = d.status;
      status.style.borderColor = d.color;
      const box = document.getElementById('evidence-list');
      if (box) {
        box.replaceChildren();
        const examples = DATA.evidence[el.dataset.system] || [];
        if (!examples.length) {
          const p = document.createElement('p'); p.className = 'empty-evidence';
          p.textContent = 'No matching excerpts in the selected model years.';
          box.appendChild(p);
        } else {
          examples.forEach(example => {
            const card = document.createElement('div');card.className='evidence-card';
            const b = document.createElement('b');
            b.textContent = example.model_year + ' · ' + example.component;
            const p = document.createElement('p');p.textContent=example.description;
            card.appendChild(b);card.appendChild(p);box.appendChild(card);
          });
        }
      }
    }
    areas.forEach(el => {
      el.addEventListener('click', () => activate(el));
      el.addEventListener('keydown', ev => {
        if(ev.key === 'Enter' || ev.key === ' ') {ev.preventDefault(); activate(el);}
      });
    });
    const initial = areas.find(a => a.dataset.system === 'Engine / cooling');
    if(initial) activate(initial);
    </script>""".replace("__DATA__", data_json)

    evidence_markup = (
        '<section class="evidence"><h4>Selected system · NHTSA complaint excerpts</h4>'
        '<div id="evidence-list"></div></section>' if detailed else ''
    )
    return (
        style + f'<div class="frame {mode}">'
        + '<div class="top"><span class="name">' + name + '</span>'
        + f'<span class="context">{total:,} unique NHTSA complaints</span></div>'
        + svg
        + '<div class="details"><span id="picked" class="selected"></span>'
        + '<span id="count" class="pill"></span>'
        + '<span id="share" class="pill"></span>'
        + '<span id="status" class="pill"></span></div>'
        + '<div class="legend">' + legend + '</div>'
        + evidence_markup + '</div>' + javascript
    )
