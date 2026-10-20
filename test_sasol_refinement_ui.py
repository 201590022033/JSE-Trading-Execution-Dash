"""Run the actual learning JavaScript against an offline interaction harness."""
from pathlib import Path
import shutil
import subprocess
import unittest


class SasolRefinementUITests(unittest.TestCase):
    def test_actual_comparison_ui_readonly_states_and_escaping(self):
        node = shutil.which("node")
        if not node:
            bundled = Path.home()/".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
            node = str(bundled) if bundled.is_file() else None
        if not node:
            self.skipTest("Node runtime unavailable for offline UI behavior harness")
        root = Path(__file__).resolve().parent
        result = subprocess.run([node, "scripts/test_sasol_refinement_ui.cjs"], cwd=root,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn("Sasol refinement UI checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
