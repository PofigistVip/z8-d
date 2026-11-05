"""Assemble the original Z8 web client into a public document root.

The concatenation order and resources follow org.zenframework.z8.js/build.gradle.
JavaScript and CSS source bytes are copied verbatim, with the same newline
separator Gradle adds between files. The index is a Z8 resource template.
"""
from pathlib import Path
import argparse
import shutil


def assemble(original_root, output):
    original = Path(original_root).resolve()
    output = Path(output).resolve()
    source = original / "org.zenframework.z8.js" / "src"
    index = original / "org.zenframework.z8.resources" / "src" / "web" / "index.html"
    if not source.is_dir() or not index.is_file():
        raise ValueError("Original Z8 web-client sources not found")
    if output == original or original in output.parents:
        raise ValueError("Output must be outside the original Z8 source tree")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    bundles = [("js", ".buildorder", "revolt.js"), ("js", ".util.buildorder", "revolt.util.js"),
               ("js", ".server.buildorder", "revolt.server.js"), ("css", ".buildorder", "css/revolt.css"),
               ("css", ".fonts.buildorder", "css/revolt.fonts.css"), ("css", ".base.buildorder", "css/revolt.base.css")]
    inputs = []
    for folder, order, destination in bundles:
        base = (source / folder).resolve()
        paths = []
        for line in (base / order).read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if not name or name.startswith("#"): continue
            item = (base / name).resolve()
            if base not in item.parents or not item.is_file():
                raise ValueError(f"Invalid build-order entry: {name}")
            paths.append(item)
        inputs.append((paths, destination))
    for name in ("fonts", "img"):
        if not (source / "css" / name).is_dir(): raise ValueError(f"Missing CSS resource directory: {name}")
    output.mkdir(parents=True, exist_ok=True)
    for paths, destination in inputs:
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as stream:
            for path in paths:
                stream.write(path.read_bytes())
                stream.write(b"\n")
    for name in ("fonts", "img"):
        shutil.copytree(source / "css" / name, output / "css" / name)
    template = index.read_bytes()
    (output / "index.html").write_bytes(template.replace(b"${project.name}", b"revolt"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_z8", type=Path, help="Root of the original Z8 source tree")
    parser.add_argument("output", type=Path, help="New or empty public document root")
    args = parser.parse_args()
    assemble(args.original_z8, args.output)
    print(f"Prepared Z8 web client in {args.output}")
