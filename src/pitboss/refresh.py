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
    run("src.pitboss.scrape_buzz")
    try:
        run("src.pitboss.score")
    except SystemExit as e:
        print(f"score: {e}")  # no overlap yet is fine on pre-air runs
    run("src.pitboss.predict")


if __name__ == "__main__":
    main()
