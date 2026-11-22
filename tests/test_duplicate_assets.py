"""Two files exist twice on purpose and must stay byte-identical.

The local Compose files mount the copies under `observability/` and `load/`; Helm can only package files that sit
inside the chart, so the cluster uses the copies under `deploy/charts/`. A symbolic link would not work for either
(a bind mount cannot follow a link that leaves the mounted folder, and Helm does not follow links), so this test
guards against the copies drifting apart instead.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    ("observability/grafana/dashboards/system.json", "deploy/charts/platform/dashboards/system.json"),
    ("load/sustained.js", "deploy/charts/food/load/sustained.js"),
)


class DuplicateAssets(unittest.TestCase):
    def test_copies_are_identical(self):
        for local, chart in PAIRS:
            with self.subTest(pair=local):
                self.assertEqual((ROOT / local).read_bytes(), (ROOT / chart).read_bytes(),
                                 f"{local} and {chart} must be edited together")


if __name__ == "__main__":
    unittest.main()
