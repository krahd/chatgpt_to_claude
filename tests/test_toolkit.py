from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from migration_core import collect_memory_candidates, dedupe_memory_items, estimate_tokens, parse_conversations, read_conversations_json, search_conversations  # noqa: E402


class ToolkitTests(unittest.TestCase):
    def make_export(self, base: Path) -> Path:
        payload = [
            {
                "title": "British English Kivy project",
                "create_time": 1710000000,
                "update_time": 1710003600,
                "mapping": {
                    "1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1710000000, "content": {"parts": ["I prefer British English. I am working on a Python Kivy project."]}}},
                    "2": {"id": "2", "parent": "1", "message": {"id": "2", "author": {"role": "assistant"}, "create_time": 1710000100, "content": {"parts": ["OK"]}}},
                    "3": {"id": "3", "parent": "2", "message": {"id": "3", "author": {"role": "user"}, "create_time": 1710000200, "content": {"parts": ["Please use concise answers. I use Kivy."]}}},
                },
            },
            {
                "title": "Writing seminar",
                "create_time": 1711000000,
                "update_time": 1711003600,
                "mapping": {
                    "1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1711000000, "content": {"parts": ["I am writing a seminar paper about AI images."]}}}
                },
            },
        ]
        export_dir = base / "export"
        export_dir.mkdir()
        (export_dir / "conversations.json").write_text(json.dumps(payload), encoding="utf-8")
        (export_dir / "notes.txt").write_text("hello", encoding="utf-8")
        out_zip = base / "export.zip"
        with zipfile.ZipFile(out_zip, "w") as zf:
            zf.write(export_dir / "conversations.json", arcname="conversations.json")
            zf.write(export_dir / "notes.txt", arcname="notes.txt")
        return out_zip

    def test_core_parsing_and_search(self):
        with tempfile.TemporaryDirectory() as td:
            export_zip = self.make_export(Path(td))
            raw = read_conversations_json(export_zip)
            convs = parse_conversations(raw)
            self.assertEqual(len(convs), 2)
            hits = search_conversations(convs, "British English")
            self.assertTrue(hits)
            self.assertIn("British English", hits[0].title)


    def test_alternate_conversation_filename(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            payload = [{"title": "Alt export", "mapping": {}}]
            export_zip = td / "alt.zip"
            with zipfile.ZipFile(export_zip, "w") as zf:
                zf.writestr("chat_history.json", json.dumps(payload))
            raw = read_conversations_json(export_zip)
            self.assertEqual(raw[0]["title"], "Alt export")

    def test_memory_extraction_and_dedup(self):
        with tempfile.TemporaryDirectory() as td:
            export_zip = self.make_export(Path(td))
            convs = parse_conversations(read_conversations_json(export_zip))
            items = dedupe_memory_items(collect_memory_candidates(convs))
            texts = [i.text for i in items]
            self.assertTrue(any("British English" in t for t in texts))
            self.assertGreaterEqual(max(i.confidence for i in items), 0.5)
            self.assertTrue(any(i.source_refs for i in items))

    def test_cli_export(self):
        with tempfile.TemporaryDirectory() as td:
            export_zip = self.make_export(Path(td))
            out = Path(td) / "out"
            subprocess.run([sys.executable, str(ROOT / "migrate_chatgpt_to_claude.py"), str(export_zip), "-o", str(out), "--query", "Kivy", "--redact", "British English"], check=True)
            self.assertTrue((out / "manifest.json").exists())
            self.assertTrue((out / "attachments_manifest.json").exists())
            self.assertTrue((out / "migration_state.json").exists())
            self.assertTrue((out / "upload_plan.json").exists())
            self.assertTrue((out / "validation_report.json").exists())
            self.assertTrue((out / "conversation_report.tsv").exists())
            self.assertTrue((out / "attachment_summary.md").exists())
            self.assertTrue((out / "attachment_previews.json").exists())
            self.assertTrue((out / "memory_provenance.json").exists())
            self.assertTrue((out / "conversation_index.csv").exists())
            self.assertTrue((out / "manifest.jsonl").exists())
            self.assertTrue((out / "filters_used.json").exists())
            self.assertTrue((out / "duplicate_titles.json").exists())
            self.assertTrue((out / "REPORT_INDEX.md").exists())
            self.assertTrue((out / "RUN_SUMMARY.md").exists())
            self.assertTrue((out / "report_fingerprints.json").exists())
            self.assertTrue((out / "browser_config.sample.json").exists())
            self.assertIn("[REDACTED]", (out / "claude_memory_import.md").read_text(encoding="utf-8"))
            self.assertGreater(estimate_tokens((out / "claude_memory_import.md").read_text(encoding="utf-8")), 0)

    def test_dry_run_and_date_filter(self):
        with tempfile.TemporaryDirectory() as td:
            export_zip = self.make_export(Path(td))
            proc = subprocess.run([sys.executable, str(ROOT / "migrate_chatgpt_to_claude.py"), str(export_zip), "--dry-run", "--after", "2024-03-15", "--max-conversations", "1"], check=True, capture_output=True, text=True)
            self.assertIn('"conversation_count"', proc.stdout)


    def test_title_filter_and_disable_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            export_zip = self.make_export(Path(td))
            out = Path(td) / "out2"
            subprocess.run([sys.executable, str(ROOT / "migrate_chatgpt_to_claude.py"), str(export_zip), "-o", str(out), "--title-include", "Writing", "--no-memory", "--no-projects", "--batch-size", "1"], check=True)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 1)
            self.assertIn("Writing seminar", manifest[0]["title"])
            self.assertTrue((out / "export_summary.json").exists())
            self.assertTrue((out / "batch_plan.json").exists())



