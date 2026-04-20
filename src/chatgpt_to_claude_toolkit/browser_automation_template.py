#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else default


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_args(args) -> None:
    if args.mode in {"memory", "guided"} and not args.memory_file and args.mode != "uploads":
        print("Warning: no memory file provided.")
    if args.mode in {"uploads", "guided"} and not args.uploads_dir and args.mode != "memory":
        print("Warning: no uploads directory provided.")


def try_set_input_files(page, selector: str, files: list[str], retries: int = 2) -> bool:
    for attempt in range(retries + 1):
        try:
            page.locator(selector).first.set_input_files(files)
            return True
        except Exception as exc:
            print(f"Upload trigger attempt {attempt + 1} failed: {exc}")
            time.sleep(1)
    return False


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
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    validate_args(args)
    cfg = load_json(args.config, {"upload_input_selector": "input[type=file]"})
    state = load_json(args.state_file, {"uploads": {}, "notes": []}) if args.state_file else {"uploads": {}, "notes": []}
    upload_plan = load_json(args.upload_plan, []) if args.upload_plan else []

    if args.dry_run:
        preview = {
            "mode": args.mode,
            "memory_file": str(args.memory_file) if args.memory_file else None,
            "uploads_dir": str(args.uploads_dir) if args.uploads_dir else None,
            "project_url": args.project_url,
            "upload_input_selector": cfg.get("upload_input_selector"),
            "planned_upload_steps": len(upload_plan),
        }
        print(json.dumps(preview, indent=2))
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(user_data_dir=str(args.user_data_dir), headless=False)
        page = browser.new_page()

        if args.mode in {"memory", "guided"} and args.memory_file:
            page.goto("https://claude.com/import-memory", wait_until="domcontentloaded")
            page.evaluate("navigator.clipboard.writeText(arguments[0])", args.memory_file.read_text(encoding="utf-8"))
            input("Memory content copied to clipboard. Paste it into Claude, then press Enter here.")
            if args.state_file:
                state.setdefault("uploads", {})[str(args.memory_file.name)] = {"status": "submitted"}
                save_json(args.state_file, state)

        if args.mode in {"uploads", "guided"} and args.uploads_dir:
            page.goto(args.project_url, wait_until="domcontentloaded")
            files = [str(p) for p in sorted(args.uploads_dir.glob("*.md"))]
            if upload_plan:
                print("Upload plan:")
                for step in upload_plan[:100]:
                    print(f"phase={step['phase']} kind={step['kind']} file={step['file']}")
            selector = cfg.get("upload_input_selector")
            if selector and files:
                ok = try_set_input_files(page, selector, files)
                if not ok:
                    print("Automatic upload trigger did not succeed. Continue manually in the browser.")
            for f in files:
                name = Path(f).name
                done = input(f"Mark {name} as uploaded? [y/N] ").strip().lower() in {"y", "yes"}
                if done and args.state_file:
                    state.setdefault("uploads", {})[name] = {"status": "uploaded"}
                    save_json(args.state_file, state)
            input("Finish the uploads in the browser, then press Enter here.")

        if args.state_file:
            save_json(args.state_file, state)
        browser.close()


if __name__ == "__main__":
    main()
