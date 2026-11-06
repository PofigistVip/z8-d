"""Compile and execute record metadata against separately built native fields."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
record_source = """
public class RecordProbe extends BaseTable {
    public IntField count;
    public string label = "Prefix";
    public string makeTitle() { return label + "!"; }
    records {
        [title "42 value"] [count -7] First = '00000000-0000-0000-0000-000000000001';
        [title makeTitle()] public Second = '00000000-0000-0000-0000-000000000002';
        Bare = '00000000-0000-0000-0000-000000000003';
    }
}
"""
base_source = """
public class BaseTable {
    public StringField title;
    records { [title "Base"] Base = '00000000-0000-0000-0000-000000000004'; }
}
"""
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "StringField.bl").write_text('[native "example.StringField"] public class StringField { public operator sql_string(); }', encoding="utf-8")
    (source / "IntField.bl").write_text('[native "example.IntField"] public class IntField { public operator sql_int(); }', encoding="utf-8")
    (source / "BaseTable.bl").write_text(base_source, encoding="utf-8")
    probe = source / "RecordProbe.bl"
    probe.write_text(record_source, encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.RecordProbe;
class CapturingTable : Z8p_5265636F726450726F6265 {
    int calls;
    override void z8_add_static_record(Z8Guid key, Z8StaticRecordValue[] values) {
        ++calls;
        super.z8_add_static_record(key, values);
    }
}
void main() {
    alias Probe = Z8p_5265636F726450726F6265;
    auto table = z8_new!Probe();
    assert(table.z8_static_records().length == 0);
    z8_initialize_static_records(table);
    auto records = table.z8_static_records();
    assert(records.length == 3);
    assert(records[0].key == z8_guid_literal("00000000-0000-0000-0000-000000000004"));
    assert(records[0].values.length == 1 && records[0].values[0].field is table.f_title);
    assert(records[0].values[0].value.textValue == "Base"w);
    assert(records[1].key == z8_guid_literal("00000000-0000-0000-0000-000000000001"));
    assert(records[1].values.length == 2);
    assert(records[1].values[0].field is table.f_title && records[1].values[0].value.textValue == "42 value"w);
    assert(records[1].values[1].field is table.f_count && records[1].values[1].value.integerValue == -7);
    assert(records[2].key == z8_guid_literal("00000000-0000-0000-0000-000000000002"));
    assert(records[2].values[0].value.textValue == "Prefix!"w);
    table.z8_init_static_records();
    assert(table.z8_static_records().length == 3);
    auto custom = z8_new!CapturingTable();
    z8_initialize_static_records(custom);
    assert(custom.calls == 3 && custom.z8_static_records().length == 3);
}
""", encoding="utf-8")
    executable = temp / ("records.exe" if os.name == "nt" else "records")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    invalid = [
        '[missing "x"]',
        '[title]',
        '[title 123]',
        '[count "x"]',
        '[title "x"] [title "y"]',
    ]
    for attributes in invalid:
        probe.write_text("class RecordProbe extends BaseTable { IntField count; records { " + attributes +
                         " A = '00000000-0000-0000-0000-000000000005'; } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(source), str(temp / "invalid")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit("Invalid record attribute accepted: " + attributes)
print("Record attributes preserve values, field identity and inheritance")
