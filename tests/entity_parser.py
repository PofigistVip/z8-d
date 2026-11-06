"""Exercise generated EntityParser hooks and JSON conversion."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/entity_parser.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "SampleEntity.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
public class SampleEntity extends Entity { public int marker = 17; }
''', encoding="utf-8")
    (source / "SampleParser.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
import org.zenframework.z8.base.entity.EntityParser;
public class SampleParser extends EntityParser {
    public int reads = 0; public int writes = 0; public int news = 0;
    virtual protected Entity newEntity() { news += 1; SampleEntity result; return result; }
    virtual public EntityParser read() { reads += 1; getEntity().set("title", getJson().getString("title")); return this; }
    virtual public EntityParser write() { writes += 1; getJson().set("title", getEntity().getString("title")); return this; }
    public void readParts() {
        readString("text"); readInt("number"); readDecimal("amount"); readBool("flag");
        readGuid("id"); readDate("day"); readDatespan("span");
        readJsonObject("object"); readJsonArray("array");
        readValue("csv", "decimal"); readValue("integerText", "integer");
        readValue("booleanText", "boolean"); readValue("text", "string");
        string[] keys = {"rawNumber", "rawBool"}; readValues(keys);
        readString("missing");
    }
}
''', encoding="utf-8")
    (source / "ParserProbe.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
import org.zenframework.z8.base.entity.Registry;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class ParserProbe {
    public static bool check() {
        SampleParser parser; Registry registry;
        if (parser.setRegistry(registry).getRegistry() != registry) return false;
        parser.setJson("{\\"title\\":\\"hello\\"}");
        Entity entity = parser.fromJson(parser.getJson());
        if (entity.getString("title") != "hello" || parser.reads != 1 || parser.news != 1) return false;
        if (!(entity instanceof SampleEntity) || !entity.isRegistered() || entity.getRegistry() != registry) return false;
        if (parser.getEntity() != entity || parser.news != 1) return false;
        entity.set("title", "changed");
        JsonObject result = parser.toJson(entity);
        if (result.getString("title") != "changed" || parser.writes != 1) return false;
        Entity noEntity = null;
        if (parser.toJson(noEntity) != null) return false;
        if (parser.getEntity() != entity) return false;
        Entity other; other.set("title", "world");
        Entity[] values = {entity, other};
        JsonArray encoded = parser.toJson(values);
        if (encoded.length() != 2 || encoded.getJsonObject(0).getString("title") != "changed" ||
            encoded.getJsonObject(1).getString("title") != "world") return false;
        Entity[] decoded = parser.fromJson(encoded);
        if (decoded.size() != 2 || decoded[0].getString("title") != "changed" ||
            decoded[1].getString("title") != "world" || parser.reads != 3 || parser.writes != 3) return false;
        JsonObject input;
        input.set("text", "hello"); input.set("number", 12); input.set("amount", 3.5); input.set("flag", true);
        input.set("id", '00000000-0000-0000-0000-000000000007'); input.set("day", "2024-02-01T00:00:00");
        input.set("span", "1 02:03:04"); input.set("csv", "1,25"); input.set("integerText", "42");
        input.set("booleanText", "true"); input.set("rawNumber", 77); input.set("rawBool", false);
        JsonObject nested; nested.set("value", "inside"); input.set("object", nested);
        JsonArray array; array.add("entry"); input.set("array", array);
        parser.setJson(input); parser.setEntity(entity); parser.readParts();
        if (entity.getString("text") != "hello" || entity.getInt("number") != 12 ||
            (decimal)entity.get("amount") != 3.5 || !entity.getBool("flag") ||
            entity.getGuid("id") != '00000000-0000-0000-0000-000000000007') return false;
        if (entity.getJsonObject("object").getString("value") != "inside" ||
            entity.getJsonArray("array").getString(0) != "entry") return false;
        if ((decimal)entity.get("csv") != 1.25 || entity.getInt("integerText") != 42 ||
            !entity.getBool("booleanText") || entity.getInt("rawNumber") != 77 || entity.getBool("rawBool")) return false;
        return true;
    }
    public static bool nullArray(SampleParser parser, JsonArray json) { return parser.fromJson(json).size() == 0; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime; import z8gen.p_ParserProbe; import z8gen.p_SampleParser;
void main() {
    assert(z8_optional_require(Z8p_50617273657250726F6265.m_check()));
    assert(z8_optional_require(Z8p_50617273657250726F6265.m_nullArray(z8_new!Z8p_53616D706C65506172736572(), null)));
}
''', encoding="utf-8")
    executable = temp / ("entity-parser.exe" if os.name == "nt" else "entity-parser")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("EntityParser state and virtual JSON hooks verified")
