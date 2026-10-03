"""Rate limiter checks with a fake clock. Run: .venv/bin/python -m unittest"""
import unittest
from unittest import mock

from fastapi import HTTPException

from ratelimit import RateLimit


class RateLimitTest(unittest.TestCase):
    def test_blocks_after_the_limit_and_says_when_to_retry(self):
        limit = RateLimit(limit=2, window_s=60)
        with mock.patch("ratelimit.time.monotonic", return_value=100.0):
            limit.check("1.2.3.4")
            limit.check("1.2.3.4")
            with self.assertRaises(HTTPException) as ctx:
                limit.check("1.2.3.4")
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(ctx.exception.headers["Retry-After"], "60")

    def test_usable_as_a_fastapi_dependency(self):
        # With postponed annotations, FastAPI sees "Request" as a string and treats it as a query param (422s).
        import inspect

        from fastapi import Request

        self.assertIs(inspect.signature(RateLimit.__call__).parameters["request"].annotation, Request)

    def test_window_slides_and_clients_are_separate(self):
        limit = RateLimit(limit=1, window_s=60)
        with mock.patch("ratelimit.time.monotonic", return_value=100.0):
            limit.check("a")
            limit.check("b")  # another client has its own budget
        with mock.patch("ratelimit.time.monotonic", return_value=160.0):
            limit.check("a")  # 60s later the old request has left the window


if __name__ == "__main__":
    unittest.main()
