"""Atomic job bookkeeping shared by dispatch and fleet monitoring."""
from __future__ import annotations

import fcntl
import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# These identify the worker; everything else belongs to one prompt attempt.
JOB_IDENTITY = frozenset({
    "name", "kind", "role", "model", "pane_id", "tab_id", "cwd", "brief",
    "captain_pane_id", "workspace_id",
})

def store_dir(cwd: Path) -> Path:
    d = cwd / ".herd-dispatch"
    d.mkdir(parents=True, exist_ok=True)
    (d / "jobs").mkdir(exist_ok=True)
    gitignore = d / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")
    return d


def load_index(cwd: Path) -> dict[str, Any]:
    path = store_dir(cwd) / "index.json"
    if not path.exists():
        return {"jobs": {}}
    return json.loads(path.read_text())


def save_index(cwd: Path, index: dict[str, Any]) -> None:
    path = store_dir(cwd) / "index.json"
    temporary = path.with_name(f".index-{secrets.token_hex(8)}.tmp")
    try:
        temporary.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def job_dir(cwd: Path, name: str) -> Path:
    d = store_dir(cwd) / "jobs" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def sidecar_path(cwd: Path, name: str) -> Path:
    return job_dir(cwd, name) / "result.json"


def generation_path(cwd: Path, name: str) -> Path:
    return job_dir(cwd, name) / "generation"


@contextmanager
def index_lock(cwd: Path):
    with (store_dir(cwd) / "index.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def job_lock(cwd: Path, name: str):
    # Submitters and collectors serialize per job; fleet observations remain available.
    with (job_dir(cwd, name) / "submit.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def begin_generation(cwd: Path, name: str) -> str:
    with index_lock(cwd):
        index = load_index(cwd)
        jobs = index.setdefault("jobs", {})
        previous = jobs.get(name) or {}
        gen = secrets.token_hex(8)
        jobs[name] = {k: v for k, v in previous.items() if k in JOB_IDENTITY}
        jobs[name].update(name=name, generation=gen, delivery="unconfirmed", ok=False)
        generation_path(cwd, name).write_text(gen + "\n")
        save_index(cwd, index)
        return gen


def expected_generation(cwd: Path, name: str) -> str | None:
    record = load_index(cwd).get("jobs", {}).get(name) or {}
    if record.get("generation"):
        return str(record["generation"])
    path = generation_path(cwd, name)
    return (path.read_text().strip() or None) if path.exists() else None


def put_job(
    cwd: Path, name: str, record: dict[str, Any], *, generation: str | None
) -> dict[str, Any]:
    with index_lock(cwd):
        index = load_index(cwd)
        jobs = index.setdefault("jobs", {})
        previous = jobs.get(name) or {}
        # An old collect/watch must not overwrite a newer prompt attempt.
        current = generation_path(cwd, name)
        if current.exists() and current.read_text().strip() != generation:
            return {**previous, "ok": False, "error": "generation superseded; collect the current attempt"}
        if generation and previous.get("generation") != generation:
            previous = {k: v for k, v in previous.items() if k in JOB_IDENTITY}
        update = dict(record)
        old_seq, new_seq = previous.get("state_change_seq"), update.get("state_change_seq")
        if isinstance(old_seq, int) and isinstance(new_seq, int) and new_seq < old_seq:
            for key in ("status", "delivery", "ok", "error", "state_change_seq"):
                update.pop(key, None)
        if previous.get("delivery") == "confirmed" and update.get("delivery") == "unconfirmed":
            update["delivery"] = "confirmed"
            for key in ("ok", "error"):
                update.pop(key, None)
        merged = {**previous, **update, "name": name}
        if generation:
            merged["generation"] = generation
        jobs[name] = merged
        save_index(cwd, index)
        return merged
