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

    def test_missing_counts_and_script_encoding(self):
        output = render_cutaway(
            {}, 0, "</script><img src=x onerror=alert(1)>",
            detailed=False,
        )
        self.assertIn("&lt;/script&gt;", output)
        self.assertNotIn('<img src=x onerror=alert(1)>', output)
        self.assertIn("No reports", output)
        self.assertNotIn("evidence-list", output)
        self.assertIn("<svg", output)


if __name__ == "__main__":
    unittest.main()
