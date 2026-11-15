"""Read-only tests of the local device bridge trust boundary."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import star_ai_web


class LocalDeviceAuthTests(unittest.TestCase):
    def make_handler(self, host="127.0.0.1:17849", origin=None, token=None):
        h = object.__new__(star_ai_web.Handler)
        h.server = SimpleNamespace(host="127.0.0.1:17849")
        h.headers = {"Host": host, "Origin": origin, "X-Star-Token": token}
        return h

    def test_missing_token_is_rejected(self):
        h = self.make_handler(origin="https://agent-ai-stayl.abdulstarzeki001.workers.dev", token="")
        self.assertFalse(h.device_authenticated())

    def test_invalid_token_is_rejected(self):
        h = self.make_handler(origin="https://agent-ai-stayl.abdulstarzeki001.workers.dev", token="not-the-secret")
        self.assertFalse(h.device_authenticated())

    def test_foreign_origin_is_rejected(self):
        h = self.make_handler(origin="https://untrusted.example", token=star_ai_web.TOKEN)
        self.assertFalse(h.device_authenticated())

    def test_host_mismatch_is_rejected(self):
        h = self.make_handler(host="evil.example", origin="https://agent-ai-stayl.abdulstarzeki001.workers.dev", token=star_ai_web.TOKEN)
        self.assertFalse(h.device_authenticated())

    def test_correct_pairing_is_accepted(self):
        h = self.make_handler(origin="https://agent-ai-stayl.abdulstarzeki001.workers.dev", token=star_ai_web.TOKEN)
        self.assertTrue(h.device_authenticated())


if __name__ == "__main__":
    unittest.main()
