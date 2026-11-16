import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode

from fastapi import HTTPException

from src.api.auth import verify_telegram_init_data
from src.config import settings
from src.services.order_filters import matches_order_filter, parse_budget_amount


class TelegramInitDataTests(unittest.TestCase):
    def setUp(self):
        self.original_token = settings.TELEGRAM_BOT_TOKEN
        self.original_max_age = settings.TELEGRAM_INIT_DATA_MAX_AGE_SECONDS
        settings.TELEGRAM_BOT_TOKEN = "test-token"
        settings.TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = 3600

    def tearDown(self):
        settings.TELEGRAM_BOT_TOKEN = self.original_token
        settings.TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = self.original_max_age

    @staticmethod
    def signed_init_data(auth_date: int | None = None) -> str:
        fields = {
            "auth_date": str(auth_date or int(time.time())),
            "query_id": "test-query",
            "user": json.dumps({"id": 12345, "username": "tester"}, separators=(",", ":")),
        }
        data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret_key = hmac.new(
            b"WebAppData",
            settings.TELEGRAM_BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()
        fields["hash"] = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        return urlencode(fields)

    def test_accepts_valid_signed_data(self):
        user = verify_telegram_init_data(self.signed_init_data())
        self.assertEqual(user["id"], 12345)
        self.assertEqual(user["username"], "tester")

    def test_rejects_bad_signature_even_in_debug_mode(self):
        original_debug = settings.DEBUG
        settings.DEBUG = True
        try:
            with self.assertRaises(HTTPException) as error:
                verify_telegram_init_data("auth_date=1&user=%7B%7D&hash=" + "0" * 64)
            self.assertEqual(error.exception.status_code, 401)
        finally:
            settings.DEBUG = original_debug

    def test_rejects_expired_data_and_duplicate_fields(self):
        with self.assertRaises(HTTPException):
            verify_telegram_init_data(self.signed_init_data(int(time.time()) - 7200))
        with self.assertRaises(HTTPException):
            verify_telegram_init_data("auth_date=1&auth_date=2&hash=" + "0" * 64)


class OrderFilterTests(unittest.TestCase):
    def test_parses_common_budget_formats(self):
        self.assertEqual(parse_budget_amount("2,000–4,000 USD"), 2000)
        self.assertEqual(parse_budget_amount("1.250,50 EUR"), 1250.5)
        self.assertIsNone(parse_budget_amount("За домовленістю"))

    def test_applies_minimum_budget_and_keywords(self):
        self.assertTrue(matches_order_filter("Python API", "Build an API", "2 000 UAH", 1500, "python, react"))
        self.assertFalse(matches_order_filter("Python API", "Build an API", "За домовленістю", 1500))
        self.assertFalse(matches_order_filter("Logo", "Brand identity", "2 000 UAH", 1000, "python"))


if __name__ == "__main__":
    unittest.main()
