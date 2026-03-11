import unittest

from config import _parse_bool, _parse_int, _parse_int_range


class ConfigParsersTestCase(unittest.TestCase):
    def test_parse_bool(self):
        self.assertTrue(_parse_bool("true"))
        self.assertTrue(_parse_bool("1"))
        self.assertFalse(_parse_bool("false"))
        self.assertTrue(_parse_bool(None, default=True))

    def test_parse_int(self):
        self.assertEqual(_parse_int("10", default=1), 10)
        self.assertEqual(_parse_int("0", default=5), 5)
        self.assertEqual(_parse_int("abc", default=7), 7)

    def test_parse_int_range(self):
        self.assertEqual(_parse_int_range("3", default=1, min_value=1, max_value=6), 3)
        self.assertEqual(_parse_int_range("9", default=2, min_value=1, max_value=6), 2)
        self.assertEqual(_parse_int_range("abc", default=4, min_value=1, max_value=6), 4)


if __name__ == "__main__":
    unittest.main()
