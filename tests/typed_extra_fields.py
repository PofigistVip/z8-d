"""Exercise date, duration, binary, geometry and text field values."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/typed_extra_fields.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "FieldType.bl").write_text('[native "org.zenframework.z8.server.db.FieldType"] public enum FieldType { None, Guid, Geometry, Boolean, Integer, String, Date, Datetime, Datespan, Decimal, Binary, Text, Attachments, File, Null }', encoding="utf-8")
    (source / "Object.bl").write_text('[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object {}', encoding="utf-8")
    (source / "Field.bl").write_text('''
[native "org.zenframework.z8.server.base.table.value.Field"] public class Field extends Object {
    public string format;
    public FieldType getType(); public string getTypeName();
    public primary primary(); public date date(); public datespan datespan(); public binary binary();
    public geometry geometry(); public string string(); public bool isChanged();
}
''', encoding="utf-8")
    for name, kind, has_default in (("DatetimeField", "date", True), ("DatespanField", "datespan", False),
                                     ("BinaryField", "binary", True), ("GeometryField", "geometry", False),
                                     ("TextField", "string", True)):
        declaration = f"public {kind} defaultValue;" if has_default else ""
        metadata = "public int srs;" if name == "GeometryField" else "public bool html; public bool singleLine;" if name == "TextField" else ""
        (source / (name + ".bl")).write_text(f'''
[native "org.zenframework.z8.server.base.table.value.{name}"] public class {name} extends Field {{
    {declaration} {metadata} virtual public {kind} getDefault(); public void setDefault({kind} value);
    virtual public {kind} get(); public {name} operator = ({kind} value);
}}
''', encoding="utf-8")
    (source / "DateField.bl").write_text('[native "org.zenframework.z8.server.base.table.value.DateField"] public class DateField extends DatetimeField {}', encoding="utf-8")
    (source / "FileField.bl").write_text('[native "org.zenframework.z8.server.base.table.value.FileField"] public class FileField extends TextField {}', encoding="utf-8")
    (source / "AttachmentField.bl").write_text('[native "org.zenframework.z8.server.base.table.value.AttachmentField"] public class AttachmentField extends FileField {}', encoding="utf-8")
    (source / "Expression.bl").write_text('[native "org.zenframework.z8.server.base.table.value.Expression"] public class Expression extends Field {}', encoding="utf-8")
    for name, native in (("IntExpression", "IntegerExpression"), ("BoolExpression", "BoolExpression"),
                         ("FileExpression", "FileExpression"), ("DateExpression", "DateExpression")):
        (source / (name + ".bl")).write_text(f'[native "org.zenframework.z8.server.base.table.value.{native}"] public class {name} extends Expression {{}}', encoding="utf-8")
    (source / "CustomDate.bl").write_text("public class CustomDate extends DateField { virtual public date get() { return '01/01/2024'; } }", encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static bool run() {
        DatetimeField instant;
        if (instant.getType() != FieldType.Datetime || instant.getTypeName() != "datetime") return false;
        if (instant.format != "d.m.Y H:i") return false;
        if (instant.get() != date.Min || instant.defaultValue != date.Min) return false;
        instant.defaultValue = '01/01/2024'; if (instant.date().year() != 2024) return false;
        instant = '01/01/2025'; if (instant.get().year() != 2025 || !instant.isChanged()) return false;
        DateField day;
        if (day.getType() != FieldType.Date || day.getTypeName() != "date") return false;
        if (day.format != "d.m.Y") return false;
        if (day.get() != date.Min) return false;
        day = '29/02/2024'; if (day.date().day() != 29 || !day.isChanged()) return false;
        DatespanField duration;
        if (duration.getType() != FieldType.Datespan || duration.getTypeName() != "datespan") return false;
        if (duration.get() != '0 00:00:00') return false;
        duration.setDefault('1 02:03:04'); if (duration.datespan() != '1 02:03:04') return false;
        duration = '2 00:00:00'; if (duration.get() != '2 00:00:00' || !duration.isChanged()) return false;
        BinaryField bytes;
        if (bytes.getType() != FieldType.Binary || bytes.getTypeName() != "binary") return false;
        if (bytes.get().length() != 0) return false;
        bytes.defaultValue = '1, 2, 3'; if (bytes.binary().length() != 3) return false;
        bytes = '4, 5'; if (bytes.get().length() != 2 || !bytes.isChanged()) return false;
        GeometryField location;
        if (location.getType() != FieldType.Geometry || location.getTypeName() != "geometry") return false;
        if (location.srs != geometry.DefaultSRS) return false;
        location.srs = 4326; if (location.srs != 4326) return false;
        if (location.get().srs() != geometry.DefaultSRS) return false;
        location = geometry.point(1, 2, 4326); if (location.geometry().srs() != 4326 || !location.isChanged()) return false;
        TextField text;
        if (text.getType() != FieldType.Text || text.getTypeName() != "text") return false;
        if (text.html || text.singleLine) return false;
        text.html = true; text.singleLine = true; if (!text.html || !text.singleLine) return false;
        if (text.get() != "") return false;
        text.defaultValue = "start"; text = "changed";
        if (text.string() != "changed" || !text.isChanged()) return false;
        FileField file;
        if (file.getType() != FieldType.File || file.getTypeName() != "file") return false;
        if (file.get() != "") return false;
        AttachmentField attachment;
        if (attachment.getType() != FieldType.Attachments || attachment.getTypeName() != "attachments") return false;
        IntExpression intExpr; BoolExpression boolExpr; FileExpression fileExpr; DateExpression dateExpr;
        if (intExpr.getType() != FieldType.Integer || boolExpr.getType() != FieldType.Boolean || fileExpr.getType() != FieldType.File || dateExpr.getType() != FieldType.Date) return false;
        CustomDate custom; return custom.date().year() == 2024;
    }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        for name in ("Object", "FieldType", "Field", "DatetimeField", "DatespanField", "BinaryField", "GeometryField", "TextField", "DateField", "FileField", "AttachmentField", "Expression", "IntExpression", "BoolExpression", "FileExpression", "DateExpression"):
            (source / (name + ".bl")).unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        imports = "".join(f"import org.zenframework.z8.base.table.value.{name};\n" for name in
                          ("FieldType", "DatetimeField", "DatespanField", "BinaryField", "GeometryField", "TextField", "DateField", "FileField", "AttachmentField", "IntExpression", "BoolExpression", "FileExpression", "DateExpression"))
        for name in ("CustomDate", "Probe"):
            path = source / (name + ".bl")
            path.write_text(imports + path.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() { assert(z8_optional_require(Z8p_50726F6265.m_run())); }
''', encoding="utf-8")
    exe = temp / ("extra-fields.exe" if os.name == "nt" else "extra-fields")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Date, duration, binary, geometry and text field values verified")
