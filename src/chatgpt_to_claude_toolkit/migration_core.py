#!/usr/bin/env python3
from __future__ import annotations

import difflib
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYSTEM_AUTHORS = {"system", "tool", "developer"}
USER_AUTHORS = {"user", "human"}
ASSISTANT_AUTHORS = {"assistant", "model"}
TEXT_EXTS = {".txt", ".md", ".markdown", ".py", ".json", ".csv", ".yaml", ".yml", ".html", ".js", ".ts", ".css", ".xml", ".rst"}
BINARY_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".docx", ".pptx", ".xlsx", ".zip", ".mp3", ".wav", ".mp4", ".mov"}


@dataclass
class Message:
    id: str
    parent: str | None
    author: str
    text: str
    create_time: float | None


@dataclass
class Conversation:
    title: str
    create_time: float | None
    update_time: float | None
    messages: list[Message]
    source_index: int


@dataclass
class MemoryItem:
    category: str
    text: str
    first_seen: str | None
    count: int
    confidence: float
    rationale: str
    stale: bool
    sensitivity_flags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)


@dataclass
class AttachmentRecord:
    archive_path: str
    output_path: str
    kind: str
    size: int
    category: str


PREFERENCE_PATTERNS: list[tuple[str, str, str]] = [
    (r"\bI prefer\b(.{0,220})", "preferences", "explicit preference"),
    (r"\bplease use\b(.{0,220})", "preferences", "explicit style request"),
    (r"\bfrom now on\b(.{0,220})", "preferences", "persistent instruction"),
    (r"\balways\b(.{0,220})", "instructions", "explicit instruction"),
    (r"\bnever\b(.{0,220})", "instructions", "explicit constraint"),
    (r"\bmy project\b(.{0,220})", "projects", "project mention"),
    (r"\bI am working on\b(.{0,220})", "projects", "ongoing work"),
    (r"\bI'?m working on\b(.{0,220})", "projects", "ongoing work"),
    (r"\bI use\b(.{0,220})", "tools", "tooling statement"),
    (r"\bI am using\b(.{0,220})", "tools", "tooling statement"),
    (r"\bmy goal is\b(.{0,220})", "goals", "goal statement"),
]
SENSITIVE_HINTS = {
    "health": ["diagnosis", "medical", "depression", "anxiety", "therapy"],
    "politics": ["vote", "voting", "republican", "democrat", "labour", "conservative"],
    "religion": ["christian", "muslim", "jewish", "religion"],
    "sexuality": ["gay", "lesbian", "sexual"],
}
TOPIC_KEYWORDS = {
    "coding": ["python", "code", "program", "bug", "github", "repo", "kivy", "api"],
    "writing": ["essay", "paper", "write", "writing", "article", "story", "seminar"],
    "productivity": ["workflow", "obsidian", "trello", "calendar", "email", "automation"],
    "ai": ["llm", "gpt", "claude", "anthropic", "openai", "rag", "model"],
    "design": ["image", "design", "davinci", "video", "ui", "graphics"],
}


def ts_to_iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def speaker_label(author: str) -> str:
    if author in USER_AUTHORS:
        return "User"
    if author in ASSISTANT_AUTHORS:
        return "Assistant"
    if author in SYSTEM_AUTHORS:
        return "System"
    return author.capitalize() if author else "Unknown"


def slugify(value: str, max_len: int = 80) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (value[:max_len].rstrip("-") or "conversation")


def sentence_split(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()] if text else []


def normalise_memory_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" \n\t-•"))[:280].strip()


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def norm_author(author: Any) -> str:
    if isinstance(author, str):
        return author.lower()
    if isinstance(author, dict):
        role = author.get("role") or author.get("name") or author.get("author")
        if isinstance(role, str):
            return role.lower()
    return "unknown"


def extract_text_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(x for x in (extract_text_from_content(i) for i in content) if x).strip()
    if isinstance(content, dict):
        parts: list[str] = []
        if isinstance(content.get("text"), str):
            parts.append(content["text"])
        for key in ("parts", "content", "result", "summary", "caption"):
            if key in content:
                parts.append(extract_text_from_content(content[key]))
        return "\n".join(x for x in parts if x).strip()
    return ""


