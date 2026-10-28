"""Offline checks for the explicitly invoked, read-only IG Demo diagnostic."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import ig_swing_data


class IGSwingCLITests(unittest.TestCase):
    def test_cli_loads_canonical_environment_and_does_not_print_credentials(self):
        env = {"IG_API_KEY": "private-key", "IG_IDENTIFIER": "private-user",
               "IG_PASSWORD": "private-password", "IG_ENVIRONMENT": "DEMO"}
        config = SimpleNamespace(environment="DEMO")
        adapter = Mock()
        result = {"state": "DATA_OBSERVED_NOT_ADMITTED", "live_execution": False}
        with patch.object(ig_swing_data, "project_environment", return_value=env) as loader, \
             patch.object(ig_swing_data.IGConfig, "from_env", return_value=config) as parse, \
             patch.object(ig_swing_data, "IGReadOnlyAdapter", return_value=adapter) as factory, \
             patch.object(ig_swing_data.PaperLoopConfig, "load", return_value=SimpleNamespace(universe=("SASOL",))), \
             patch.object(ig_swing_data, "investigate", return_value=result) as probe, \
             patch("builtins.print") as output:
            self.assertEqual(ig_swing_data.main(), 0)
        loader.assert_called_once_with()
        parse.assert_called_once_with(env)
        factory.assert_called_once_with(config)
        self.assertEqual(probe.call_args.args[:2], (adapter, ("SASOL",)))
        rendered = output.call_args.args[0]
        self.assertEqual(json.loads(rendered), result)
        for value in ("private-key", "private-user", "private-password"):
            self.assertNotIn(value, rendered)

    def test_live_configuration_is_rejected_before_constructing_adapter(self):
        with patch.object(ig_swing_data, "project_environment", return_value={}), \
             patch.object(ig_swing_data.IGConfig, "from_env", return_value=SimpleNamespace(environment="LIVE")), \
             patch.object(ig_swing_data, "IGReadOnlyAdapter") as factory, \
             patch("builtins.print") as output:
            self.assertEqual(ig_swing_data.main(), 2)
        factory.assert_not_called()
        self.assertEqual(json.loads(output.call_args.args[0])["state"], "CONFIGURATION_OR_PROVIDER_UNAVAILABLE")

    def test_configuration_error_does_not_print_exception(self):
        with patch.object(ig_swing_data, "project_environment", return_value={}), \
             patch.object(ig_swing_data.IGConfig, "from_env", side_effect=ValueError("private-password")), \
             patch("builtins.print") as output:
            self.assertEqual(ig_swing_data.main(), 2)
        self.assertNotIn("private-password", output.call_args.args[0])

    def test_direct_script_invocation_handles_missing_credentials_without_network(self):
        root = Path(__file__).resolve().parent
        env = {k: v for k, v in os.environ.items() if not k.startswith("IG_")}
        env["PYTHON_DOTENV_DISABLED"] = "1"
        run = subprocess.run([sys.executable, str(root / "scripts" / "ig_swing_data.py")],
                             cwd=root, env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["state"], "CONFIGURATION_OR_PROVIDER_UNAVAILABLE")
        self.assertEqual(run.stderr, "")


if __name__ == "__main__":
    unittest.main()
