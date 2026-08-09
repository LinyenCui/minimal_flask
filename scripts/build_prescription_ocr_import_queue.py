#!/usr/bin/env python3
"""Build official Drug/ICD matches and the existing OCR Review queue."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rewrite.tools.prescription_ocr_reference_matcher import (  # noqa: E402
    DEFAULT_DRUG_REFERENCE,
    DEFAULT_ICD_REFERENCE,
    build_import_queue_from_match_artifacts,
    build_import_decision_queue,
    build_official_reference_matches,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Match Prescription OCR Drug/ICD candidates to pinned official references and build import_decision_queue.csv."
    )
    parser.add_argument("--work-dir", required=True, help="Existing Prescription OCR run directory.")
    parser.add_argument("--drug-reference", default=str(DEFAULT_DRUG_REFERENCE))
    parser.add_argument("--icd-reference", default=str(DEFAULT_ICD_REFERENCE))
    parser.add_argument("--dry-run", action="store_true", help="Compute only; do not write artifacts.")
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument("--match-only", action="store_true", help="Write official Drug/ICD match artifacts only.")
    phase.add_argument("--queue-only", action="store_true", help="Build the existing queue from prior official match artifacts.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    builder = (
        build_official_reference_matches
        if args.match_only
        else build_import_queue_from_match_artifacts
        if args.queue_only
        else build_import_decision_queue
    )
    summary = builder(
        Path(args.work_dir),
        drug_reference=Path(args.drug_reference),
        icd_reference=Path(args.icd_reference),
        write_artifacts=not args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
