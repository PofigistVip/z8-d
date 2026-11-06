module z8.database.catalog;

import std.conv : to;
import z8.database.postgres;

// Read-only counterpart of the Java DataSchema descriptions. SQL definitions
// are retained verbatim so later migration planning can compare them.
struct Z8PostgresColumnDescription {
    string name, type, defaultExpression;
    bool nullable, hasDefault;
}
struct Z8PostgresIndexDescription {
    string name, definition;
    bool unique, primary;
}
struct Z8PostgresForeignKeyDescription {
    string name, definition;
    string targetSchema, targetTable;
    string[] columns, targetColumns;
    string matchType, updateAction, deleteAction;
    bool deferrable, initiallyDeferred, validated;
}
class Z8PostgresTableDescription {
    string schema, name, primaryKeyName;
    Z8PostgresColumnDescription[] columns;
    string[] primaryKeyColumns;
    string[] constraintNames;
    Z8PostgresIndexDescription[] indexes;
    Z8PostgresForeignKeyDescription[] foreignKeys;
}

// Return null when the table does not exist. Schema and table are parameters,
// including pg_temp, whose actual namespace varies by connection.
Z8PostgresTableDescription z8_postgres_describe_table(Z8PostgresConnection db, wstring schema, wstring table) {
    if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (schema is null || !schema.length || table is null || !table.length)
        throw new Z8PostgresException("empty PostgreSQL schema or table name");
    auto params = [Z8PostgresParameter.value(schema.to!string), Z8PostgresParameter.value(table.to!string)];
    enum whereTable = ` WHERE c.relnamespace = CASE WHEN $1 = 'pg_temp' THEN pg_catalog.pg_my_temp_schema()
        ELSE (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = $1) END
        AND c.relname = $2 AND c.relkind IN ('r', 'p') `;
    auto tables = db.execute(`SELECT n.nspname, c.relname FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace` ~ whereTable, params);
    if (!tables.rows.length) return null;
    auto description = new Z8PostgresTableDescription();
    description.schema = tables.rows[0][0].text; description.name = tables.rows[0][1].text;
    auto columns = db.execute(`SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
        NOT a.attnotnull, pg_catalog.pg_get_expr(d.adbin, d.adrelid)
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
        LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum` ~ whereTable ~
        ` AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum`, params);
    foreach (row; columns.rows)
        description.columns ~= Z8PostgresColumnDescription(row[0].text, row[1].text, row[3].text, row[2].text == "t", !row[3].isNull);
    auto keys = db.execute(`SELECT k.conname, a.attname FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_constraint k ON k.conrelid = c.oid AND k.contype = 'p'
        JOIN LATERAL unnest(k.conkey) WITH ORDINALITY AS keycols(attnum, position) ON true
        JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = keycols.attnum` ~ whereTable ~
        ` ORDER BY keycols.position`, params);
    foreach (row; keys.rows) { description.primaryKeyName = row[0].text; description.primaryKeyColumns ~= row[1].text; }
    auto constraints = db.execute(`SELECT k.conname FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_constraint k ON k.conrelid = c.oid` ~ whereTable ~ ` ORDER BY k.conname`, params);
    foreach (row; constraints.rows) description.constraintNames ~= row[0].text;
    auto indexes = db.execute(`SELECT i.relname, pg_catalog.pg_get_indexdef(i.oid), x.indisunique, x.indisprimary
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_index x ON x.indrelid = c.oid
        JOIN pg_catalog.pg_class i ON i.oid = x.indexrelid` ~ whereTable ~ ` ORDER BY i.relname`, params);
    foreach (row; indexes.rows) description.indexes ~= Z8PostgresIndexDescription(row[0].text, row[1].text, row[2].text == "t", row[3].text == "t");
    auto foreignKeys = db.execute(`SELECT k.conname, pg_catalog.pg_get_constraintdef(k.oid), n.nspname, r.relname,
        source_col.attname, target_col.attname, k.confmatchtype::text, k.confupdtype::text, k.confdeltype::text,
        k.condeferrable, k.condeferred, k.convalidated
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_constraint k ON k.conrelid = c.oid AND k.contype = 'f'
        JOIN pg_catalog.pg_class r ON r.oid = k.confrelid
        JOIN pg_catalog.pg_namespace n ON n.oid = r.relnamespace
        JOIN LATERAL unnest(k.conkey) WITH ORDINALITY AS source_keys(attnum, position) ON true
        JOIN LATERAL unnest(k.confkey) WITH ORDINALITY AS target_keys(attnum, position) ON target_keys.position = source_keys.position
        JOIN pg_catalog.pg_attribute source_col ON source_col.attrelid = c.oid AND source_col.attnum = source_keys.attnum
        JOIN pg_catalog.pg_attribute target_col ON target_col.attrelid = r.oid AND target_col.attnum = target_keys.attnum` ~ whereTable ~
        ` ORDER BY k.conname, source_keys.position`, params);
    foreach (row; foreignKeys.rows) {
        if (!description.foreignKeys.length || description.foreignKeys[$ - 1].name != row[0].text) {
            Z8PostgresForeignKeyDescription key;
            key.name = row[0].text; key.definition = row[1].text;
            key.targetSchema = row[2].text; key.targetTable = row[3].text;
            key.matchType = row[6].text; key.updateAction = row[7].text; key.deleteAction = row[8].text;
            key.deferrable = row[9].text == "t"; key.initiallyDeferred = row[10].text == "t"; key.validated = row[11].text == "t";
            description.foreignKeys ~= key;
        }
        description.foreignKeys[$ - 1].columns ~= row[4].text;
        description.foreignKeys[$ - 1].targetColumns ~= row[5].text;
    }
    return description;
}
