"""Local SQLite CRM. Idempotent: re-running a mission never duplicates
an account or a contact (unique on mission + canonical id / domain)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions(
  id TEXT PRIMARY KEY, raw_prompt TEXT, normalized_brief_json TEXT,
  status TEXT, started_at TEXT, finished_at TEXT, warnings_json TEXT);
CREATE TABLE IF NOT EXISTS companies(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT,
  crustdata_company_id TEXT, domain TEXT, normalized_json TEXT,
  fit_score INTEGER, coverage_score REAL, verification_status TEXT,
  UNIQUE(mission_id, crustdata_company_id));
CREATE TABLE IF NOT EXISTS people(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT,
  crustdata_person_id TEXT, company_id TEXT, normalized_json TEXT,
  verified_employment INTEGER,
  UNIQUE(mission_id, crustdata_person_id));
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT, subject_id TEXT,
  claim TEXT, source_type TEXT, source_pointer TEXT, field_path TEXT,
  retrieved_at TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS tool_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT, tool_name TEXT,
  request_hash TEXT, result_status TEXT, duration_ms INTEGER,
  credit_cost TEXT, error_type TEXT);
CREATE TABLE IF NOT EXISTS crm_tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT, company_id TEXT,
  task_type TEXT, title TEXT, status TEXT, draft_text TEXT,
  UNIQUE(mission_id, company_id, task_type));
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_company(conn, mission_id, company, fit_score, coverage, status):
    conn.execute(
        """INSERT INTO companies(mission_id, crustdata_company_id, domain,
             normalized_json, fit_score, coverage_score, verification_status)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(mission_id, crustdata_company_id) DO UPDATE SET
             normalized_json=excluded.normalized_json,
             fit_score=excluded.fit_score, coverage_score=excluded.coverage_score,
             verification_status=excluded.verification_status""",
        (mission_id, company.company_id, company.domain,
         json.dumps(company.__dict__, default=str), fit_score, coverage, status))
    conn.commit()


def upsert_person(conn, mission_id, person, verified: bool):
    conn.execute(
        """INSERT INTO people(mission_id, crustdata_person_id, company_id,
             normalized_json, verified_employment)
           VALUES(?,?,?,?,?)
           ON CONFLICT(mission_id, crustdata_person_id) DO UPDATE SET
             normalized_json=excluded.normalized_json,
             verified_employment=excluded.verified_employment""",
        (mission_id, person.person_id, person.company_id,
         json.dumps(person.__dict__, default=str), 1 if verified else 0))
    conn.commit()


def add_task(conn, mission_id, company_id, task_type, title, draft_text):
    conn.execute(
        """INSERT OR IGNORE INTO crm_tasks(mission_id, company_id, task_type,
             title, status, draft_text) VALUES(?,?,?,?, 'unsent_draft', ?)""",
        (mission_id, company_id, task_type, title, draft_text))
    conn.commit()
