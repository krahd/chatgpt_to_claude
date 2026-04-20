import json, subprocess, tempfile, zipfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    payload = [{"title": "Smoke", "create_time": 1710000000, "update_time": 1710000500, "mapping": {"1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1710000000, "content": {"parts": ["I prefer British English."]}}}}}]
    export_zip = td / "export.zip"
    with zipfile.ZipFile(export_zip, "w") as zf:
        zf.writestr("conversations.json", json.dumps(payload))
    out = td / "out"
    subprocess.run(["chatgpt-to-claude", str(export_zip), "-o", str(out)], check=True)
    assert (out / "manifest.json").exists()
    assert (out / "claude_memory_import.json").exists()
print("smoke ok")
