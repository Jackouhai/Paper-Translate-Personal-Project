#!/usr/bin/env python3
"""Run the PP-DocLayout pipeline sequentially for every PDF in a folder."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Paste the root folder containing the PDFs to process here.
INPUT_DIR = Path("/home/bocchi/Downloads/Paper_Data")

# Output mirrors the folder structure under INPUT_DIR.
OUTPUT_DIR = PROJECT_ROOT / "output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PP-DocLayout sequentially for every PDF in a folder tree."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        type=Path,
        default=INPUT_DIR,
        help=f"Root folder containing PDFs (default: {INPUT_DIR})",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed PDF instead of continuing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()

    if not input_dir.is_dir():
        print(f"error: input folder does not exist: {input_dir}", file=sys.stderr)
        return 2

    pdf_files = sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )
    if not pdf_files:
        print(f"error: no PDF files found in: {input_dir}", file=sys.stderr)
        return 2

    failed_files: list[Path] = []
    completed_count = 0
    processed_count = 0
    total = len(pdf_files)

    for index, pdf_file in enumerate(pdf_files, start=1):
        processed_count += 1
        command = [sys.executable, "-m", "pp_doclayout.cli", "run", str(pdf_file)]
        relative_parent = pdf_file.relative_to(input_dir).parent
        output_dir = OUTPUT_DIR / relative_parent
        environment = os.environ.copy()
        environment["PPDOCLAYOUT_OUTPUT_DIR"] = str(output_dir)

        print(f"\n=== [{index}/{total}] {pdf_file.name} ===", flush=True)
        print(f"Output: {output_dir / pdf_file.stem}", flush=True)

        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            check=False,
        )
        if result.returncode == 0:
            completed_count += 1
            print(f"=== Completed: {pdf_file.name} ===", flush=True)
            continue

        failed_files.append(pdf_file)
        print(
            f"=== Failed ({result.returncode}): {pdf_file.name} ===",
            file=sys.stderr,
            flush=True,
        )
        if args.fail_fast:
            break

    print("\n=== Batch summary ===")
    print(f"Completed: {completed_count}/{processed_count}")
    if processed_count < total:
        print(f"Not run: {total - processed_count}")
    if failed_files:
        print("Failed:")
        for pdf_file in failed_files:
            print(f"- {pdf_file}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
