#!/usr/bin/env python3
"""herdr-core (hc) backend tests. No live core, no model calls."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
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

    def test_finished_null_status_clears_stale_working(self):
        view = hd.hc_view(
            {"address": "t6", "name": "leaf", "state": "live",
             "status": "working", "turn": 0},
            {"address": "t6", "name": "leaf", "state": "finished",
             "status": None, "turn": 1, "exit_code": 9},
        )
        self.assertEqual(view["state"], "finished")
        self.assertEqual(view["exit_code"], 9)
        self.assertEqual(view["agent_status"], "error")

    def test_live_reported_error_stays_live(self):
        view = hd.hc_view({
            "address": "t7", "state": "live",
            "status": {"state": "error", "msg": "quota"},
        })
        self.assertEqual(view["state"], "live")
        self.assertEqual(view["agent_status"], "error")
        self.assertIsNone(view["exit_code"])


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

    def test_idle_send_uses_atomic_status_precondition(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return completed(argv, stdout=json.dumps({"started": True, "turn": 4}))

        with patch.object(hd.subprocess, "run", fake_run):
            hd.prompt_agent_hc(
                "t1", "hi", force=False, timeout_ms=1000, only_if="idle"
            )
        self.assertEqual(calls[0][:5], ["hc", "send", "--json", "--if", "idle"])
        self.assertEqual(calls[0][5:], ["t1", "hi"])

    def test_send_into_an_already_working_turn_is_unconfirmed(self):
        with patch.object(hd.subprocess, "run", lambda argv, **kw: completed(
            argv, stdout=json.dumps(
                {"started": True, "status": "working", "turn": 4}
            )
        )):
            result = hd.prompt_agent_hc("t1", "hi", force=False, timeout_ms=1000)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "delivery_joined_working")
        self.assertIn("already working", result["error"]["message"])

    def test_status_mismatch_is_rejected_not_unconfirmed(self):
        with patch.object(hd.subprocess, "run", lambda argv, **kw: completed(
            argv,
            stdout=json.dumps({"error": {
                "kind": "status_mismatch",
                "message": "t1 is working, not idle",
                "hint": "nothing was typed",
            }}),
            returncode=1,
        )):
            result = hd.prompt_agent_hc(
                "t1", "hi", force=False, timeout_ms=1000, only_if="idle"
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "status_mismatch")

    def test_timeout_is_unconfirmed_not_a_retry(self):
        def boom(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 1)

        with patch.object(hd.subprocess, "run", boom):
            result = hd.prompt_agent_hc("leaf", "hi", force=False, timeout_ms=1000)
        self.assertEqual(result["error"]["code"], "prompt_transport_unknown")


class StartTests(unittest.TestCase):
    def test_run_uses_bg_name_cwd_and_resolved_binary(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return completed(argv, stdout=json.dumps(
                {"address": "t8", "name": "leaf", "state": "live", "turn": 0}
            ))

        def fake_ready(address, timeout_ms):
            self.assertEqual(address, "t8")
            return {"status": "idle"}

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(hd, "run", fake_run), \
             patch.object(hd.shutil, "which", return_value="/opt/bin/claude"), \
             patch.object(hd, "hc_wait_ready", fake_ready):
            result = hd.start_agent_hc("leaf", "claude", Path(tmp), ["--model", "x"], 5000)
        argv = calls[0]
        self.assertEqual(argv[:3], ["hc", "run", "--bg"])
        self.assertIn("--name", argv)
        self.assertEqual(argv[argv.index("--name") + 1], "leaf")
        self.assertIn("--cwd", argv)
        # An absolute path never matches an hc template name.
        self.assertEqual(argv[-3:], ["/opt/bin/claude", "--model", "x"])
        self.assertEqual(result["result"]["agent"]["pane_id"], "t8")

    def test_cursor_kind_starts_cursor_agent(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return completed(argv, stdout=json.dumps(
                {"address": "t9", "name": "leaf", "state": "live", "turn": 0}
            ))

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(hd, "run", fake_run), \
             patch.object(hd.shutil, "which", return_value="/opt/bin/cursor-agent"), \
             patch.object(hd, "hc_wait_ready", return_value={"status": "idle"}):
            hd.start_agent_hc("leaf", "cursor", Path(tmp), [], 5000)
        self.assertEqual(calls[0][-1], "/opt/bin/cursor-agent")

    def test_missing_binary_fails_before_run(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(hd, "run") as run, \
             patch.object(hd.shutil, "which", return_value=None), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                hd.start_agent_hc("leaf", "claude", Path(tmp), [], 5000)
        run.assert_not_called()

    def test_failed_ready_kills_the_started_terminal(self):
        killed = []

        def fake_run(argv, **kwargs):
            return completed(argv, stdout=json.dumps(
                {"address": "t8", "name": "leaf", "state": "live", "turn": 0}
            ))

        def fake_json_soft(argv, **kwargs):
            killed.append(argv)
            return {}

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(hd, "run", fake_run), \
             patch.object(hd.shutil, "which", return_value="/opt/bin/claude"), \
             patch.object(hd, "hc_json_soft", side_effect=fake_json_soft), \
             patch.object(hd, "hc_wait_ready", side_effect=SystemExit(1)), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                hd.start_agent_hc("leaf", "claude", Path(tmp), [], 5000)
        self.assertIn(["kill", "t8"], killed)

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
    def test_snapshot_uses_all_short_records_without_n_plus_one(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return completed(argv, stdout=json.dumps({"terminals": [
                {"address": "t1", "name": "a", "state": "live",
                 "turn": 2, "status": "working", "cwd": "/repo"},
                {"address": "t2", "name": "b", "state": "finished",
                 "turn": 4, "exit_code": 0, "status": None, "cwd": "/repo"},
            ]}))

        with patch.object(hd.subprocess, "run", fake_run):
            views, error = hd.hc_fleet_snapshot(5, observation_seq=7)
        self.assertIsNone(error)
        self.assertEqual(len(calls), 1, "fleet observation is one bounded call")
        self.assertEqual(calls[0][0], ["hc", "ls", "--all", "--json"])
        self.assertLessEqual(calls[0][1]["timeout"], 5)
        self.assertEqual([v["pane_id"] for v in views], ["t1", "t2"])
        self.assertEqual([v["agent_status"] for v in views], ["working", "done"])
        self.assertTrue(all(v["observation_seq"] == 7 for v in views))

    def test_snapshot_error_is_not_an_empty_fleet(self):
        with patch.object(hd.subprocess, "run", lambda argv, **kw: completed(
            argv, stdout=json.dumps({"error": {"kind": "down"}}), returncode=1
        )):
            views, error = hd.hc_fleet_snapshot(5)
        self.assertEqual(views, [])
        self.assertIsNotNone(error)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name)

    def record(self, pane="t2", **extra):
        return hd.put_job(self.cwd, "leaf", {
            "pane_id": pane, "cwd": str(self.cwd), "kind": "codex",
            "role": "worker", "model": "m",
            "brief": str(hd.job_dir(self.cwd, "leaf") / "brief.md"),
            "captain_pane_id": "cap", "workspace_id": "",
            "status": "done", "delivery": "confirmed", "baseline_seq": 0,
            **extra,
        }, generation="gen1")

    def test_collect_uses_recorded_address_not_same_named_replacement(self):
        self.record()
        finished = {
            "pane_id": "t2", "address": "t2", "name": "leaf",
            "agent_status": "done", "state": "finished", "exit_code": 0,
            "turn": 1, "cwd": str(self.cwd),
        }
        replacement = {
            "pane_id": "t3", "address": "t3", "name": "leaf",
            "agent_status": "idle", "state": "live", "turn": 0,
            "cwd": str(self.cwd),
        }
        reads = []
        targets = []

        def fake_get(target, observation_seq=None):
            targets.append(target)
            return dict(finished if target == "t2" else replacement,
                        observation_seq=observation_seq)

        def fake_read(name, lines=400, address=None):
            reads.append((name, address))
            return "OLD WORKER ANSWER"

        with patch.object(hd, "runtime", return_value="hc"), \
             patch.object(hd, "require_runtime"), \
             patch.object(hd, "assert_not_self"), \
             patch.object(hd, "hc_get", side_effect=fake_get), \
             patch.object(hd, "fleet_snapshot",
                          return_value=([finished, replacement], None)), \
             patch.object(hd, "read_agent", side_effect=fake_read), \
             patch.object(hd, "emit") as emit:
            hd.cmd_collect(SimpleNamespace(
                cwd=str(self.cwd), name="leaf", wait=False, timeout=1000, lines=50,
            ))
        payload = emit.call_args.args[0]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["pane_id"], "t2")
        self.assertEqual(reads, [("leaf", "t2")])
        self.assertIn("OLD WORKER ANSWER", payload["result_excerpt"] or "")
        self.assertEqual(targets, ["t2"])
        self.assertEqual(hd.load_index(self.cwd)["jobs"]["leaf"]["pane_id"], "t2")

    def test_stop_kills_recorded_address_not_same_named_replacement(self):
        self.record()
        live = {
            "pane_id": "t2", "address": "t2", "name": "leaf",
            "agent_status": "idle", "state": "live", "turn": 0,
            "cwd": str(self.cwd),
        }
        with patch.object(hd, "runtime", return_value="hc"), \
             patch.object(hd, "require_runtime"), \
             patch.object(hd, "assert_not_self"), \
             patch.object(hd, "hc_get", return_value=live), \
             patch.object(hd, "hc_json", return_value={}) as kill, \
             patch.object(hd, "emit"):
            hd.cmd_stop(SimpleNamespace(cwd=str(self.cwd), name="leaf", yes=True))
        kill.assert_called_once_with(["kill", "t2"])

    def test_send_targets_recorded_address_with_idle_precondition(self):
        self.record(status="idle", delivery="confirmed")
        live = {
            "pane_id": "t2", "address": "t2", "name": "leaf",
            "agent_status": "idle", "state": "live", "turn": 3,
            "cwd": str(self.cwd),
        }
        with patch.object(hd, "runtime", return_value="hc"), \
             patch.object(hd, "require_runtime"), \
             patch.object(hd, "assert_not_self"), \
             patch.object(hd, "hc_get", return_value=live), \
             patch.object(hd, "submit_job", return_value={"ok": True}) as submit, \
             patch.object(hd, "emit"):
            hd.cmd_send(SimpleNamespace(
                cwd=str(self.cwd), name="leaf", message="follow-up",
                message_file=None, force=False, wait=False, timeout=1000, lines=20,
            ))
        self.assertEqual(submit.call_args.kwargs["target"], "t2")
        self.assertEqual(submit.call_args.kwargs["only_if"], "idle")

    def test_finished_name_is_reusable_but_live_name_is_not(self):
        with patch.object(hd, "runtime", return_value="hc"), \
             patch.object(hd, "hc_terminals", return_value=[]):
            self.assertEqual(hd.resolve_spawn_name("leaf", "worker", "codex"), "leaf")
        live = [{"address": "t3", "name": "leaf", "state": "live"}]
        with patch.object(hd, "runtime", return_value="hc"), \
             patch.object(hd, "hc_terminals", return_value=live), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                hd.resolve_spawn_name("leaf", "worker", "codex")

    def test_auto_name_does_not_overwrite_a_finished_job(self):
        hd.put_job(self.cwd, "worker-codex", {
            "pane_id": "t2", "status": "done", "delivery": "confirmed",
        }, generation="gen1")
        with patch.object(hd, "agent_list", return_value=[]):
            name = hd.resolve_spawn_name(None, "worker", "codex", self.cwd)
        self.assertEqual(name, "worker-codex-2")


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name)

    def job(self, **extra):
        return hd.put_job(self.cwd, "leaf", {
            "pane_id": "t1", "cwd": str(self.cwd), "kind": "codex",
            "role": "worker", "model": "m",
            "brief": str(hd.job_dir(self.cwd, "leaf") / "brief.md"),
            "captain_pane_id": "cap", "workspace_id": "",
            "status": "idle", "delivery": "confirmed", "baseline_seq": 3,
            **extra,
        }, generation="gen1")

    def agent(self, status, turn=3, seq=1, **extra):
        return {
            "pane_id": "t1", "address": "t1", "name": "leaf",
            "agent_status": status, "turn": turn, "observation_seq": seq,
            "cwd": str(self.cwd), **extra,
        }

    def test_stale_equal_turn_snapshot_cannot_downgrade_working(self):
        self.job()
        with patch.object(hd, "runtime", return_value="hc"):
            working = hd.observe_job(
                self.cwd, "leaf", hd.load_index(self.cwd)["jobs"]["leaf"],
                self.agent("working", seq=11),
            )
            self.assertEqual(working["status"], "working")
            stale = hd.observe_job(
                self.cwd, "leaf", working, self.agent("idle", seq=10),
            )
        self.assertEqual(stale["status"], "working")
        self.assertEqual(stale["state_change_seq"], 11)
        self.assertTrue(stale["ok"])

    def test_stale_missing_observation_cannot_downgrade_working(self):
        self.job(state_change_seq=11)
        with patch.object(hd, "runtime", return_value="hc"):
            result = hd.observe_job(
                self.cwd, "leaf", hd.load_index(self.cwd)["jobs"]["leaf"],
                None, observation_seq=10,
            )
        self.assertEqual(result["status"], "idle")
        self.assertEqual(result["state_change_seq"], 11)

    def test_joined_working_turn_is_never_auto_confirmed(self):
        self.job(delivery="unconfirmed", prompt_error={
            "code": "delivery_joined_working", "message": "already working",
        })
        with patch.object(hd, "runtime", return_value="hc"):
            result = hd.observe_job(
                self.cwd, "leaf", hd.load_index(self.cwd)["jobs"]["leaf"],
                self.agent("working", seq=11),
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["delivery"], "unconfirmed")

    def test_finished_terminal_settles_a_confirmed_job(self):
        self.job(status="working")
        with patch.object(hd, "runtime", return_value="hc"):
            result = hd.observe_job(
                self.cwd, "leaf", hd.load_index(self.cwd)["jobs"]["leaf"],
                self.agent("done", turn=4, seq=12, state="finished", exit_code=0),
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "done")
        self.assertIsNone(result["error"])

    def test_unknown_observation_preserves_existing_dump_and_deliverable(self):
        dump = hd.job_dir(self.cwd, "leaf") / "pane.md"
        dump.write_text("OLD DUMP")
        report = hd.job_dir(self.cwd, "leaf") / "report.md"
        report.write_text("# OLD REPORT")
        self.job(result=str(dump), deliverable=str(report))
        previous = hd.load_index(self.cwd)["jobs"]["leaf"]
        with patch.object(hd, "observe_current_job", return_value={
            **previous, "status": "unknown", "error": "probe timed out",
        }), patch.object(hd, "read_agent") as read, \
             patch.object(hd, "write_pane_dump") as write:
            result = hd.finish_sync(
                self.cwd, "leaf", mode="collect", kind=None, role=None,
                pane="t1", work_cwd=None, prompt_path=None, lines=20,
                created_at=None, generation="gen1",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["deliverable"], str(report))
        self.assertEqual(dump.read_text(), "OLD DUMP")
        read.assert_not_called()
        write.assert_not_called()

    def test_observation_counter_is_above_legacy_turn_values(self):
        self.job(state_change_seq=50)
        self.assertEqual(hd.next_observation_seq(self.cwd), 51)
        self.assertEqual(hd.next_observation_seq(self.cwd), 52)


class HcCliIntegrationTests(unittest.TestCase):
    def test_collect_ignores_a_replacement_with_the_same_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            hd.put_job(cwd, "leaf", {
                "pane_id": "t2", "cwd": str(cwd), "kind": "codex",
                "role": "worker", "model": "m",
                "brief": str(hd.job_dir(cwd, "leaf") / "brief.md"),
                "captain_pane_id": "cap", "workspace_id": "",
                "status": "done", "delivery": "confirmed",
                "baseline_seq": 1,
            }, generation="gen1")
            finished = {
                "address": "t2", "name": "leaf", "state": "finished",
                "status": None, "exit_code": 0, "turn": 1, "cwd": str(cwd),
            }
            replacement = {
                "address": "t3", "name": "leaf", "state": "live",
                "status": {"state": "idle"}, "turn": 0, "cwd": str(cwd),
            }
            binary = cwd / "bin" / "hc"
            binary.parent.mkdir()
            binary.write_text("#!/usr/bin/env python3\n" + (
                "import json, sys\n"
                f"finished = {finished!r}\n"
                f"replacement = {replacement!r}\n"
                "args = sys.argv[1:]\n"
                "if args[:2] == ['ls', '--all']:\n"
                "    print(json.dumps({'terminals': [finished, replacement]}))\n"
                "elif args[:1] == ['get']:\n"
                "    target = args[1]\n"
                "    if target == 't2':\n"
                "        print(json.dumps(finished))\n"
                "    elif target in ('leaf', 't3'):\n"
                "        print(json.dumps(replacement))\n"
                "    else:\n"
                "        print(json.dumps({'error': {'kind': 'not_found'}}))\n"
                "        sys.exit(1)\n"
                "elif args[:1] == ['read']:\n"
                "    print('OLD WORKER ANSWER' if args[1] == 't2' else 'REPLACEMENT WORKER REPLY')\n"
                "else:\n"
                "    print(json.dumps({'error': {'kind': 'unexpected', 'args': args}}))\n"
                "    sys.exit(1)\n"
            ))
            binary.chmod(0o755)
            env = {
                **os.environ,
                "PATH": str(binary.parent) + os.pathsep + os.environ["PATH"],
                "HERD_DISPATCH_RUNTIME": "hc",
                "HC_TERMINAL_ID": "cap",
            }
            env.pop("HERDR_ENV", None)
            cli = str(Path(__file__).with_name("herd-dispatch"))
            proc = subprocess.run(
                [sys.executable, cli, "collect", "--name", "leaf",
                 "--cwd", str(cwd), "--lines", "50"],
                env=env, text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["pane_id"], "t2")
            self.assertIn("OLD WORKER ANSWER", payload["result_excerpt"] or "")
            self.assertEqual(
                hd.load_index(cwd)["jobs"]["leaf"]["pane_id"], "t2"
            )


class HcWatchResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name)

    def job(self, **extra):
        return hd.put_job(self.cwd, "leaf", {
            "pane_id": "t2", "cwd": str(self.cwd), "kind": "codex",
            "role": "worker", "model": "m",
            "brief": str(hd.job_dir(self.cwd, "leaf") / "brief.md"),
            "captain_pane_id": "cap", "workspace_id": "",
            "status": "working", "delivery": "confirmed", "baseline_seq": 0,
            **extra,
        }, generation="gen1")

    def test_watch_sees_a_finished_terminal_as_collectable(self):
        self.job()
        finished = {
            "pane_id": "t2", "address": "t2", "name": "leaf",
            "agent_status": "done", "state": "finished", "exit_code": 0,
            "turn": 1, "cwd": str(self.cwd), "observation_seq": 9,
        }
        with patch.object(hd, "runtime", return_value="hc"), \
             patch.object(hd, "require_runtime"), \
             patch.object(hd, "assert_not_self"), \
             patch.object(hd, "self_ids", return_value={"pane_id": "cap"}), \
             patch.object(hd, "fleet_snapshot",
                          return_value=([finished], None)), \
             patch.object(hd, "emit") as emit:
            hd.cmd_watch(SimpleNamespace(
                cwd=str(self.cwd), name=["leaf"], timeout=1000, interval=10,
            ))
        payload = emit.call_args.args[0]
        self.assertEqual(payload["jobs"][0]["status"], "done")
        self.assertEqual(payload["jobs"][0]["action"], "collect")

    def test_result_refresh_reads_the_recorded_address(self):
        self.job(status="done")
        finished = {
            "pane_id": "t2", "address": "t2", "name": "leaf",
            "agent_status": "done", "state": "finished", "exit_code": 0,
            "turn": 1, "cwd": str(self.cwd),
        }
        reads = []

        def fake_read(name, lines=400, address=None):
            reads.append((name, address))
            return "OLD WORKER ANSWER"

        with patch.object(hd, "runtime", return_value="hc"), \
             patch.object(hd, "require_runtime"), \
             patch.object(hd, "find_job_agent", return_value=finished), \
             patch.object(hd, "read_agent", side_effect=fake_read), \
             patch.object(hd, "emit") as emit:
            hd.cmd_result(SimpleNamespace(
                cwd=str(self.cwd), name="leaf", refresh=True, lines=20,
            ))
        self.assertEqual(reads, [("leaf", "t2")])
        self.assertTrue(emit.call_args.args[0]["ok"])


class HcSpawnTests(unittest.TestCase):
    def test_spawn_binds_the_run_address_and_idle_precondition(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            hd.put_job(cwd, "leaf", {
                "pane_id": "t2", "status": "done", "delivery": "confirmed",
            }, generation="old")
            started = {"result": {"agent": {
                "pane_id": "t9", "address": "t9", "name": "leaf",
                "agent_status": "idle", "turn": 0, "state": "live",
                "cwd": str(cwd),
            }}}
            placement = hd.Placement(
                pane_id="", tab_id="", created_pane=False, created_tab=False,
            )
            args = SimpleNamespace(
                cwd=str(cwd), name="leaf", kind="codex", model="m",
                role="worker", message="task", message_file=None,
                worktree=False, args="", direction="right",
                start_timeout=1000, timeout=2000, lines=20,
            )
            with patch.object(hd, "runtime", return_value="hc"), \
                 patch.object(hd, "require_runtime"), \
                 patch.object(hd, "known_kinds", return_value={"codex"}), \
                 patch.object(hd, "resolve_spawn_name", return_value="leaf"), \
                 patch.object(hd, "assert_not_self"), \
                 patch.object(hd, "find_live_agent", return_value=None), \
                 patch.object(hd, "maybe_worktree", return_value=cwd), \
                 patch.object(hd, "place_worker_pane", return_value=placement), \
                 patch.object(hd, "start_agent", return_value=started), \
                 patch.object(hd, "rename_pane_quiet"), \
                 patch.object(hd, "self_ids", return_value={
                     "pane_id": "cap", "workspace_id": "", "tab_id": "",
                 }), \
                 patch.object(hd, "submit_job", return_value={"ok": True}) as submit:
                hd.spawn(args, "assign")
            record = hd.load_index(cwd)["jobs"]["leaf"]
            self.assertEqual(record["pane_id"], "t9")
            self.assertEqual(record["baseline_seq"], 0)
            self.assertEqual(record["status"], "idle")
            self.assertEqual(submit.call_args.kwargs["target"], "t9")
            self.assertEqual(submit.call_args.kwargs["only_if"], "idle")


class VerdictTests(unittest.TestCase):
    def test_error_is_terminal_but_not_ok(self):
        ok, err = hd.verdict("error", sync=True)
        self.assertFalse(ok)
        self.assertIn("error", err or "")

    def test_idle_settles_sync(self):
        self.assertEqual(hd.verdict("idle", sync=True), (True, None))


if __name__ == "__main__":
    unittest.main()
