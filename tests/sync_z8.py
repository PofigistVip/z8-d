"""Exercise byte-exact upstream sync, conflict protection and native tracking."""
from contextlib import redirect_stdout
import importlib.util
import io
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_z8", root / "tools/sync_z8.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
    temp = Path(directory)
    original = temp / "original"
    sync.ROOT = temp
    sync.VENDOR = temp / "vendor/z8"
    sync.MANIFEST = temp / "vendor/z8-sync.json"
    sync.NATIVE = temp / "vendor/z8-native-baseline.json"
    bl = original / sync.TREES["bl"][0] / "example/Value.bl"
    java = original / "org.zenframework.z8.server/src/main/java/example/Value.java"
    helper = java.parent / "Helper.java"
    web = original / sync.TREES["web"][0] / "js/Z8.js"
    html = original / sync.TREES["web"][1] / "index.html"
    for path in (bl, java, web, html):
        path.parent.mkdir(parents=True, exist_ok=True)
    bl.write_bytes(b'[native "example.Value"]\r\nclass Value {}\r\n')
    java.write_bytes(b'class Value { int n = 1; }\n')
    helper.write_bytes(b'class Helper {}\n')
    web.write_bytes(b'// bytes \xef\xbb\xbf\r\n')
    html.write_bytes(b'<html>\r\n')
    assert sync.synchronize(original, "bl", True)
    assert sync.synchronize(original, "web", True)
    assert (sync.VENDOR / web.relative_to(original)).read_bytes() == web.read_bytes()
    assert (sync.VENDOR / bl.relative_to(original)).read_bytes() == bl.read_bytes()
    assert sync.native_report(original, True)
    assert not sync.native_report(original, False)
    helper.write_bytes(b'class Helper { int n; }\n')
    assert sync.native_report(original, False)
    sync.native_report(original, True)
    platform = temp / "platform/bl/example/System.bl"
    platform.parent.mkdir(parents=True)
    platform.write_text('[native "example.Value"] public class System {}', encoding="utf-8")
    assert sync.native_report(original, False)
    sync.native_report(original, True)
    java.write_bytes(b'class Value { int n = 2; }\n')
    bl.write_bytes(b'[native "example.Value"]\r\nclass Value { int changed; }\r\n')
    assert sync.native_report(original, False)
    with patch.object(sys, "argv", ["sync_z8.py", "bl", str(original), "--apply"]):
        assert sync.main() == 1  # Applying BL must still flag unreviewed Java changes.
    assert (sync.VENDOR / bl.relative_to(original)).read_bytes() == bl.read_bytes()
    sync.synchronize(original, "bl", True)
    assert sync.native_report(original, False)  # BL sync must not acknowledge Java changes.
    assert sync.native_report(original, True)
    assert not sync.native_report(original, False)
    with patch.object(sys, "argv", ["sync_z8.py", "bl", str(original), "--apply"]):
        assert sync.main() == 0
    target = sync.VENDOR / web.relative_to(original)
    target.write_bytes(b'local edit')
    web.write_bytes(b'upstream edit')
    try:
        sync.synchronize(original, "web", True)
        raise AssertionError("Expected a local modification conflict")
    except ValueError as error:
        assert "no changes applied" in str(error)
    assert target.read_bytes() == b'local edit'
    target.write_bytes(b'// bytes \xef\xbb\xbf\r\n')
    assert sync.synchronize(original, "web", True)
    assert target.read_bytes() == b'upstream edit'
    web.unlink()
    assert sync.synchronize(original, "web", True)
    assert not target.exists()
print("Upstream byte preservation, conflicts, removals and native change tracking passed")
