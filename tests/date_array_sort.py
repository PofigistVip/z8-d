"""Compile date-array sorting and verify shared primary-array views."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/DateArraySort.bl"
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("date-sort.exe" if os.name == "nt" else "date-sort")
    subprocess.run([str(compiler), "build", str(temp), "DateArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    source = temp / "views.d"
    source.write_text('''import z8.runtime;
import std.exception : assertThrown;
void main() {
    auto earlier = z8_date_from_ticks(1000), first = z8_date_from_ticks(2000), equal = z8_date_from_ticks(2000);
    auto values = new Z8Array!Z8Date([equal, earlier, first]);
    auto view = z8_primary_array_view(values);
    auto result = values.z8_sort();
    assert(result is values && values.z8_get(0) is earlier && values.z8_get(1) is equal && values.z8_get(2) is first);
    assert(z8_primary_cast!Z8Date(view.z8_get(0)) is earlier && z8_primary_cast!Z8Date(view.z8_get(1)) is equal);
    view.z8_add(null);
    assertThrown!Exception(values.z8_sort());
    auto empty = new Z8Array!Z8Date(); assert(empty.z8_sort() is empty);
    auto single = new Z8Array!Z8Date([null]); assert(single.z8_sort() is single);
    auto nullFirst = new Z8Array!Z8Date([null, earlier]);
    auto nullView = z8_primary_array_view(nullFirst);
    nullFirst.z8_sort();
    assert(nullFirst.z8_get(0) is earlier && nullFirst.z8_get(1) is null && nullView.z8_get(1) is null);
}
''', encoding="utf-8")
    executable = temp / ("date-views.exe" if os.name == "nt" else "date-views")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    original = os.environ.get("Z8_ORIGINAL_ROOT")
    if original:
        jars = list((Path(original) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
        jars += [p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar") if not p.name.endswith("-sources.jar")]
        if not jars:
            raise SystemExit("Original Z8 server jars are unavailable")
        java = temp / "DateSortOracle.java"
        java.write_text('''import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.date;
class DateSortOracle {
    public static void main(String[] args) {
        date earlier = new date(1000L), first = new date(2000L), equal = new date(2000L);
        RCollection<date> values = new RCollection<>(new date[]{equal, earlier, first});
        if (values.z8_sort() != values || values.get(0) != earlier || values.get(1) != equal || values.get(2) != first)
            throw new AssertionError("sort order or stability differs");
        RCollection<date> single = new RCollection<>(new date[]{null});
        if (single.z8_sort() != single) throw new AssertionError("single null failed");
        RCollection<date> nullFirst = new RCollection<>(new date[]{null, earlier});
        nullFirst.z8_sort();
        if (nullFirst.get(0) != earlier || nullFirst.get(1) != null) throw new AssertionError("leading null differs");
        values.add(null);
        try { values.z8_sort(); throw new AssertionError("null was accepted"); }
        catch (NullPointerException expected) {}
    }
}''', encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
        subprocess.run(["java", "-cp", str(temp) + os.pathsep + classpath, "DateSortOracle"], cwd=temp, check=True)
print("Date-array sorting, stability and shared views verified")
