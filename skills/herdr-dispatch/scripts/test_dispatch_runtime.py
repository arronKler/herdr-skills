"""Regression scenarios from captain traces; no live agents or model calls."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

hd = SourceFileLoader("herd_dispatch_runtime_tests", str(Path(__file__).with_name("herd-dispatch"))).load_module()


class Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name)
        self.clock = Clock()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(hd.time, "monotonic", self.clock.now))
        self.stack.enter_context(patch.object(hd.time, "sleep", self.clock.sleep))
        self.stack.enter_context(patch.object(hd, "require_herdr"))
        self.stack.enter_context(patch.object(hd, "assert_not_self"))
        self.stack.enter_context(patch.object(hd, "self_ids", return_value={
            "pane_id": "captain", "workspace_id": "ws", "tab_id": "tab",
        }))

    def agent(self, name="leaf", state="idle", seq=10):
        return {"name": name, "pane_id": name + "-pane", "agent": "pi",
                "agent_status": state, "state_change_seq": seq,
                "cwd": str(self.cwd / name), "tab_id": "workers"}

    def job(self, name="leaf", state="idle", delivery="unconfirmed", captain="captain"):
        generation = hd.begin_generation(self.cwd, name)
        return hd.put_job(self.cwd, name, {
            "pane_id": name + "-pane", "cwd": str(self.cwd / name),
            "kind": "pi", "role": "implementer", "model": "test-model",
            "tab_id": "workers", "brief": str(hd.job_dir(self.cwd, name) / "brief.md"),
            "captain_pane_id": captain, "status": state, "delivery": delivery,
            "baseline_seq": 10,
        }, generation=generation)

    def send_args(self, **overrides):
        return argparse.Namespace(**{
            "cwd": str(self.cwd), "name": "leaf", "message": "follow-up",
            "message_file": None, "force": False, "wait": False,
            "timeout": 3000, "lines": 20, **overrides,
        })

    def collect(self, name="leaf", wait=False):
        with patch.object(hd, "find_agent", return_value=self.agent(name, "done", 12)), \
             patch.object(hd, "fleet_snapshot", return_value=([self.agent(name, "done", 12)], None)), \
             patch.object(hd, "read_agent", return_value="The reply is ready."), \
             patch.object(hd, "emit") as emit:
            hd.cmd_collect(argparse.Namespace(cwd=str(self.cwd), name=name, wait=wait, timeout=5000, lines=20))
            return emit.call_args.args[0]

    def test_stalled_prompt_later_working_is_not_replayed(self):
        self.job()
        snapshots = [([self.agent()], None), ([self.agent(state="working", seq=11)], None)]
        with patch.object(hd, "prompt_agent", return_value={"ok": False, "error": {"code": "agent_prompt_stalled"}}) as prompt, \
             patch.object(hd, "fleet_snapshot", side_effect=snapshots):
            result = hd.submit_job(self.cwd, "leaf", "task", sync=False, timeout_ms=3000)
        self.assertEqual(prompt.call_count, 1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["delivery"], "confirmed")
        self.assertEqual(result["status"], "working")
        self.assertIsNone(result["error"])
        self.assertEqual(result["prompt_error"]["code"], "agent_prompt_stalled")

    def test_stalled_idle_stays_unconfirmed_and_blocks_resend_even_force(self):
        original = self.job()
        with patch.object(hd, "prompt_agent", return_value={"ok": False, "error": {"code": "timeout"}}) as prompt, \
             patch.object(hd, "fleet_snapshot", return_value=([self.agent()], None)):
            result = hd.submit_job(self.cwd, "leaf", "task", sync=False, timeout_ms=2000)
            self.assertFalse(result["ok"])
            self.assertEqual(result["delivery"], "unconfirmed")
            self.assertLessEqual(self.clock.value, 2)
            with patch.object(hd, "find_agent", return_value=self.agent()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    hd.cmd_send(self.send_args(force=True))
            self.assertEqual(prompt.call_count, 1)
        self.assertEqual(hd.expected_generation(self.cwd, "leaf"), original["generation"])

    def test_busy_followup_does_not_create_generation_or_submit(self):
        original = self.job(delivery="confirmed", state="working")
        with patch.object(hd, "find_agent", return_value=self.agent(state="working")), \
             patch.object(hd, "prompt_agent") as prompt, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                hd.cmd_send(self.send_args())
        prompt.assert_not_called()
        self.assertEqual(hd.expected_generation(self.cwd, "leaf"), original["generation"])

    def test_fast_completion_after_stall_is_recognized_by_sequence(self):
        record = self.job()
        result = hd.observe_job(self.cwd, "leaf", record, self.agent(state="done", seq=12))
        self.assertTrue(result["ok"])
        self.assertEqual(result["delivery"], "confirmed")

    def test_same_idle_sequence_is_not_completion(self):
        record = self.job()
        result = hd.observe_job(self.cwd, "leaf", record, self.agent(state="done"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["delivery"], "unconfirmed")

    def test_rejected_prompt_cannot_be_confirmed_by_unrelated_activity(self):
        record = self.job(delivery="rejected")
        result = hd.observe_job(self.cwd, "leaf", record, self.agent(state="working", seq=11))
        self.assertFalse(result["ok"])
        self.assertEqual(result["delivery"], "rejected")

    def test_missing_or_changed_pane_fails_closed(self):
        record = self.job(delivery="confirmed")
        for agent in [None, {**self.agent(state="done", seq=12), "pane_id": "different"}]:
            result = hd.observe_job(self.cwd, "leaf", record, agent)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "unknown")

    def test_spawn_persists_identity_before_prompt_failure(self):
        args = argparse.Namespace(cwd=str(self.cwd), name="leaf", kind="pi", model="test",
                                  role="implementer", message="task", message_file=None,
                                  worktree=True, args="", direction="right", start_timeout=1000,
                                  timeout=2000, lines=20)
        def prompt(*_args, **_kwargs):
            stored = hd.load_index(self.cwd)["jobs"]["leaf"]
            self.assertEqual(stored["cwd"], str(self.cwd / "leaf"))
            self.assertEqual(stored["pane_id"], "leaf-pane")
            self.assertEqual(stored["captain_pane_id"], "captain")
            self.assertTrue(Path(stored["brief"]).exists())
            return {"ok": False, "error": {"code": "agent_prompt_stalled"}}
        placement = hd.Placement(pane_id="leaf-pane", tab_id="workers", created_pane=True, created_tab=True)
        with patch.object(hd, "known_kinds", return_value={"pi"}), \
             patch.object(hd, "resolve_spawn_name", return_value="leaf"), \
             patch.object(hd, "maybe_worktree", return_value=self.cwd / "leaf"), \
             patch.object(hd, "place_worker_pane", return_value=placement), \
             patch.object(hd, "start_agent"), patch.object(hd, "rename_pane_quiet"), \
             patch.object(hd, "find_agent", side_effect=[None, self.agent()]), \
             patch.object(hd, "prompt_agent", side_effect=prompt) as submit, \
             patch.object(hd, "fleet_snapshot", return_value=([self.agent()], None)):
            result = hd.spawn(args, "assign")
        self.assertEqual(submit.call_count, 1)
        self.assertEqual(result["name"], "leaf")
        self.assertEqual(result["delivery"], "unconfirmed")
        self.assertIn("generation", result)

    def test_send_preserves_identity_collect_finds_only_new_worktree_report(self):
        initial = self.job(delivery="confirmed", state="done")
        report = hd.job_dir(self.cwd / "leaf", "leaf") / "result.md"
        report.write_text("old answer")
        os.utime(report, (1, 1))
        hd.put_job(self.cwd, "leaf", {"deliverable": str(report), "error": "old error",
                                     "collected_at": "yesterday"}, generation=initial["generation"])
        with patch.object(hd, "find_agent", return_value=self.agent()), \
             patch.object(hd, "prompt_agent", return_value={"ok": True}), \
             patch.object(hd, "fleet_snapshot", return_value=([self.agent(state="working", seq=11)], None)), \
             patch.object(hd, "emit"):
            hd.cmd_send(self.send_args())
        sent = hd.load_index(self.cwd)["jobs"]["leaf"]
        for key in ("cwd", "pane_id", "kind", "model", "role", "brief", "captain_pane_id"):
            self.assertEqual(sent[key], initial[key])
        self.assertNotEqual(sent["generation"], initial["generation"])
        self.assertNotIn("deliverable", sent)
        self.assertNotIn("collected_at", sent)
        self.assertIsNone(hd.find_deliverable(self.cwd, "leaf", None, self.cwd / "leaf"))
        report.write_text("# New answer\nverified")
        result = self.collect(wait=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["deliverable"], str(report.resolve()))
        self.assertEqual(report.read_text(), "# New answer\nverified")
        self.assertEqual(self.clock.value, 0, "already done should not wait 120 seconds")

    def test_old_observation_cannot_replace_new_generation(self):
        old = self.job()
        new = self.job()
        hd.observe_job(self.cwd, "leaf", old, self.agent(state="working", seq=11))
        self.assertEqual(hd.load_index(self.cwd)["jobs"]["leaf"], new)

    def test_dump_is_not_published_as_report_on_second_collect(self):
        self.job(delivery="confirmed", state="done")
        self.assertIsNone(self.collect()["deliverable"])
        self.assertIsNone(self.collect()["deliverable"])

    def test_observation_transport_failure_keeps_recoverable_identity(self):
        initial = self.job()
        with patch.object(hd, "prompt_agent", return_value={"ok": False, "error": {"code": "timeout"}}), \
             patch.object(hd, "fleet_snapshot", return_value=([], "probe timed out")):
            result = hd.submit_job(self.cwd, "leaf", "task", sync=False, timeout_ms=3000)
        self.assertFalse(result["ok"])
        self.assertEqual(result["delivery"], "unconfirmed")
        self.assertEqual(result["cwd"], initial["cwd"])
        self.assertEqual(result["error"], "probe timed out")

    def test_fleet_detects_completion_and_block_while_another_works(self):
        for name in ["slow", "ready", "blocked"]:
            self.job(name, state="working", delivery="confirmed")
        self.job("foreign", state="working", delivery="confirmed", captain="other")
        snapshots = [
            ([self.agent(n, "working", 11) for n in ["slow", "ready", "blocked"]], None),
            ([self.agent("slow", "working", 11), self.agent("ready", "done", 12), self.agent("blocked", "blocked", 12)], None),
        ]
        args = argparse.Namespace(cwd=str(self.cwd), name=None, timeout=30000, interval=2000)
        with patch.object(hd, "fleet_snapshot", side_effect=snapshots) as snapshot, \
             patch.object(hd, "emit") as emit, patch.object(hd, "prompt_agent") as prompt:
            hd.cmd_watch(args)
        result = emit.call_args.args[0]
        self.assertEqual(snapshot.call_count, 2, "one probe for the whole fleet per cycle")
        self.assertEqual(set(result["changed"]), {"ready", "blocked"})
        self.assertEqual({r["name"]: r["action"] for r in result["jobs"]},
                         {"slow": "wait", "ready": "collect", "blocked": "inspect"})
        self.assertEqual(self.clock.value, 2)
        prompt.assert_not_called()

    def test_watch_timeout_is_bounded_and_does_not_resubmit(self):
        self.job()
        with patch.object(hd, "fleet_snapshot", return_value=([self.agent()], None)), \
             patch.object(hd, "emit") as emit:
            hd.cmd_watch(argparse.Namespace(cwd=str(self.cwd), name=["leaf"], timeout=3000, interval=2000))
        result = emit.call_args.args[0]
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["jobs"][0]["delivery"], "unconfirmed")
        self.assertEqual(self.clock.value, 3)

    def test_watch_probe_failure_is_not_missing_workers(self):
        before = self.job()
        with patch.object(hd, "fleet_snapshot", return_value=([], "server unavailable")), patch.object(hd, "emit") as emit:
            hd.cmd_watch(argparse.Namespace(cwd=str(self.cwd), name=["leaf"], timeout=3000, interval=2000))
        self.assertFalse(emit.call_args.args[0]["ok"])
        self.assertEqual(hd.load_index(self.cwd)["jobs"]["leaf"], before)

    def test_parallel_job_updates_and_layout_writes_survive(self):
        def update(i):
            for n in range(10):
                hd.put_job(self.cwd, f"leaf-{i}", {"status": str(n)}, generation=f"gen-{i}")
                hd.save_layout_entry(self.cwd, f"layout-{i}", {"tabs": []}, "ws", "captain")
                hd.load_index(self.cwd)  # Must never observe half-written JSON.
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(update, range(4)))
        index = hd.load_index(self.cwd)
        self.assertEqual(len(index["jobs"]), 4)
        self.assertEqual(len(index["layouts"]), 4)
        self.assertTrue(all(r["status"] == "9" for r in index["jobs"].values()))

    def test_prompt_transport_timeout_is_uncertain_not_retried(self):
        with patch.object(hd.subprocess, "run", side_effect=subprocess.TimeoutExpired("herdr", 1)) as run:
            result = hd.prompt_agent("leaf", "task", True, 1000)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "prompt_transport_unknown")
        self.assertEqual(run.call_count, 1)

    def test_legacy_send_record_recovers_worktree_without_new_prompt(self):
        hd.put_job(self.cwd, "leaf", {"ok": True, "status": "working", "mode": "send_message"}, generation="legacy")
        report = hd.job_dir(self.cwd / "leaf", "leaf") / "result.md"
        report.write_text("# Legacy worker report")
        result = self.collect()
        self.assertTrue(result["ok"])
        self.assertEqual(Path(result["cwd"]).resolve(), (self.cwd / "leaf").resolve())
        self.assertEqual(result["deliverable"], str(report.resolve()))

    def test_out_of_order_observation_does_not_downgrade_confirmation(self):
        original = self.job()
        hd.observe_job(self.cwd, "leaf", original, self.agent(state="working", seq=11))
        hd.observe_job(self.cwd, "leaf", original, self.agent(state="idle", seq=10))
        result = hd.load_index(self.cwd)["jobs"]["leaf"]
        self.assertEqual(result["delivery"], "confirmed")
        self.assertEqual(result["status"], "working")
        self.assertTrue(result["ok"])

    def test_success_exit_with_malformed_prompt_json_is_unconfirmed(self):
        with patch.object(hd.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "not json", "")):
            result = hd.prompt_agent("leaf", "task", True, 1000)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_prompt_response")

    def test_explicit_blocked_rejection_is_recorded_without_replay(self):
        self.job()
        with patch.object(hd, "prompt_agent", return_value={"ok": False, "error": {"code": "agent_blocked"}}) as prompt, \
             patch.object(hd, "fleet_snapshot", return_value=([self.agent(state="blocked", seq=11)], None)):
            result = hd.submit_job(self.cwd, "leaf", "task", sync=False, timeout_ms=3000)
        self.assertEqual(result["delivery"], "rejected")
        self.assertFalse(result["ok"])
        self.assertEqual(prompt.call_count, 1)

    def test_real_cli_send_watch_collect_with_fake_herdr_transport(self):
        self.job(state="done", delivery="confirmed")
        fixture = self.cwd / "fake-state.json"
        fixture.write_text(json.dumps({"worker": self.agent(), "prompts": 0}))
        binary = self.cwd / "bin" / "herdr"
        binary.parent.mkdir()
        binary.write_text("#!/usr/bin/env python3\n" + r'''import json, os, sys
from pathlib import Path
path = Path(os.environ["HERDR_TEST_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
if args[:2] == ["agent", "list"]:
    print(json.dumps({"result": {"agents": [state["worker"]]}}))
elif args[:2] == ["agent", "prompt"]:
    state["prompts"] += 1
    state["worker"]["agent_status"] = "working"
    state["worker"]["state_change_seq"] = 11
    path.write_text(json.dumps(state))
    print(json.dumps({"error": {"code": "agent_prompt_stalled", "message": "late status"}}))
    sys.exit(1)
elif args[:2] == ["agent", "read"]:
    print("Finished. Report is in the worker job directory.")
else:
    print(json.dumps({"error": {"code": "unexpected_command", "args": args}}))
    sys.exit(1)
''')
        binary.chmod(0o755)
        env = {**os.environ, "PATH": str(binary.parent) + os.pathsep + os.environ["PATH"],
               "HERDR_ENV": "1", "HERDR_PANE_ID": "captain", "HERDR_WORKSPACE_ID": "ws",
               "HERDR_TEST_STATE": str(fixture)}
        cli = str(Path(__file__).with_name("herd-dispatch"))
        def invoke(*args):
            proc = subprocess.run([sys.executable, cli, *args, "--cwd", str(self.cwd)],
                                  env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        sent = invoke("send", "--name", "leaf", "--message", "follow-up", "--timeout", "3000")
        self.assertEqual(sent["delivery"], "confirmed")
        self.assertEqual(sent["status"], "working")
        report = hd.job_dir(self.cwd / "leaf", "leaf") / "result.md"
        report.write_text("# Done\nTargeted tests passed.")
        state = json.loads(fixture.read_text())
        state["worker"].update(agent_status="done", state_change_seq=12)
        fixture.write_text(json.dumps(state))
        watched = invoke("watch", "--name", "leaf", "--timeout", "1000")
        self.assertEqual(watched["jobs"][0]["action"], "collect")
        collected = invoke("collect", "--name", "leaf", "--wait", "--timeout", "1000")
        self.assertTrue(collected["ok"])
        self.assertEqual(collected["deliverable"], str(report.resolve()))
        self.assertEqual(json.loads(fixture.read_text())["prompts"], 1)


if __name__ == "__main__":
    unittest.main()
