import json
from pathlib import Path

from marketentry.history import delete_mission, load_history, record_mission, remove_entry
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


def test_delete_mission_removes_folder_and_entry(tmp_path):
    out = tmp_path / "outputs" / "m2"
    result = run_mission(BRIEF, out, sample=True)
    assert (out / "mission_result.json").exists()
    assert load_history(out)
    assert delete_mission(out, result["mission_id"]) is True
    assert not out.exists()
    assert load_history(out) == []
    # Guard: a folder outside outputs/ is never deleted.
    other = tmp_path / "safe"
    other.mkdir()
    (other / "mission_result.json").write_text('{"mission_id": "x"}', encoding="utf-8")
    assert delete_mission(other, "x") is False
    assert other.exists()
