import unittest

from log_analyzer import get_median, get_stat_from_file, MIN_PARSING_ERR_COUNT, REPORT_PRECISION


ACCURACY_FLOAT = .0000001


def invalid_log_generator(count):
    for _ in range(count):
        yield "invalid log"


class LoggerStub:
    def __init__(self):
        self.info_message = ""
        self.error_message = ""

    def info(self, message):
        self.info_message = message

    def error(self, message):
        self.error_message = message


class TestMedian(unittest.TestCase):
    def test_pass_empty_list(self):
        self.assertIsNone(get_median([]))
        self.assertEqual(get_median([4]), 4)
        self.assertEqual(get_median([2, 4]), 3)
        self.assertEqual(get_median([1, 2, 3]), 2)
        self.assertEqual(get_median([1, 2, 3, 4]), 2.5)


class TestGetStat(unittest.TestCase):
    def setUp(self):
        self.logger = LoggerStub()

    def test_get_stat_from_file_correct_with_two_urls(self):
        config = {"REPORT_SIZE": 2}

        test_logs = [
            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 0.390',
            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 2.390',
            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 0.490',

            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test1 HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 0.370',
            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test1 HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 0.480',
            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test1 HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 0.210',

            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test2 HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 3.390',
            '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /test2 HTTP/1.1" 200 927 "-" "-" "-" "-" "-" 0.100',
        ]

        stat = get_stat_from_file(test_logs, config, self.logger)

        self.assertEqual(len(stat), 2)

        first = stat[0]
        second = stat[1]

        # url /test2 (first)
        self.assertEqual(first.get("url"), "/test2")
        self.assertEqual(first.get("count"), 2)
        self.assertLess(abs(first.get("count_perc") - round((2/8)*100, REPORT_PRECISION)), ACCURACY_FLOAT)
        self.assertLess(abs(first.get("time_sum") - 3.49), ACCURACY_FLOAT)
        self.assertLess(abs(first.get("time_perc") - round((3.49/7.82)*100, REPORT_PRECISION)), ACCURACY_FLOAT)
        self.assertLess(abs(first.get("time_avg") - 1.745), ACCURACY_FLOAT)
        self.assertEqual(first.get("time_max"), 3.390)
        self.assertLess(abs(first.get("time_med") - 1.745), ACCURACY_FLOAT)

        # url /test (second)
        self.assertEqual(second.get("url"), "/test")
        self.assertEqual(second.get("count"), 3)
        self.assertLess(abs(second.get("count_perc") - round((3/8)*100, REPORT_PRECISION)), ACCURACY_FLOAT)
        self.assertLess(abs(second.get("time_sum") - 3.27), ACCURACY_FLOAT)
        self.assertLess(abs(second.get("time_perc") - round((3.27/7.82)*100, REPORT_PRECISION)), ACCURACY_FLOAT)
        self.assertLess(abs(second.get("time_avg") - 1.09), ACCURACY_FLOAT)
        self.assertEqual(second.get("time_max"), 2.390)
        self.assertEqual(second.get("time_med"), .49)

    def test_get_stat_from_file_invalid_config(self):
        with self.assertRaises(ValueError):
            get_stat_from_file([], {}, self.logger)

        with self.assertRaises(ValueError):
            get_stat_from_file([], {"REPORT_SIZE": 0}, self.logger)

    def test_get_stat_from_file_empty_log(self):
        stat = get_stat_from_file([], {"REPORT_SIZE": 2}, self.logger)
        self.assertEqual(len(stat), 0)

    def test_get_stat_from_file_invalid_log(self):
        config = {"REPORT_SIZE": 2}
        invalid_logs = invalid_log_generator(MIN_PARSING_ERR_COUNT + 1)

        stat = get_stat_from_file(invalid_logs, config, self.logger)
        self.assertIsNone(stat)
        self.assertTrue("exceed max paring errors" in self.logger.error_message)

        invalid_logs = invalid_log_generator(MIN_PARSING_ERR_COUNT - 1)
        stat = get_stat_from_file(invalid_logs, config, self.logger)
        self.assertIsNone(stat)
        self.assertTrue("exceed max paring errors" in self.logger.error_message)


if __name__ == "__main__":
    unittest.main()
