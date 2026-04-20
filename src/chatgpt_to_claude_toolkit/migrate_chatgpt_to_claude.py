#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .migration_core import (
    build_attachment_previews,
    build_upload_plan,
    bundle_topics_with_budgets,
    collect_memory_candidates,
    conversation_to_markdown,
    dedupe_memory_items,
    estimate_tokens,
    extract_attachments,
    filter_conversations_by_date,
    infer_topics,
    load_state,
    parse_conversations,
    read_conversations_json,
    redact_text,
    save_state,
    search_conversations,
    slugify,
    summarise_conversation,
    ts_to_iso,
    validate_output_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert a ChatGPT export zip into Claude-friendly files.")
    p.add_argument("export_zip", type=Path)
    p.add_argument("-o", "--output-dir", type=Path, default=Path("claude_migration_output"))
    p.add_argument("--selection-file", type=Path, default=None)
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--min-memory-frequency", type=int, default=1)
    p.add_argument("--max-memory-items", type=int, default=300)
    p.add_argument("--token-budget", type=int, default=120000)
    p.add_argument("--query", type=str, default=None, help="Optional fuzzy search query to export only matching conversations")
    p.add_argument("--redact", action="append", default=[], help="Regex or literal pattern to redact from exported text. Repeatable.")
    p.add_argument("--no-attachments", action="store_true", help="Skip extracting non-conversation files from the export zip.")
    p.add_argument("--after", type=str, default=None, help="Only include conversations created on or after YYYY-MM-DD.")
    p.add_argument("--before", type=str, default=None, help="Only include conversations created on or before YYYY-MM-DD.")
    p.add_argument("--dry-run", action="store_true", help="Print what would be exported without writing files.")
    p.add_argument("--max-conversations", type=int, default=None, help="Limit the number of conversations exported after filtering.")
    p.add_argument("--title-include", type=str, default=None, help="Only include conversations whose title contains this string.")
    p.add_argument("--title-exclude", type=str, default=None, help="Exclude conversations whose title contains this string.")
    p.add_argument("--no-memory", action="store_true", help="Skip memory extraction outputs.")
    p.add_argument("--no-projects", action="store_true", help="Skip topic project bundle outputs.")
    p.add_argument("--batch-size", type=int, default=None, help="Create a batch plan that groups conversations into batches of N.")
    p.add_argument("--conversation-ids-file", type=Path, default=None, help="Only include source conversation ids listed one per line in this file.")
    p.add_argument("--report-only", action="store_true", help="Only write metadata and reports, not conversation/project markdown payloads.")
    p.add_argument("--strict", action="store_true", help="Exit non-zero if validation reports any errors or warnings.")
    p.add_argument("--stale-before", type=str, default=None, help="Mark conversations updated before this YYYY-MM-DD date as stale in reports.")
    return p.parse_args()


def parse_numeric_selection(raw: str, max_index: int) -> set[int]:
    selected: set[int] = set()
    raw = raw.strip().lower()
    if raw in {"all", "*"}:
        return set(range(1, max_index + 1))
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            for idx in range(min(int(a), int(b)), max(int(a), int(b)) + 1):
                if 1 <= idx <= max_index:
                    selected.add(idx)
        else:
            idx = int(part)
            if 1 <= idx <= max_index:
                selected.add(idx)
    return selected




def _selection_list(data: dict[str, Any], key: str, legacy_key: str) -> list[Any]:
    value = data.get(key)
    if value is None:
        value = data.get(legacy_key, [])
    if not isinstance(value, list):
        raise ValueError(f"Selection file field {key!r} must be a list.")
    return value


def validate_selection_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Selection file must contain a JSON object.")
    selected_conversations = _selection_list(data, "selected_conversations", "conversation_indices")
    selected_memory_items = _selection_list(data, "selected_memory_items", "memory_indices")
    selected_topics = _selection_list(data, "selected_topics", "topics")
    edited_memory_items = data.get("edited_memory_items", {})
    if not isinstance(edited_memory_items, dict):
        raise ValueError("Selection file field 'edited_memory_items' must be an object.")
    return {
        "conversation_count": len(selected_conversations),
        "memory_count": len(selected_memory_items),
        "topic_count": len(selected_topics),
        "selected_conversations": selected_conversations,
        "selected_memory_items": selected_memory_items,
        "selected_topics": selected_topics,
    }


