"""Mission history: every run, in one place, so past queries are not lost
when the app restarts.

Storage: <outputs-dir>/history.json — a plain JSON list, newest first.
outputs/ is gitignored, so history stays local and is never committed.
A history write must never break a mission: callers wrap it, and this
module itself swallows I/O errors and returns False instead of raising.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def history_path_for(out_dir: str | Path) -> Path:
    """History lives next to the mission outputs, not inside one mission."""
    return Path(out_dir).resolve().parent / "history.json"


def load_history(out_dir: str | Path) -> list[dict]:
    try:
        data = json.loads(history_path_for(out_dir).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record_mission(out_dir: str | Path, raw_prompt: str, result: dict) -> bool:
    """Append one entry (deduplicated by mission_id), newest first, cap 200."""
    try:
        path = history_path_for(out_dir)
        entries = load_history(out_dir)
        entries = [e for e in entries if e.get("mission_id") != result.get("mission_id")]
        brief = result.get("brief", {}) or {}
        sizing = result.get("sizing", {}) or {}
        decision = result.get("decision", {}) or {}
        entries.insert(0, {
            "mission_id": result.get("mission_id"),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": result.get("mode"),
            "state": result.get("state"),
            "brief_text": (raw_prompt or "")[:500],
            "product_name": brief.get("product_name", ""),
            "target_country": brief.get("target_country", ""),
            "target_industry": brief.get("target_industry", ""),
            "verdict": decision.get("verdict", ""),
            "company_records": result.get("company_records", 0),
            "buyer_records": result.get("buyer_records", 0),
            "competitor_records": result.get("competitor_records", 0),
            "serviceable_annual_pool": sizing.get("serviceable_annual_pool"),
            "currency": sizing.get("currency", ""),
            "out_dir": str(Path(out_dir).resolve()),
        })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries[:200], indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def remove_entry(out_dir: str | Path, mission_id: str) -> bool:
    """Remove an entry from the list only — output files are left alone."""
    try:
        path = history_path_for(out_dir)
        entries = [e for e in load_history(out_dir) if e.get("mission_id") != mission_id]
        path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def delete_mission(out_dir: str | Path, mission_id: str) -> bool:
    """Permanently delete a research mission: its output folder AND its
    history entry. Safety guard: only delete a folder that actually
    contains that mission's mission_result.json and sits under an
    outputs/ directory, so a wrong path can never wipe an unrelated dir.
    Returns False (and deletes nothing) if the guard fails."""
    try:
        folder = Path(out_dir).resolve()
        if "outputs" not in folder.parts:
            return False
        result_path = folder / "mission_result.json"
        if not result_path.exists():
            return False
        data = json.loads(result_path.read_text(encoding="utf-8"))
        if data.get("mission_id") != mission_id:
            return False
        import shutil
        shutil.rmtree(folder)
        remove_entry(out_dir, mission_id)
        return True
    except Exception:
        return False
