#!/usr/bin/env python3
"""CLI entry point for the shared pipeline orchestration runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.orchestration.pipeline_runner import PipelineRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Green Taxi BI pipeline orchestration steps.")
    parser.add_argument("--release-id", required=True, help="Data release identifier.")
    parser.add_argument("--step", help="Run one pipeline step only.")
    parser.add_argument("--dry-run", action="store_true", help="Emit planned step results without executing loaders.")
    parser.add_argument("--resume", action="store_true", help="Skip previously supplied successful step results when used by Python callers.")
    parser.add_argument("--no-fail-fast", action="store_true", help="Continue after failed steps.")
    parser.add_argument("--data-root", default="data", help="Repository-relative or absolute data root. Default: data.")
    return parser.parse_args()


def main() -> int:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    args = parse_args()
    runner = PipelineRunner(release_id=args.release_id, data_root=REPO_ROOT / args.data_root)
    result = runner.run(
        step=args.step,
        dry_run=args.dry_run,
        resume=args.resume,
        fail_fast=not args.no_fail_fast,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status in {"SUCCEEDED", "DRY_RUN"} else 1


if __name__ == "__main__":
    sys.exit(main())
