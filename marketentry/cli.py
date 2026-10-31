"""CLI: one brief -> one complete mission.

Usage:
  python -m marketentry.cli --brief "We sell cybersecurity compliance software for fintech companies. Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees. Estimate using a £12,000 annual contract value; identify competitors and buyer roles; produce a ranked shortlist."
  python -m marketentry.cli --brief "..." --sample        # labelled smoke test, no key needed
  python -m marketentry.cli --brief-file brief.txt --out outputs/my-mission

Setup (local only, never commit):
  cp .env.example .env   # then put your Crustdata key in .env
  # or: export CRUSTDATA_API_KEY=...
  # Never paste a key in chat, in a screenshot, or in the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # dotenv is optional: plain environment variables work too.
    pass

from .mission import run_mission


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="MarketEntryOS: autonomous market-entry mission.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--brief", help="Free-text brief (or JSON brief object).")
    g.add_argument("--brief-file", help="File containing the brief.")
    p.add_argument("--out", default="outputs/mission", help="Output directory.")
    p.add_argument("--sample", action="store_true", help="Labelled sample-data smoke test (no live API).")
    p.add_argument("--max-accounts", type=int, default=None)
    args = p.parse_args(argv)
    brief = args.brief or Path(args.brief_file).read_text(encoding="utf-8").strip()
    result = run_mission(brief, args.out, api_key=os.environ.get("CRUSTDATA_API_KEY"),
                         sample=args.sample, max_accounts=args.max_accounts)
    print(f"Mission {result['mission_id']} — {result['state']} (mode: {result['mode']})")
    print(f"Accounts: {result['company_records']}  Buyers: {result['buyer_records']}  "
          f"Competitors: {result['competitor_records']}")
    print(f"Sizing: {json.dumps(result['sizing'])}")
    print(f"Artifacts in {args.out}: {', '.join(result['artifacts'])}")
    if result["warnings"]:
        print("Warnings:")
        for w in result["warnings"]:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