def extract_message(node: dict[str, Any]) -> Message | None:
    message = node.get("message") or node.get("current_message") or node
    if not isinstance(message, dict):
        return None
    mid = str(message.get("id") or node.get("id") or "")
    if not mid:
        return None
    text = extract_text_from_content(message.get("content"))
    author = norm_author(message.get("author"))
    create_time = message.get("create_time")
    if create_time is None:
        create_time = node.get("create_time")
    parent = node.get("parent") or message.get("parent")
    if author == "unknown" and not text:
        return None
    return Message(mid, str(parent) if parent else None, author, text, float(create_time) if isinstance(create_time, (int, float)) else None)


def order_messages(mapping: dict[str, dict[str, Any]]) -> list[Message]:
    extracted: dict[str, Message] = {}
    children: dict[str, list[str]] = defaultdict(list)
    roots: list[str] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = extract_message(node)
        if not msg:
            continue
        extracted[msg.id] = msg
        if msg.parent and msg.parent in mapping:
            children[msg.parent].append(msg.id)
        else:
            roots.append(msg.id)

    def sort_key(mid: str) -> tuple[float, str]:
        msg = extracted[mid]
        return (msg.create_time if msg.create_time is not None else float("inf"), mid)

    ordered: list[str] = []
    seen: set[str] = set()

    def dfs(mid: str) -> None:
        if mid in seen or mid not in extracted:
            return
        seen.add(mid)
        ordered.append(mid)
        for child in sorted(children.get(mid, []), key=sort_key):
            dfs(child)

    for root in sorted(roots, key=sort_key):
        dfs(root)
    for mid in sorted(extracted, key=sort_key):
        dfs(mid)

    msgs = [extracted[mid] for mid in ordered]
    msgs.sort(key=lambda m: (m.create_time if m.create_time is not None else float("inf"), m.id))
    deduped, keys = [], set()
    for msg in msgs:
        key = (msg.author, msg.text, msg.create_time)
        if key not in keys:
            keys.add(key)
            deduped.append(msg)
    return deduped


def ensure_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("conversations", "items", "data"):
            if isinstance(raw.get(key), list):
                return raw[key]
    raise ValueError("Unsupported conversations.json structure.")


def read_conversations_json(export_zip: Path) -> Any:
    with zipfile.ZipFile(export_zip) as zf:
        names = zf.namelist()
        candidates = []
        for name in names:
            lower = name.lower()
            if lower.endswith('.json') and ('conversation' in lower or 'chat' in lower or lower == 'conversations.json'):
                candidates.append(name)
        if 'conversations.json' in names:
            candidates = ['conversations.json'] + [n for n in candidates if n != 'conversations.json']
        ordered = []
        seen = set()
        for item in candidates:
            if item not in seen:
                ordered.append(item)
                seen.add(item)
        for candidate in ordered:
            try:
                with zf.open(candidate) as fp:
                    data = json.load(fp)
                if isinstance(data, list) and all(isinstance(x, dict) for x in data):
                    return data
            except Exception:
                continue
        for name in names:
            if not name.lower().endswith('.json'):
                continue
            try:
                with zf.open(name) as fp:
                    data = json.load(fp)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    if any(('mapping' in x) or ('title' in x) for x in data[:5]):
                        return data
            except Exception:
                continue
        raise FileNotFoundError('Could not find a plausible conversations JSON file inside the zip export.')


def parse_conversations(raw: Any) -> list[Conversation]:
    conversations: list[Conversation] = []
    for idx, item in enumerate(ensure_list(raw), start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or f"Conversation {idx}").strip() or f"Conversation {idx}"
        mapping = item.get("mapping")
        messages: list[Message] = []
        if isinstance(mapping, dict):
            messages = order_messages(mapping)
        elif isinstance(item.get("messages"), list):
            msgs = [{"message": m, "id": m.get("id"), "parent": m.get("parent")} for m in item["messages"] if isinstance(m, dict)]
            messages = order_messages({str(i): m for i, m in enumerate(msgs)})
        conversations.append(Conversation(title, float(item["create_time"]) if isinstance(item.get("create_time"), (int, float)) else None, float(item["update_time"]) if isinstance(item.get("update_time"), (int, float)) else None, messages, idx))
    return conversations