if __name__ == "__main__":
    unittest.main()


class ExtraCliTests(unittest.TestCase):
    def test_report_only_and_ids_filter(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            payload = [
                {"title": "A", "create_time": 1710000000, "update_time": 1710000001, "mapping": {"1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1710000000, "content": {"parts": ["alpha"]}}}}},
                {"title": "A", "create_time": 1711000000, "update_time": 1711000001, "mapping": {"1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1711000000, "content": {"parts": ["beta"]}}}}},
            ]
            z = td / "e.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("conversations.json", json.dumps(payload))
            ids = td / "ids.txt"
            ids.write_text("1\n", encoding="utf-8")
            out = td / "out"
            subprocess.run([sys.executable, str(ROOT / "migrate_chatgpt_to_claude.py"), str(z), "-o", str(out), "--conversation-ids-file", str(ids), "--report-only"], check=True)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 1)
            self.assertFalse(any((out / "conversations").glob("*.md")))
            self.assertTrue((out / "selection_mismatch_report.json").exists())



class StrictModeTests(unittest.TestCase):
    def test_strict_mode_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            payload = [
                {"title": "Dup", "create_time": 1710000000, "update_time": 1710000001, "mapping": {"1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1710000000, "content": {"parts": ["alpha"]}}}}},
                {"title": "Dup", "create_time": 1711000000, "update_time": 1711000001, "mapping": {"1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1711000000, "content": {"parts": ["beta"]}}}}},
            ]
            z = td / "e.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("conversations.json", json.dumps(payload))
            out = td / "out"
            proc = subprocess.run([sys.executable, str(ROOT / "migrate_chatgpt_to_claude.py"), str(z), "-o", str(out), "--strict"], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertTrue((out / "validation_report.json").exists())



class SelectionValidationTests(unittest.TestCase):
    def test_invalid_selection_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            payload = [{"title": "A", "create_time": 1710000000, "update_time": 1710000001, "mapping": {"1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1710000000, "content": {"parts": ["alpha"]}}}}}]
            z = td / "e.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("conversations.json", json.dumps(payload))
            sel = td / "sel.json"
            sel.write_text(json.dumps({"conversation_indices": "bad"}), encoding="utf-8")
            out = td / "out"
            proc = subprocess.run([sys.executable, str(ROOT / "migrate_chatgpt_to_claude.py"), str(z), "-o", str(out), "--selection-file", str(sel)], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)

