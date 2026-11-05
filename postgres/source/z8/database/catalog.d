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
}
class Z8PostgresTableDescription {
    string schema, name, primaryKeyName;
    Z8PostgresColumnDescription[] columns;
    string[] primaryKeyColumns;
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
    auto indexes = db.execute(`SELECT i.relname, pg_catalog.pg_get_indexdef(i.oid), x.indisunique, x.indisprimary
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_index x ON x.indrelid = c.oid
        JOIN pg_catalog.pg_class i ON i.oid = x.indexrelid` ~ whereTable ~ ` ORDER BY i.relname`, params);
    foreach (row; indexes.rows) description.indexes ~= Z8PostgresIndexDescription(row[0].text, row[1].text, row[2].text == "t", row[3].text == "t");
    auto foreignKeys = db.execute(`SELECT k.conname, pg_catalog.pg_get_constraintdef(k.oid)
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_constraint k ON k.conrelid = c.oid AND k.contype = 'f'` ~ whereTable ~
        ` ORDER BY k.conname`, params);
    foreach (row; foreignKeys.rows) description.foreignKeys ~= Z8PostgresForeignKeyDescription(row[0].text, row[1].text);
    return description;
}