def detect_sensitivity(text: str) -> list[str]:
    lower = text.lower()
    flags = [label for label, words in SENSITIVE_HINTS.items() if any(w in lower for w in words)]
    return flags


def collect_memory_candidates(conversations: list[Conversation]) -> list[MemoryItem]:
    counts: Counter[tuple[str, str]] = Counter()
    first_seen: dict[tuple[str, str], str | None] = {}
    rationales: dict[tuple[str, str], str] = {}
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    source_refs: dict[tuple[str, str], list[str]] = defaultdict(list)
    statements_by_prefix: dict[str, list[str]] = defaultdict(list)

    for conv in conversations:
        for msg in conv.messages:
            if msg.author not in USER_AUTHORS:
                continue
            for sentence in sentence_split(msg.text):
                lowered = sentence.lower()
                statements_by_prefix[lowered[:32]].append(sentence)
                matched = False
                for pattern, category, rationale in PREFERENCE_PATTERNS:
                    if re.search(pattern, sentence, flags=re.IGNORECASE):
                        candidate = normalise_memory_text(sentence)
                        if len(candidate) >= 18:
                            key = (category, candidate)
                            counts[key] += 1
                            first_seen.setdefault(key, ts_to_iso(msg.create_time))
                            rationales[key] = rationale
                            if sentence not in examples[key] and len(examples[key]) < 3:
                                examples[key].append(sentence[:280])
                            ref = f"conv:{conv.source_index}/msg:{msg.id}"
                            if ref not in source_refs[key] and len(source_refs[key]) < 5:
                                source_refs[key].append(ref)
                            matched = True
                if lowered.startswith(("my ", "i ", "i'm ", "i am ")) and len(sentence) >= 18:
                    candidate = normalise_memory_text(sentence)
                    if 18 <= len(candidate) <= 220:
                        key = ("personal_context", candidate)
                        counts[key] += 1
                        first_seen.setdefault(key, ts_to_iso(msg.create_time))
                        rationales.setdefault(key, "first-person statement")
                        if sentence not in examples[key] and len(examples[key]) < 3:
                            examples[key].append(sentence[:280])
                        ref = f"conv:{conv.source_index}/msg:{msg.id}"
                        if ref not in source_refs[key] and len(source_refs[key]) < 5:
                            source_refs[key].append(ref)
                if matched:
                    continue

    items: list[MemoryItem] = []
    for (category, text), count in counts.items():
        contradictions = []
        prefix = text.lower()[:32]
        for other in statements_by_prefix.get(prefix, []):
            if other != text and difflib.SequenceMatcher(None, other.lower(), text.lower()).ratio() < 0.72:
                contradictions.append(other[:200])
        confidence = min(0.98, 0.45 + 0.18 * min(count, 3) + (0.08 if category in {"preferences", "instructions"} else 0.0))
        items.append(MemoryItem(
            category=category,
            text=text,
            first_seen=first_seen.get((category, text)),
            count=count,
            confidence=round(confidence, 2),
            rationale=rationales.get((category, text), "heuristic extraction"),
            stale=count == 1,
            sensitivity_flags=detect_sensitivity(text),
            examples=examples.get((category, text), []),
            contradictions=sorted(set(contradictions))[:3],
            source_refs=source_refs.get((category, text), []),
        ))
    items.sort(key=lambda x: (-x.confidence, -x.count, x.category, x.text.lower()))
    return items


def dedupe_memory_items(items: list[MemoryItem], similarity_threshold: float = 0.88) -> list[MemoryItem]:
    kept: list[MemoryItem] = []
    for item in items:
        duplicate = False
        for existing in kept:
            if item.category == existing.category and difflib.SequenceMatcher(None, item.text.lower(), existing.text.lower()).ratio() >= similarity_threshold:
                existing.count += item.count
                existing.examples = list(dict.fromkeys(existing.examples + item.examples))[:3]
                existing.confidence = max(existing.confidence, item.confidence)
                existing.source_refs = list(dict.fromkeys(existing.source_refs + item.source_refs))[:5]
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    kept.sort(key=lambda x: (-x.confidence, -x.count, x.category, x.text.lower()))
    return kept