def write_selection_summary(output_dir: Path, summary: dict | None) -> None:
    if summary is None:
        return
    (output_dir / "selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

def apply_selection_file(conversations, memory_items, topics, path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Selection file must contain a JSON object.")
    selected_conversations = _selection_list(data, "selected_conversations", "conversation_indices")
    selected_memory_items = _selection_list(data, "selected_memory_items", "memory_indices")
    selected_topics_raw = _selection_list(data, "selected_topics", "topics")
    edited_memory_items = data.get("edited_memory_items", {})
    if not isinstance(edited_memory_items, dict):
        raise ValueError("Selection file field 'edited_memory_items' must be an object.")
    conv_keys = {str(x) for x in selected_conversations}
    mem_keys = {str(x) for x in selected_memory_items}
    topic_keys = {str(x) for x in selected_topics_raw}
    conversation_map = {str(c.source_index): c for c in conversations}
    memory_map = {str(idx): m for idx, m in enumerate(memory_items, start=1)}
    selected_conversations = [conversation_map[k] for k in conv_keys if k in conversation_map] if conv_keys else list(conversations)
    selected_memory = [memory_map[k] for k in mem_keys if k in memory_map] if mem_keys else list(memory_items)
    edited = {str(k): str(v) for k, v in edited_memory_items.items() if v}
    for key, item in memory_map.items():
        if key in edited and edited[key]:
            item.text = edited[key]
    selected_topics = {k: v for k, v in topics.items() if not topic_keys or k in topic_keys}
    return selected_conversations, selected_memory, selected_topics


def maybe_clear_output_dir(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        response = input(f"Output directory {output_dir} is not empty. Clear it first? [Y/n] ").strip().lower()
        if response in {"", "y", "yes"}:
            shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)


def choose_memory_items_interactively(items):
    print("\nMemory candidates:\n")
    for i, item in enumerate(items, start=1):
        flags = f" flags={','.join(item.sensitivity_flags)}" if item.sensitivity_flags else ""
        print(f"{i:>3}. [{item.category}] conf={item.confidence} x{item.count}{flags} {item.text}")
    raw = input("\nEnter memory items to KEEP (all or 1,2,5-9). Leave blank for all: ").strip()
    if not raw:
        return items
    sel = parse_numeric_selection(raw, len(items))
    return [item for idx, item in enumerate(items, start=1) if idx in sel]


def choose_topics_interactively(topics):
    names = sorted(topics)
    print("\nTopic bundles:\n")
    for i, name in enumerate(names, start=1):
        print(f"{i:>3}. {name} ({len(topics[name])} conversations)")
    raw = input("\nChoose topic bundles to export (all or numbers). Leave blank for all: ").strip()
    if not raw:
        return {k: topics[k] for k in names}
    sel = parse_numeric_selection(raw, len(names))
    return {name: topics[name] for idx, name in enumerate(names, start=1) if idx in sel}


def choose_conversations_interactively(conversations):
    print("\nConversations:\n")
    for i, conv in enumerate(conversations, start=1):
        print(f"{i:>4}. [{ts_to_iso(conv.create_time) or 'unknown'}] {conv.title} ({len(conv.messages)} messages)")
    raw = input("\nChoose conversations to export (all or numbers/ranges). Leave blank for all: ").strip()
    if not raw:
        return conversations
    sel = parse_numeric_selection(raw, len(conversations))
    return [conv for idx, conv in enumerate(conversations, start=1) if idx in sel]


def write_memory_files(selected_items, output_dir: Path, redactions=None) -> None:
    redactions = redactions or []
    review = output_dir / "memory_review.tsv"
    md = output_dir / "claude_memory_import.md"
    js = output_dir / "claude_memory_import.json"
    prov = output_dir / "memory_provenance.json"
    with md.open("w", encoding="utf-8") as f:
        f.write("```text\n")
        for item in selected_items:
            f.write(f"[{item.first_seen or 'unknown-date'}] - {redact_text(item.text, redactions)}\n")
        f.write("```\n")
    payload = []
    for item in selected_items:
        row = dict(item.__dict__)
        row["text"] = redact_text(row["text"], redactions)
        row["examples"] = [redact_text(x, redactions) for x in row.get("examples", [])]
        payload.append(row)
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    prov.write_text(json.dumps([{"text": row["text"], "source_refs": row.get("source_refs", []), "examples": row.get("examples", [])} for row in payload], ensure_ascii=False, indent=2), encoding="utf-8")
    with review.open("w", encoding="utf-8") as f:
        f.write("keep\tcategory\tconfidence\tcount\tfirst_seen\tstale\tsensitivity\trationale\ttext\texamples\tcontradictions\tsource_refs\n")
        for item in selected_items:
            f.write(
                f"yes\t{item.category}\t{item.confidence}\t{item.count}\t{item.first_seen or ''}\t{item.stale}\t{','.join(item.sensitivity_flags)}\t{item.rationale}\t{redact_text(item.text, redactions)}\t{' | '.join(redact_text(x, redactions) for x in item.examples)}\t{' | '.join(redact_text(x, redactions) for x in item.contradictions)}\t{' | '.join(item.source_refs)}\n"
            )


def write_conversations(conversations, output_dir: Path, redactions=None, report_only: bool = False) -> None:
    redactions = redactions or []
    conv_dir = output_dir / "conversations"
    preview_dir = output_dir / "previews"
    conv_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    with (output_dir / "conversation_index.csv").open("w", encoding="utf-8", newline="") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=["source_index", "file", "title", "created", "updated", "message_count", "estimated_tokens", "sha256"])
        writer.writeheader()
        for i, conv in enumerate(conversations, start=1):
            title = display_title(conv)
            filename = f"{i:04d}_{ts_to_iso(conv.create_time) or f'idx-{i:04d}'}_{slugify(title)}.md"
            text = redact_text(conversation_to_markdown(conv), redactions)
            preview = redact_text(summarise_conversation(conv), redactions)
            digest = sha256_text(text)
            if not report_only:
                (conv_dir / filename).write_text(text, encoding="utf-8")
                (preview_dir / filename).write_text(preview, encoding="utf-8")
            manifest.append({
                "source_index": conv.source_index,
                "file": filename,
                "title": title,
                "created": ts_to_iso(conv.create_time),
                "updated": ts_to_iso(conv.update_time),
                "message_count": len(conv.messages),
                "estimated_tokens": estimate_tokens(text),
                "sha256": digest,
            })
            writer.writerow(manifest[-1])
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_projects(topics, output_dir: Path, token_budget: int, redactions=None, report_only: bool = False) -> None:
    redactions = redactions or []
    proj_dir = output_dir / "projects"
    proj_dir.mkdir(parents=True, exist_ok=True)
    plan = []
    bundles = bundle_topics_with_budgets(topics, token_budget)
    lines_summary = ["# Project plan", ""]
    for topic, convs in sorted(bundles.items()):
        path = proj_dir / f"{topic}.md"
        lines = [f"# {topic.title()} context", "", f"Target budget: {token_budget} tokens", ""]
        total = 0
        for conv in convs:
            preview = redact_text(summarise_conversation(conv), redactions)
            total += estimate_tokens(preview)
            lines.append(preview)
            lines.append("")
        if not report_only:
            path.write_text("\n".join(lines), encoding="utf-8")
        plan.append({"topic": topic, "conversation_count": len(convs), "estimated_tokens": total})
        lines_summary.append(f"- {topic}: {len(convs)} conversations, ~{total} tokens")
    (output_dir / "project_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (output_dir / "project_plan.md").write_text("\n".join(lines_summary), encoding="utf-8")


def write_attachment_summary(attachments, output_dir: Path) -> None:
    counts: dict[str, int] = {}
    total_size = 0
    for item in attachments:
        counts[item.category] = counts.get(item.category, 0) + 1
        total_size += item.size
    lines = ["# Attachment summary", "", f"- Total attachments: {len(attachments)}", f"- Total size: {total_size} bytes", "", "## By category", ""]
    for category, count in sorted(counts.items()):
        lines.append(f"- {category}: {count}")
    if not attachments:
        lines.append("- none")
    (output_dir / "attachment_summary.md").write_text("\n".join(lines), encoding="utf-8")





def display_title(conv) -> str:
    title = (conv.title or "").strip()
    return title if title else f"Untitled conversation {conv.source_index}"

def filter_conversations_by_ids(conversations, ids_file: Path | None):
    if not ids_file or not ids_file.exists():
        return conversations
    wanted = {line.strip() for line in ids_file.read_text(encoding="utf-8").splitlines() if line.strip()}
    return [c for c in conversations if str(c.source_index) in wanted]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_filters_used(output_dir: Path, args) -> None:
    payload = {
        "query": args.query,
        "after": args.after,
        "before": args.before,
        "title_include": args.title_include,
        "title_exclude": args.title_exclude,
        "max_conversations": args.max_conversations,
        "batch_size": args.batch_size,
        "report_only": args.report_only,
        "no_memory": args.no_memory,
        "no_projects": args.no_projects,
        "no_attachments": args.no_attachments,
        "conversation_ids_file": str(args.conversation_ids_file) if args.conversation_ids_file else None,
    }
    (output_dir / "filters_used.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")



def write_batch_plan(output_dir: Path, conversations, batch_size: int | None) -> None:
    if not batch_size or batch_size <= 0:
        return
    batches: list[dict[str, Any]] = []
    for i in range(0, len(conversations), batch_size):
        chunk = conversations[i:i + batch_size]
        batches.append({
            "batch": len(batches) + 1,
            "conversation_ids": [c.source_index for c in chunk],
            "titles": [c.title for c in chunk],
            "count": len(chunk),
        })
    (output_dir / "batch_plan.json").write_text(json.dumps(batches, indent=2, ensure_ascii=False), encoding="utf-8")



def filter_conversations_by_title(conversations, include: str | None, exclude: str | None):
    out = []
    inc = include.lower() if include else None
    exc = exclude.lower() if exclude else None
    for conv in conversations:
        title = (conv.title or "").lower()
        if inc and inc not in title:
            continue
        if exc and exc in title:
            continue
        out.append(conv)
    return out


def write_export_summary(output_dir: Path, conversations, memory_items, topics, attachments) -> None:
    category_counts: dict[str, int] = {}
    for item in attachments:
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
    summary = {
        "conversation_count": len(conversations),
        "memory_count": len(memory_items),
        "topic_count": len(topics),
        "attachment_count": len(attachments),
        "attachment_category_counts": category_counts,
        "estimated_conversation_tokens": sum(estimate_tokens(conversation_to_markdown(c)) for c in conversations),
    }
    (output_dir / "export_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")



def write_quality_reports(output_dir: Path, conversations, stale_before: str | None = None) -> None:
    title_counts: dict[str, int] = {}
    stale: list[dict[str, Any]] = []
    stale_threshold = None
    if stale_before:
        try:
            stale_threshold = datetime.strptime(stale_before, "%Y-%m-%d").timestamp()
        except ValueError:
            stale_threshold = None
    for conv in conversations:
        title_counts[conv.title] = title_counts.get(conv.title, 0) + 1
        if stale_threshold is not None and conv.update_time and conv.update_time < stale_threshold:
            stale.append({"source_index": conv.source_index, "title": conv.title, "updated": ts_to_iso(conv.update_time)})
    dupes = [{"title": k, "count": v} for k, v in sorted(title_counts.items()) if v > 1]
    (output_dir / "duplicate_titles.json").write_text(json.dumps(dupes, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "stale_conversations.json").write_text(json.dumps(stale, indent=2, ensure_ascii=False), encoding="utf-8")



def write_strategy(conversations, memory_items, topics, attachments, output_dir: Path) -> None:
    lines = ["# Migration strategy", "", "## Recommended order", "", "1. Review and trim memory candidates.", "2. Upload topic bundles to Claude Projects.", "3. Keep raw conversations as archival context.", "4. Upload attachments selectively.", "", "## Counts", ""]
    lines.append(f"- Conversations selected: {len(conversations)}")
    lines.append(f"- Memory items selected: {len(memory_items)}")
    lines.append(f"- Topic bundles selected: {len(topics)}")
    lines.append(f"- Attachments extracted: {len(attachments)}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Project bundles are budgeted heuristically by estimated token count.")
    lines.append("- Raw conversation files preserve more detail than project summaries.")
    lines.append("- Memory items with sensitivity flags should be reviewed manually before import.")
    (output_dir / "migration_strategy.md").write_text("\n".join(lines), encoding="utf-8")


def write_browser_automation(output_dir: Path) -> None:
    template = (Path(__file__).with_name("browser_automation_template.py")).read_text(encoding="utf-8")
    (output_dir / "browser_automation.py").write_text(template, encoding="utf-8")
    (output_dir / "browser_automation.example.json").write_text(json.dumps({"upload_input_selector": ""}, indent=2), encoding="utf-8")






def write_run_summary(output_dir: Path, state: dict, validation: dict) -> None:
    conv_files = len(list((output_dir / "conversations").glob("*.md"))) if (output_dir / "conversations").exists() else 0
    project_files = len(list((output_dir / "projects").glob("*.md"))) if (output_dir / "projects").exists() else 0
    lines = ["# Run summary", "", f"Conversations: {state.get('conversation_count', 0)}", f"Memory items: {state.get('memory_count', 0)}", f"Topics: {state.get('topic_count', 0)}", f"Attachments: {state.get('attachment_count', 0)}", f"Conversation markdown files: {conv_files}", f"Project markdown files: {project_files}", f"Warnings: {len(validation.get('warnings', []))}", f"Errors: {len(validation.get('errors', []))}"]
    (output_dir / "RUN_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def write_report_fingerprints(output_dir: Path) -> None:
    payload = {}
    for path in sorted(output_dir.glob('*')):
        if path.is_file() and path.suffix in {'.json', '.md', '.csv', '.tsv', '.html', '.jsonl'}:
            payload[path.name] = sha256_text(path.read_text(encoding='utf-8', errors='ignore'))
    (output_dir / 'report_fingerprints.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')



def write_selection_mismatch_report(output_dir: Path, selection_summary: dict | None, conversations, memory_items, topics) -> None:
    if not selection_summary:
        payload: dict[str, list[Any]] = {"missing_conversation_indices": [], "missing_topics": []}
        (output_dir / "selection_mismatch_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return
    conversation_ids = {c.source_index for c in conversations}
    missing_conversations = [i for i in selection_summary.get("selected_conversations", []) if i not in conversation_ids]
    topic_names = set(topics.keys()) if isinstance(topics, dict) else set()
    missing_topics = [t for t in selection_summary.get("selected_topics", []) if t not in topic_names]
    payload = {
        "missing_conversation_indices": missing_conversations,
        "missing_topics": missing_topics,
    }
    (output_dir / "selection_mismatch_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

def write_report_index(output_dir: Path) -> None:
    entries = [
        "manifest.json", "manifest.jsonl", "conversation_index.csv", "filters_used.json",
        "export_summary.json", "validation_report.json", "manual_attention.md",
        "migration_strategy.md", "project_plan.json", "project_plan.md",
        "duplicate_titles.json", "stale_conversations.json", "memory_provenance.json",
        "batch_plan.json", "attachment_previews.json", "migration_summary.html"
    ]
    lines = ["# Report index", ""]
    for name in entries:
        if (output_dir / name).exists():
            lines.append(f"- {name}")
    (output_dir / "REPORT_INDEX.md").write_text("\n".join(lines), encoding="utf-8")



def write_browser_config_sample(output_dir: Path) -> None:
    payload = {
        "upload_input_selector": "input[type=file]",
        "notes": ["Adjust selectors for Claude UI changes before running browser automation."]
    }
    (output_dir / "browser_config.sample.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

def write_reports(output_dir: Path) -> None:
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8")) if (output_dir / "manifest.json").exists() else []
    memory = json.loads((output_dir / "claude_memory_import.json").read_text(encoding="utf-8")) if (output_dir / "claude_memory_import.json").exists() else []
    validation = json.loads((output_dir / "validation_report.json").read_text(encoding="utf-8")) if (output_dir / "validation_report.json").exists() else {"warnings": [], "errors": []}
    with (output_dir / "conversation_report.tsv").open("w", encoding="utf-8") as f:
        f.write("file\ttitle\tcreated\tupdated\tmessage_count\testimated_tokens\n")
        for row in manifest:
            f.write(f"{row['file']}\t{row['title']}\t{row.get('created','')}\t{row.get('updated','')}\t{row.get('message_count','')}\t{row.get('estimated_tokens','')}\n")
    risky = [m for m in memory if m.get("sensitivity_flags") or m.get("contradictions") or m.get("stale")]
    with (output_dir / "manual_attention.md").open("w", encoding="utf-8") as f:
        f.write("# Manual attention report\n\n")
        f.write("## Validation warnings\n\n")
        for w in validation.get("warnings", []):
            f.write(f"- {w}\n")
        if not validation.get("warnings"):
            f.write("- None\n")
        f.write("\n## Risky memory items\n\n")
        for item in risky:
            f.write(f"- {item.get('text','')}\n")
            if item.get("sensitivity_flags"):
                f.write(f"  - sensitivity: {', '.join(item['sensitivity_flags'])}\n")
            if item.get("contradictions"):
                f.write(f"  - contradictions: {' | '.join(item['contradictions'])}\n")
            if item.get("stale"):
                f.write("  - stale: true\n")
        if not risky:
            f.write("- None\n")
    html_lines = [
        "<html><head><meta charset='utf-8'><title>Migration Summary</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ccc;padding:.4rem;text-align:left;}code{background:#f4f4f4;padding:.1rem .3rem;} .warn{color:#9a6700;} .err{color:#b00020;}</style>",
        "</head><body>",
        "<h1>Migration Summary</h1>",
        f"<p>Conversations: <strong>{len(manifest)}</strong> | Memory items: <strong>{len(memory)}</strong></p>",
        "<h2>Validation</h2>",
        "<ul>" + ''.join(f"<li class='warn'>{w}</li>" for w in validation.get('warnings', [])) + ''.join(f"<li class='err'>{e}</li>" for e in validation.get('errors', [])) + "</ul>",
        "<h2>Conversations</h2><table><tr><th>File</th><th>Title</th><th>Created</th><th>Messages</th><th>Tokens</th></tr>",
    ]
    for row in manifest:
        html_lines.append(f"<tr><td><code>{row['file']}</code></td><td>{row['title']}</td><td>{row.get('created','')}</td><td>{row.get('message_count','')}</td><td>{row.get('estimated_tokens','')}</td></tr>")
    html_lines.append("</table><h2>Memory needing attention</h2><ul>")
    for item in risky[:200]:
        flags = ', '.join(item.get('sensitivity_flags', []))
        html_lines.append(f"<li><code>{item.get('category','')}</code> {item.get('text','')} {'(' + flags + ')' if flags else ''}</li>")
    html_lines.append("</ul></body></html>")
    (output_dir / "migration_summary.html").write_text(''.join(html_lines), encoding="utf-8")


def write_readme(output_dir: Path) -> None:
    text = """# ChatGPT → Claude migration toolkit

This toolkit converts a ChatGPT export zip into a reviewable migration package for Claude.

## Requirements

- Python 3.11+ recommended
- `playwright` only if you want browser automation

## Typical workflow

```bash
python chatgpt_migration_tui.py /path/to/chatgpt-export.zip ./selection.json
python migrate_chatgpt_to_claude.py /path/to/chatgpt-export.zip -o ./out --selection-file ./selection.json
```

## Key outputs

- `conversations/`
- `previews/`
- `projects/`
- `attachments/`
- `claude_memory_import.md`
- `memory_review.tsv`
- `upload_plan.json`
- `validation_report.json`
- `conversation_report.tsv`
- `manual_attention.md`
- `migration_summary.html`

## Direct export

```bash
python migrate_chatgpt_to_claude.py /path/to/chatgpt-export.zip -o ./out --token-budget 120000
```

## Redaction

```bash
python migrate_chatgpt_to_claude.py /path/to/chatgpt-export.zip -o ./out --redact "sk-[A-Za-z0-9]+"
```

## Review migration state

```bash
python review_state.py ./out/migration_state.json --mark-uploaded projects/ai.md --note "Uploaded first bundle"
```

## Notes

- memory extraction is heuristic
- contradiction detection is approximate
- token estimates are approximate
- browser automation is guided rather than fully autonomous
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    raw = read_conversations_json(args.export_zip)
    conversations = parse_conversations(raw)
    if args.interactive:
        maybe_clear_output_dir(args.output_dir)
    else:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.query:
        conversations = search_conversations(conversations, args.query, limit=100)
    conversations = filter_conversations_by_date(conversations, args.after, args.before)
    conversations = filter_conversations_by_title(conversations, args.title_include, args.title_exclude)
    conversations = filter_conversations_by_ids(conversations, args.conversation_ids_file)

    if args.max_conversations is not None:
        conversations = conversations[: max(0, args.max_conversations)]

    memory_items = [] if args.no_memory else dedupe_memory_items([m for m in collect_memory_candidates(conversations) if m.count >= args.min_memory_frequency])[: args.max_memory_items]
    topics = {} if args.no_projects else infer_topics(conversations)
    selection_summary = None
    if args.selection_file is not None:
        selection_summary = validate_selection_file(args.selection_file)
        conversations, memory_items, topics = apply_selection_file(conversations, memory_items, topics, args.selection_file)
    elif args.interactive:
        memory_items = choose_memory_items_interactively(memory_items)
        topics = choose_topics_interactively(topics)
        conversations = choose_conversations_interactively(conversations)

    if args.dry_run:
        summary = {
            "conversation_count": len(conversations),
            "memory_count": len(memory_items),
            "topic_count": len(topics),
            "would_extract_attachments": not args.no_attachments,
            "date_after": args.after,
            "date_before": args.before,
            "query": args.query,
            "max_conversations": args.max_conversations,
            "title_include": args.title_include,
            "title_exclude": args.title_exclude,
            "no_memory": args.no_memory,
            "no_projects": args.no_projects,
            "batch_size": args.batch_size,
        }
        print(json.dumps(summary, indent=2))
        return 0

    attachments = [] if args.no_attachments else extract_attachments(args.export_zip, args.output_dir)
    if not args.no_memory:
        write_memory_files(memory_items, args.output_dir, args.redact)
    write_conversations(conversations, args.output_dir, args.redact, report_only=args.report_only)
    if not args.no_projects:
        write_projects(topics, args.output_dir, args.token_budget, args.redact, report_only=args.report_only)
    write_filters_used(args.output_dir, args)
    write_quality_reports(args.output_dir, conversations, args.stale_before)
    write_strategy(conversations, memory_items, topics, attachments, args.output_dir)
    write_batch_plan(args.output_dir, conversations, args.batch_size)
    write_attachment_summary(attachments, args.output_dir)
    build_attachment_previews(args.output_dir)
    write_export_summary(args.output_dir, conversations, memory_items, topics, attachments)
    write_browser_automation(args.output_dir)
    write_readme(args.output_dir)

    state_path = args.output_dir / "migration_state.json"
    state = load_state(state_path)
    state["summary"] = {
        "conversation_count": len(conversations),
        "memory_count": len(memory_items),
        "topic_count": len(topics),
        "attachment_count": len(attachments),
    }
    upload_plan = build_upload_plan(args.output_dir)
    (args.output_dir / "upload_plan.json").write_text(json.dumps(upload_plan, indent=2), encoding="utf-8")
    validation = validate_output_dir(args.output_dir)
    if not conversations:
        validation.setdefault("warnings", []).append("No conversations matched the current filters.")
    try:
        project_plan = json.loads((args.output_dir / "project_plan.json").read_text(encoding="utf-8"))
        for row in project_plan:
            if row.get("estimated_tokens", 0) > args.token_budget:
                validation.setdefault("warnings", []).append(f"Project bundle exceeds target budget: {row['topic']}")
    except Exception:
        pass
    (args.output_dir / "validation_report.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    write_selection_summary(args.output_dir, selection_summary)
    write_selection_mismatch_report(args.output_dir, selection_summary, conversations, memory_items, topics)
    write_reports(args.output_dir)
    write_browser_config_sample(args.output_dir)
    write_report_index(args.output_dir)
    write_run_summary(args.output_dir, state, validation)
    write_report_fingerprints(args.output_dir)
    if args.strict and (validation.get("errors") or validation.get("warnings")):
        state["strict_failed"] = True
        state["validation"] = validation
        save_state(state_path, state)
        return 2
    save_state(state_path, state)

    print(f"Wrote output to: {args.output_dir}")
    print(f"Selected conversations: {len(conversations)}")
    print(f"Selected memory items: {len(memory_items)}")
    print(f"Selected topic bundles: {len(topics)}")
    print(f"Extracted attachments: {len(attachments)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
