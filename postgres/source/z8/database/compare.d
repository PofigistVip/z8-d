module z8.database.compare;

import std.ascii : toLower;
import std.conv : to;
import z8.runtime;
import z8.database.catalog;
import z8.database.postgres : Z8PostgresException;
import z8.database.schema : fieldType, foreignKeyTarget;

enum Z8SchemaDifferenceKind { missingTable, missingColumn, extraColumn, columnType, nullability, primaryKey, missingForeignKey, extraForeignKey }
struct Z8SchemaDifference {
    Z8SchemaDifferenceKind kind;
    string column, expected, actual;
}

enum Z8SchemaIndexDifferenceKind { missingIndex, unsupportedIndex }
struct Z8SchemaIndexDifference {
    Z8SchemaIndexDifferenceKind kind;
    string column, expected;
}
package struct Z8ExpectedIndex {
    Z8Object field;
    string column, method, operatorClass;
    bool unique, unsupported;
}
package Z8ExpectedIndex[] z8_postgres_expected_indexes(Z8Object table) {
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
        throw new Z8PostgresException("PostgreSQL schema requires a Table");
    Z8ExpectedIndex[] result;
    foreach (field; z8_query_declared_fields(table, true)) {
        auto options = z8_field_index_options(field);
        auto kind = z8_field_type_id(field);
        if (!options.indexed && !options.unique && !(kind == "string"w && options.trigram)) continue;
        if (options.unique && (kind == "geometry"w || (kind == "string"w && options.trigram)))
            throw new Z8PostgresException("PostgreSQL GIN and GiST indexes cannot be unique");
        Z8ExpectedIndex expected; expected.field = field;
        expected.column = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field).to!string;
        expected.method = kind == "geometry"w ? "gist" : kind == "string"w && options.trigram ? "gin" : "btree";
        expected.operatorClass = expected.method == "gin" ? "gin_trgm_ops" : null;
        expected.unique = options.unique;
        expected.unsupported = kind == "string"w && options.caseInsensitive;
        result ~= expected;
    }
    return result;
}
private bool indexMatches(Z8ExpectedIndex expected, Z8PostgresIndexDescription actual) {
    import std.algorithm.searching : canFind;
    if (actual.primary || !actual.valid || !actual.ready || actual.partial || actual.columns != 1 || actual.options != 0 ||
        !actual.immediate || actual.exclusion || !actual.columnCollation || actual.column != expected.column ||
        actual.method != expected.method || actual.unique != expected.unique ||
        (actual.unique && actual.definition.canFind(" NULLS NOT DISTINCT"))) return false;
    return expected.operatorClass is null ? actual.defaultOperatorClass : actual.operatorClass == expected.operatorClass;
}
// Compare supported single-column indexes structurally, independent of names.
// Expression indexes are reported separately; extra user indexes are retained.
Z8SchemaIndexDifference[] z8_postgres_compare_indexes(Z8Object table, Z8PostgresTableDescription actual) {
    auto expected = z8_postgres_expected_indexes(table);
    if (actual is null) throw new Z8PostgresException("cannot compare indexes on a missing PostgreSQL table");
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table).to!string;
    if (actual.name != tableName) throw new Z8PostgresException("PostgreSQL table description does not match BL table");
    Z8SchemaIndexDifference[] result;
    foreach (index; expected) {
        auto description = (index.unique ? "unique " : "") ~ index.method;
        if (index.unsupported) { result ~= Z8SchemaIndexDifference(Z8SchemaIndexDifferenceKind.unsupportedIndex, index.column, description ~ " expression"); continue; }
        bool found; foreach (existing; actual.indexes) if (indexMatches(index, existing)) { found = true; break; }
        if (!found) result ~= Z8SchemaIndexDifference(Z8SchemaIndexDifferenceKind.missingIndex, index.column, description);
    }
    return result;
}

// PostgreSQL's format_type may insert spaces or vary type-name capitalization.
private string normalizedType(string value) {
    char[] result;
    foreach (char ch; value) if (ch != ' ' && ch != '\t' && ch != '\r' && ch != '\n') result ~= toLower(ch);
    return cast(string)result;
}

