import unittest

from validators import normalize_phone, validate_phone


class ValidatorsTestCase(unittest.TestCase):
    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("+380 97 123 45 67"), "380971234567")

    def test_validate_phone_ok(self):
        self.assertIsNone(validate_phone("380971234567"))

    def test_validate_phone_invalid_format(self):
        self.assertEqual(
            validate_phone("80971234567"),
            "Номер у форматі 380971234567 або +380971234567",
        )

    def test_validate_phone_invalid_operator(self):
        self.assertEqual(
            validate_phone("380111234567"),
            "Номер має містити валідний мобільний код оператора України",
        )


if __name__ == "__main__":
    unittest.main()
