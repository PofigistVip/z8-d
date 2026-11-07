"""Check the original stable, all-equal sort for binary and file arrays."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/BinaryFileArraySort.bl"
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("sort.exe" if os.name == "nt" else "sort")
    subprocess.run([str(compiler), "build", str(temp), "BinaryFileArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    source = temp / "views.d"
    source.write_text('''import z8.runtime;
import std.exception : assertThrown;
void check(T)(T first, T second) {
    auto values = new Z8Array!T([second, first]); auto view = z8_primary_array_view(values);
    auto savedVersion = values.z8_version; assert(values.z8_sort() is values);
    assert(values.z8_version == savedVersion + 1 && values.z8_get(0) is second && values.z8_get(1) is first);
    assert(z8_primary_cast!T(view.z8_get(0)) is second);
    auto leading = new Z8Array!T([null, first]); assert(leading.z8_sort() is leading && leading.z8_get(0) is null);
    auto invalid = new Z8Array!T([first, null]); assertThrown!Exception(invalid.z8_sort());
    auto large = new Z8Array!T(); large.z8_add(null);
    foreach (i; 0 .. 64) large.z8_add(i % 2 ? first : second);
    assert(large.z8_sort() is large && large.z8_get(0) is null);
    auto largeView = z8_primary_array_view(large); largeView.z8_sort();
    foreach (i; 1 .. 65) assert(large.z8_get(i) is ((i - 1) % 2 ? first : second));
    large.z8_add(null); assertThrown!Exception(large.z8_sort()); assertThrown!Exception(largeView.z8_sort());
}
void main() {
    check(z8_binary_literal("1"), z8_binary_literal("2"));
    check(z8_file_from_path("one"w), z8_file_from_path("two"w));
}''', encoding="utf-8")
    executable = temp / ("views.exe" if os.name == "nt" else "views")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    original = os.environ.get("Z8_ORIGINAL_ROOT")
    if original:
        jars = list((Path(original) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
        jars += [p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar") if not p.name.endswith("-sources.jar")]
        jars += [p for p in cache.rglob("*.jar") if p.name.startswith(("commons-fileupload-", "commons-io-", "commons-lang-", "commons-logging-")) and not p.name.endswith("-sources.jar")]
        if not jars:
            raise SystemExit("Original Z8 server jars are unavailable")
        java = temp / "BinaryFileSortOracle.java"
        java.write_text('''import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.binary;
import org.zenframework.z8.server.types.file;
class BinaryFileSortOracle {
  static <T> void check(T first, T second) {
    RCollection<T> values = new RCollection<>(); values.add(second); values.add(first);
    if (values.z8_sort() != values || values.get(0) != second || values.get(1) != first) throw new AssertionError("order");
    RCollection<T> leading = new RCollection<>(); leading.add(null); leading.add(first);
    leading.z8_sort(); if (leading.get(0) != null || leading.get(1) != first) throw new AssertionError("leading null");
    RCollection<T> invalid = new RCollection<>(); invalid.add(first); invalid.add(null);
    try { invalid.z8_sort(); throw new AssertionError("null accepted"); } catch (NullPointerException expected) {}
    RCollection<T> large = new RCollection<>(); large.add(null);
    for (int i = 0; i < 64; ++i) large.add(i % 2 == 0 ? second : first);
    large.z8_sort(); if (large.get(0) != null) throw new AssertionError("large leading null");
    for (int i = 1; i < 65; ++i) if (large.get(i) != ((i - 1) % 2 == 0 ? second : first)) throw new AssertionError("large order");
    large.add(null); try { large.z8_sort(); throw new AssertionError("large null accepted"); } catch (NullPointerException expected) {}
  }
  public static void main(String[] args) throws Exception {
    org.zenframework.z8.server.config.ServerConfig.load(args[0]);
    check(new binary(new byte[]{1}), new binary(new byte[]{2})); check(new file("one"), new file("two"));
  }
}''', encoding="utf-8")
        config = temp / "oracle.properties"
        config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
        subprocess.run(["java", "-cp", str(temp) + os.pathsep + classpath, "BinaryFileSortOracle", str(config)], cwd=temp, check=True)
print("Binary/file array sorting and shared views verified")
