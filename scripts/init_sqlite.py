#!/usr/bin/env python
from __future__ import annotations

import argparse

from service.infrastructure.sqlite_store import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the service SQLite database.")
    parser.add_argument("--database", default="data/service.db", help="SQLite database path")
    args = parser.parse_args()
    SQLiteStore(args.database).initialize()
    print(f"initialized {args.database}")


if __name__ == "__main__":
    main()

