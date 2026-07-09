"""One-command weekly refresh: season results -> buzz -> score -> next predictions.

python -m src.pitboss.refresh
Safe to run any day (every step is idempotent / cached per day).
"""
from __future__ import annotations

import runpy
import sys


def run(module: str, argv: list[str] | None = None) -> None:
    print(f"\n=== {module} ===")
    sys.argv = [module] + (argv or [])
    runpy.run_module(module, run_name="__main__")


def main() -> None:
    run("src.pitboss.scrape_season")
    # accountability first: scoring failures must fail the whole run (red CI),
    # EXCEPT the benign pre-air case of nothing to score yet
    try:
        run("src.pitboss.score")
    except SystemExit as e:
        if "no scored fights yet" in str(e):
            print(f"score: {e}")
        else:
            raise
    # buzz is enrichment: its failure never blocks scoring or prediction
    try:
        run("src.pitboss.scrape_buzz")
    except Exception as e:
        print(f"buzz FAILED (non-fatal): {e}")
    run("src.pitboss.predict")


if __name__ == "__main__":
    main()
