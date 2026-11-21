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

    # Independently size each mechanical assembly around its own center.
    # Scaling a whole chassis around (0,0) displaced components from the
    # wheels and body. Body geometry stays fixed in either layout.
    part_sizes = {
        "Interior / comfort": ((555, 240), .73, .85),
        "Safety / driver assistance": ((640, 210), .75, .88),
        "Fuel system": ((464, 343), .83, .91),
        "Electrical / electronics": ((672, 285), .72, .86),
        "Powertrain / transmission": ((672, 328), .80, .91),
        "Engine / cooling": ((813, 281), .77, .88),
        "Steering": ((779, 287), .83, .92),
        "Visibility / lighting": ((980, 318), .88, .95),
        "Other / unspecified": ((115, 191), .72, .86),
    }

    def part(system, body, center=None, scales=None):
        color = payload[system]["color"]
        cx, cy = center or part_sizes.get(system, ((0, 0), 1, 1))[0]
        compact_scale, detailed_scale = scales or part_sizes.get(
            system, ((0, 0), 1, 1)
        )[1:]
        scale = detailed_scale if detailed else compact_scale
        transform = (
            f'transform="translate({cx} {cy}) scale({scale}) '
            f'translate({-cx} {-cy})"'
            if scale != 1 else ""
        )
        return (
            '<g class="hotspot" role="button" tabindex="0" data-system="'
            + html.escape(system, quote=True)
            + '" style="--heat:' + color + '" ' + transform + '>'
            + body + '</g>'
        )

    # Each component is a separately selectable SVG group.
    # Compact mode simplifies secondary details, while expanded mode retains them.
    sections = []

    # A high-roof cargo-van profile based on common full-size van proportions.
    # The long, almost level roof, forward cabin, raked windshield, short hood,
    # wheel-arch cutouts and rear cargo doors make the silhouette legible
    # even when two vehicles are displayed side by side.
    sections.append(part("Body / structure", """
      <path d="
       M 61,399 Q 46,398 46,380
       L 46,171 Q 46,133 84,128
       Q 310,117 555,123 L 703,123
       Q 738,124 757,143 L 853,247
       Q 862,260 903,260
       L 962,265 Q 1010,273 1021,307
       L 1032,362 Q 1041,392 1017,402
       L 973,402
       C 969,346 926,312 865,316
       C 819,319 787,350 784,403
       L 327,403
       C 324,350 282,315 238,315
       C 188,315 155,348 151,402
       L 74,402 Z" class="skin"/>
      <!-- High-roof cargo panel, roof gutter and pressed vertical ribs -->
      <path d="M 67,166 Q 69,146 93,145
               L 710,143" class="roof-line"/>
      <path d="M 80,153 H695" class="panel-line" opacity=".35"/>
      <path d="M 71,181 L 71,343" class="panel-line"/>
      <path d="M 402,160 V365
               M 594,154 V371" class="panel-line"/>
      <path d="M 71,344 H784 M 79,380 H165 M 328,379 H785"
            class="rail-soft"/>
      <!-- Sliding cargo door, track, recessed handle and rear door -->
      <path d="M 409,218 L 584,218
               L 584,364 L 409,364 Z" class="door-panel"/>
      <path d="M 397,207 H601" class="body-rail" opacity=".55"/>
      <path d="M 528,249 H561" class="handles"/>
      <path d="M 75,184 L 75,356 M 94,185 L94,358"
            class="panel-line" opacity=".38"/>
      <!-- Cab door and raked side window, clearly behind the hood -->
      <path d="M 650,174 L 733,157 Q 741,156 750,164
               L 849,269 L 846,281 L 649,281 Z" class="window"/>
      <path d="M 743,163 L 748,279 M 649,280 L 649,363
               M 850,280 L 849,319" class="panel-line"/>
      <path d="M 805,304 H829" class="handles"/>
      <path d="M 852,271 L 868,269 L 883,279
               L 880,294 L 860,297 Z" class="mirror"/>
      <!-- Front windshield follows the steep, rounded front pillar -->
      <path d="M 756,144 Q 782,150 803,174
               L 881,258" class="windshield-line"/>
      <!-- The wheel openings are intentionally NOT filled with body panels. -->
      <path d="M 151,401 C 155,348 188,315 238,315
               C 282,315 324,350 327,401"
            class="arch-line"/>
      <path d="M 784,401 C 787,350 819,319 865,316
               C 926,312 969,346 973,401"
            class="arch-line"/>
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
    """))
    # Cooling system shares NHTSA Engine / cooling category, but the radiator
    # is separately scaled and stays at the nose of the van.
    sections.append(part("Engine / cooling", """
      <rect x="928" y="210" width="43" height="152" rx="4" class="heat-fill"/>
      <path d="M936 220 V351 M943 220 V351 M950 220 V351 M957 220 V351
               M964 220 V351" class="detail-line"/>
      <path d="M927 235 Q913 215 887 226" class="part-line"/>
      <path d="M927 338 Q911 351 889 333" class="part-line"/>
      <circle cx="916" cy="287" r="15" class="heat-fill"/>
      <path d="M907 287 H925 M916 278 V296" class="detail-line"/>
    """, center=(950, 285), scales=(.75, .88)))

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
        """, center=(pos, 330), scales=(.78, .89)))
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
        """, center=(pos, 410), scales=(.86, .93)))
        sections.append(part("Brakes", f"""
          <circle cx="{pos}" cy="410" r="49" fill="none"
                  stroke="var(--heat)" stroke-width="6" opacity=".8"/>
          <path d="M{pos+17} 360 Q{pos+80} 348 {pos+86} 402
                   L{pos+65} 432 L{pos+43} 417 L{pos+50} 391Z"
                class="heat-fill" stroke-width="3"/>
          <path d="M{pos+47} 390 L{pos+72} 397 M{pos+47} 405 L{pos+70} 411"
                class="detail-line"/>
          <circle cx="{pos+72}" cy="398" r="5" class="bolt"/>
        """, center=(pos, 410), scales=(.78, .90)))

    # Headlamps, rear tail lamps and bright front lamp signatures.
    sections.append(part("Visibility / lighting", """
      <path d="M 1001,291 L 1021,304 L 1026,322
               L 1004,328 L 987,308 Z" class="heat-fill"/>
      <path d="M 47,296 H 69 V 342 H 47 Z" class="heat-fill"/>
      <path d="M 997,305 L 1018,314" class="detail-line"/>
      <path d="M 1020,308 L 1074,278 L 1060,325 L 1022,326"
            fill="rgba(255,232,161,.08)" stroke="none"/>
    """))

    # Translucent exterior details over the exposed powertrain. These elements
    # remain noninteractive so clicking visible mechanical parts still works.
    sections.append("""
      <g aria-hidden="true" pointer-events="none">
        <path d="M 863,257 Q 906,254 964,263 Q 1003,269 1020,307"
              fill="none" stroke="#a2dafa" stroke-width="4" opacity=".76"/>
        <path d="M 982,360 L 1029,360 L 1035,385
                 Q 1029,400 1008,402 H 977"
              fill="none" stroke="#8dc8ed" stroke-width="3" opacity=".6"/>
        <path d="M 1014,352 H1030" fill="none"
              stroke="#d8edf9" stroke-width="3" opacity=".6"/>
        <path d="M 80,393 H150 M 328,395 H785"
              stroke="#9bc7e4" stroke-width="3" opacity=".6"/>
        <path d="M 659,296 H843" stroke="#a3d6ef" stroke-width="2"
              opacity=".35"/>
        <path d="M 69,347 L 145,347 M 336,346 L 399,346"
              fill="none" stroke="#9ac9e8" stroke-width="2" opacity=".35"/>
        <path d="M 88,118 Q 390,109 706,117"
              fill="none" stroke="#c1e8ff" stroke-width="2" opacity=".3"/>
      </g>
    """)

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
      .frame{height:var(--frame-height);display:flex;flex-direction:column}
      svg{display:block;width:100%;height:100%;min-height:0;flex:1 1 auto;
          overflow:visible}
      .frame.compact .detail-line{opacity:.30}
      .frame.compact .panel-line{opacity:.20}
      .frame.compact .roof-line{opacity:.4}
      .frame.compact .handles{stroke-width:4}
      .frame.compact .hotspot:hover{filter:brightness(1.18)}
      .frame.compact .legend{padding-bottom:8px}
      .frame.compact .details{min-height:47px}
      .frame.expanded .evidence{flex:0 0 auto;max-height:235px;
          overflow-y:auto}
      .frame.expanded .legend{flex:0 0 auto}
      .frame .top{flex:0 0 auto}
      .frame .details{flex:0 0 auto}
      .skin{fill:rgba(108,163,199,.105);stroke:rgba(189,226,247,.87);stroke-width:4}
      .door-panel{fill:rgba(105,153,189,.025);stroke:rgba(166,212,241,.42);stroke-width:2}
      .mirror{fill:rgba(110,160,193,.26);stroke:rgba(181,224,245,.75);stroke-width:2}
      .windshield-line{fill:none;stroke:rgba(203,234,250,.68);stroke-width:3}
      .arch-line{fill:none;stroke:rgba(173,218,245,.65);stroke-width:4}
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

    viewer_class = "expanded" if detailed else "compact"
    frame_height = 945 if detailed else 505
    return (
      style
      + f'<div class="frame {viewer_class}" style="--frame-height:{frame_height}px">'
      + '<div class="top">'
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
