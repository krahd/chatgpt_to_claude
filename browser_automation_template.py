#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else default


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="Guided Claude browser automation helper")
    p.add_argument("mode", choices=["memory", "uploads", "guided"])
    p.add_argument("--memory-file", type=Path)
    p.add_argument("--uploads-dir", type=Path)
    p.add_argument("--upload-plan", type=Path, default=None)
    p.add_argument("--state-file", type=Path, default=None)
    p.add_argument("--project-url", type=str, default="https://claude.ai")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--user-data-dir", type=Path, default=Path(".playwright-profile"))
    args = p.parse_args()

    cfg = load_json(args.config, {})
    state = load_json(args.state_file, {"uploads": {}, "notes": []}) if args.state_file else {"uploads": {}, "notes": []}
    upload_plan = load_json(args.upload_plan, []) if args.upload_plan else []

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(user_data_dir=str(args.user_data_dir), headless=False)
        page = browser.new_page()

        if args.mode in {"memory", "guided"} and args.memory_file:
            page.goto("https://claude.com/import-memory", wait_until="domcontentloaded")
            page.evaluate("navigator.clipboard.writeText(arguments[0])", args.memory_file.read_text(encoding="utf-8"))
            input("Memory content copied to clipboard. Paste it into Claude, then press Enter here.")
            if args.state_file:
                state.setdefault("uploads", {})[str(args.memory_file.name)] = {"status": "submitted"}

        if args.mode in {"uploads", "guided"} and args.uploads_dir:
            page.goto(args.project_url, wait_until="domcontentloaded")
            files = [str(p) for p in sorted(args.uploads_dir.glob("*.md"))]
            if upload_plan:
                print("Upload plan:")
                for step in upload_plan[:100]:
                    print(f"phase={step['phase']} kind={step['kind']} file={step['file']}")
            if cfg.get("upload_input_selector"):
                try:
                    page.locator(cfg["upload_input_selector"]).first.set_input_files(files)
                except Exception as exc:
                    print("Automatic upload trigger failed:", exc)
            for f in files:
                name = Path(f).name
                done = input(f"Mark {name} as uploaded? [y/N] ").strip().lower() in {"y", "yes"}
                if done and args.state_file:
                    state.setdefault("uploads", {})[name] = {"status": "uploaded"}
            input("Finish the uploads in the browser, then press Enter here.")

        if args.state_file:
            save_json(args.state_file, state)
        browser.close()


if __name__ == "__main__":
    main()
