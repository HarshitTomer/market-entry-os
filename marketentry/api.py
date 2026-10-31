"""FastAPI surface (spec §9, recommended). Optional: only loaded when
fastapi is installed. Run: uvicorn marketentry.api:app --reload

POST /missions  {brief, sample} -> mission summary + artifact paths
GET  /missions/{id}/accounts, /evidence, /artifacts/{name}
Missions run synchronously (a hackathon mission is minutes, not hours)
and are stored under outputs/<mission_id>/.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from pydantic import BaseModel
except Exception:  # pragma: no cover - fastapi is optional
    FastAPI = None  # type: ignore

if FastAPI is not None:
    app = FastAPI(title="MarketEntryOS", version="1.1.0")
    _STORE: dict[str, dict] = {}

    class MissionRequest(BaseModel):
        brief: str
        sample: bool = False

    @app.post("/missions")
    def create_mission(req: MissionRequest):
        from .mission import run_mission
        out = Path("outputs") / "api-mission"
        result = run_mission(req.brief, out, api_key=os.environ.get("CRUSTDATA_API_KEY"),
                             sample=req.sample)
        _STORE[result["mission_id"]] = result
        return {"mission_id": result["mission_id"], "state": result["state"],
                "mode": result["mode"], "sizing": result["sizing"],
                "company_records": result["company_records"],
                "buyer_records": result["buyer_records"],
                "artifacts": result["artifacts"], "warnings": result["warnings"]}

    @app.get("/missions/{mission_id}/accounts")
    def accounts(mission_id: str):
        r = _STORE.get(mission_id)
        if not r:
            raise HTTPException(404, "Mission not found (API store is in-memory; use the CLI output dir for older missions).")
        return r["ranked"]

    @app.get("/missions/{mission_id}/evidence")
    def evidence(mission_id: str):
        r = _STORE.get(mission_id)
        if not r:
            raise HTTPException(404, "Mission not found.")
        return {"mission_id": mission_id, "verified_claim_fraction": r["verified_claim_fraction"],
                "trace": r["trace"]}

    @app.get("/missions/{mission_id}/artifacts/{name}")
    def artifact(mission_id: str, name: str):
        p = Path("outputs") / "api-mission" / name
        if not p.exists():
            raise HTTPException(404, "Artifact not found.")
        return FileResponse(str(p))
else:
    app = None  # type: ignore
