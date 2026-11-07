"""Preserve user files while removing unchanged obsolete project modules."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    base = Path(directory)
    source = base / "source"
    source.mkdir()
    generated = base / "generated"
    for name in ("Main", "Old", "Edited", "Linked"):
        (source / (name + ".bl")).write_text("public class " + name + " {}", encoding="utf-8")
    command = [str(compiler), "project", str(source), str(generated)]
    subprocess.run(command, check=True)
    manifest_path = generated / ".z8-project-generated.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = {Path(item["path"]).name: generated / item["path"] for item in manifest["files"]}
    old, edited = paths["Old.d"], paths["Edited.d"]
    linked = paths["Linked.d"]
    external = base / "external.d"
    external.write_bytes(linked.read_bytes())
    linked.unlink()
    has_symlink = False
    try:
        linked.symlink_to(external)
        has_symlink = True
    except OSError:
        linked.write_bytes(external.read_bytes())
    custom = generated / "z8gen" / "custom.d"
    custom.write_text("// user file\n", encoding="utf-8")
    edited.write_text("// user modified\n", encoding="utf-8")
    (source / "Old.bl").unlink()
    (source / "Edited.bl").unlink()
    (source / "Linked.bl").unlink()
    # A failed compilation must not remove prior output.
    (source / "Main.bl").write_text("invalid", encoding="utf-8")
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert old.exists() and edited.exists()
    (source / "Main.bl").write_text("public class Main {}", encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert not old.exists() and edited.read_text(encoding="utf-8") == "// user modified\n"
    assert custom.read_text(encoding="utf-8") == "// user file\n"
    assert external.exists()
    if has_symlink:
        assert linked.is_symlink() and linked.exists()
    assert "Preserving modified generated file" in result.stderr
    subprocess.run(command, check=True)
    assert edited.exists() and custom.exists()
    # A tampered manifest cannot designate files outside the generated tree.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].append({"path": "z8gen/../../custom.d", "sha256": "0" * 64})
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert custom.exists()
print("Project regeneration removes only unchanged previously generated modules")
