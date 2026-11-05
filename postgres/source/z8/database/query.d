module z8.database.query;

import std.conv : to;
import std.string : replace;
import z8.runtime;
import z8.database.postgres;

private string quoteIdentifier(wstring value) {
    if (value is null || !value.length) throw new Z8PostgresException("empty PostgreSQL identifier");
    foreach (c; value) if (c == 0) throw new Z8PostgresException("PostgreSQL identifier contains a NUL byte");
    return `"` ~ value.to!string.replace(`"`, `""`) ~ `"`;
}
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
    private bool closed;
    this(Z8Object[] selected, wstring[] kinds, Z8PostgresResult result) {
        this.selected = selected.dup; this.kinds = kinds.dup; this.result = result;
    }
    Z8Object[] fields() { return selected.dup; }
    bool isClosed() { return closed; }
    bool isGrouped() { return false; }
    bool next() {
        if (closed) throw new Z8PostgresException("PostgreSQL cursor is closed");
        return ++position < cast(long)result.rows.length;
    }
    void close() { closed = true; result.rows = null; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) {
        if (closed || position < 0 || position >= cast(long)result.rows.length) throw new Z8PostgresException("PostgreSQL cursor is not on a row");
        if (asArray) throw new Z8PostgresException("grouped PostgreSQL reads are not implemented");
        foreach (column, selectedField; selected) if (selectedField is field) {
            auto value = result.rows[cast(size_t)position][column]; wasNull = value.isNull;
            return decodeField(kinds[column], value);
        }
        throw new Z8PostgresException("field is not present in PostgreSQL cursor");
    }
}

// Executes the single-table subset of Query. Links, grouping and UI-derived
// default field selection are rejected until their query planning is available.
class Z8PostgresQueryExecutor : IZ8QueryExecutor {
    private Z8PostgresConnection connection;
    private wstring schema, table;
    this(Z8PostgresConnection connection, wstring schema, wstring table) {
        if (connection is null) throw new Z8PostgresException("PostgreSQL connection is null");
        quoteIdentifier(schema); quoteIdentifier(table);
        this.connection = connection; this.schema = schema.idup; this.table = table.idup;
    }
    IZ8QueryCursor read(Z8Object query, Z8QueryReadRequest request) {
        if (request.groupFields.length || z8_query_array(query, "groupBy"w).length || z8_query_array(query, "aggregateBy"w).length)
            throw new Z8PostgresException("grouped PostgreSQL queries are not implemented");
        if (!trivialTrue(request.having) || !trivialTrue(request.queryHaving))
            throw new Z8PostgresException("PostgreSQL HAVING filters require grouped query support");
        if (!request.fields.length) throw new Z8PostgresException("PostgreSQL query requires explicit selected fields");
        if (request.start < 0) throw new Z8PostgresException("negative PostgreSQL query offset");
        auto declared = z8_query_declared_fields(query);
        foreach (field; declared) {
            auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field);
            z8_field_bind_sql(field, "t"w, name);
        }
        Z8Object[] selected;
        foreach (field; request.fields) foreach (dependency; z8_field_fields(field)) {
            if (!containsField(declared, dependency)) throw new Z8PostgresException("PostgreSQL query links are not implemented");
            selected ~= dependency;
        }
        auto key = z8_query_primary_key(query);
        if (key !is null) selected ~= key;
        selected = uniqueFields(selected);
        foreach (field; request.sortFields) if (!containsField(declared, field)) throw new Z8PostgresException("PostgreSQL sort field belongs to another query");
        auto previous = z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        scope(exit) z8_sql_set_field_options(previous);
        string sql = "SELECT ";
        wstring[] kinds;
        foreach (index, field; selected) {
            if (index) sql ~= ", ";
            auto kind = z8_field_type_id(field); kinds ~= kind;
            if (kind == "geometry"w || kind == "none"w) throw new Z8PostgresException("unsupported PostgreSQL field type: " ~ kind.to!string);
            auto expression = z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
            if (kind == "binary"w) expression = "encode(" ~ expression ~ ", 'hex')";
            else if (z8_native_is_instance("org.zenframework.z8.server.base.table.value.TextField"w, field))
                expression = "convert_from(" ~ expression ~ ", 'UTF8')";
            sql ~= expression ~ " AS " ~ quoteIdentifier(("z8_" ~ index.to!string).to!wstring);
        }
        sql ~= " FROM " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(table) ~ " AS t";
        string[] filters;
        foreach (condition; [request.where, request.queryWhere, request.queryScope])
            if (condition !is null) filters ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
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
        if (request.sortFields.length) {
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
        return new Z8PostgresRows(selected, kinds, connection.execute(sql, parameters));
    }
}
