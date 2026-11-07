"""Compare geometry-array sort order and stable aliases with Java Z8."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/GeometryArraySort.bl"
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("sort.exe" if os.name == "nt" else "sort")
    subprocess.run([str(compiler), "build", str(temp), "GeometryArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    source = temp / "views.d"
    source.write_text('''import z8.runtime;
import std.exception : assertThrown;
import std.stdio : writeln;
import std.conv : to;
void main() {
    auto first = z8_geometry_fromHexString("B"w), equal = z8_geometry_fromHexString("B"w), earlier = z8_geometry_fromHexString("A"w);
    auto values = new Z8Array!Z8Geometry([first, earlier, equal]); auto view = z8_primary_array_view(values);
    assert(values.z8_sort() is values && values.z8_get(0) is earlier && values.z8_get(1) is first && values.z8_get(2) is equal);
    assert(z8_primary_cast!Z8Geometry(view.z8_get(0)) is earlier && z8_primary_cast!Z8Geometry(view.z8_get(2)) is equal);
    auto leading = new Z8Array!Z8Geometry([null, first]); leading.z8_sort();
    assert(leading.z8_get(0) is first && leading.z8_get(1) is null);
    auto invalid = new Z8Array!Z8Geometry([first, z8_geometry_none(4326)]);
    assertThrown!Exception(invalid.z8_sort());
    auto points = new Z8Array!Z8Geometry([z8_geometry_point(z8_decimal_from_int(2), z8_decimal_from_int(0), 4326),
        z8_geometry_point(z8_decimal_from_int(-1), z8_decimal_from_int(0), 4326)]);
    points.z8_sort(); foreach (i; 0 .. points.z8_size()) writeln(z8_geometry_to_string(points.z8_get(i)).to!string);
}''', encoding="utf-8")
    executable = temp / ("views.exe" if os.name == "nt" else "views")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    output = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    original = os.environ.get("Z8_ORIGINAL_ROOT")
    if original:
        jars = list((Path(original) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
        jars += [p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar") if not p.name.endswith("-sources.jar")]
        if not jars:
            raise SystemExit("Original Z8 server jars are unavailable")
        java = temp / "GeometrySortOracle.java"
        java.write_text('''import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.geometry;
class GeometrySortOracle {
  public static void main(String[] args) throws Exception {
    org.zenframework.z8.server.config.ServerConfig.load(args[0]);
    geometry first = new geometry("B"), equal = new geometry("B"), earlier = new geometry("A");
    RCollection<geometry> values = new RCollection<>(new geometry[]{first, earlier, equal});
    if (values.z8_sort() != values || values.get(0) != earlier || values.get(1) != first || values.get(2) != equal)
      throw new AssertionError("geometry order differs");
    RCollection<geometry> leading = new RCollection<>(new geometry[]{null, first});
    leading.z8_sort(); if (leading.get(0) != first || leading.get(1) != null) throw new AssertionError("leading null differs");
    RCollection<geometry> points = new RCollection<>(new geometry[]{new geometry(2, 0, 4326), new geometry(-1, 0, 4326)});
    points.z8_sort(); for (geometry point : points) System.out.println(point.get());
  }
}''', encoding="utf-8")
        config = temp / "oracle.properties"
        config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
        expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "GeometrySortOracle", str(config)], cwd=temp, text=True, encoding="utf-8").splitlines()
        assert output == expected, (output, expected)
print("Geometry-array sorting and shared views verified")
