#!/usr/bin/env python3
"""herdr-core (hc) backend tests. No live core, no model calls."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

hd = SourceFileLoader(
    "herd_dispatch_hc_tests",
    str(Path(__file__).resolve().parent / "herd-dispatch"),
).load_module()


def completed(argv, stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


class RuntimeDetectionTests(unittest.TestCase):
    def test_hc_terminal_selects_hc(self):
        env = {"HC_TERMINAL_ID": "t7"}
        with patch.dict(hd.os.environ, env, clear=True), \
             patch.object(hd.shutil, "which", return_value="/bin/hc"):
            self.assertEqual(hd.runtime(), "hc")

    def test_herdr_pane_wins_when_both_are_set(self):
        env = {"HERDR_ENV": "1", "HC_TERMINAL_ID": "t7"}
        with patch.dict(hd.os.environ, env, clear=True), \
             patch.object(hd.shutil, "which", return_value="/bin/both"):
            self.assertEqual(hd.runtime(), "herdr")

    def test_explicit_runtime_overrides_detection(self):
        env = {"HERDR_ENV": "1", "HC_TERMINAL_ID": "t7",
               hd.RUNTIME_ENV: "hc"}
        with patch.dict(hd.os.environ, env, clear=True), \
             patch.object(hd.shutil, "which", return_value="/bin/both"):
            self.assertEqual(hd.runtime(), "hc")

    def test_self_ids_use_the_hc_terminal(self):
        with patch.object(hd, "runtime", return_value="hc"), \
             patch.dict(hd.os.environ, {"HC_TERMINAL_ID": "t9"}, clear=True):
            self.assertEqual(hd.self_ids()["pane_id"], "t9")


class TerminalViewTests(unittest.TestCase):
    def test_reported_status_wins(self):
        view = hd.hc_view({"address": "t1", "name": "leaf", "state": "live"},
                          {"status": {"state": "working"}, "turn": 3})
        self.assertEqual(view["pane_id"], "t1")
        self.assertEqual(view["agent_status"], "working")
        self.assertEqual(view["turn"], 3)

    def test_live_terminal_without_status_is_unknown(self):
        view = hd.hc_view({"address": "t2", "name": "leaf", "state": "live"})
        self.assertEqual(view["agent_status"], "unknown")

    def test_finished_terminal_maps_exit_code(self):
        done = hd.hc_view({"address": "t3", "state": "finished", "exit_code": 0})
        failed = hd.hc_view({"address": "t4", "state": "finished", "exit_code": 2})
        self.assertEqual(done["agent_status"], "done")
        self.assertEqual(failed["agent_status"], "error")

    def test_foreground_cwd_fills_missing_cwd(self):
        view = hd.hc_view({
            "address": "t5", "state": "live", "cwd": "/repo",
            "foreground": {"cwd": "/repo/sub"},
        })
        self.assertEqual(view["cwd"], "/repo")


class PromptTests(unittest.TestCase):
    def test_send_confirms_delivery_when_started(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return completed(argv, stdout=json.dumps(
                {"started": True, "status": "idle", "turn": 4}
            ))

        with patch.object(hd.subprocess, "run", fake_run):
            result = hd.prompt_agent_hc("leaf", "do it", force=False, timeout_ms=1000)
        self.assertTrue(result["ok"])
        self.assertEqual(calls[0][:3], ["hc", "send", "--json"])
        self.assertNotIn("--force", calls[0])
        self.assertEqual(calls[0][3:], ["leaf", "do it"])

    def test_send_without_started_is_unconfirmed(self):
        with patch.object(hd.subprocess, "run", lambda argv, **kw: completed(
            argv, stdout=json.dumps({"started": None, "status": None, "turn": 0})
        )):
            result = hd.prompt_agent_hc("leaf", "hi", force=False, timeout_ms=1000)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "delivery_unconfirmed")

    def test_blocked_send_is_rejected_not_retried(self):
        with patch.object(hd.subprocess, "run", lambda argv, **kw: completed(
            argv,
            stdout=json.dumps({"error": {"kind": "blocked",
                                        "message": "terminal is blocked"}}),
            returncode=1,
        )):
            result = hd.prompt_agent_hc("leaf", "hi", force=False, timeout_ms=1000)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "agent_blocked")

    def test_force_is_passed_through(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return completed(argv, stdout=json.dumps({"started": True, "turn": 1}))

        with patch.object(hd.subprocess, "run", fake_run):
            hd.prompt_agent_hc("leaf", "hi", force=True, timeout_ms=1000)
        self.assertIn("--force", calls[0])

    def test_timeout_is_unconfirmed_not_a_retry(self):
        def boom(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 1)

        with patch.object(hd.subprocess, "run", boom):
            result = hd.prompt_agent_hc("leaf", "hi", force=False, timeout_ms=1000)
        self.assertEqual(result["error"]["code"], "prompt_transport_unknown")


class StartTests(unittest.TestCase):
    def test_run_uses_bg_name_cwd_and_kind(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return completed(argv, stdout=json.dumps(
                {"address": "t8", "name": "leaf", "state": "live", "turn": 0}
            ))

        def fake_ready(name, timeout_ms):
            return {"status": "idle"}

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(hd, "run", fake_run), \
             patch.object(hd, "hc_wait_ready", fake_ready), \
             patch.object(hd, "find_agent", return_value={"pane_id": "t8"}):
            hd.start_agent_hc("leaf", "claude", Path(tmp), ["--model", "x"], 5000)
        argv = calls[0]
        self.assertEqual(argv[:3], ["hc", "run", "--bg"])
        self.assertIn("--name", argv)
        self.assertEqual(argv[argv.index("--name") + 1], "leaf")
        self.assertIn("--cwd", argv)
        self.assertEqual(argv[-3:], ["claude", "--model", "x"])

    def test_ready_returns_when_status_settles(self):
        with patch.object(hd, "hc_json_soft", return_value={
            "status": "idle", "reason": "status", "ended": True,
        }):
            self.assertEqual(hd.hc_wait_ready("leaf", 1000)["status"], "idle")

    def test_ready_loops_on_timeout_checkin(self):
        replies = [
            {"status": None, "reason": "timeout", "ended": False},
            {"status": "idle", "reason": "status", "ended": True},
        ]
        with patch.object(hd, "hc_json_soft", side_effect=replies), \
             patch.object(hd.time, "sleep"), \
             patch.object(hd.time, "monotonic", side_effect=[0, 0.1, 0.2, 0.3]):
            self.assertEqual(hd.hc_wait_ready("leaf", 5000)["status"], "idle")


class FleetTests(unittest.TestCase):
    def test_snapshot_merges_list_and_get(self):
        def fake_run(argv, **kwargs):
            if argv[:2] == ["hc", "ls"]:
                return completed(argv, stdout=json.dumps({"terminals": [
                    {"address": "t1", "name": "a", "state": "live"},
                    {"address": "t2", "name": "b", "state": "live"},
                ]}))
            addr = argv[2]
            return completed(argv, stdout=json.dumps(
                {"address": addr, "state": "live", "turn": 2,
                 "status": {"state": "working"}}
            ))

        with patch.object(hd.subprocess, "run", fake_run):
            views, error = hd.hc_fleet_snapshot(5)
        self.assertIsNone(error)
        self.assertEqual([v["pane_id"] for v in views], ["t1", "t2"])
        self.assertTrue(all(v["agent_status"] == "working" for v in views))

    def test_snapshot_error_is_not_an_empty_fleet(self):
        with patch.object(hd.subprocess, "run", lambda argv, **kw: completed(
            argv, stdout=json.dumps({"error": {"kind": "down"}}), returncode=1
        )):
            views, error = hd.hc_fleet_snapshot(5)
        self.assertEqual(views, [])
        self.assertIsNotNone(error)


class VerdictTests(unittest.TestCase):
    def test_error_is_terminal_but_not_ok(self):
        ok, err = hd.verdict("error", sync=True)
        self.assertFalse(ok)
        self.assertIn("error", err or "")

    def test_idle_settles_sync(self):
        self.assertEqual(hd.verdict("idle", sync=True), (True, None))


if __name__ == "__main__":
    unittest.main()
