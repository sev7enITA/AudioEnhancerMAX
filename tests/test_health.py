import asyncio
import sys
import unittest
from unittest.mock import patch

from app.main import health
from app.release import APP_VERSION, RELEASE_CHANNEL, RELEASE_LABEL


class HealthEndpointTests(unittest.TestCase):
    def test_health_works_without_optional_torch(self):
        with patch.dict(sys.modules, {"torch": None}):
            payload = asyncio.run(health())

        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["version"], APP_VERSION)
        self.assertEqual(payload["release_channel"], RELEASE_CHANNEL)
        self.assertEqual(payload["release_label"], RELEASE_LABEL)
        self.assertIn("build", payload)
        self.assertFalse(payload["mps_available"])


if __name__ == "__main__":
    unittest.main()
