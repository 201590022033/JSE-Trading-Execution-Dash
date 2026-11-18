import unittest
from scripts import llama_3b_candidate as candidate
from scripts import calibrate_calendar_model as calibration
from scripts import calendar_ollama as runner


class CandidateProfileTests(unittest.TestCase):
    def test_profile_is_separate_and_restored_after_exception(self):
        before = (calibration.MODEL, calibration.DIGEST, calibration.START_MEMORY,
                  calibration.ABORT_MEMORY, calibration.PROFILE, runner.TIMEOUT_SECONDS,
                  runner.MODEL, runner.MODEL_DIGEST)
        digest = candidate.EXPECTED_DIGEST
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with candidate.candidate_profile(digest):
                self.assertEqual(calibration.MODEL, 'llama3.2:3b')
                self.assertEqual(calibration.PROFILE['timeout_seconds'], 330)
                self.assertEqual(runner.MODEL, before[-2])
                raise RuntimeError('fixture')
        self.assertEqual(before, (calibration.MODEL, calibration.DIGEST, calibration.START_MEMORY,
                         calibration.ABORT_MEMORY, calibration.PROFILE, runner.TIMEOUT_SECONDS,
                         runner.MODEL, runner.MODEL_DIGEST))

    def test_unverified_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            with candidate.candidate_profile('0' * 64):
                pass


if __name__ == '__main__':
    unittest.main()
