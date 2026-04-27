#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="POST a local provider fixture to the webhook receiver.")
    parser.add_argument("provider", choices=["codeup", "gitlab"])
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--token", default=None, help="Provider webhook token. Falls back to CODEUP_SECRET_TOKEN or GITLAB_SECRET_TOKEN.")
    args = parser.parse_args()

    env_name = "CODEUP_SECRET_TOKEN" if args.provider == "codeup" else "GITLAB_SECRET_TOKEN"
    token = args.token or os.getenv(env_name)
    if not token:
        print(f"missing --token or {env_name}", file=sys.stderr)
        sys.exit(2)
    event_header = {"codeup": "Codeup-Event", "gitlab": "X-Gitlab-Event"}[args.provider]
    token_header = {"codeup": "X-Codeup-Token", "gitlab": "X-Gitlab-Token"}[args.provider]
    payload = json.loads(args.fixture.read_text(encoding="utf-8"))

    response = httpx.post(
        f"{args.base_url}/webhooks/{args.provider}",
        headers={event_header: "Push Hook", token_header: token},
        json=payload,
        timeout=10,
    )
    print(response.status_code)
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    main()
