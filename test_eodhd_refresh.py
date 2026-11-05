import unittest
from scripts.refresh_eodhd_zebra import remaining_quota, ordered_instruments


class EodhdRefreshTests(unittest.TestCase):
    def test_uncaptured_and_oldest_attempts_take_priority(self):
        result=ordered_instruments({'AAA':'AAA','BBB':'BBB','CCC':'CCC'}, {'AAA':'2026-11-04','BBB':'2026-11-02'})
        self.assertEqual([x[0] for x in result], ['CCC','BBB','AAA'])

    def test_current_day_reserves_one_call(self):
        self.assertEqual(remaining_quota({'dailyRateLimit':20,'apiRequests':5,'apiRequestsDate':'2026-11-04'}, '2026-11-04'),14)

    def test_prior_day_usage_is_reset_and_never_exceeds_limit(self):
        self.assertEqual(remaining_quota({'dailyRateLimit':20,'apiRequests':20,'apiRequestsDate':'2026-11-03'}, '2026-11-04'),19)
        self.assertEqual(remaining_quota({'dailyRateLimit':20,'apiRequests':20,'apiRequestsDate':'2026-11-04'}, '2026-11-04'),0)


if __name__ == '__main__': unittest.main()
