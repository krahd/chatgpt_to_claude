#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Inspect or update migration_state.json")
    p.add_argument("state_file", type=Path)
    p.add_argument("--mark-uploaded", nargs="*", default=[])
    p.add_argument("--note", type=str, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    data = json.loads(args.state_file.read_text(encoding="utf-8")) if args.state_file.exists() else {"reviewed_memory": {}, "reviewed_conversations": {}, "uploads": {}, "notes": []}
    for item in args.mark_uploaded:
        data.setdefault("uploads", {})[item] = {"status": "uploaded"}
    if args.note:
        data.setdefault("notes", []).append(args.note)
    args.state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
