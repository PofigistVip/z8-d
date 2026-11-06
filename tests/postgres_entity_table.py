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
    (source / "RegionTable.bl").write_text('''
import org.zenframework.z8.base.entity.EntityTable;
import org.zenframework.z8.base.table.value.StringField;
[name "Regions"] public class RegionTable extends EntityTable { [name "Label"] [entityValue] public StringField label; }
''', encoding="utf-8")
    (source / "GroupTable.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
import org.zenframework.z8.base.entity.EntityTable;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
[name "Groups"] public class GroupTable extends EntityTable {
    [name "Label"] [entityValue] public StringField label;
    public RegionTable region; [name "RegionId"] [entityValue] public Link regionId = region;
    regionId.joinType = JoinType.Left;
}
''', encoding="utf-8")
    (source / "PersonTable.bl").write_text('''
import org.zenframework.z8.base.entity.Entity;
import org.zenframework.z8.base.entity.EntityTable;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
[name "People"] public class PersonTable extends EntityTable {
    [name "Title"] [entityValue] public StringField title;
    [name "Amount"] [entityValue] public IntField amount;
    [name "Ignored"] public StringField ignored;
    public GroupTable group; [name "GroupId"] [entityValue] public Link groupId = group;
    groupId.joinType = JoinType.Left;
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
import org.zenframework.z8.base.entity.EntityTable;
public class EntityTableProbe {
    public static PersonTable table() { PersonTable table; return table; }
    public static Entity person() { PersonEntity entity; entity.set("title", "Alice"); entity.set("amount", 5); return entity; }
    public static Entity group() { Entity entity; entity.set("label", "Team"); return entity; }
    public static Entity region() { Entity entity; entity.set("label", "North"); return entity; }
    public static void link(Entity entity, guid id) { entity.set("groupId", id); }
    public static void linkRegion(Entity entity, guid id) { entity.set("regionId", id); }
    public static Entity withGroup(PersonTable table, guid id) { EntityTable[] dependencies = {table.group, table.group.region}; return table.readEntity(id, dependencies); }
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
    auto table = z8_nonnull(P.m_table());
    z8_nonnull(table.f_group);
    connection.execute(z8_postgres_create_table_sql("pg_temp"w, table.f_group.f_region));
    connection.execute(z8_postgres_create_table_sql("pg_temp"w, table.f_group));
    connection.execute(z8_postgres_create_table_sql("pg_temp"w, table));
    auto registry = P.m_registry(); table.m_setRegistry(registry);
    auto region = P.m_region(); table.f_group.f_region.m_create(region); auto regionId = region.m_getEntityId();
    auto group = P.m_group(); P.m_linkRegion(group, regionId); table.f_group.m_create(group); auto groupId = group.m_getEntityId();
    auto entity = P.m_person(); P.m_link(entity, groupId); table.m_create(entity);
    auto id = entity.m_getEntityId();
    assert(id !is null && id != z8_guid_zero() && z8_optional_require(entity.m_isPersistent()));
    assert(!z8_optional_require(entity.m_isChanged()) && z8_optional_require(table.m_exists(entity)));
    assert(z8_optional_require(table.f_beforeCreates) == 1 && z8_optional_require(table.f_afterCreates) == 1);
    auto loaded = P.m_withGroup(table, id);
    assert(loaded !is entity && z8_optional_require(P.m_personType(loaded)) && z8_optional_require(P.m_values(loaded, "Alice"w, 5)));
    assert(z8_optional_require(loaded.m_isRegistered()) && z8_optional_require(loaded.m_isPersistent()));
    auto loadedGroup = registry.m_getEntity(groupId);
    assert(loadedGroup !is null && loadedGroup !is group && loadedGroup.m_getString("label"w) == "Team"w);
    assert(z8_optional_require(loadedGroup.m_isPersistent()) && loaded.m_getEntity("groupId"w) is loadedGroup);
    auto loadedRegion = registry.m_getEntity(regionId);
    assert(loadedRegion !is null && loadedRegion.m_getString("label"w) == "North"w && loadedGroup.m_getEntity("regionId"w) is loadedRegion);
    assert(z8_optional_require(table.f_reads) == 1 && table.m_readEntity(id) is loaded && z8_optional_require(table.f_reads) == 1);
    P.m_change(loaded); table.m_update(loaded);
    assert(!z8_optional_require(loaded.m_isChanged()) && z8_optional_require(table.f_beforeUpdates) == 1 && z8_optional_require(table.f_afterUpdates) == 1);
    assert(connection.execute(`SELECT "Amount" FROM "People"`).rows[0][0].text == "9");
    table.m_readEntities(); auto entities = table.m_getEntities();
    assert(entities.z8_size() == 1 && entities.z8_get(id) is loaded);
    table.m_destroy(loaded);
    assert(!z8_optional_require(loaded.m_isPersistent()) && !z8_optional_require(table.m_exists(loaded)));
    assert(z8_optional_require(table.f_beforeDeletes) == 1 && z8_optional_require(table.f_afterDeletes) == 1);
    auto soloTable = P.m_table(); soloTable.m_setRegistry(registry);
    auto solo = P.m_person(); soloTable.m_create(solo); auto soloId = solo.m_getEntityId();
    registry.m_reset();
    auto soloLoaded = P.m_withGroup(soloTable, soloId);
    assert(soloLoaded !is null && soloLoaded.m_getEntity("groupId"w) is null);
    assert(registry.m_getEntity(groupId) is null && registry.m_getEntity(regionId) is null);
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
