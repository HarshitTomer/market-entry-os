import json
from pathlib import Path

from marketentry.history import load_history, record_mission, remove_entry
from marketentry.mission import run_mission

BRIEF = ("We sell cybersecurity compliance software for financial technology companies. "
         "Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees. "
         "Estimate using a £12,000 annual contract value.")


def test_history_record_load_remove(tmp_path):
    out = tmp_path / "outputs" / "m1"
    result = run_mission(BRIEF, out, sample=True)
    entries = load_history(out)
    assert len(entries) == 1
    assert entries[0]["mission_id"] == result["mission_id"]
    assert entries[0]["product_name"] and entries[0]["out_dir"] == str(out.resolve())
    # Re-recording the same mission does not duplicate it.
    record_mission(out, BRIEF, result)
    assert len(load_history(out)) == 1
    assert remove_entry(out, result["mission_id"]) is True
    assert load_history(out) == []


def test_history_survives_missing_file(tmp_path):
    assert load_history(tmp_path / "nope" / "m") == []
