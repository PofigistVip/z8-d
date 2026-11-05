module z8.database.query;

import std.conv : to;
import z8.runtime;
import z8.database.postgres;
import z8.database.plan;
private Z8Object[] uniqueFields(Z8Object[] fields) {
    Z8Object[] result;
    foreach (field; fields) {
        bool found;
        foreach (existing; result) if (existing is field) { found = true; break; }
        if (!found) result ~= field;
    }
    return result;
}
private bool containsField(Z8Object[] fields, Z8Object field) {
    foreach (item; fields) if (item is field) return true;
    return false;
}
private bool trivialTrue(Z8SqlBool condition) {
    return condition is null || (condition.kind == Z8SqlBoolKind.constant && condition.constant);
}
private ubyte[] decodeHex(string value) {
    if (value.length % 2) throw new Z8PostgresException("invalid PostgreSQL binary value");
    int digit(char c) {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        throw new Z8PostgresException("invalid PostgreSQL binary value");
    }
    ubyte[] result;
    for (size_t i; i < value.length; i += 2) result ~= cast(ubyte)((digit(value[i]) << 4) | digit(value[i + 1]));
    return result;
}
package string encodeBinary(Z8Binary binary) {
    immutable digits = "0123456789abcdef";
    char[] result;
    ubyte[8192] buffer;
    scope(exit) z8_binary_close(binary);
    while (true) {
        auto chunk = z8_binary_read_chunk(binary, buffer[]);
        if (!chunk.length) break;
        foreach (b; chunk) { result ~= digits[b >> 4]; result ~= digits[b & 15]; }
    }
    return cast(string)result;
}
private struct FieldParameter { string sql; Z8PostgresParameter value; }
private FieldParameter fieldParameter(Z8Object field, size_t index) {
    auto kind = z8_field_type_id(field);
    auto value = z8_field_default_value(field);
    auto marker = "$" ~ index.to!string;
    string expression, text;
    switch (kind) {
        case "int"w:
            expression = marker ~ "::bigint";
            if (value !is null) text = z8_optional_require(z8_primary_cast!long(value)).to!string;
            break;
        case "boolean"w:
            expression = marker ~ "::smallint";
            if (value !is null) text = z8_optional_require(z8_primary_cast!bool(value)) ? "1" : "0";
            break;
        case "float"w:
            expression = marker ~ "::numeric";
            if (value !is null) text = z8_optional_require(z8_primary_cast!Z8Decimal(value)).z8_string().to!string;
            break;
        case "string"w:
            expression = marker ~ "::text";
            if (value !is null) text = z8_primary_cast!wstring(value).to!string;
            break;
        case "text"w: case "file"w: case "attachments"w:
            expression = "convert_to(" ~ marker ~ "::text, 'UTF8')";
            if (value !is null) text = z8_primary_cast!wstring(value).to!string;
            break;
        case "guid"w:
            expression = marker ~ "::uuid";
            if (value !is null) text = z8_guid_to_string(z8_primary_cast!Z8Guid(value)).to!string;
            break;
        case "date"w: case "datetime"w:
            expression = marker ~ "::bigint";
            if (value !is null) text = z8_date_ticks(z8_primary_cast!Z8Date(value)).to!string;
            break;
        case "datespan"w:
            expression = marker ~ "::bigint";
            if (value !is null) text = z8_datespan_milliseconds(z8_primary_cast!Z8Datespan(value)).to!string;
            break;
        case "binary"w:
            expression = "decode(" ~ marker ~ "::text, 'hex')";
            if (value !is null) text = encodeBinary(z8_primary_cast!Z8Binary(value));
            break;
        default: throw new Z8PostgresException("unsupported PostgreSQL write field type: " ~ kind.to!string);
    }
    return FieldParameter(expression, value is null ? Z8PostgresParameter.nullValue() : Z8PostgresParameter.value(text));
}
private string fieldColumn(Z8Object field) {
    return quoteIdentifier(z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field));
}
private Z8Primary decodeField(wstring kind, Z8PostgresValue value) {
    auto text = value.isNull ? null : value.text.to!wstring;
    switch (kind) {
        case "int"w: return z8_primary_box(value.isNull ? 0L : z8_int_parse(text));
        case "boolean"w: return z8_primary_box(value.isNull ? false : z8_bool_parse(text));
        case "float"w: return z8_primary_box(value.isNull ? z8_decimal_from_int(0) : z8_decimal_parse(text));
        case "string"w: case "text"w: case "file"w: case "attachments"w:
            return z8_primary_box(value.isNull ? ""w : z8_string_new(text));
        case "guid"w: return z8_primary_box(value.isNull ? z8_guid_zero() : z8_guid_parse(text));
        case "date"w: case "datetime"w: return z8_primary_box(value.isNull ? z8_date_min : z8_date_from_ticks(z8_int_parse(text)));
        case "datespan"w: return z8_primary_box(value.isNull ? new Z8Datespan() : new Z8Datespan(z8_int_parse(text)));
        case "binary"w: return z8_primary_box(new Z8Binary(value.isNull ? null : decodeHex(value.text)));
        default: throw new Z8PostgresException("unsupported PostgreSQL field type: " ~ kind.to!string);
    }
}
private class Z8PostgresRows : IZ8QueryCursor {
    private Z8Object[] selected;
    private wstring[] kinds;
    private Z8PostgresResult result;
    private long position = -1;
    private bool closed, grouped;
    this(Z8Object[] selected, wstring[] kinds, Z8PostgresResult result, bool grouped) {
        this.selected = selected.dup; this.kinds = kinds.dup; this.result = result; this.grouped = grouped;
    }
    Z8Object[] fields() { return selected.dup; }
    bool isClosed() { return closed; }
    bool isGrouped() { return grouped; }
    bool next() {
        if (closed) throw new Z8PostgresException("PostgreSQL cursor is closed");
        return ++position < cast(long)result.rows.length;
    }
    void close() { closed = true; result.rows = null; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) {
        if (closed || position < 0 || position >= cast(long)result.rows.length) throw new Z8PostgresException("PostgreSQL cursor is not on a row");
        foreach (column, selectedField; selected) if (selectedField is field) {
            auto value = result.rows[cast(size_t)position][column]; wasNull = value.isNull;
            if (asArray) return z8_primary_box(value.isNull ? ""w : value.text.to!wstring);
            return decodeField(kinds[column], value);
        }
        throw new Z8PostgresException("field is not present in PostgreSQL cursor");
    }
}

