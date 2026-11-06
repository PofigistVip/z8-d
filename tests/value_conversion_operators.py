"""Execute binary operators after conversion to non-SQL primary types."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    for name, kind in (("GuidValue", "guid"), ("DateValue", "date"), ("SpanValue", "datespan"),
                       ("FileValue", "file"), ("IntValue", "int"), ("TextValue", "string")):
        (source / (name + ".bl")).write_text(
            f'[native "example.{name}"] public class {name} {{ public operator {kind}(); }}', encoding="utf-8")
    (source / "Probe.bl").write_text("""
public class Probe {
    public static bool sameGuid(GuidValue value, guid other) { return value == other; }
    public static bool bothGuids(GuidValue left, GuidValue right) { return left == right; }
    public static bool rightGuid(guid left, GuidValue right) { return left == right; }
    public static bool earlier(DateValue value, date other) { return value < other; }
    public static bool bothDates(DateValue left, DateValue right) { return left <= right; }
    public static datespan difference(DateValue value, date other) { return value - other; }
    public static date plusDate(SpanValue value, date other) { return value + other; }
    public static bool longer(SpanValue value, datespan other) { return value > other; }
    public static bool sameFile(FileValue value, file other) { return value == other; }
    public static int sum(IntValue left, IntValue right) { return left + right; }
    public static int rightInt(int left, IntValue right) { return left + right; }
    public static bool sameText(TextValue left, TextValue right) { return left == right; }
}
""", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.Probe;
import z8gen.GuidValue;
import z8gen.DateValue;
import z8gen.SpanValue;
import z8gen.FileValue;
import z8gen.IntValue;
import z8gen.TextValue;
Z8Guid asGuid(Z8Object self) { return z8_guid_literal("00000000-0000-0000-0000-000000000001"); }
Z8Date asDate(Z8Object self) { return z8_date_from_ticks(1000); }
Z8Datespan asSpan(Z8Object self) { return new Z8Datespan(2000); }
Z8File asFile(Z8Object self) { return z8_file_from_path("same.txt"w); }
Z8Optional!long asInt(Z8Object self) { return z8_optional_wrap(3L); }
wstring asText(Z8Object self) { return "same"w; }
void main() {
    alias P = Z8p_50726F6265;
    z8_native_bind("example.GuidValue.z8cast_guid"w, &asGuid);
    z8_native_bind("example.DateValue.z8cast_date"w, &asDate);
    z8_native_bind("example.SpanValue.z8cast_datespan"w, &asSpan);
    z8_native_bind("example.FileValue.z8cast_file"w, &asFile);
    z8_native_bind("example.IntValue.z8cast_int"w, &asInt);
    z8_native_bind("example.TextValue.z8cast_string"w, &asText);
    auto g = z8_new!Z8p_4775696456616C7565();
    auto d = z8_new!Z8p_4461746556616C7565();
    auto s = z8_new!Z8p_5370616E56616C7565();
    auto f = z8_new!Z8p_46696C6556616C7565();
    auto i = z8_new!Z8p_496E7456616C7565();
    auto t = z8_new!Z8p_5465787456616C7565();
    assert(z8_optional_require(P.m_sameGuid(g, asGuid(null))));
    assert(z8_optional_require(P.m_bothGuids(g, g)));
    assert(z8_optional_require(P.m_rightGuid(asGuid(null), g)));
    assert(z8_optional_require(P.m_earlier(d, z8_date_from_ticks(5000))));
    assert(z8_optional_require(P.m_bothDates(d, d)));
    assert(z8_datespan_milliseconds(P.m_difference(d, z8_date_from_ticks(5000))) == -4000);
    assert(z8_date_ticks(P.m_plusDate(s, z8_date_from_ticks(5000))) == 7000);
    assert(z8_optional_require(P.m_longer(s, new Z8Datespan(1000))));
    assert(z8_optional_require(P.m_sameFile(f, z8_file_from_path("same.txt"w))));
    assert(z8_optional_require(P.m_sum(i, i)) == 6);
    assert(z8_optional_require(P.m_rightInt(4, i)) == 7);
    assert(z8_optional_require(P.m_sameText(t, t)));
}
""", encoding="utf-8")
    executable = temp / ("value-operators.exe" if os.name == "nt" else "value-operators")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Ambiguous.bl").write_text(
        '[native "example.Ambiguous"] class Ambiguous { public operator guid(); public operator sql_guid(); }',
        encoding="utf-8")
    (source / "Bad.bl").write_text(
        'class Bad { public static void f(Ambiguous value, guid id) { if (value == id) return; } }',
        encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "invalid")], capture_output=True, text=True)
    if result.returncode == 0 or "ambiguous binary operator" not in result.stderr:
        raise SystemExit("A conflicting pair of conversions was not diagnosed: " + result.stderr)
print("Operators after guid, date, datespan and file conversions verified")
