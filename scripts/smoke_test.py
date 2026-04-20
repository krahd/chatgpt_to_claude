import json, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    payload = [{"title": "Smoke", "create_time": 1710000000, "update_time": 1710000500, "mapping": {"1": {"id": "1", "message": {"id": "1", "author": {"role": "user"}, "create_time": 1710000000, "content": {"parts": ["I prefer British English."]}}}}}]
    export_zip = td / "export.zip"
    with zipfile.ZipFile(export_zip, "w") as zf:
        zf.writestr("conversations.json", json.dumps(payload))
    out = td / "out"
    cli = shutil.which("chatgpt-to-claude")
    if cli:
        cmd = [cli, str(export_zip), "-o", str(out)]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve().parents[1] / "migrate_chatgpt_to_claude.py"), str(export_zip), "-o", str(out)]
    subprocess.run(cmd, check=True)
    assert (out / "manifest.json").exists()
    assert (out / "claude_memory_import.json").exists()
print("smoke ok")
