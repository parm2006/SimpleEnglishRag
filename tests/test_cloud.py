import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from ser.cloud import ensure_cloud_ready


class CloudWakeTests(unittest.TestCase):
    def setUp(self):
        env = {
            "QDRANT_STORAGE": "cloud",
            "QDRANT_CLOUD_MANAGEMENT_KEY": "test-secret",
            "QDRANT_CLOUD_ACCOUNT_ID": "11111111-1111-1111-1111-111111111111",
            "QDRANT_CLOUD_CLUSTER_ID": "22222222-2222-2222-2222-222222222222",
        }
        self.environment = patch.dict(os.environ, env)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def run_with_phases(self, phases, status=200):
        requests = []
        phases = iter(phases)

        def handle(request):
            requests.append(request)
            self.assertEqual(request.headers["Authorization"], "apikey test-secret")
            if request.method == "POST":
                self.assertTrue(str(request.url).endswith("/unsuspend"))
                return httpx.Response(200, json={})
            return httpx.Response(status, json={"cluster": {"state": {"phase": next(phases)}}})

        client = httpx.Client(transport=httpx.MockTransport(handle), headers={"Authorization": "apikey test-secret"})
        with patch("ser.cloud.httpx.Client", return_value=client), patch("ser.cloud.time.sleep"):
            ensure_cloud_ready(lambda message: None)
        return requests

    def test_suspended_cluster_resumes_once_and_waits_until_healthy(self):
        requests = self.run_with_phases([
            "CLUSTER_PHASE_SUSPENDED", "CLUSTER_PHASE_SUSPENDED",
            "CLUSTER_PHASE_RESUMING", "CLUSTER_PHASE_HEALTHY",
        ])
        self.assertEqual([r.method for r in requests], ["GET", "POST", "GET", "GET", "GET"])

    def test_healthy_cluster_is_not_modified(self):
        self.assertEqual(len(self.run_with_phases(["CLUSTER_PHASE_HEALTHY"])), 1)

    def test_already_resuming_does_not_post(self):
        requests = self.run_with_phases(["CLUSTER_PHASE_RESUMING", "CLUSTER_PHASE_HEALTHY"])
        self.assertTrue(all(r.method == "GET" for r in requests))

    def test_placeholder_and_non_cloud_skip_management_api(self):
        for env in ({"QDRANT_CLOUD_MANAGEMENT_KEY": "your-management-key-here"}, {"QDRANT_STORAGE": "memory"}):
            with patch.dict(os.environ, env), patch("ser.cloud.httpx.Client") as client:
                ensure_cloud_ready()
                client.assert_not_called()

    def test_auth_failure_is_actionable_and_does_not_expose_key(self):
        with self.assertRaisesRegex(RuntimeError, "HTTP 403") as error:
            self.run_with_phases(["CLUSTER_PHASE_HEALTHY"], status=403)
        self.assertNotIn("test-secret", str(error.exception))

    def test_wait_times_out(self):
        with patch("ser.cloud.time.monotonic", side_effect=[0, 181]):
            with self.assertRaisesRegex(RuntimeError, "still starting"):
                self.run_with_phases(["CLUSTER_PHASE_RESUMING"])

    def test_invalid_ids_fail_before_network(self):
        with patch.dict(os.environ, {"QDRANT_CLOUD_ACCOUNT_ID": "your-account-id-here"}):
            with self.assertRaisesRegex(RuntimeError, "valid UUIDs"):
                ensure_cloud_ready()

    def test_failed_resume_stops_without_another_wake_request(self):
        with self.assertRaisesRegex(RuntimeError, "FAILED_TO_RESUME"):
            self.run_with_phases(["CLUSTER_PHASE_FAILED_TO_RESUME"])

    def test_entry_point_wakes_before_loading_cli(self):
        import ser

        events = []
        cli = SimpleNamespace(main=lambda: events.append("cli"))
        with patch("dotenv.load_dotenv"), patch.dict(sys.modules, {"ser.cli": cli}):
            with patch("ser.cloud.ensure_cloud_ready", side_effect=lambda: events.append("wake")):
                ser.main()
        self.assertEqual(events, ["wake", "cli"])

    def test_entry_point_exits_cleanly_when_wake_fails(self):
        import ser

        with patch("dotenv.load_dotenv"), patch("sys.stderr"):
            with patch("ser.cloud.ensure_cloud_ready", side_effect=RuntimeError("Cannot wake cluster")):
                with self.assertRaises(SystemExit) as error:
                    ser.main()
        self.assertEqual(error.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