// Read-only structural comparison. Defaults and indexes require separate
// PostgreSQL expression comparison.
Z8SchemaDifference[] z8_postgres_compare_table(Z8Object table, Z8PostgresTableDescription actual) {
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
        throw new Z8PostgresException("PostgreSQL schema requires a Table");
    auto expectedTable = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table).to!string;
    if (actual is null) return [Z8SchemaDifference(Z8SchemaDifferenceKind.missingTable, "", expectedTable, "")];
    if (actual.name != expectedTable) throw new Z8PostgresException("PostgreSQL table description does not match BL table");
    auto fields = z8_query_declared_fields(table, true);
    auto key = z8_query_primary_key(table);
    if (key is null) throw new Z8PostgresException("PostgreSQL table has no primary key");
    string[] expectedNames;
    Z8SchemaDifference[] result;
    foreach (field; fields) {
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field).to!string;
        foreach (previous; expectedNames) if (previous == name) throw new Z8PostgresException("duplicate PostgreSQL column name");
        expectedNames ~= name;
        Z8PostgresColumnDescription* existing;
        foreach (ref column; actual.columns) if (column.name == name) { existing = &column; break; }
        auto type = fieldType(field);
        if (existing is null) { result ~= Z8SchemaDifference(Z8SchemaDifferenceKind.missingColumn, name, type, ""); continue; }
        if (normalizedType(type) != normalizedType(existing.type))
            result ~= Z8SchemaDifference(Z8SchemaDifferenceKind.columnType, name, type, existing.type);
        auto nullable = field !is key && !z8_native_is_instance("org.zenframework.z8.server.base.table.value.GuidField"w, field);
        if (nullable != existing.nullable)
            result ~= Z8SchemaDifference(Z8SchemaDifferenceKind.nullability, name, nullable ? "nullable" : "not null", existing.nullable ? "nullable" : "not null");
    }
    foreach (column; actual.columns) {
        bool found;
        foreach (name; expectedNames) if (column.name == name) { found = true; break; }
        if (!found) result ~= Z8SchemaDifference(Z8SchemaDifferenceKind.extraColumn, column.name, "", column.type);
    }
    auto keyName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, key).to!string;
    if (actual.primaryKeyColumns.length != 1 || actual.primaryKeyColumns[0] != keyName) {
        import std.array : join;
        result ~= Z8SchemaDifference(Z8SchemaDifferenceKind.primaryKey, "", keyName, actual.primaryKeyColumns.join(", "));
    }
    bool[] matchedKeys; matchedKeys.length = actual.foreignKeys.length;
    foreach (field; fields) {
        auto target = foreignKeyTarget(table, field);
        if (target is null) continue;
        auto targetKey = z8_query_primary_key(target);
        if (targetKey is null) throw new Z8PostgresException("foreign key target has no primary key");
        auto fieldName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field).to!string;
        auto targetName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, target).to!string;
        auto targetKeyName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, targetKey).to!string;
        bool found;
        foreach (i, fk; actual.foreignKeys) {
            if (!matchedKeys[i] && fk.columns == [fieldName] && fk.targetSchema == actual.schema && fk.targetTable == targetName &&
                fk.targetColumns == [targetKeyName] && fk.matchType == "s" && fk.updateAction == "a" && fk.deleteAction == "a" &&
                !fk.deferrable && !fk.initiallyDeferred && fk.validated) {
                matchedKeys[i] = true; found = true; break;
            }
        }
        if (!found) result ~= Z8SchemaDifference(Z8SchemaDifferenceKind.missingForeignKey, fieldName,
            actual.schema ~ "." ~ targetName ~ "(" ~ targetKeyName ~ ")", "");
    }
    foreach (i, fk; actual.foreignKeys)
        if (!matchedKeys[i]) result ~= Z8SchemaDifference(Z8SchemaDifferenceKind.extraForeignKey, "", "", fk.name ~ ": " ~ fk.definition);
    return result;
}
