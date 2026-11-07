"""Build separately compiled BL libraries and reuse them in a project."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    alpha, beta, app = (temp / name for name in ("alpha-source", "beta-source", "app-source"))
    for path in (alpha / "alpha", beta / "beta", app / "demo"):
        path.mkdir(parents=True)
    (alpha / "alpha/Value.bl").write_text('public class Value { public int number() { return 20; } }', encoding="utf-8")
    (alpha / "alpha/SecurityLog.bl").write_text('[native "org.zenframework.z8.server.base.security.SecurityLog"] public class SecurityLog {}', encoding="utf-8")
    (alpha / "alpha/Logger.bl").write_text('import alpha.SecurityLog; [log] public class Logger extends SecurityLog {}', encoding="utf-8")
    (beta / "beta/Value.bl").write_text('public class Value { public int number() { return 22; } }', encoding="utf-8")
    (beta / "beta/Builder.bl").write_text('import beta.Value; public class Builder { public int number() { Value v; return v.number(); } }', encoding="utf-8")
    (app / "demo/Main.bl").write_text('''
import alpha.Value; import beta.Builder;
public class Main { public static int run() { Value a; Builder b; return a.number() + b.number(); } }
''', encoding="utf-8")
    one, two = temp / "first-library", temp / "second-library"
    subprocess.run([str(compiler), "library", str(alpha), str(one), "first"], check=True)
    subprocess.run([str(compiler), "library", str(beta), str(two), "second"], check=True)
    for library in (one, two):
        manifest = json.loads((library / "z8-library.json").read_text(encoding="utf-8"))
        assert manifest["format"] == "z8-d-library-1" and manifest["sources"] and manifest["types"]
        assert (library / ("z8-library.lib" if os.name == "nt" else "libz8-library.a")).is_file()
    generated = temp / "generated"
    libraries = ["--library", str(one), "--library", str(two)]
    subprocess.run([str(compiler), "project", str(app), str(generated), *libraries], check=True)
    paths = {p.relative_to(generated).as_posix() for p in generated.rglob("*.d")}
    assert paths == {"z8gen/demo/Main.d", "z8gen/project_registry.d"}, paths
    source = (generated / "z8gen/demo/Main.d").read_text(encoding="utf-8")
    assert "import z8lib.l_first.alpha.Value : Z8q_alpha_2EValue = Z8_Value;" in source
    assert "import z8lib.l_second.beta.Builder" in source
    executable = temp / ("application.exe" if os.name == "nt" else "application")
    subprocess.run([str(compiler), "build", str(app), "demo.Main.run", str(executable), *libraries], check=True)
    assert subprocess.run([str(executable)]).returncode == 42
    harness = temp / "harness.d"
    harness.write_text('''import z8.runtime; import z8gen.project_registry; import z8gen.demo.Main;
void main() {
    auto registry = new Z8RuntimeRegistry(); z8_register_project(registry);
    assert(Z8_Main.m_run() == 42);
    assert(z8_object_new_instance("alpha.Value"w).z8_class_id() == "alpha.Value"w);
    assert(z8_object_new_instance("beta.Value"w).z8_class_id() == "beta.Value"w);
    assert(registry.newSecurityLog().z8_class_id() == "alpha.Logger"w);
}''', encoding="utf-8")
    binary = temp / ("probe.exe" if os.name == "nt" else "probe")
    archive = lambda p: p / ("z8-library.lib" if os.name == "nt" else "libz8-library.a")
    args = ["-I" + str(generated), "-I" + str(one / "d"), "-I" + str(two / "d"), *import_args(),
            *map(str, generated.rglob("*.d")), str(harness), str(archive(one)), str(archive(two)), str(runtime), "-of=" + str(binary)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(binary)], check=True)

    manifest_path = one / "z8-library.json"
    old_api = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_api["registryApi"] = 2
    manifest_path.write_text(json.dumps(old_api), encoding="utf-8")
    incompatible_api = subprocess.run([str(compiler), "project", str(app), str(temp / "old-api"), *libraries], capture_output=True, text=True)
    assert incompatible_api.returncode and "registry API changed; rebuild first" in incompatible_api.stderr, incompatible_api.stderr
    subprocess.run([str(compiler), "library", str(alpha), str(one), "first"], check=True)

    original_manifest = manifest_path.read_bytes()
    altered = json.loads(original_manifest)
    altered["compiler"] = "DMD from a different build"
    manifest_path.write_text(json.dumps(altered), encoding="utf-8")
    project_env = os.environ.copy()
    project_env["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32") if os.name == "nt" else ""
    subprocess.run([str(compiler), "project", str(app), str(temp / "other-dmd-generated"), *libraries], env=project_env, check=True)
    mismatch = subprocess.run([str(compiler), "build", str(app), "demo.Main.run", str(executable), *libraries], capture_output=True, text=True)
    assert mismatch.returncode and "DMD version differs; rebuild first" in mismatch.stderr, mismatch.stderr
    mismatch = subprocess.run([str(compiler), "library", str(beta), str(temp / "wrong-dmd-library"), "wrong", "--library", str(one)], capture_output=True, text=True)
    assert mismatch.returncode and "DMD version differs; rebuild first" in mismatch.stderr, mismatch.stderr
    del altered["compiler"]
    manifest_path.write_text(json.dumps(altered), encoding="utf-8")
    missing_dmd = subprocess.run([str(compiler), "build", str(app), "demo.Main.run", str(executable), *libraries], capture_output=True, text=True)
    assert missing_dmd.returncode and "has no DMD version; rebuild first" in missing_dmd.stderr, missing_dmd.stderr
    subprocess.run([str(compiler), "library", str(alpha), str(one), "first"], check=True)
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["compiler"]

    interface = one / "d/z8lib/l_first/alpha/Value.d"
    original_interface = interface.read_bytes()
    interface.write_bytes(original_interface + b"\n// changed\n")
    broken = subprocess.run([str(compiler), "project", str(app), str(temp / "broken"), *libraries], capture_output=True, text=True)
    assert broken.returncode and "files do not match their manifest" in broken.stderr, broken.stderr
    interface.write_bytes(original_interface)
    original_archive = archive(one).read_bytes()
    with archive(one).open("ab") as output:
        output.write(b"changed")
    broken_archive = subprocess.run([str(compiler), "project", str(app), str(temp / "broken-archive"), *libraries], capture_output=True, text=True)
    assert broken_archive.returncode and "files do not match their manifest" in broken_archive.stderr, broken_archive.stderr
    archive(one).write_bytes(original_archive)
    keep = one / "do-not-delete.txt"
    keep.write_text("user data", encoding="utf-8")
    unsafe = subprocess.run([str(compiler), "library", str(alpha), str(one), "first"], capture_output=True, text=True)
    assert unsafe.returncode and keep.read_text(encoding="utf-8") == "user data", unsafe.stderr
    keep.unlink()
    keep = one / "d/z8lib/l_first/alpha/do-not-delete.txt"
    keep.write_text("user data", encoding="utf-8")
    unsafe = subprocess.run([str(compiler), "library", str(alpha), str(one), "first"], capture_output=True, text=True)
    assert unsafe.returncode and keep.read_text(encoding="utf-8") == "user data", unsafe.stderr
    keep.unlink()
    manifest_path = one / "z8-library.json"
    original_manifest = manifest_path.read_bytes()
    altered = json.loads(original_manifest)
    altered["runtime"] = "different-runtime"
    manifest_path.write_text(json.dumps(altered), encoding="utf-8")
    incompatible = subprocess.run([str(compiler), "project", str(app), str(temp / "incompatible"), *libraries], capture_output=True, text=True)
    assert incompatible.returncode and "runtime changed; rebuild first" in incompatible.stderr, incompatible.stderr
    manifest_path.write_bytes(original_manifest)

    middle_source = temp / "middle-source"
    (middle_source / "middle").mkdir(parents=True)
    (middle_source / "middle/Proxy.bl").write_text('''
import alpha.Value; public class Proxy { public int number() { Value v; return v.number(); } }
''', encoding="utf-8")
    middle = temp / "middle-library"
    subprocess.run([str(compiler), "library", str(middle_source), str(middle), "middle", "--library", str(one)], check=True)
    manifest = json.loads((middle / "z8-library.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in manifest["requires"]] == ["first"], manifest
    (app / "demo/Main.bl").write_text('''
import middle.Proxy; public class Main { public static int run() { Proxy value; return value.number(); } }
''', encoding="utf-8")
    missing = subprocess.run([str(compiler), "project", str(app), str(temp / "missing"), "--library", str(middle)], capture_output=True, text=True)
    assert missing.returncode and "missing BL library dependency: first" in missing.stderr, missing.stderr
    transitive = ["--library", str(one), "--library", str(middle)]
    subprocess.run([str(compiler), "build", str(app), "demo.Main.run", str(executable), *transitive], check=True)
    assert subprocess.run([str(executable)]).returncode == 20
    # Rebuilding a dependency with different declarations invalidates packages
    # compiled against its previous public metadata.
    (alpha / "alpha/Value.bl").write_text('public class Value { public int number() { return 21; } }', encoding="utf-8")
    subprocess.run([str(compiler), "library", str(alpha), str(one), "first"], check=True)
    outdated = subprocess.run([str(compiler), "project", str(app), str(temp / "outdated"), *transitive], capture_output=True, text=True)
    assert outdated.returncode and "dependency changed; rebuild middle" in outdated.stderr, outdated.stderr
print("Separately compiled BL libraries, collisions and dynamic lookup passed")
