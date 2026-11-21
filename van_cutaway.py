"""Interactive vector cutaway for FleetIQ complaint hotspots.

The generic front-engine diagram is not vehicle-specific service documentation.
A colored component represents the share of *reported* complaints mentioning
its broad NHTSA category, never an observed failure probability.
"""
from __future__ import annotations

import html
import json

COLORS = {
    "none": "#71859e",
    "low": "#11edc1",
    "moderate": "#f7dc65",
    "elevated": "#ff9e4a",
    "high": "#ff496f",
}

SYSTEMS = [
    "Engine / cooling", "Powertrain / transmission", "Fuel system",
    "Electrical / electronics", "Brakes", "Steering", "Suspension",
    "Wheels / tires", "Body / structure", "Safety / driver assistance",
    "Visibility / lighting", "Interior / comfort", "Other / unspecified",
]


def band(share, count):
    if count == 0:
        return "No reports", COLORS["none"]
    if share >= 30:
        return "High share", COLORS["high"]
    if share >= 15:
        return "Elevated share", COLORS["elevated"]
    if share >= 5:
        return "Moderate share", COLORS["moderate"]
    return "Lower share", COLORS["low"]


def render_cutaway(lookup, total, vehicle, detailed=False, evidence_rows=None):
    """Return self-contained SVG/HTML to embed with st.components.v1.html.

    Colored, addressable SVG groups are interactive within the iframe. Native
    Streamlit complaint evidence controls remain available below the viewer.
    """
    payload = {}
    for system in SYSTEMS:
        d = lookup.get(system, {})
        count = int(d.get("complaints", 0))
        share = float(d.get("share_pct", 0))
        label, color = band(share, count)
        payload[system] = {
            "count": count, "share": round(share, 1),
            "status": label, "color": color,
        }

    evidence_rows = evidence_rows or {}
    safe_evidence = {
        system: [
            {
                "model_year": str(item.get("model_year", ""))[:8],
                "component": str(item.get("component", ""))[:120],
                "description": str(item.get("description", ""))[:300],
            }
            for item in evidence_rows.get(system, [])[:3]
        ]
        for system in SYSTEMS
    }

    def part(system, body):
        color = payload[system]["color"]
        return (
            '<g class="hotspot" role="button" tabindex="0" data-system="'
            + html.escape(system, quote=True)
            + '" style="--heat:' + color + '">'
            + body + '</g>'
        )

    # Every part is a separate selectable SVG group. Main mechanical items
    # are deliberately larger than numbered markers in the previous design.
    sections = []

    # Bodywork: thin translucent skins and sliding-door seams.
    sections.append(part("Body / structure", """
      <path d="M58 294 L58 129 Q58 106 81 106 L606 106 L646 68
       L844 68 Q877 68 900 100 L1006 219 L1023 249
       L1023 301 L58 301 Z" class="skin"/>
      <path d="M65 294 H1008" class="body-rail"/>
      <path d="M644 114 L667 85 H837 L913 194 H644Z" class="window"/>
      <path d="M575 108 V295 M370 110 V295 M200 112 V293" class="panel-line"/>
      <path d="M406 198 h42 M541 194 h32" class="handles"/>
      <path d="M72 117 H605" class="roof-line"/>
      <path d="M102 291 L105 308 H981" class="rail-soft"/>
      <path d="M86 142 H570" class="panel-line" opacity=".35"/>
    """))

    # Chassis underbody beneath both axles.
    structure = """
      <path d="M106 326 H973" stroke="#678da7" stroke-width="12"
            stroke-linecap="round" opacity=".55" />
      <path d="M110 344 H985" stroke="#86b3d0" stroke-width="3"
            stroke-dasharray="13 9" opacity=".3"/>
      <path d="M244 326 L284 345 H804 L848 326"
            stroke="#a4b9ca" stroke-width="7" fill="none" opacity=".4"/>
    """

    # Cabin: clearly shaped front bucket seat / seatback.
    sections.append(part("Interior / comfort", """
      <path d="M548 250 Q536 203 545 168 L582 165 Q606 174 601 195
               L588 256 L619 270 Q626 279 610 288 L530 288
               Q508 278 518 267Z" class="heat-fill"/>
      <path d="M525 292 H613 M560 292 V323" class="part-line"/>
      <path d="M407 234 L456 234 L464 269 L399 269Z" class="heat-fill"/>
      <path d="M425 266 V307" class="part-line"/>
    """))

    # Safety area: airbag housing/cabin sensor, not a claimed airbag location.
    sections.append(part("Safety / driver assistance", """
      <path d="M617 192 L663 189 L671 228 L616 231 Z" class="heat-fill"/>
      <circle cx="640" cy="209" r="13" class="part-line"/>
      <path d="M625 210 L655 210 M640 194 V225" class="part-line"/>
    """))

    # Fuel cell rear-mid under floor, with filler tube and collar.
    sections.append(part("Fuel system", """
      <rect x="370" y="315" width="189" height="58" rx="16" class="heat-fill"/>
      <path d="M390 329 H540 M388 359 H540" class="detail-line"/>
      <path d="M410 318 L397 278 L360 264" class="part-line"/>
      <circle cx="360" cy="264" r="10" class="heat-fill"/>
      <rect x="444" y="325" width="40" height="14" rx="4" class="detail-line"/>
    """))

    # Battery, controller and fuse block; visible wiring harness.
    sections.append(part("Electrical / electronics", """
      <rect x="631" y="254" width="91" height="63" rx="7" class="heat-fill"/>
      <path d="M645 269 H706 M645 284 H706 M645 299 H706" class="detail-line"/>
      <path d="M675 255 Q685 228 728 228 Q762 223 789 201"
             class="part-line"/>
      <path d="M686 250 V236 H742 L761 242" class="part-line"/>
      <circle cx="660" cy="268" r="5" class="bolt"/>
      <circle cx="698" cy="268" r="5" class="bolt"/>
    """))

    # Transmission connected to the engine via bellhousing.
    sections.append(part("Powertrain / transmission", """
      <path d="M612 321 L664 294 L733 297 L752 331 L730 352
               L678 354 L651 339 L610 340Z" class="heat-fill"/>
      <path d="M663 294 L669 355 M688 296 L688 354 M715 297 L715 348"
            class="detail-line"/>
      <path d="M612 326 L518 326 L478 344 L390 344"
            class="part-line" stroke-width="11"/>
      <circle cx="470" cy="344" r="11" class="heat-fill"/>
      <path d="M610 320 L633 303 L645 300" class="part-line"/>
      <path d="M566 317 L552 336" class="detail-line"/>
    """))

    # Detailed engine: block, cylinder cover, visible intake & belt housing.
    sections.append(part("Engine / cooling", """
      <path d="M742 215 H873 L897 250 L897 334 L861 356
               H753 L730 328 L731 245 Z" class="heat-fill"/>
      <rect x="751" y="192" width="137" height="40" rx="9" class="heat-fill"/>
      <path d="M762 206 H878 M771 216 H878" class="detail-line"/>
      <path d="M762 242 V334 M784 239 V343 M808 240 V346 M831 239 V347
               M855 241 V343 M880 257 V328" class="detail-line"/>
      <path d="M752 356 H868 L855 376 H777Z" class="heat-fill"/>
      <circle cx="846" cy="314" r="25" class="part-line"/>
      <circle cx="846" cy="314" r="10" class="detail-line"/>
      <circle cx="778" cy="311" r="12" class="part-line"/>
      <path d="M778 311 L846 314" class="detail-line"/>
      <path d="M769 193 Q775 163 813 166 L870 170" class="part-line"/>
      <path d="M889 261 Q904 254 912 266" class="part-line"/>
      <!-- Radiator is separately drawn but shares Engine / cooling classification -->
      <rect x="928" y="210" width="43" height="152" rx="4" class="heat-fill"/>
      <path d="M936 220 V351 M943 220 V351 M950 220 V351 M957 220 V351
               M964 220 V351" class="detail-line"/>
      <path d="M927 235 Q913 215 887 226" class="part-line"/>
      <path d="M927 338 Q911 351 889 333" class="part-line"/>
      <circle cx="916" cy="287" r="15" class="heat-fill"/>
      <path d="M907 287 H925 M916 278 V296" class="detail-line"/>
    """))

    # Steering column, steering wheel, rack and tie rod.
    sections.append(part("Steering", """
      <circle cx="690" cy="176" r="32" class="part-line" stroke-width="9"/>
      <circle cx="690" cy="176" r="7" class="heat-fill"/>
      <path d="M690 176 L738 287 L806 308" class="part-line"/>
      <path d="M766 378 H970" class="part-line" stroke-width="9"/>
      <path d="M803 376 L835 392 M942 376 L960 394" class="part-line"/>
      <rect x="818" y="370" width="88" height="15" rx="7" class="heat-fill"/>
    """))

    # Wheel-end assemblies, with coils and paired disc/brake rotors.
    for pos in (242, 864):
        sections.append(part("Suspension", f"""
          <path d="M{pos-70} 355 L{pos-31} 389 L{pos+28} 389
                   L{pos+65} 355" class="part-line"/>
          <path d="M{pos-16} 266 V300" class="part-line"/>
          <path d="M{pos-22} 290 Q{pos+21} 295 {pos-22} 309
                   Q{pos+21} 324 {pos-22} 338
                   Q{pos+21} 354 {pos-22} 368
                   Q{pos+21} 380 {pos-22} 390" class="part-line"
                stroke-width="7"/>
          <path d="M{pos-28} 266 H{pos+19} M{pos-30} 391 H{pos+20}"
                class="part-line"/>
        """))
        sections.append(part("Wheels / tires", f"""
          <circle cx="{pos}" cy="410" r="93" fill="#091221" stroke="var(--heat)"
                  stroke-width="15"/>
          <circle cx="{pos}" cy="410" r="69" fill="#34475c"
                  stroke="#6b8598" stroke-width="5"/>
          <circle cx="{pos}" cy="410" r="51" class="heat-fill"/>
          <circle cx="{pos}" cy="410" r="31" fill="#25384d" stroke="#c8daea"
                  stroke-width="3"/>
          <circle cx="{pos}" cy="410" r="11" class="bolt"/>
          <path d="M{pos-52} 410 H{pos+52} M{pos} 358 V462" class="detail-line"/>
          <circle cx="{pos}" cy="410" r="83" fill="none"
                  stroke="#71889e" stroke-width="4"
                  stroke-dasharray="14 8" opacity=".56"/>
        """))
        sections.append(part("Brakes", f"""
          <circle cx="{pos}" cy="410" r="49" fill="none"
                  stroke="var(--heat)" stroke-width="6" opacity=".8"/>
          <path d="M{pos+17} 360 Q{pos+80} 348 {pos+86} 402
                   L{pos+65} 432 L{pos+43} 417 L{pos+50} 391Z"
                class="heat-fill" stroke-width="3"/>
          <path d="M{pos+47} 390 L{pos+72} 397 M{pos+47} 405 L{pos+70} 411"
                class="detail-line"/>
          <circle cx="{pos+72}" cy="398" r="5" class="bolt"/>
        """))

    # Body lighting zones.
    sections.append(part("Visibility / lighting", """
      <path d="M1001 241 L1023 238 L1023 278 L1001 277Z" class="heat-fill"/>
      <path d="M58 237 H76 V276 H58Z" class="heat-fill"/>
      <path d="M1019 239 L1073 215 L1060 270 L1023 274"
            fill="rgba(255,231,150,.08)" stroke="none"/>
    """))

    # Fallback only: other/unspecified has no discrete physical part.
    sections.append(part("Other / unspecified", """
      <circle cx="115" cy="191" r="23" class="heat-fill"/>
      <path d="M115 177 V196 M115 205 V209" class="detail-line"
            stroke-width="5"/>
    """))

    schema = json.dumps(
        {"stats": payload, "evidence": safe_evidence},
        ensure_ascii=True
    ).replace("<", "\\u003c")
    title = html.escape(vehicle, quote=True)
    style = """
    <style>
      *{box-sizing:border-box} html,body{margin:0;padding:0;background:transparent;
        color:#e9f4ff;font:13px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
      .frame{border:1px solid rgba(120,196,242,.23);border-radius:20px;
        background:linear-gradient(140deg,rgba(24,45,74,.78),rgba(8,20,38,.55));
        box-shadow:inset 0 1px rgba(207,235,255,.09),0 16px 34px rgba(0,0,0,.1);
        overflow:hidden}
      .top{display:flex;justify-content:space-between;align-items:center;gap:8px;
        padding:14px 17px 6px;color:#e3f3ff}
      .name{font-size:15px;font-weight:700;letter-spacing:.02em}
      .context{font-size:11px;color:#98b1cb}
      svg{display:block;width:100%;height:auto;max-height:520px}
      .skin{fill:rgba(81,138,181,.10);stroke:rgba(164,217,249,.8);stroke-width:4}
      .body-rail{fill:none;stroke:rgba(120,195,238,.75);stroke-width:3}
      .window{fill:rgba(47,134,171,.24);stroke:rgba(165,227,250,.64);stroke-width:3}
      .panel-line{fill:none;stroke:rgba(144,207,243,.30);stroke-width:2}
      .handles{fill:none;stroke:rgba(182,231,251,.6);stroke-width:7;stroke-linecap:round}
      .roof-line{fill:none;stroke:rgba(174,228,252,.5);stroke-width:4}
      .rail-soft{fill:none;stroke:rgba(125,201,243,.36);stroke-width:5}
      .heat-fill{fill:var(--heat);fill-opacity:.53;stroke:var(--heat);stroke-width:3}
      .part-line{fill:none;stroke:var(--heat);stroke-width:4;stroke-linejoin:round;
        stroke-linecap:round}
      .detail-line{fill:none;stroke:#12263d;stroke-width:4;
        stroke-linecap:round;stroke-linejoin:round;opacity:.77}
      .bolt{fill:#d3e0e9;stroke:#2b4b62;stroke-width:2}
      .hotspot{cursor:pointer;outline:none;transition:filter .15s}
      .hotspot:hover,.hotspot.active,.hotspot:focus-visible{filter:url(#glow)}
      .hotspot.active .heat-fill{fill-opacity:.86}
      .details{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
        padding:10px 16px 15px;border-top:1px solid rgba(122,194,231,.15);
        min-height:48px}
      .pill{padding:4px 9px;border:1px solid rgba(154,220,252,.26);
        background:rgba(27,48,77,.55);border-radius:50px;color:#ddf0ff}
      .selected{font-weight:700;color:#fff}
      .note{color:#a2bad3;font-size:11px}
      .legend{display:flex;gap:8px;flex-wrap:wrap;padding:0 16px 12px}
      .legend span{font-size:10px;color:#bad0e4}
      .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px}
      .legend b{font-weight:600}
      .evidence{padding:4px 16px 16px;border-top:1px solid rgba(122,194,231,.16)}
      .evidence h4{margin:7px 0 9px;font-size:13px;font-weight:650;color:#d9edff}
      .evidence-card{background:rgba(26,48,78,.42);
          border:1px solid rgba(124,191,226,.16);border-radius:10px;
          padding:8px 11px;margin:7px 0}
      .evidence-card b{font-size:11px;color:#b7d8ed;display:block;margin-bottom:3px}
      .evidence-card p{margin:0;color:#dbe7f3;font-size:11px;line-height:1.45}
      .empty-evidence{font-size:12px;color:#a7bfd6}
    </style>"""

    # Fixed coordinate system: width 1100 by height 530; front points right.
    svg = (
      '<svg viewBox="0 0 1100 530" role="img" '
      'aria-label="Detailed illustrative vehicle component cutaway" '
      'xmlns="http://www.w3.org/2000/svg">'
      '<defs><filter id="glow" x="-45%" y="-45%" width="190%" height="190%">'
      '<feGaussianBlur in="SourceGraphic" stdDeviation="2.7" result="blur"/>'
      '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/>'
      '</feMerge></filter>'
      '<linearGradient id="floorShade" x1="0" y1="0" x2="0" y2="1">'
      '<stop stop-color="#183452"/><stop offset="1" stop-color="#081322"/>'
      '</linearGradient></defs>'
      '<rect x="12" y="20" width="1075" height="492" rx="20" '
      'fill="url(#floorShade)" opacity=".44"/>'
      '<path d="M62 502 H1035" stroke="#4b6c89" stroke-width="2" opacity=".24"/>'
      + "".join(sections) + structure
      + '<text x="62" y="47" fill="#91aeca" font-size="19" '
      'font-family="Arial" letter-spacing="2">MECHANICAL SYSTEM CUTAWAY · FRONT →</text>'
      + '</svg>'
    )
    legend = "".join(
        '<span><i class="dot" style="background:' + color + '"></i>'
        + html.escape(label) + '</span>'
        for label, color in [
            ("Lower share",COLORS["low"]),("Moderate",COLORS["moderate"]),
            ("Elevated",COLORS["elevated"]),("High share",COLORS["high"]),
            ("No reports",COLORS["none"]),
        ]
    )
    javascript = """
    <script>
    const DATA = __DATA__;
    const areas = Array.from(document.querySelectorAll('.hotspot'));
    const chosen = document.getElementById('picked');
    const count = document.getElementById('count');
    const share = document.getElementById('share');
    const status = document.getElementById('status');
    function activate(el) {
       areas.forEach(node => node.classList.remove('active'));
       el.classList.add('active');
       const entry = DATA.stats[el.dataset.system];
       chosen.textContent = el.dataset.system;
       count.textContent = entry.count.toLocaleString() + ' complaint(s)';
       share.textContent = entry.share.toFixed(1) + '% of this vehicle\\'s complaints';
       status.textContent = entry.status;
       status.style.borderColor = entry.color;
       const evidenceBox = document.getElementById('evidence-list');
       if (evidenceBox) {
          evidenceBox.replaceChildren();
          const examples = DATA.evidence[el.dataset.system] || [];
          if (!examples.length) {
              const empty = document.createElement('p');
              empty.className = 'empty-evidence';
              empty.textContent = 'No matching excerpts for this vehicle, model-year range and system.';
              evidenceBox.appendChild(empty);
          } else {
              examples.forEach(example => {
                 const card = document.createElement('div');
                 card.className = 'evidence-card';
                 const heading = document.createElement('b');
                 heading.textContent = example.model_year + ' · ' + example.component;
                 const paragraph = document.createElement('p');
                 paragraph.textContent = example.description;
                 card.appendChild(heading);
                 card.appendChild(paragraph);
                 evidenceBox.appendChild(card);
              });
          }
       }
    }
    areas.forEach(el => {
       el.addEventListener('click', () => activate(el));
       el.addEventListener('keydown', ev => {
          if (ev.key === 'Enter' || ev.key === ' ') {
             ev.preventDefault(); activate(el);
          }
       });
    });
    const preferred = areas.find(el => el.dataset.system === 'Engine / cooling');
    if (preferred) activate(preferred);
    </script>""".replace("__DATA__", schema)

    return (
      style
      + '<div class="frame"><div class="top">'
      + '<span class="name">' + title + '</span>'
      + '<span class="context">' + f"{total:,}" + ' unique NHTSA complaints</span>'
      + '</div>' + svg
      + '<div class="details"><span class="selected" id="picked"></span>'
      + '<span class="pill" id="count"></span>'
      + '<span class="pill" id="share"></span>'
      + '<span class="pill" id="status"></span></div>'
      + '<div class="legend">' + legend + '</div>'
      + ('<div class="evidence"><h4>Selected system · NHTSA complaint excerpts</h4>'
         '<div id="evidence-list"></div></div>' if detailed else '')
      + '</div>'
      + javascript
    )
