import os
from pathlib import Path
import subprocess
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows shortcut setup')
class NotificationSetupTests(unittest.TestCase):
    def test_preview_and_whatif_do_not_create_shortcut(self):
        target = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Strategy Radar.lnk'
        if target.exists():
            self.skipTest('Existing user shortcut must not be modified')
        script = Path(__file__).parent / 'scripts/setup_radar_notifications.ps1'
        for arguments in ([], ['-Install', '-WhatIf']):
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), *arguments], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(target.exists())
