import unittest

from kyivstar_client import map_error_message


class MapErrorMessageTestCase(unittest.TestCase):
    def test_known_statuses(self):
        self.assertIn("400 Bad Request", map_error_message(400, "bad"))
        self.assertIn("401 Unauthorized", map_error_message(401, "unauth"))
        self.assertIn("403 Forbidden", map_error_message(403, "forbidden"))
        self.assertIn("413 Payload Too Large", map_error_message(413, "large"))
        self.assertIn("422 Unprocessable Entity", map_error_message(422, "invalid"))
        self.assertIn("500 Internal Server Error", map_error_message(500, "error"))

    def test_unknown_status(self):
        self.assertEqual(map_error_message(418, "teapot"), "teapot")


if __name__ == "__main__":
    unittest.main()
