"""Smoke tests for the interactive FleetIQ cutaway renderer."""
import re
import unittest
from xml.etree import ElementTree as ET

from van_cutaway import SYSTEMS, render_cutaway


class CutawayTests(unittest.TestCase):
    def test_svg_components_and_evidence(self):
        lookup = {
            "Engine / cooling": {"complaints": 12, "share_pct": 35.3},
            "Brakes": {"complaints": 3, "share_pct": 8.8},
        }
        evidence = {
            "Engine / cooling": [
                {"model_year": 2021, "component": "ENGINE",
                 "description": "Loss of power reported on highway."}
            ]
        }
        output = render_cutaway(lookup, 34, "Ford Transit",
                                detailed=True, evidence_rows=evidence)
        match = re.search(r"<svg\b.*?</svg>", output, flags=re.DOTALL)
        self.assertIsNotNone(match, "Missing inline SVG")
        svg = ET.fromstring(match.group(0))
        self.assertTrue(svg.tag.endswith("svg"))
        self.assertIn("TRANSMISSION", output.upper())
        self.assertIn("Loss of power", output)
        self.assertIn("evidence-list", output)
        for component in SYSTEMS:
            self.assertIn('data-system="' + component + '"', output)
        self.assertIn("#ff496f", output.lower())
        self.assertIn("34 unique NHTSA complaints", output)

    def test_compact_and_expanded_have_separate_sizing(self):
        data = {
            "Engine / cooling": {"complaints": 25, "share_pct": 18.4},
            "Wheels / tires": {"complaints": 3, "share_pct": 2.2},
        }
        compact = render_cutaway(data, 136, "Ford Transit", detailed=False)
        expanded = render_cutaway(data, 136, "Ford Transit", detailed=True)
        self.assertIn('class="frame compact"', compact)
        self.assertIn('--frame-height:505px', compact)
        self.assertIn('class="frame expanded"', expanded)
        self.assertIn('--frame-height:945px', expanded)
        self.assertIn('scale(0.77)', compact)  # compact engine
        self.assertIn('scale(0.88)', expanded)  # expanded engine
        self.assertIn('scale(0.86)', compact)  # compact tires
        self.assertIn('scale(0.93)', expanded)  # expanded tires
        self.assertIn('translate(950 285)', compact)  # radiator keeps position
        self.assertIn('height:var(--frame-height)', compact)
        self.assertIn('MECHANICAL SYSTEM CUTAWAY', compact)
        self.assertNotIn('<div id="evidence-list"></div>', compact)
        self.assertIn('<div id="evidence-list"></div>', expanded)
        for markup in (compact, expanded):
            match = re.search(r"<svg\\b.*?</svg>", markup, flags=re.DOTALL)
            self.assertIsNotNone(match)
            ET.fromstring(match.group(0))

    def test_missing_counts_and_script_encoding(self):
        output = render_cutaway(
            {}, 0, "</script><img src=x onerror=alert(1)>",
            detailed=False,
        )
        self.assertIn("&lt;/script&gt;", output)
        self.assertNotIn('<img src=x onerror=alert(1)>', output)
        self.assertIn("No reports", output)
        self.assertNotIn('<div id="evidence-list"></div>', output)
        self.assertIn("<svg", output)


if __name__ == "__main__":
    unittest.main()