def infer_topics(conversations: list[Conversation]) -> dict[str, list[Conversation]]:
    buckets: dict[str, list[Conversation]] = defaultdict(list)
    for conv in conversations:
        haystack = " ".join([conv.title] + [m.text[:400] for m in conv.messages[:8]]).lower()
        assigned = False
        for topic, words in TOPIC_KEYWORDS.items():
            if any(w in haystack for w in words):
                buckets[topic].append(conv)
                assigned = True
        if not assigned:
            buckets["misc"].append(conv)
    return buckets


def bundle_topics_with_budgets(topics: dict[str, list[Conversation]], token_budget: int) -> dict[str, list[Conversation]]:
    bundles: dict[str, list[Conversation]] = {}
    for topic, convs in topics.items():
        running, selected = 0, []
        for conv in sorted(convs, key=lambda c: (c.update_time or 0), reverse=True):
            approx = estimate_tokens(conversation_to_markdown(conv))
            if running + approx > token_budget and selected:
                continue
            selected.append(conv)
            running += approx
        bundles[topic] = selected
    return bundles


def parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def filter_conversations_by_date(conversations: list[Conversation], after: str | None = None, before: str | None = None) -> list[Conversation]:
    after_dt = parse_iso_date(after)
    before_dt = parse_iso_date(before)
    out = []
    for conv in conversations:
        created = parse_iso_date(ts_to_iso(conv.create_time)) if conv.create_time else None
        if after_dt and created and created < after_dt:
            continue
        if before_dt and created and created > before_dt:
            continue
        out.append(conv)
    return out


def search_conversations(conversations: list[Conversation], query: str, limit: int = 20) -> list[Conversation]:
    scored = []
    q = query.lower().strip()
    for conv in conversations:
        haystack = (conv.title + "\n" + "\n".join(m.text[:500] for m in conv.messages[:6])).lower()
        if q in haystack:
            score = 1.0
        else:
            score = difflib.SequenceMatcher(None, q, haystack[:800]).ratio()
        scored.append((score, conv))
    return [c for score, c in sorted(scored, key=lambda x: x[0], reverse=True)[:limit] if score > 0.15]


def conversation_to_markdown(conv: Conversation) -> str:
    lines = [f"# {conv.title}", "", f"- Source index: {conv.source_index}"]
    if conv.create_time is not None:
        lines.append(f"- Created: {ts_to_iso(conv.create_time)}")
    if conv.update_time is not None:
        lines.append(f"- Updated: {ts_to_iso(conv.update_time)}")
    lines.append(f"- Message count: {len(conv.messages)}")
    lines.append("")
    for msg in conv.messages:
        lines.append(f"## {speaker_label(msg.author)}")
        lines.append("")
        if msg.create_time is not None:
            lines.append(f"_Date: {ts_to_iso(msg.create_time)}_")
            lines.append("")
        lines.append(msg.text.strip() or "[No textual content extracted]")
        lines.append("")
    return "\n".join(lines)


def summarise_conversation(conv: Conversation, max_turns: int = 6) -> str:
    out = [f"# {conv.title}", "", "## Summary preview", ""]
    for msg in conv.messages[:max_turns]:
        out.append(f"**{speaker_label(msg.author)}:** {msg.text[:500].strip()}")
        out.append("")
    return "\n".join(out)


def extract_attachments(export_zip: Path, output_dir: Path) -> list[AttachmentRecord]:
    attachments_dir = output_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    records: list[AttachmentRecord] = []
    with zipfile.ZipFile(export_zip) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename)
            if name.name == "conversations.json":
                continue
            ext = name.suffix.lower()
            if ext not in TEXT_EXTS and ext not in BINARY_EXTS:
                continue
            out_name = name.name
            target = attachments_dir / out_name
            stem, suffix, counter = target.stem, target.suffix, 1
            while target.exists():
                target = attachments_dir / f"{stem}-{counter}{suffix}"
                counter += 1
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            category = classify_attachment(target)
            kind = "text" if category == "text" else "binary"
            records.append(AttachmentRecord(info.filename, str(target.relative_to(output_dir)), kind, info.file_size, category))
    (output_dir / "attachments_manifest.json").write_text(json.dumps([asdict(r) for r in records], indent=2), encoding="utf-8")
    return records


