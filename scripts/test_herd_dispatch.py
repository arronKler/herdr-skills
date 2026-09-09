#!/usr/bin/env python3
"""Unit tests for reply harvest and ok verdict (no live herdr required)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

hd = SourceFileLoader(
    "herd_dispatch",
    str(Path(__file__).resolve().parent / "herd-dispatch"),
).load_module()


TUI_DUMP = """
╭─────────────────────────────────────────────────╮
│ >_ OpenAI Codex
╰─────────────────────────────────────────────────╯

  I am Composer, running composer-2.5.
  Wrote the long answer to notes/who.md.

─ Worked for 4m 19s ────────────────────────────────
› Ask Codex to do anything
"""


class ReplyHarvestTests(unittest.TestCase):
    def test_excerpt_unwraps_tui_and_cuts_composer(self) -> None:
        block = hd.excerpt_reply(TUI_DUMP)
        self.assertIsNotNone(block)
        assert block is not None
        self.assertIn("I am Composer", block)
        self.assertIn("notes/who.md", block)
        self.assertNotIn("Ask Codex", block)

    def test_harvest_is_the_pane_reply(self) -> None:
        harvested = hd.harvest_reply(TUI_DUMP)
        self.assertEqual(harvested["result_source"], "pane")
        self.assertIn("composer-2.5", harvested["result_excerpt"] or "")
        self.assertNotIn("deliverable", harvested)

    def test_empty_pane_has_no_reply(self) -> None:
        harvested = hd.harvest_reply("")
        self.assertIsNone(harvested["result_excerpt"])
        self.assertIsNone(harvested["result_source"])

    def test_job_reply_md_is_deliverable_even_when_pane_wraps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "board-ux-pi"
            job = hd.job_dir(cwd, name)
            (job / "brief.md").write_text("brief\n")
            (job / "reply.md").write_text("# 拍板\n必须改 chip 行\n")
            harvested = hd.harvest_reply(
                "oint,\nand the sema ntics\nwrite reply.md\n",
                cwd=cwd,
                name=name,
            )
            self.assertEqual(harvested["result_source"], "file")
            self.assertEqual(
                Path(harvested["deliverable"]), (job / "reply.md").resolve()
            )

    def test_named_report_path_is_deliverable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "who-cursor"
            job = hd.job_dir(cwd, name)
            (job / "brief.md").write_text("brief\n")
            notes = cwd / "notes" / "who.md"
            notes.parent.mkdir()
            notes.write_text("I am Composer, running composer-2.5.\n")
            harvested = hd.harvest_reply(
                TUI_DUMP, cwd=cwd, name=name, work_cwd=cwd
            )
            self.assertEqual(harvested["result_source"], "file")
            self.assertEqual(Path(harvested["deliverable"]), notes.resolve())

    def test_source_file_mention_is_not_deliverable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "rev"
            job = hd.job_dir(cwd, name)
            (job / "brief.md").write_text("brief\n")
            src = cwd / "pwa" / "src" / "lib" / "dashboard.ts"
            src.parent.mkdir(parents=True)
            src.write_text("export const x = 1\n")
            harvested = hd.harvest_reply(
                "See pwa/src/lib/dashboard.ts:10 for the leak.",
                cwd=cwd,
                name=name,
                work_cwd=cwd,
            )
            self.assertNotIn("deliverable", harvested)
            self.assertEqual(harvested["result_source"], "pane")

    def test_tui_result_md_is_not_deliverable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "git-status"
            job = hd.job_dir(cwd, name)
            (job / "brief.md").write_text("brief\n")
            (job / "result.md").write_text(TUI_DUMP)
            harvested = hd.harvest_reply(TUI_DUMP, cwd=cwd, name=name)
            self.assertNotIn("deliverable", harvested)

    def test_worker_result_md_kept_and_dump_goes_to_pane_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "impl-wait-unknown"
            job = hd.job_dir(cwd, name)
            (job / "brief.md").write_text("brief\n")
            (job / "result.md").write_text(
                "# impl-wait-unknown\nUnknown is not idle.\n"
            )
            harvested = hd.harvest_reply(
                "Wrote .herd-dispatch/jobs/impl-wait-unknown/result.md",
                cwd=cwd,
                name=name,
            )
            self.assertTrue(
                harvested["deliverable"].endswith("result.md"),
                harvested.get("deliverable"),
            )
            dump = hd.write_pane_dump(job, TUI_DUMP, harvested.get("deliverable"))
            self.assertEqual(dump.name, "pane.md")
            self.assertIn("Unknown is not idle", (job / "result.md").read_text())
            self.assertIn("OpenAI Codex", dump.read_text())

    def test_stale_reply_from_prior_turn_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "rev"
            job = hd.job_dir(cwd, name)
            stale = job / "reply.md"
            stale.write_text("old verdict\n")
            os.utime(stale, (stale.stat().st_atime, stale.stat().st_mtime - 10))
            (job / "brief.md").write_text("new brief\n")
            harvested = hd.harvest_reply("still thinking", cwd=cwd, name=name)
            self.assertNotIn("deliverable", harvested)

    def test_sidecar_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "rev"
            path = hd.sidecar_path(cwd, name)
            path.write_text(json.dumps({"status": "ok", "notes": "sidecar"}))
            harvested = hd.harvest_reply(TUI_DUMP)
            self.assertEqual(harvested["result_source"], "pane")
            self.assertNotIn("sidecar", harvested["result_excerpt"] or "")

    def test_wrap_brief_has_no_result_contract(self) -> None:
        text = hd.wrap_brief("Who are you?", cwd=Path("/tmp/work"), role="identity")
        self.assertIn("Who are you?", text)
        self.assertIn("Role: identity", text)
        self.assertIn("/tmp/work", text)
        self.assertNotIn("RESULT", text)
        self.assertNotIn("result.json", text)
        self.assertNotIn("generation", text)

    def test_put_job_replaces_stale_fields_on_new_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            name = "git-status"
            hd.put_job(
                cwd,
                name,
                {
                    "mode": "handoff",
                    "created_at": "2026-09-03T04:22:44Z",
                    "collected_at": "2026-09-03T04:22:44Z",
                    "ok": True,
                },
                generation="aaa",
            )
            record = hd.put_job(
                cwd,
                name,
                {
                    "mode": "handoff",
                    "created_at": "2026-09-03T06:08:38Z",
                    "finished_at": "2026-09-03T06:09:41Z",
                    "ok": True,
                },
                generation="bbb",
            )
            self.assertEqual(record["generation"], "bbb")
            self.assertEqual(record["created_at"], "2026-09-03T06:08:38Z")
            self.assertNotIn("collected_at", record)


class VerdictTests(unittest.TestCase):
    def test_sync_unknown_is_not_ok(self) -> None:
        ok, err = hd.verdict("unknown", sync=True)
        self.assertFalse(ok)
        self.assertIn("unknown", err or "")

    def test_sync_idle_is_ok(self) -> None:
        ok, err = hd.verdict("idle", sync=True)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_sync_blocked_is_not_ok(self) -> None:
        ok, _err = hd.verdict("blocked", sync=True)
        self.assertFalse(ok)

    def test_assign_working_is_ok(self) -> None:
        ok, err = hd.verdict("working", sync=False)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_assign_idle_is_stalled(self) -> None:
        ok, err = hd.verdict("idle", sync=False)
        self.assertFalse(ok)
        self.assertIn("stalled", err or "")

    def test_kinds_parse_from_start_help_and_usage(self) -> None:
        help_text = (
            "      --kind <KIND>\n"
            "          [possible values: pi, claude, codex, grok]\n"
        )
        self.assertEqual(hd._parse_kinds(help_text), {"pi", "claude", "codex", "grok"})
        usage = "kinds: pi|claude|codex|maki\n"
        self.assertIn("maki", hd._parse_kinds(usage))


class ModelCatalogTests(unittest.TestCase):
    def test_kind_aliases(self) -> None:
        self.assertEqual(hd.resolve_kind("grok-build"), "grok")
        self.assertEqual(hd.resolve_kind("Grok Build"), "grok")
        self.assertEqual(hd.resolve_kind("cursor-agent"), "cursor")
        self.assertEqual(hd.resolve_kind("cursor"), "cursor")
        self.assertEqual(hd.kind_binary("cursor"), "cursor-agent")
        self.assertEqual(hd.kind_binary("grok"), "grok")

    def test_model_start_args(self) -> None:
        self.assertEqual(
            hd.merge_start_args("grok", "grok-4.5", ""),
            ["--model", "grok-4.5"],
        )
        self.assertEqual(
            hd.merge_start_args("cursor", "composer-2.5", "--trust"),
            ["--model", "composer-2.5", "--trust"],
        )
        self.assertEqual(hd.merge_start_args("grok", None, "--always-approve"), ["--always-approve"])

    def test_model_args_conflict(self) -> None:
        with self.assertRaises(SystemExit):
            hd.merge_start_args("grok", "grok-4.5", "--model grok-4.6")
        with self.assertRaises(SystemExit):
            hd.merge_start_args("droid", "some-model", "")

    def test_parse_grok_models(self) -> None:
        text = (
            "You are logged in with grok.com.\n\n"
            "Default model: grok-4.6\n\n"
            "Available models:\n"
            "  * grok-4.6 (default)\n"
            "  - grok-4.5\n"
        )
        parsed = hd.parse_grok_models(text)
        self.assertEqual(parsed["default"], "grok-4.6")
        self.assertEqual([m["id"] for m in parsed["models"]], ["grok-4.6", "grok-4.5"])
        self.assertTrue(parsed["models"][0]["default"])
        self.assertFalse(parsed["models"][1]["default"])

    def test_parse_cursor_models(self) -> None:
        text = (
            "Available models\n\n"
            "auto - Auto (default)\n"
            "composer-2.5 - Composer 2.5\n"
            "cursor-grok-4.6-high - Cursor Grok 4.6\n"
        )
        parsed = hd.parse_cursor_models(text)
        self.assertEqual(parsed["default"], "auto")
        self.assertEqual(parsed["models"][0]["id"], "auto")
        self.assertEqual(parsed["models"][1]["id"], "composer-2.5")
        self.assertEqual(parsed["models"][2]["label"], "Cursor Grok 4.6")

    def test_parse_codex_models_json_and_hidden(self) -> None:
        raw = (
            'ERROR: TERM is set to "dumb".\n'
            '{"models":[{"slug":"gpt-5.4","display_name":"GPT-5.4","is_default":true},'
            '{"slug":"gpt-reserve","display_name":"GPT-Reserve","visibility":"hide"}]}'
        )
        parsed = hd.parse_codex_models(raw)
        self.assertEqual(parsed["default"], "gpt-5.4")
        by_id = {m["id"]: m for m in parsed["models"]}
        self.assertTrue(by_id["gpt-5.4"]["default"])
        self.assertTrue(by_id["gpt-reserve"]["hidden"])

    def test_parse_pi_models_provider_id(self) -> None:
        text = (
            "provider            model                              context\n"
            "ark                 deepseek-v4-flash                  1.0M\n"
            "deepseek            deepseek-v4-pro                    1M\n"
        )
        parsed = hd.parse_pi_models(text)
        self.assertEqual(
            [m["id"] for m in parsed["models"]],
            ["ark/deepseek-v4-flash", "deepseek/deepseek-v4-pro"],
        )

    def test_parse_claude_not_logged_in(self) -> None:
        with self.assertRaises(ValueError):
            hd.parse_claude_models("Not logged in · Please run /login")

    def test_probe_without_recipe(self) -> None:
        payload = hd.probe_models("droid")
        self.assertFalse(payload["ok"])
        self.assertIn("no model catalog probe", payload["error"])


class GeometryTests(unittest.TestCase):
    def test_post_split_right_and_down(self) -> None:
        self.assertEqual(hd.post_split_size(80, 24, "right"), ((40, 24), (40, 24)))
        self.assertEqual(hd.post_split_size(80, 24, "down"), ((80, 12), (80, 12)))
        left, right = hd.post_split_size(213, 60, "right")
        self.assertEqual(left[0] + right[0], 213)
        self.assertTrue(hd.split_fits(80, 24, "right"))
        self.assertFalse(hd.split_fits(79, 24, "right"))
        self.assertFalse(hd.split_fits(80, 20, "down"))

    def test_pick_split_target_prefers_idle_and_skips_captain(self) -> None:
        captain = "wV:p1"
        panes = [
            {
                "pane_id": captain,
                "agent_status": "idle",
                "rect": {"width": 200, "height": 60},
            },
            {
                "pane_id": "wV:p2",
                "agent_status": "working",
                "rect": {"width": 120, "height": 60},
            },
            {
                "pane_id": "wV:p3",
                "agent_status": "idle",
                "rect": {"width": 80, "height": 60},
            },
        ]
        picked = hd.pick_split_target(panes, captain, "right")
        assert picked is not None
        self.assertEqual(picked["pane_id"], "wV:p3")

    def test_pick_split_target_caps_and_geometry(self) -> None:
        panes = [
            {
                "pane_id": f"wV:p{i}",
                "agent_status": "idle",
                "rect": {"width": 200, "height": 60},
            }
            for i in range(4)
        ]
        self.assertIsNone(hd.pick_split_target(panes, "captain", "right"))
        tight = [
            {
                "pane_id": "wV:p2",
                "agent_status": "idle",
                "rect": {"width": 50, "height": 24},
            }
        ]
        self.assertIsNone(hd.pick_split_target(tight, "captain", "right"))

    def test_worker_tab_label_and_layout_key(self) -> None:
        self.assertEqual(hd.worker_tab_label(0), "herd")
        self.assertEqual(hd.worker_tab_label(1), "herd-2")
        self.assertEqual(hd.layout_key("wV", "wV:p1D"), "wV:wV:p1D")
        self.assertEqual(hd.layout_key("", "wV:p1D"), "unknown:wV:p1D")

    def test_required_verbs_include_tabs(self) -> None:
        verbs = {" ".join(v) for v in hd.REQUIRED_VERBS}
        self.assertIn("tab create", verbs)
        self.assertIn("tab get", verbs)
        self.assertIn("pane layout", verbs)
        self.assertIn("pane list", verbs)


class ResolveNameTests(unittest.TestCase):
    def tearDown(self) -> None:
        if hasattr(self, "_orig_find"):
            hd.find_agent = self._orig_find
        if hasattr(self, "_orig_list"):
            hd.agent_list = self._orig_list

    def test_explicit_live_name_refuses(self) -> None:
        self._orig_find = hd.find_agent
        hd.find_agent = lambda name: {"name": name, "pane_id": "wV:p9"}
        with self.assertRaises(SystemExit):
            hd.resolve_spawn_name("rev-codex", "reviewer", "codex")

    def test_explicit_free_name_kept(self) -> None:
        self._orig_find = hd.find_agent
        hd.find_agent = lambda name: None
        self.assertEqual(
            hd.resolve_spawn_name("rev-codex", "reviewer", "codex"), "rev-codex"
        )

    def test_auto_name_suffixes(self) -> None:
        self._orig_find = hd.find_agent
        self._orig_list = hd.agent_list
        hd.find_agent = lambda name: None
        hd.agent_list = lambda: [{"name": "reviewer-codex"}]
        self.assertEqual(hd.resolve_spawn_name(None, "reviewer", "codex"), "reviewer-codex-2")


class FakeHerdr:
    def __init__(self, root_size: tuple[int, int] = (80, 24)) -> None:
        self.root_size = root_size
        self.seq = 20
        self.calls: list[list[str]] = []
        self.tabs = {
            "wV:tA": {
                "tab_id": "wV:tA",
                "workspace_id": "wV",
                "label": "herd",
                "pane_ids": ["wV:p1D", "wV:p1C"],
            }
        }
        self.panes = {
            "wV:p1D": {
                "pane_id": "wV:p1D",
                "tab_id": "wV:tA",
                "workspace_id": "wV",
                "agent": "grok",
                "agent_status": "working",
                "rect": {"width": 80, "height": 24, "x": 0, "y": 0},
            },
            "wV:p1C": {
                "pane_id": "wV:p1C",
                "tab_id": "wV:tA",
                "workspace_id": "wV",
                "agent": "pi",
                "agent_status": "idle",
                "rect": {"width": 80, "height": 24, "x": 80, "y": 0},
            },
        }

    def nid(self, prefix: str) -> str:
        self.seq += 1
        return f"wV:{prefix}{self.seq}"

    def occupy(self, pane_id: str, agent: str = "codex", status: str = "idle") -> None:
        self.panes[pane_id]["agent"] = agent
        self.panes[pane_id]["agent_status"] = status

    def herdr_json(self, args: list[str], timeout: float | None = None, quiet: bool = False):
        return self.handle(args)

    def herdr_json_soft(self, args: list[str], timeout: float | None = None):
        if args[:2] == ["tab", "get"] and args[-1] not in self.tabs:
            self.calls.append(list(args))
            return None
        if args[:2] == ["pane", "layout"]:
            pane_id = args[args.index("--pane") + 1] if "--pane" in args else ""
            if pane_id not in self.panes:
                self.calls.append(list(args))
                return None
        return self.handle(args)

    def handle(self, args: list[str]):
        self.calls.append(list(args))
        if args[:2] == ["pane", "list"]:
            return {"result": {"panes": list(self.panes.values()), "type": "pane_list"}}
        if args[:2] == ["tab", "create"]:
            return self.create_tab(args)
        if args[:2] == ["pane", "split"]:
            return self.split(args)
        if args[:2] == ["pane", "close"]:
            return self.close(args[2])
        if args[:2] == ["pane", "rename"]:
            return {"ok": True}
        if args[:2] == ["tab", "get"]:
            tab = self.tabs[args[2]]
            return {
                "result": {
                    "tab": {
                        "tab_id": tab["tab_id"],
                        "workspace_id": tab["workspace_id"],
                        "label": tab.get("label"),
                        "pane_count": len(tab["pane_ids"]),
                    }
                }
            }
        if args[:2] == ["pane", "layout"]:
            pane_id = args[args.index("--pane") + 1]
            tab_id = self.panes[pane_id]["tab_id"]
            members = [
                self.panes[pid]
                for pid in self.tabs[tab_id]["pane_ids"]
                if pid in self.panes
            ]
            return {
                "result": {
                    "layout": {
                        "tab_id": tab_id,
                        "panes": [
                            {"pane_id": p["pane_id"], "rect": p["rect"]} for p in members
                        ],
                    }
                }
            }
        raise AssertionError(f"unexpected herdr call {args}")

    def create_tab(self, args: list[str]):
        if "--current" in args:
            raise AssertionError("tab create must not use --current")
        if "--no-focus" not in args:
            raise AssertionError("tab create must pass --no-focus")
        tab_id = self.nid("t")
        pane_id = self.nid("p")
        label = args[args.index("--label") + 1]
        width, height = self.root_size
        self.tabs[tab_id] = {
            "tab_id": tab_id,
            "workspace_id": "wV",
            "label": label,
            "pane_ids": [pane_id],
        }
        self.panes[pane_id] = {
            "pane_id": pane_id,
            "tab_id": tab_id,
            "workspace_id": "wV",
            "agent": None,
            "agent_status": "unknown",
            "rect": {"width": width, "height": height, "x": 0, "y": 0},
        }
        return {
            "result": {
                "tab": {"tab_id": tab_id, "workspace_id": "wV", "label": label},
                "root_pane": {"pane_id": pane_id},
            }
        }

    def split(self, args: list[str]):
        if "--current" in args:
            raise AssertionError("pane split must not use --current")
        if "--no-focus" not in args:
            raise AssertionError("pane split must pass --no-focus")
        target = args[2]
        direction = args[args.index("--direction") + 1]
        src = self.panes[target]
        width, height = src["rect"]["width"], src["rect"]["height"]
        first, second = hd.post_split_size(width, height, direction)
        src["rect"]["width"], src["rect"]["height"] = first
        new_id = self.nid("p")
        self.panes[new_id] = {
            "pane_id": new_id,
            "tab_id": src["tab_id"],
            "workspace_id": "wV",
            "agent": None,
            "agent_status": "unknown",
            "rect": {"width": second[0], "height": second[1], "x": 0, "y": 0},
        }
        self.tabs[src["tab_id"]]["pane_ids"].append(new_id)
        return {"result": {"pane": {"pane_id": new_id}}}

    def close(self, pane_id: str):
        self.panes.pop(pane_id, None)
        for tab in self.tabs.values():
            tab["pane_ids"] = [p for p in tab["pane_ids"] if p != pane_id]
        return {"ok": True}


class PlacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.backend = FakeHerdr()
        self._orig_json = hd.herdr_json
        self._orig_soft = hd.herdr_json_soft
        self._orig_self = hd.self_ids
        hd.herdr_json = self.backend.herdr_json
        hd.herdr_json_soft = self.backend.herdr_json_soft
        hd.self_ids = lambda: {
            "pane_id": "wV:p1D",
            "workspace_id": "wV",
            "tab_id": "wV:tA",
        }

    def tearDown(self) -> None:
        hd.herdr_json = self._orig_json
        hd.herdr_json_soft = self._orig_soft
        hd.self_ids = self._orig_self
        self.tmp.cleanup()

    def _no_current(self) -> None:
        for args in self.backend.calls:
            self.assertNotIn("--current", args)

    def test_first_worker_creates_owned_tab_not_captain_split(self) -> None:
        placed = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.assertTrue(placed.created_tab)
        creates = [c for c in self.backend.calls if c[:2] == ["tab", "create"]]
        splits = [c for c in self.backend.calls if c[:2] == ["pane", "split"]]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0][creates[0].index("--label") + 1], "herd")
        self.assertIn("--workspace", creates[0])
        self.assertEqual(splits, [])
        self.assertNotEqual(placed.tab_id, "wV:tA")
        self.assertNotEqual(placed.pane_id, "wV:p1D")
        index = hd.load_index(self.cwd)
        entry = index["layouts"]["wV:wV:p1D"]
        self.assertEqual(entry["tabs"][0]["tab_id"], placed.tab_id)
        self._no_current()

    def test_does_not_adopt_foreign_tab_labeled_herd(self) -> None:
        placed = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.assertNotEqual(placed.tab_id, "wV:tA")
        self.assertTrue(self.backend.panes["wV:p1C"]["agent"])

    def test_empty_owned_shell_is_reused(self) -> None:
        first = hd.place_worker_pane(self.cwd, self.cwd, "right")
        second = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.assertEqual(first.pane_id, second.pane_id)
        self.assertFalse(second.created_pane)
        splits = [c for c in self.backend.calls if c[:2] == ["pane", "split"]]
        self.assertEqual(splits, [])

    def test_second_worker_tiles_on_owned_tab(self) -> None:
        first = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.backend.occupy(first.pane_id)
        second = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.assertEqual(second.tab_id, first.tab_id)
        self.assertTrue(second.created_pane)
        self.assertFalse(second.created_tab)
        splits = [c for c in self.backend.calls if c[:2] == ["pane", "split"]]
        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0][2], first.pane_id)
        self._no_current()

    def test_geometry_overflow_creates_next_tab(self) -> None:
        first = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.backend.occupy(first.pane_id)
        second = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.backend.occupy(second.pane_id)
        third = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.assertTrue(third.created_tab)
        self.assertNotEqual(third.tab_id, first.tab_id)
        creates = [c for c in self.backend.calls if c[:2] == ["tab", "create"]]
        self.assertEqual(creates[-1][creates[-1].index("--label") + 1], "herd-2")

    def test_stale_pointer_degrades_to_create(self) -> None:
        hd.save_layout_entry(
            self.cwd,
            "wV:wV:p1D",
            {
                "tabs": [
                    {
                        "tab_id": "wV:tDEAD",
                        "root_pane_id": "wV:pDEAD",
                        "pane_ids": ["wV:pDEAD"],
                    }
                ]
            },
            "wV",
            "wV:p1D",
        )
        placed = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.assertTrue(placed.created_tab)
        self.assertNotEqual(placed.tab_id, "wV:tDEAD")
        entry = hd.load_index(self.cwd)["layouts"]["wV:wV:p1D"]
        ids = [t["tab_id"] for t in entry["tabs"]]
        self.assertNotIn("wV:tDEAD", ids)

    def test_rollback_closes_created_pane(self) -> None:
        placed = hd.place_worker_pane(self.cwd, self.cwd, "right")
        hd.rollback_placement(self.cwd, placed)
        self.assertNotIn(placed.pane_id, self.backend.panes)
        entry = hd.load_index(self.cwd)["layouts"]["wV:wV:p1D"]
        self.assertEqual(entry["tabs"], [])

    def test_tab_create_failure_does_not_split_captain(self) -> None:
        def boom(args, timeout=None, quiet=False):
            self.backend.calls.append(list(args))
            if args[:2] == ["tab", "create"]:
                hd.die("tab create failed")
            return FakeHerdr.handle(self.backend, args)

        hd.herdr_json = boom
        with self.assertRaises(SystemExit):
            hd.place_worker_pane(self.cwd, self.cwd, "right")
        splits = [c for c in self.backend.calls if c[:2] == ["pane", "split"]]
        self.assertEqual(splits, [])
        self._no_current()

    def test_is_empty_shell_rejects_foreign_captain(self) -> None:
        pane = {
            "pane_id": "wV:p1C",
            "agent": "pi",
            "agent_status": "idle",
        }
        self.assertFalse(hd.is_empty_shell(pane, "wV:p1D"))
        empty = {"pane_id": "wV:p9", "agent_status": "unknown"}
        self.assertTrue(hd.is_empty_shell(empty, "wV:p1D"))

    def test_put_job_preserves_layouts(self) -> None:
        hd.place_worker_pane(self.cwd, self.cwd, "right")
        hd.put_job(
            self.cwd,
            "rev-codex",
            {"ok": True, "mode": "assign"},
            generation="abc",
        )
        index = hd.load_index(self.cwd)
        self.assertIn("layouts", index)
        self.assertIn("wV:wV:p1D", index["layouts"])
        self.assertEqual(index["jobs"]["rev-codex"]["generation"], "abc")

    def test_four_wide_panes_overflow_to_new_tab(self) -> None:
        self.backend.root_size = (200, 60)
        first = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.backend.occupy(first.pane_id)
        for _ in range(3):
            placed = hd.place_worker_pane(self.cwd, self.cwd, "right")
            self.assertEqual(placed.tab_id, first.tab_id)
            self.backend.occupy(placed.pane_id)
        fifth = hd.place_worker_pane(self.cwd, self.cwd, "right")
        self.assertTrue(fifth.created_tab)
        self.assertNotEqual(fifth.tab_id, first.tab_id)


if __name__ == "__main__":
    unittest.main()
