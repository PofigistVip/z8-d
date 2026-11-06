"""Verify that the original client is assembled without changing its sources."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/prepare_client.py [z8-source-root]")
original = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else root / "vendor/z8"
js = original / "org.zenframework.z8.js/src"
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "public"
    subprocess.run([sys.executable, str(root / "webserver/prepare_client.py"), str(original), str(output)], check=True)
    compiled = (output / "revolt.js").read_bytes()
    prefix = (js / "js/Z8.js").read_bytes() + b"\n"
    second = (js / "js/i18n/messages/messages_en.js").read_bytes() + b"\n"
    assert compiled.startswith(prefix + second)
    assert (output / "revolt.util.js").stat().st_size and (output / "revolt.server.js").stat().st_size
    css = (js / "css/font-awesome-0.css").read_bytes() + b"\n"
    assert (output / "css/revolt.css").read_bytes().startswith(css)
    icon = js / "css/img/revolt-32x32.png"
    assert (output / "css/img/revolt-32x32.png").read_bytes() == icon.read_bytes()
    assert any((output / "css/fonts").rglob("*.*"))
    template = (original / "org.zenframework.z8.resources/src/web/index.html").read_bytes()
    assert (output / "index.html").read_bytes() == template.replace(b"${project.name}", b"revolt")
    before = (output / "revolt.js").read_bytes()
    result = subprocess.run([sys.executable, str(root / "webserver/prepare_client.py"), str(original), str(output)], capture_output=True)
    assert result.returncode != 0 and (output / "revolt.js").read_bytes() == before
print("Original web client assets and build order verified")