// Executes queries and their required linked-table plans.
class Z8PostgresQueryExecutor : IZ8QueryExecutor, IZ8QueryCounter, IZ8QueryWriter, IZ8RoleAccessPropagator {
    private Z8PostgresConnection connection;
    private wstring schema, table;
    this(Z8PostgresConnection connection, wstring schema, wstring table) {
        if (connection is null) throw new Z8PostgresException("PostgreSQL connection is null");
        quoteIdentifier(schema); quoteIdentifier(table);
        this.connection = connection; this.schema = schema.idup; this.table = table.idup;
    }
    void updateRoleFieldAccess(Z8Guid recordId, Z8Optional!bool read, Z8Optional!bool write) {
        if (recordId is null) throw new Z8PostgresException("role access record has no GUID");
        if (read.present && !read.value) write = z8_optional_wrap(false);
        else if (!read.present && write.present && write.value) read = z8_optional_wrap(true);
        string[] changes;
        if (read.present) changes ~= `"Read" = ` ~ (read.value ? "1" : "0");
        if (write.present) changes ~= `"Write" = ` ~ (write.value ? "1" : "0");
        if (!changes.length) return;
        import std.array : join;
        auto namespaceName = quoteIdentifier(schema);
        auto sql = "UPDATE " ~ namespaceName ~ `."SystemRoleFieldAccess" AS a SET ` ~ changes.join(", ") ~
            " FROM " ~ namespaceName ~ `."SystemFields" AS f, ` ~ namespaceName ~ "." ~ quoteIdentifier(table) ~ " AS t" ~
            ` WHERE t."RecordId" = $1::uuid AND a."Role" = t."Role" AND a."Field" = f."RecordId" AND f."Table" = t."Table"` ~
            ` AND a."RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid`;
        connection.execute(sql, [Z8PostgresParameter.value(z8_guid_to_string(recordId).to!string)]);
    }
    void insert(Z8Object query, Z8Object[] fields) {
        auto declared = z8_query_declared_fields(query, true);
        string columns, values;
        Z8PostgresParameter[] parameters;
        foreach (field; uniqueFields(fields)) {
            if (!containsField(declared, field)) throw new Z8PostgresException("PostgreSQL insert field belongs to another query");
            auto parameter = fieldParameter(field, parameters.length + 1);
            if (parameters.length) { columns ~= ", "; values ~= ", "; }
            columns ~= fieldColumn(field); values ~= parameter.sql; parameters ~= parameter.value;
        }
        auto sql = "INSERT INTO " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(table);
        sql ~= parameters.length ? " (" ~ columns ~ ") VALUES (" ~ values ~ ")" : " DEFAULT VALUES";
        connection.execute(sql, parameters);
    }
    long update(Z8Object query, Z8Guid id, Z8Object[] fields) {
        auto declared = z8_query_declared_fields(query, true);
        auto key = z8_query_primary_key(query);
        string set;
        Z8PostgresParameter[] parameters;
        foreach (field; uniqueFields(fields)) {
            if (!containsField(declared, field)) throw new Z8PostgresException("PostgreSQL update field belongs to another query");
            if (field is key) continue;
            auto parameter = fieldParameter(field, parameters.length + 1);
            if (parameters.length) set ~= ", ";
            set ~= fieldColumn(field) ~ " = " ~ parameter.sql; parameters ~= parameter.value;
        }
        if (!parameters.length) throw new Z8PostgresException("PostgreSQL update has no writable fields");
        auto sql = "UPDATE " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(table) ~ " SET " ~ set;
        if (id !is null) {
            if (key is null) throw new Z8PostgresException("record update requires a primary key");
            parameters ~= Z8PostgresParameter.value(z8_guid_to_string(id).to!string);
            sql ~= " WHERE " ~ fieldColumn(key) ~ " = $" ~ parameters.length.to!string ~ "::uuid";
        }
        return connection.execute(sql, parameters).affectedRows;
    }
    long destroy(Z8Object query, Z8Guid id) {
        auto key = z8_query_primary_key(query);
        if (key is null) throw new Z8PostgresException("record deletion requires a primary key");
        auto parameter = id is null ? Z8PostgresParameter.nullValue() : Z8PostgresParameter.value(z8_guid_to_string(id).to!string);
        auto sql = "DELETE FROM " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(table) ~ " WHERE " ~ fieldColumn(key) ~ " = $1::uuid";
        return connection.execute(sql, [parameter]).affectedRows;
    }
    long count(Z8Object query, Z8QueryReadRequest request) {
        if (!request.disableGrouping && z8_query_array(query, "aggregateBy"w).length) throw new Z8PostgresException("PostgreSQL aggregateBy links are not implemented");
        auto groups = request.disableGrouping ? null : request.groupFields.length ? request.groupFields : z8_query_array(query, "groupBy"w);
        auto plan = new Z8PostgresQueryPlan(query, schema, table);
        foreach (field; groups) plan.includeField(field);
        foreach (condition; [request.where, request.queryWhere, request.queryScope, request.having, request.queryHaving]) plan.includeExpression(condition);
        plan.finish(!request.byRecordId);
        auto previous = z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        scope(exit) z8_sql_set_field_options(previous);
        string sql = groups.length ? "SELECT count(*) FROM (SELECT 1" : "SELECT count(0)";
        sql ~= " FROM " ~ plan.fromClause();
        string[] filters;
        foreach (condition; [request.where, request.queryWhere, request.queryScope] ~ plan.where)
            if (condition !is null) filters ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
        auto key = z8_query_primary_key(query);
        if (!groups.length && key !is null) {
            auto column = z8_field_sql_format(key, Z8SqlVendor.Postgres).to!string;
            auto rightKeys = plan.rightJoinKeys();
            filters ~= "(" ~ column ~ " <> '00000000-0000-0000-0000-000000000000'::uuid" ~ (rightKeys.length ? " OR " ~ column ~ " IS NULL" : "") ~ ")";
            foreach (rightKey; rightKeys) filters ~= "(" ~ z8_field_sql_format(rightKey, Z8SqlVendor.Postgres).to!string ~ " <> '00000000-0000-0000-0000-000000000000'::uuid)";
        }
        if (filters.length) {
            sql ~= " WHERE ";
            foreach (index, filter; filters) { if (index) sql ~= " AND "; sql ~= filter; }
        }
        if (groups.length) {
            sql ~= " GROUP BY ";
            foreach (index, field; groups) { if (index) sql ~= ", "; sql ~= z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string; }
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, false));
            string[] having;
            foreach (condition; [request.having, request.queryHaving] ~ plan.having)
                if (!trivialTrue(condition)) having ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
            if (having.length) {
                sql ~= " HAVING ";
                foreach (index, condition; having) { if (index) sql ~= " AND "; sql ~= condition; }
            }
            sql ~= ") AS z8_count";
        }
        auto result = connection.execute(sql);
        if (result.rows.length != 1 || result.rows[0].length != 1 || result.rows[0][0].isNull)
            throw new Z8PostgresException("invalid PostgreSQL count result");
        return result.rows[0][0].text.to!long;
    }
    IZ8QueryCursor read(Z8Object query, Z8QueryReadRequest request) {
        if (!request.disableGrouping && z8_query_array(query, "aggregateBy"w).length) throw new Z8PostgresException("PostgreSQL aggregateBy links are not implemented");
        auto groups = request.disableGrouping ? null : request.groupFields.length ? request.groupFields : z8_query_array(query, "groupBy"w);
        bool grouped = groups.length != 0;
        if (!request.disableGrouping && !grouped && (!trivialTrue(request.having) || !trivialTrue(request.queryHaving)))
            throw new Z8PostgresException("PostgreSQL HAVING filters require grouped query support");
        if (request.start < 0) throw new Z8PostgresException("negative PostgreSQL query offset");
        auto plan = new Z8PostgresQueryPlan(query, schema, table);
        auto requested = request.fields;
        if (!requested.length) {
            foreach (name; ["controls"w, "names"w, "columns"w, "extraFields"w])
                foreach (field; z8_query_array(query, name)) {
                    if (field is null || !z8_native_is_instance("org.zenframework.z8.server.base.table.value.Field"w, field))
                        throw new Z8PostgresException("nested PostgreSQL form controls are not implemented");
                    requested ~= field;
                }
        }
        Z8Object[] selected;
        foreach (field; requested) foreach (dependency; z8_field_fields(field)) {
            plan.includeField(dependency);
            selected ~= dependency;
        }
        auto key = z8_query_primary_key(query);
        if (grouped) selected ~= groups;
        else if (key !is null) selected ~= key;
        selected = uniqueFields(selected);
        if (grouped) {
            Z8Object[] projected;
            foreach (field; selected) if (containsField(groups, field) || z8_field_aggregation(field) != Z8FieldAggregation.none ||
                z8_native_is_instance("org.zenframework.z8.server.base.table.value.Expression"w, field)) projected ~= field;
            selected = projected;
        }
        foreach (field; request.sortFields) plan.includeField(field);
        foreach (field; groups) plan.includeField(field);
        foreach (condition; [request.where, request.queryWhere, request.queryScope, request.having, request.queryHaving]) plan.includeExpression(condition);
        plan.finish(!request.byRecordId);
        if (!request.disableGrouping && !grouped && plan.having.length)
            throw new Z8PostgresException("PostgreSQL HAVING filters require grouped query support");
        auto previous = z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        scope(exit) z8_sql_set_field_options(previous);
        string sql = "SELECT ";
        wstring[] kinds;
        if (!selected.length) sql ~= "count(0) AS z8_0";
        foreach (index, field; selected) {
            if (index) sql ~= ", ";
            auto kind = z8_field_type_id(field); kinds ~= kind;
            if (kind == "geometry"w || kind == "none"w) throw new Z8PostgresException("unsupported PostgreSQL field type: " ~ kind.to!string);
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(grouped, false));
            auto expression = z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
            auto aggregation = z8_field_aggregation(field);
            bool raw = !grouped || aggregation == Z8FieldAggregation.none || aggregation == Z8FieldAggregation.bitwiseOr || aggregation == Z8FieldAggregation.bitwiseAnd;
            if (kind == "binary"w && raw) expression = "encode(" ~ expression ~ ", 'hex')";
            else if (raw && z8_native_is_instance("org.zenframework.z8.server.base.table.value.TextField"w, field))
                expression = "convert_from(" ~ expression ~ ", 'UTF8')";
            sql ~= expression ~ " AS " ~ quoteIdentifier(("z8_" ~ index.to!string).to!wstring);
        }
        z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        sql ~= " FROM " ~ plan.fromClause();
        string[] filters;
        z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        foreach (condition; [request.where, request.queryWhere, request.queryScope] ~ plan.where)
            if (condition !is null) filters ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
        if (!grouped && key !is null) {
            auto column = z8_field_sql_format(key, Z8SqlVendor.Postgres).to!string;
            auto rightKeys = plan.rightJoinKeys();
            filters ~= "(" ~ column ~ " <> '00000000-0000-0000-0000-000000000000'::uuid" ~ (rightKeys.length ? " OR " ~ column ~ " IS NULL" : "") ~ ")";
            foreach (rightKey; rightKeys) filters ~= "(" ~ z8_field_sql_format(rightKey, Z8SqlVendor.Postgres).to!string ~ " <> '00000000-0000-0000-0000-000000000000'::uuid)";
        }
        Z8PostgresParameter[] parameters;
        if (request.byRecordId) {
            if (key is null) throw new Z8PostgresException("record lookup requires a primary key");
            filters ~= "(" ~ z8_field_sql_format(key, Z8SqlVendor.Postgres).to!string ~ " = $1::uuid)";
            parameters ~= Z8PostgresParameter.value(z8_guid_to_string(request.recordId).to!string);
        }
        if (filters.length) {
            sql ~= " WHERE ";
            foreach (index, filter; filters) { if (index) sql ~= " AND "; sql ~= filter; }
        }
        if (grouped) {
            sql ~= " GROUP BY ";
            foreach (index, field; groups) {
                if (index) sql ~= ", ";
                sql ~= z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
            }
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, false));
            string[] having;
            foreach (condition; [request.having, request.queryHaving] ~ plan.having)
                if (!trivialTrue(condition)) having ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
            if (having.length) {
                sql ~= " HAVING ";
                foreach (index, condition; having) { if (index) sql ~= " AND "; sql ~= condition; }
            }
        }
        if (request.sortFields.length) {
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(grouped, true));
            sql ~= " ORDER BY ";
            foreach (index, field; request.sortFields) {
                if (index) sql ~= ", ";
                auto direction = z8_field_sort_direction(field);
                if (direction != "asc"w && direction != "desc"w) throw new Z8PostgresException("invalid PostgreSQL sort direction");
                sql ~= z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string ~ " " ~ direction.to!string;
            }
        }
        if (request.limit >= 0) sql ~= " LIMIT " ~ request.limit.to!string;
        if (request.start) sql ~= " OFFSET " ~ request.start.to!string;
        final switch (request.readLock) {
            case Z8QueryReadLock.none: break;
            case Z8QueryReadLock.update: sql ~= " FOR UPDATE"; break;
            case Z8QueryReadLock.share: sql ~= " FOR SHARE"; break;
            case Z8QueryReadLock.updateNoWait: sql ~= " FOR UPDATE NOWAIT"; break;
            case Z8QueryReadLock.shareNoWait: sql ~= " FOR SHARE NOWAIT"; break;
        }
        return new Z8PostgresRows(selected, kinds, connection.execute(sql, parameters), grouped);
    }
}
