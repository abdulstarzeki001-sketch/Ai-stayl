"""Read-only tests of the local device bridge trust boundary."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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

    def make_remote(self, host="my-laptop.example-tailnet.ts.net", login="owner@example.com",
                    token=None, origin="https://agent-ai-stayl.abdulstarzeki001.workers.dev"):
        h = self.make_handler(host=host, origin=origin, token=token)
        h.headers["Tailscale-User-Login"] = login
        return h

    def test_local_origin_unchanged(self):
        h = self.make_handler(origin="http://127.0.0.1:17849", token=star_ai_web.TOKEN)
        self.assertEqual(h.page_origin(), "http://127.0.0.1:17849")

    def test_valid_remote_tailnet_identity_and_pairing(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", "my-laptop.example-tailnet.ts.net"), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", "owner@example.com"):
            h = self.make_remote(token=star_ai_web.TOKEN)
            self.assertTrue(h.is_remote_request())
            self.assertTrue(h.device_authenticated())
            self.assertTrue(h.authorized())
            self.assertEqual(h.page_origin(), "https://my-laptop.example-tailnet.ts.net")

    def test_remote_proxy_rewriting_host_to_loopback(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", "my-laptop.example-tailnet.ts.net"), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", "owner@example.com"):
            h = self.make_remote(host="127.0.0.1:17849", token=star_ai_web.TOKEN)
            self.assertTrue(h.device_authenticated())
            self.assertEqual(h.page_origin(), "https://my-laptop.example-tailnet.ts.net")

    def test_remote_access_rejected_when_disabled(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", ""), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", ""):
            h = self.make_remote(token=star_ai_web.TOKEN)
            self.assertFalse(h.authorized())

    def test_wrong_tailnet_identity_rejected(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", "my-laptop.example-tailnet.ts.net"), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", "owner@example.com"):
            h = self.make_remote(login="intruder@example.com", token=star_ai_web.TOKEN)
            self.assertFalse(h.authorized())
            self.assertFalse(h.device_authenticated())

    def test_remote_missing_identity_rejected(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", "my-laptop.example-tailnet.ts.net"), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", "owner@example.com"):
            h = self.make_handler(host="my-laptop.example-tailnet.ts.net", token=star_ai_web.TOKEN,
                                  origin="https://agent-ai-stayl.abdulstarzeki001.workers.dev")
            self.assertFalse(h.authorized())

    def test_remote_wrong_origin_rejected(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", "my-laptop.example-tailnet.ts.net"), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", "owner@example.com"):
            h = self.make_remote(token=star_ai_web.TOKEN, origin="https://evil.example")
            self.assertTrue(h.authorized())
            self.assertFalse(h.device_authenticated())

    def test_remote_missing_pairing_token_rejected(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", "my-laptop.example-tailnet.ts.net"), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", "owner@example.com"):
            h = self.make_remote(token=None)
            self.assertFalse(h.authorized())

    def test_remote_unexpected_hostname_rejected(self):
        with patch.object(star_ai_web, "TAILSCALE_HOST", "my-laptop.example-tailnet.ts.net"), \
             patch.object(star_ai_web, "TAILSCALE_LOGIN", "owner@example.com"):
            h = self.make_remote(host="attacker.example.ts.net", token=star_ai_web.TOKEN)
            self.assertFalse(h.authorized())


if __name__ == "__main__":
    unittest.main()
