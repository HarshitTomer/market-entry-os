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


def test_per_mission_folders_do_not_overwrite_each_other(tmp_path):
    """Regression for 'output folder is gone': two missions in two
    subfolders must both stay openable, and both must share one
    history file under outputs/."""
    from marketentry.history import history_path_for
    out1 = tmp_path / "outputs" / "streamlit-mission" / "mission_aaa"
    out2 = tmp_path / "outputs" / "streamlit-mission" / "mission_bbb"
    r1 = run_mission(BRIEF, out1, sample=True)
    r2 = run_mission(BRIEF, out2, sample=True)
    assert r1["mission_id"] != r2["mission_id"]
    assert history_path_for(out1) == history_path_for(out2) == tmp_path / "outputs" / "history.json"
    entries = load_history(out1)
    assert {e["mission_id"] for e in entries} == {r1["mission_id"], r2["mission_id"]}
    # Deleting one must not touch the other.
    assert delete_mission(out1, r1["mission_id"]) is True
    assert not out1.exists() and out2.exists()
    assert [e["mission_id"] for e in load_history(out2)] == [r2["mission_id"]]
