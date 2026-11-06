"""Synchronize unmodified Z8 BL/web sources and monitor native Java classes."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor/z8"
MANIFEST = ROOT / "vendor/z8-sync.json"
NATIVE = ROOT / "vendor/z8-native-baseline.json"
TREES = {
    "bl": ("org.zenframework.z8.lang/src/bl",),
    "web": ("org.zenframework.z8.js/src", "org.zenframework.z8.resources/src/web"),
}
ATTRIBUTE = re.compile(r'\[(?:native|primary)\s+"([A-Za-z_$][\w.$]*)"\s*\]')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def assert_safe(root, path):
    """Do not follow links within a managed tree or escape its root."""
    root = root.absolute()
    path = path.absolute()
    relative = path.relative_to(root)
    current = root
    for part in ("", *relative.parts):
        if part:
            current /= part
        if current.is_symlink():
            raise ValueError(f"Symbolic link in managed tree: {current}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path outside managed tree: {path}")


def source_files(original, group):
    result = {}
    for name in TREES[group]:
        base = original / name
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"Missing or linked source directory: {base}")
        for path in base.rglob("*"):
            assert_safe(original, path)
            if path.is_file():
                relative = path.relative_to(original).as_posix()
                result[relative] = path.read_bytes()
    if not result:
        raise ValueError(f"No {group} source files found")
    return result


def synchronize(original, group, apply):
    files = source_files(original, group)
    manifest = load(MANIFEST, {"format": 1, "groups": {}})
    if manifest.get("format") != 1:
        raise ValueError("Unsupported sync manifest")
    previous = manifest["groups"].get(group, {})
    changes, conflicts = [], []
    for name in sorted(set(previous) | set(files)):
        target = VENDOR / name
        assert_safe(VENDOR, target)
        if target.exists() and not target.is_file():
            conflicts.append(name)
            continue
        actual = digest(target.read_bytes()) if target.exists() else None
        old, desired = previous.get(name), digest(files[name]) if name in files else None
        if actual not in (old, desired):
            conflicts.append(name)
        elif actual != desired:
            changes.append((name, desired))
    if conflicts:
        raise ValueError("Locally modified or unmanaged files; no changes applied:\n" + "\n".join(conflicts))
    for name, value in changes:
        print(("update " if value else "remove ") + name)
    if apply:
        for name, value in changes:
            target = VENDOR / name
            if value:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(files[name])
            else:
                target.unlink()
        manifest["groups"][group] = {name: digest(data) for name, data in sorted(files.items())}
        save(MANIFEST, manifest)
    print(f"{group}: {len(files)} source files, {len(changes)} changes" + (" applied" if apply else " (preview)"))
    return bool(changes)


def native_snapshot(original):
    bl_root = original / TREES["bl"][0]
    if not bl_root.is_dir():
        raise ValueError(f"Missing BL source directory: {bl_root}")
    java_roots = sorted(p for p in original.glob("*/src/main/java") if p.is_dir())
    if not java_roots:
        raise ValueError("No Java source roots found")
    entries = {}
    for base, prefix in ((bl_root, ""), (ROOT / "platform/bl", "platform/bl/")):
        if not base.is_dir():
            continue
        for bl in sorted(base.rglob("*.bl")):
            for name in set(ATTRIBUTE.findall(bl.read_text(encoding="utf-8-sig"))):
                java_relative = Path(*name.split(".")).with_suffix(".java")
                matches = [root / java_relative for root in java_roots if (root / java_relative).is_file()]
                if len(matches) > 1:
                    raise ValueError(f"Ambiguous Java native class: {name}")
                key = prefix + bl.relative_to(base).as_posix() + " :: " + name
                path = matches[0] if matches else None
                entries[key] = {"java": path.relative_to(original).as_posix() if path else None,
                                "sha256": digest(path.read_bytes()) if path else None}
    # Conservatively monitor helper classes in modules containing native code.
    # The explicitly deferred justintime module is intentionally excluded.
    direct = {value["java"] for value in entries.values() if value["java"]}
    modules = {name.split("/", 1)[0] for name in direct if name.split("/", 1)[0] != "org.zenframework.z8.justintime"}
    supporting = {}
    for module in sorted(modules):
        for path in sorted((original / module / "src/main/java").rglob("*.java")):
            name = path.relative_to(original).as_posix()
            if name not in direct:
                supporting[name] = digest(path.read_bytes())
    return entries, supporting


def native_report(original, accept):
    current, supporting = native_snapshot(original)
    baseline = load(NATIVE, {"format": 1, "entries": {}})
    if baseline.get("format") != 1:
        raise ValueError("Unsupported native baseline")
    before = baseline["entries"]
    changed = [key for key in sorted(set(before) | set(current)) if before.get(key) != current.get(key)]
    for key in changed:
        kind = "added" if key not in before else "removed" if key not in current else "changed"
        print(f"{kind}: {key}")
        if key in before:
            print("  previous: " + str(before[key]["java"]))
        if key in current:
            print("  current:  " + str(current[key]["java"]))
    missing = [key for key, value in current.items() if value["java"] is None]
    print(f"Native bindings: {len(current)}, changed: {len(changed)}, unresolved: {len(missing)}")
    for key in missing:
        print("unresolved: " + key)
    old_supporting = baseline.get("supporting", {})
    changed_supporting = [name for name in sorted(set(old_supporting) | set(supporting))
                          if old_supporting.get(name) != supporting.get(name)]
    for name in changed_supporting:
        kind = "added" if name not in old_supporting else "removed" if name not in supporting else "changed"
        print(f"{kind} supporting Java source: {name}")
    print(f"Supporting Java sources: {len(supporting)}, changed: {len(changed_supporting)}")
    if accept:
        save(NATIVE, {"format": 1, "entries": current, "supporting": supporting})
        print("Native baseline updated; review the corresponding D implementations separately.")
    return bool(changed or changed_supporting)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=("bl", "web", "native"))
    parser.add_argument("original", type=Path, help="Original org.zenframework.z8 checkout")
    parser.add_argument("--apply", action="store_true", help="Apply BL/web file changes")
    parser.add_argument("--accept", action="store_true", help="Update the native Java baseline after review")
    args = parser.parse_args()
    if (args.group == "native" and args.apply) or (args.group != "native" and args.accept):
        parser.error("--apply is for bl/web; --accept is for native")
    original = args.original.resolve()
    if not original.is_dir():
        parser.error("Original checkout not found")
    try:
        if args.group == "bl":
            print("Checking Java sources for BL native bindings:")
            native_changed = native_report(original, False)
            changed = synchronize(original, args.group, args.apply)
            if native_changed:
                print("Java native changes require review; BL sync does not accept the native baseline.")
            return 1 if native_changed or (changed and not args.apply) else 0
        changed = native_report(original, args.accept) if args.group == "native" else synchronize(original, args.group, args.apply)
        return 1 if changed and not (args.apply or args.accept) else 0
    except (OSError, ValueError, KeyError) as error:
        print(f"sync_z8: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