def classify_attachment(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if ext in {".pdf"}:
        return "pdf"
    if ext in {".docx", ".pptx", ".xlsx"}:
        return "office"
    if ext in {".mp3", ".wav"}:
        return "audio"
    if ext in {".mp4", ".mov"}:
        return "video"
    if ext in TEXT_EXTS:
        return "text"
    return "binary"


def load_state(state_path: Path) -> dict[str, Any]:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {"reviewed_memory": {}, "reviewed_conversations": {}, "uploads": {}, "notes": []}


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def redact_text(text: str, patterns: list[str]) -> str:
    redacted = text
    for pat in patterns:
        try:
            redacted = re.sub(pat, "[REDACTED]", redacted, flags=re.IGNORECASE)
        except re.error:
            redacted = redacted.replace(pat, "[REDACTED]")
    return redacted


def build_attachment_previews(output_dir: Path, limit_chars: int = 800) -> None:
    manifest_path = output_dir / "attachments_manifest.json"
    if not manifest_path.exists():
        return
    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    previews = []
    for row in records:
        if row.get("category") != "text":
            continue
        path = output_dir / row["output_path"]
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:limit_chars].strip()
        except Exception:
            text = ""
        previews.append({"file": row["output_path"], "preview": text})
    (output_dir / "attachment_previews.json").write_text(json.dumps(previews, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_output_dir(output_dir: Path) -> dict[str, Any]:
    report = {"ok": True, "errors": [], "warnings": []}
    expected = [
        output_dir / "manifest.json",
        output_dir / "migration_state.json",
        output_dir / "migration_strategy.md",
    ]
    optional_expected = [
        output_dir / "claude_memory_import.md",
        output_dir / "claude_memory_import.json",
    ]
    for path in expected:
        if not path.exists():
            report["ok"] = False
            report["errors"].append(f"Missing required file: {path.name}")
    if not any(p.exists() for p in optional_expected):
        report["warnings"].append("Memory export files are missing; this may be intentional if memory export was disabled.")
    conv_dir = output_dir / "conversations"
    manifest = output_dir / "manifest.json"
    if conv_dir.exists() and not any(conv_dir.glob("*.md")) and not manifest.exists():
        report["warnings"].append("No conversation markdown files were exported.")
    memory_json = output_dir / "claude_memory_import.json"
    if memory_json.exists():
        try:
            items = json.loads(memory_json.read_text(encoding="utf-8"))
            seen = set()
            for item in items:
                text = item.get("text", "")
                if text in seen:
                    report["warnings"].append(f"Duplicate memory item: {text[:80]}")
                seen.add(text)
        except Exception as exc:
            report["ok"] = False
            report["errors"].append(f"Could not parse claude_memory_import.json: {exc}")
    dupes = output_dir / "duplicate_titles.json"
    if dupes.exists():
        try:
            data = json.loads(dupes.read_text(encoding="utf-8"))
            if data:
                report["warnings"].append(f"Duplicate conversation titles detected: {len(data)}")
        except Exception:
            pass
    return report


def build_upload_plan(output_dir: Path) -> list[dict[str, Any]]:
    plan = []
    for path in sorted((output_dir / "projects").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        plan.append({"phase": 1, "kind": "project_bundle", "file": str(path.relative_to(output_dir)), "estimated_tokens": estimate_tokens(text)})
    for path in sorted((output_dir / "conversations").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        plan.append({"phase": 2, "kind": "conversation", "file": str(path.relative_to(output_dir)), "estimated_tokens": estimate_tokens(text)})
    for path in sorted((output_dir / "attachments").glob("*")):
        if path.is_file():
            plan.append({"phase": 3, "kind": "attachment", "file": str(path.relative_to(output_dir)), "estimated_tokens": None})
    return plan
