"""Exercise Entity value state and lifecycle hooks from generated BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/entity_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "TrackedEntity.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
public class TrackedEntity extends Entity {
    public int changes = 0; public int created = 0; public int removed = 0; public string last = "";
    virtual protected void onChange(string key) { changes = changes + 1; last = key; }
    virtual protected void onCreate() { created = created + 1; }
    virtual protected void onDelete() { removed = removed + 1; }
}
''', encoding="utf-8")
    (source / "EntityProbe.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class EntityProbe {
    public static JsonObject noObject() { return null; }
    public static bool verify() {
        TrackedEntity item;
        if (!item.isNull() || item.isInitialized() || item.isChanged() || item.isDeleted() || item.isPersistent()) return false;
        item.init("number", 1); item.init("name", "initial");
        if (!item.isInitialized() || item.isChanged() || item.getInt("number") != 1 || item.getString("name") != "initial") return false;
        item.set("number", 1); if (item.changes != 0) return false;
        item.set("number", 2); item.set("new", "value");
        if (!item.isChanged() || !item.isChanged("number") || !item.has("new") || item.getInt("number") != 2 || item.changes != 2) return false;
        primary[string] values = item.values();
        if ((int)values["number"] != 1 || values.containsKey("new")) return false;
        string[] keys = {"number", "new"}; values = item.values(keys);
        if ((int)values["number"] != 2 || (string)values["new"] != "value") return false;
        item.touch("name"); if (item.changes != 3 || item.last != "name") return false;
        item.set("flag", "true"); if (!item.getBool("flag")) return false;
        item.set("link", "00000000-0000-0000-0000-000000000007");
        if (item.getGuid("link") != guid.create(7)) return false;
        item.set("object", JsonObject.parse("{a:1}")); item.set("array", JsonArray.parse("[2,3]"));
        if (item.getJsonObject("object").getInt("a") != 1 || item.getJsonArray("array").getInt(1) != 3) return false;
        Entity absent = null; JsonObject missing = noObject();
        item.set("nullLink", absent); item.set("nullObject", missing);
        if (item.getGuid("nullLink") != guid.Null || item.getJsonObject("nullObject") != null) return false;
        item.create(guid.create(17));
        if (item.getEntityId() != guid.create(17) || item.created != 1 || item.isNull() || item.isChanged(Entity.EntityId)) return false;
        item.delete(); if (!item.isDeleted() || item.removed != 1) return false;
        Entity first; Entity second;
        if (first != second) return false;
        first.setEntityId(guid.create(1)); second.setEntityId(guid.create(2));
        return first != second && Entity.EntityId == "recordId" && Entity.OriginId == "originId";
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_EntityProbe;
void main() { assert(z8_optional_require(Z8p_456E7469747950726F6265.m_verify())); }
''', encoding="utf-8")
    executable = temp / ("entity.exe" if os.name == "nt" else "entity")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Entity defaults, changes and lifecycle hooks verified")
