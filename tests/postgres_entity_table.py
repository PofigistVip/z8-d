"""Exercise EntityTable reads, writes and lifecycle hooks on PostgreSQL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_entity_table.py <original-z8-root> [postgres-bin]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "PersonEntity.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
public class PersonEntity extends Entity {}
''', encoding="utf-8")
    (source / "PersonTable.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
import org.zenframework.z8.base.entity.EntityTable;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntField;
[name "People"] public class PersonTable extends EntityTable {
    [name "Title"] [entityValue] public StringField title;
    [name "Amount"] [entityValue] public IntField amount;
    [name "Ignored"] public StringField ignored;
    public int beforeCreates = 0; public int afterCreates = 0; public int beforeUpdates = 0;
    public int afterUpdates = 0; public int beforeDeletes = 0; public int afterDeletes = 0; public int reads = 0;
    virtual protected Entity newEntity() { PersonEntity value; return value; }
    virtual protected void beforeCreate(Entity entity) { beforeCreates = beforeCreates + 1; }
    virtual protected void afterCreate(Entity entity) { afterCreates = afterCreates + 1; }
    virtual protected void beforeUpdate(Entity entity) { beforeUpdates = beforeUpdates + 1; }
    virtual protected void afterUpdate(Entity entity) { afterUpdates = afterUpdates + 1; }
    virtual protected void beforeDestroy(Entity entity) { beforeDeletes = beforeDeletes + 1; }
    virtual protected void afterDestroy(Entity entity) { afterDeletes = afterDeletes + 1; }
    virtual protected void afterRead(Entity entity) { reads = reads + 1; }
}
''', encoding="utf-8")
    (source / "EntityTableProbe.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
import org.zenframework.z8.base.entity.Registry;
public class EntityTableProbe {
    public static PersonTable table() { PersonTable table; return table; }
    public static Entity person() { PersonEntity entity; entity.set("title", "Alice"); entity.set("amount", 5); return entity; }
    public static Registry registry() { Registry value; return value; }
    public static void change(Entity entity) { entity.set("amount", 9); }
    public static bool values(Entity entity, string title, int amount) { return entity.getString("title") == title && entity.getInt("amount") == amount; }
    public static bool personType(Entity entity) { return entity instanceof PersonEntity; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8.database.schema;
import z8gen.p_EntityTableProbe;
void main(string[] args) {
    alias P = Z8p_456E746974795461626C6550726F6265;
    auto connection = new Z8PostgresConnection(args[1]); scope(exit) connection.close();
    auto backend = new Z8PostgresDatabase(connection, "pg_temp"w);
    auto previous = z8_connection_set_current(backend); scope(exit) z8_connection_set_current(previous);
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    auto request = new Z8ApplicationRequest(); request.session = new Z8ApplicationSession("test"w, user, user);
    auto previousRequest = z8_application_set_request(request); scope(exit) z8_application_set_request(previousRequest);
    auto table = P.m_table(); connection.execute(z8_postgres_create_table_sql("pg_temp"w, table));
    auto registry = P.m_registry(); table.m_setRegistry(registry);
    auto entity = P.m_person(); table.m_create(entity);
    auto id = entity.m_getEntityId();
    assert(id !is null && id != z8_guid_zero() && z8_optional_require(entity.m_isPersistent()));
    assert(!z8_optional_require(entity.m_isChanged()) && z8_optional_require(table.m_exists(entity)));
    assert(z8_optional_require(table.f_beforeCreates) == 1 && z8_optional_require(table.f_afterCreates) == 1);
    auto loaded = table.m_readEntity(id);
    assert(loaded !is entity && z8_optional_require(P.m_personType(loaded)) && z8_optional_require(P.m_values(loaded, "Alice"w, 5)));
    assert(z8_optional_require(loaded.m_isRegistered()) && z8_optional_require(loaded.m_isPersistent()));
    assert(z8_optional_require(table.f_reads) == 1 && table.m_readEntity(id) is loaded && z8_optional_require(table.f_reads) == 1);
    P.m_change(loaded); table.m_update(loaded);
    assert(!z8_optional_require(loaded.m_isChanged()) && z8_optional_require(table.f_beforeUpdates) == 1 && z8_optional_require(table.f_afterUpdates) == 1);
    assert(connection.execute(`SELECT "Amount" FROM "People"`).rows[0][0].text == "9");
    table.m_readEntities(); auto entities = table.m_getEntities();
    assert(entities.z8_size() == 1 && entities.z8_get(id) is loaded);
    table.m_destroy(loaded);
    assert(!z8_optional_require(loaded.m_isPersistent()) && !z8_optional_require(table.m_exists(loaded)));
    assert(z8_optional_require(table.f_beforeDeletes) == 1 && z8_optional_require(table.f_afterDeletes) == 1);
}
''', encoding="utf-8")
    executable = temp / ("entity-table.exe" if os.name == "nt" else "entity-table")
    args = ["-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
            *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(harness), str(runtime)]
    args += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    args += ["-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        subprocess.run([str(executable), connection], env=environment, cwd=temp, check=True)
print("EntityTable CRUD, identity and lifecycle hooks verified")
