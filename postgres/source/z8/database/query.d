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
        case "geometry"w:
            expression = "ST_GeomFromEWKB(decode(" ~ marker ~ "::text, 'hex'))";
            if (value !is null) {
                text = z8_geometry_to_string(z8_primary_cast!Z8Geometry(value)).to!string;
                if (!text.length) return FieldParameter(expression, Z8PostgresParameter.nullValue());
            }
            break;
        default: throw new Z8PostgresException("unsupported PostgreSQL write field type: " ~ kind.to!string);
    }
    return FieldParameter(expression, value is null ? Z8PostgresParameter.nullValue() : Z8PostgresParameter.value(text));
}
private string fieldColumn(Z8Object field) {
    return quoteIdentifier(z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field));
}
private Z8Primary decodeField(wstring kind, Z8PostgresValue value, Z8Object field) {
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
        case "geometry"w: return z8_primary_box(value.isNull ? z8_geometry_none(z8_optional_require(z8_field_srs(field))) : z8_geometry_fromHexString(text));
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
            return decodeField(kinds[column], value, field);
        }
        throw new Z8PostgresException("field is not present in PostgreSQL cursor");
    }
}

private struct Z8PostgresRootAggregation {
    string sql;
    Z8Object[] fields;
    wstring[] kinds;
    Z8SqlBool[] deferredHaving;
    Z8Object[] deferredHavingOwners;
}

// Executes queries and their required linked-table plans.
class Z8PostgresQueryExecutor : IZ8QueryExecutor, IZ8QueryCounter, IZ8QueryWriter, IZ8RoleAccessPropagator, IZ8RoleLifecycle, IZ8DatabaseSchema, IZ8AfterCommit {
    private Z8PostgresConnection connection;
    private wstring schema, table;
    private Z8RuntimeRegistry registry;
    this(Z8PostgresConnection connection, wstring schema, wstring table, Z8RuntimeRegistry registry = null) {
        if (connection is null) throw new Z8PostgresException("PostgreSQL connection is null");
        quoteIdentifier(schema); quoteIdentifier(table);
        this.connection = connection; this.schema = schema.idup; this.table = table.idup; this.registry = registry;
    }
    wstring databaseSchema() { return schema; }
    void afterCommit(void delegate() callback) { connection.afterCommit(callback); }
    // First stage of SelectFactory's aggregateBy: group root fields by Link.
    // Outer linked projections and a second grouping are rejected until the
    // corresponding subselect planner is available.
    private Z8PostgresRootAggregation rootAggregation(Z8Object query, Z8QueryReadRequest request, bool counting, bool preserveAverage = false, bool outerGrouping = false) {
        if (request.groupFields.length || (!outerGrouping && z8_query_array(query, "groupBy"w).length) || request.aggregateAll ||
            request.byRecordId || request.byRecordIds || request.readLock != Z8QueryReadLock.none ||
            !trivialTrue(request.having) || !trivialTrue(request.queryHaving))
            throw new Z8PostgresException("unsupported PostgreSQL aggregateBy query option");
        if (request.start < 0) throw new Z8PostgresException("negative PostgreSQL query offset");
        auto groups = uniqueFields(z8_query_array(query, "aggregateBy"w));
        auto declared = z8_query_declared_fields(query);
        foreach (field; groups) {
            if (field !is null) field.z8_ensure();
            if (field is null || !containsField(declared, field) || !z8_native_is_instance("org.zenframework.z8.server.base.table.value.Link"w, field))
                throw new Z8PostgresException("aggregateBy requires root Link fields");
            auto aggregation = z8_field_aggregation(field);
            if (aggregation != Z8FieldAggregation.none && aggregation != Z8FieldAggregation.max && aggregation != Z8FieldAggregation.min)
                throw new Z8PostgresException("unsupported aggregateBy Link aggregation");
        }
        auto requested = request.fields;
        if (!requested.length && !counting) foreach (name; ["controls"w, "names"w, "columns"w, "extraFields"w])
            foreach (field; z8_query_array(query, name)) requested ~= field;
        Z8Object[] selected = groups.dup;
        if (!counting) foreach (field; requested) {
            if (field is null || !containsField(declared, field))
                throw new Z8PostgresException("aggregateBy linked projections are not implemented");
            if (containsField(groups, field) || z8_field_aggregation(field) != Z8FieldAggregation.none) selected ~= field;
        }
        selected = uniqueFields(selected);
        foreach (field; request.sortFields) if (!counting && !containsField(declared, field))
            throw new Z8PostgresException("aggregateBy sort field is not a root field");
        auto plan = new Z8PostgresQueryPlan(query, schema, table);
        foreach (field; selected) plan.includeField(field);
        if (!counting) foreach (field; request.sortFields) plan.includeField(field);
        foreach (condition; [request.where, request.queryWhere, request.queryScope]) plan.includeExpression(condition);
        plan.finish(true);
        auto previous = z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        scope(exit) z8_sql_set_field_options(previous);
        Z8PostgresRootAggregation result; result.fields = selected;
        result.deferredHaving = plan.having.dup; result.deferredHavingOwners = plan.havingOwners.dup;
        string sql = "SELECT ";
        foreach (index, field; selected) {
            if (index) sql ~= ", ";
            auto kind = z8_field_type_id(field); result.kinds ~= kind;
            if (kind == "none"w) throw new Z8PostgresException("unsupported PostgreSQL aggregateBy field type");
            auto aggregation = z8_field_aggregation(field);
            if (!containsField(groups, field)) {
                bool numeric = kind == "int"w || kind == "float"w;
                bool comparable = numeric || kind == "string"w || kind == "text"w || kind == "guid"w || kind == "boolean"w ||
                    kind == "date"w || kind == "datetime"w || kind == "datespan"w;
                bool extrema = aggregation == Z8FieldAggregation.min || aggregation == Z8FieldAggregation.max;
                bool arithmetic = aggregation == Z8FieldAggregation.sum || aggregation == Z8FieldAggregation.average;
                bool countable = (comparable && kind != "guid"w) || kind == "binary"w;
                if (!(comparable && extrema) && !(numeric && arithmetic) && !(countable && aggregation == Z8FieldAggregation.count))
                    throw new Z8PostgresException("unsupported PostgreSQL aggregateBy field aggregation");
            }
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, false));
            auto expression = z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
            if (kind == "int"w && z8_field_aggregation(field) == Z8FieldAggregation.average && !preserveAverage) expression = "trunc(" ~ expression ~ ")::bigint";
            // TextField columns are bytea. Keep that representation across
            // the subselect so outer filters can use their normal SQL format.
            if (outerGrouping && kind == "text"w) expression = "convert_to((" ~ expression ~ ")::text, 'UTF8')";
            if (kind == "binary"w && aggregation == Z8FieldAggregation.count) {
                expression = "convert_to((" ~ expression ~ ")::text, 'UTF8')";
                if (!outerGrouping) expression = "encode(" ~ expression ~ ", 'hex')";
            }
            sql ~= expression ~ " AS " ~ quoteIdentifier(("z8_" ~ index.to!string).to!wstring);
        }
        z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        sql ~= " FROM " ~ plan.fromClause();
        string[] filters;
        foreach (condition; [request.where, request.queryWhere, request.queryScope] ~ plan.where)
            if (condition !is null) filters ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
        auto key = z8_query_primary_key(query);
        if (request.excludeNullRecord && key !is null) {
            auto column = z8_field_sql_format(key, Z8SqlVendor.Postgres).to!string;
            auto rightKeys = plan.rightJoinKeys();
            filters ~= "(" ~ column ~ " <> '00000000-0000-0000-0000-000000000000'::uuid" ~ (rightKeys.length ? " OR " ~ column ~ " IS NULL" : "") ~ ")";
            foreach (rightKey; rightKeys) filters ~= "(" ~ z8_field_sql_format(rightKey, Z8SqlVendor.Postgres).to!string ~ " <> '00000000-0000-0000-0000-000000000000'::uuid)";
        }
        if (filters.length) {
            sql ~= " WHERE "; foreach (index, filter; filters) { if (index) sql ~= " AND "; sql ~= filter; }
        }
        sql ~= " GROUP BY ";
        foreach (index, field; groups) { if (index) sql ~= ", "; sql ~= z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string; }
        if (!counting && request.sortFields.length) {
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, true)); sql ~= " ORDER BY ";
            foreach (index, field; request.sortFields) {
                if (index) sql ~= ", ";
                if (!containsField(groups, field) && z8_field_aggregation(field) == Z8FieldAggregation.none)
                    throw new Z8PostgresException("aggregateBy sort field is not grouped or aggregated");
                auto direction = z8_field_sort_direction(field);
                if (direction != "asc"w && direction != "desc"w) throw new Z8PostgresException("invalid PostgreSQL sort direction");
                sql ~= z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string ~ " " ~ direction.to!string;
            }
        }
        if (!counting && request.limit >= 0) sql ~= " LIMIT " ~ request.limit.to!string;
        if (!counting && request.start) sql ~= " OFFSET " ~ request.start.to!string;
        result.sql = sql; return result;
    }
    private Z8Object[] aggregateRequestedFields(Z8Object query, Z8QueryReadRequest request) {
        auto fields = request.fields.dup;
        if (!fields.length && !request.aggregateAll) fields = z8_query_form_fields(query);
        return uniqueFields(fields);
    }
    private bool hasLinkedAggregateFields(Z8Object query, Z8QueryReadRequest request, bool counting) {
        // A group filter runs against the grouped root in the outer SELECT.
        if (!trivialTrue(request.having) || !trivialTrue(request.queryHaving) || request.groupFields.length || z8_query_array(query, "groupBy"w).length) return true;
        auto declared = z8_query_declared_fields(query);
        auto fields = aggregateRequestedFields(query, request);
        if (!counting) fields ~= request.sortFields;
        foreach (field; fields) if (!containsField(declared, field)) return true;
        return false;
    }
    // SelectFactory's outer select joins grouped Link values to their targets.
    private Z8PostgresRootAggregation linkedRootAggregation(Z8Object query, Z8QueryReadRequest request, bool counting, bool preserveAverage = false) {
        auto declared = z8_query_declared_fields(query);
        auto groups = uniqueFields(z8_query_array(query, "aggregateBy"w));
        auto outerGroups = uniqueFields(request.groupFields.length ? request.groupFields : z8_query_array(query, "groupBy"w));
        auto requested = aggregateRequestedFields(query, request);
        Z8Object[] filterFields;
        foreach (condition; [request.having, request.queryHaving])
            if (!trivialTrue(condition)) filterFields ~= z8_sql_collect_fields(condition);
        Z8Object[] candidates;
        void includeCandidate(Z8Object field) {
            if (field is null || containsField(candidates, field)) return;
            candidates ~= field;
            if (containsField(declared, field)) return; // Computed root fields are evaluated in the inner SELECT.
            foreach (dependency; z8_field_query_dependencies(field)) if (dependency !is field) includeCandidate(dependency);
        }
        foreach (field; requested ~ outerGroups ~ (counting ? null : request.sortFields) ~ filterFields) {
            if (field is null) throw new Z8PostgresException("null aggregateBy field");
            includeCandidate(field);
        }
        Z8Object[] linked;
        foreach (field; candidates) {
            if (field is null) throw new Z8PostgresException("null aggregateBy field");
            if (containsField(declared, field)) continue;
            bool reachable;
            foreach (link; groups) {
                auto target = z8_link_query(link);
                for (auto container = z8_object_container(field); container !is null && container !is query; container = z8_object_container(container))
                    if (container is target) { reachable = true; break; }
                if (reachable) break;
            }
            if (!reachable)
                throw new Z8PostgresException("unsupported aggregateBy linked field");
            linked ~= field;
        }
        auto innerRequest = request;
        innerRequest.fields = null;
        foreach (field; candidates)
            if (containsField(declared, field)) innerRequest.fields ~= field;
        // An empty list means default fields to rootAggregation, so provide the
        // grouping keys explicitly if all requested fields belong to targets.
        if (!innerRequest.fields.length) innerRequest.fields = groups.dup;
        innerRequest.sortFields = null; innerRequest.start = 0; innerRequest.limit = -1;
        innerRequest.groupFields = null;
        innerRequest.having = null; innerRequest.queryHaving = null;
        // Keep AVG's fractional value for outer filters, ordering and totals;
        // convert integer fields only when projecting the final result.
        auto inner = rootAggregation(query, innerRequest, false, true, true);
        auto plan = new Z8PostgresQueryPlan(query, schema, table);
        foreach (field; linked) plan.includeField(field);
        foreach (condition; [request.having, request.queryHaving]) if (!trivialTrue(condition)) plan.includeExpression(condition);
        foreach (condition; inner.deferredHaving) plan.includeExpression(condition);
        plan.finish(true);
        auto groupFilters = plan.having.dup;
        foreach (index, condition; inner.deferredHaving)
            if (!containsField(plan.havingOwners, inner.deferredHavingOwners[index])) groupFilters ~= condition;
        groupFilters ~= [request.having, request.queryHaving];
        Z8Object[] checked;
        void checkDependency(Z8Object field) {
            if (containsField(checked, field)) return;
            checked ~= field;
            if (containsField(declared, field)) {
                if (!containsField(inner.fields, field))
                    throw new Z8PostgresException("aggregateBy linked expression requires an unprojected root field");
                return; // Its dependencies were resolved before grouping.
            }
            foreach (dependency; z8_field_query_dependencies(field)) if (dependency !is field) checkDependency(dependency);
        }
        foreach (field; linked) checkDependency(field);
        foreach (condition; plan.where ~ plan.joinConditions() ~ groupFilters)
            foreach (field; z8_sql_collect_fields(condition)) checkDependency(field);
        foreach (index, field; inner.fields) z8_field_bind_sql(field, "t"w, ("z8_" ~ index.to!string).to!wstring);
        Z8PostgresRootAggregation result;
        result.fields = uniqueFields(inner.fields ~ (counting ? null : requested) ~ outerGroups);
        // Unaggregated root fields are intentionally omitted, as in SelectFactory.
        Z8Object[] projected;
        foreach (field; result.fields) {
            if (containsField(declared, field) && !containsField(inner.fields, field)) continue;
            if (outerGroups.length && !containsField(outerGroups, field) && z8_field_aggregation(field) == Z8FieldAggregation.none &&
                !z8_native_is_instance("org.zenframework.z8.server.base.table.value.Expression"w, field)) continue;
            projected ~= field;
        }
        result.fields = projected;
        auto previous = z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        scope(exit) z8_sql_set_field_options(previous);
        string sql = "SELECT ";
        z8_sql_set_field_options(Z8SqlFieldFormatOptions(outerGroups.length != 0, false, outerGroups.length != 0));
        foreach (index, field; result.fields) {
            if (index) sql ~= ", ";
            auto kind = z8_field_type_id(field); result.kinds ~= kind;
            if (kind == "none"w) throw new Z8PostgresException("unsupported PostgreSQL aggregateBy field type");
            auto expression = z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
            if ((containsField(declared, field) || outerGroups.length) && kind == "int"w && z8_field_aggregation(field) == Z8FieldAggregation.average && !preserveAverage)
                expression = "trunc(" ~ expression ~ ")::bigint";
            if (kind == "binary"w) {
                if (outerGroups.length && z8_field_aggregation(field) == Z8FieldAggregation.count)
                    expression = "convert_to((" ~ expression ~ ")::text, 'UTF8')";
                expression = "encode(" ~ expression ~ ", 'hex')";
            }
            else if (kind == "geometry"w) expression = "encode(ST_AsEWKB(" ~ expression ~ ", 'NDR'), 'hex')";
            else if (z8_native_is_instance("org.zenframework.z8.server.base.table.value.TextField"w, field) &&
                (!outerGroups.length || z8_field_aggregation(field) == Z8FieldAggregation.none))
                expression = "convert_from(" ~ expression ~ ", 'UTF8')";
            sql ~= expression ~ " AS " ~ quoteIdentifier(("z8_" ~ index.to!string).to!wstring);
        }
        z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        sql ~= " FROM " ~ plan.fromClause(inner.sql);
        string[] filters;
        foreach (condition; plan.where ~ (outerGroups.length ? null : groupFilters))
            if (!trivialTrue(condition)) filters ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
        if (filters.length) { sql ~= " WHERE "; foreach (index, filter; filters) { if (index) sql ~= " AND "; sql ~= filter; } }
        if (outerGroups.length) {
            sql ~= " GROUP BY ";
            foreach (index, field; outerGroups) {
                if (containsField(declared, field) && !containsField(inner.fields, field)) throw new Z8PostgresException("aggregateBy group field is not projected");
                if (index) sql ~= ", ";
                sql ~= z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
            }
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, false, true));
            string[] having;
            foreach (condition; groupFilters) if (!trivialTrue(condition))
                having ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
            if (having.length) { sql ~= " HAVING "; foreach (index, filter; having) { if (index) sql ~= " AND "; sql ~= filter; } }
        }
        if (!counting && request.sortFields.length) {
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(outerGroups.length != 0, true, outerGroups.length != 0));
            sql ~= " ORDER BY ";
            foreach (index, field; request.sortFields) {
                if (containsField(declared, field) && !containsField(inner.fields, field))
                    throw new Z8PostgresException("aggregateBy sort field is not grouped or aggregated");
                if (index) sql ~= ", ";
                auto direction = z8_field_sort_direction(field);
                if (direction != "asc"w && direction != "desc"w) throw new Z8PostgresException("invalid PostgreSQL sort direction");
                sql ~= z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string ~ " " ~ direction.to!string;
            }
        }
        if (!counting && request.limit >= 0) sql ~= " LIMIT " ~ request.limit.to!string;
        if (!counting && request.start) sql ~= " OFFSET " ~ request.start.to!string;
        result.sql = sql; return result;
    }
    private IZ8QueryCursor aggregateRootTotals(Z8Object query, Z8QueryReadRequest request) {
        auto fields = uniqueFields(request.fields);
        auto groupedRequest = request;
        groupedRequest.aggregateAll = false; groupedRequest.sortFields = null;
        groupedRequest.start = 0; groupedRequest.limit = -1;
        auto declared = z8_query_declared_fields(query);
        groupedRequest.fields = fields.dup;
        foreach (field; request.aggregateSourceFields) if (!containsField(declared, field)) groupedRequest.fields ~= field;
        if (!groupedRequest.fields.length) groupedRequest.fields = z8_query_array(query, "aggregateBy"w);
        auto grouped = linkedRootAggregation(query, groupedRequest, false, true);
        string sql = "SELECT "; wstring[] kinds;
        foreach (index, field; fields) {
            auto aggregation = z8_field_aggregation(field);
            auto kind = z8_field_type_id(field); kinds ~= kind;
            if ((aggregation != Z8FieldAggregation.sum && aggregation != Z8FieldAggregation.average) ||
                (kind != "int"w && kind != "float"w))
                throw new Z8PostgresException("unsupported PostgreSQL aggregateBy totals field");
            size_t position = size_t.max;
            foreach (i, projected; grouped.fields) if (projected is field) { position = i; break; }
            if (position == size_t.max) throw new Z8PostgresException("aggregateBy totals field is not projected");
            auto expression = (aggregation == Z8FieldAggregation.sum ? "sum(" : "avg(") ~
                "z8_totals." ~ quoteIdentifier(("z8_" ~ position.to!string).to!wstring) ~ ")";
            if (kind == "int"w && aggregation == Z8FieldAggregation.average) expression = "trunc(" ~ expression ~ ")::bigint";
            if (index) sql ~= ", ";
            sql ~= expression ~ " AS " ~ quoteIdentifier(("z8_" ~ index.to!string).to!wstring);
        }
        if (!fields.length) sql ~= "count(0) AS z8_0";
        sql ~= " FROM (" ~ grouped.sql ~ ") AS z8_totals";
        return new Z8PostgresRows(fields, kinds, connection.execute(sql), true);
    }
    private void createRoleAccess(wstring nativeName, wstring tableName, wstring targetIndex, Z8Guid roleId, Z8Guid targetId) {
        auto access = z8_native_new(nativeName); access.z8_ensure();
        Z8Object role, target;
        foreach (field; z8_query_declared_fields(access, true)) {
            if (field.z8_index() == "role"w) role = field;
            if (field.z8_index() == targetIndex) target = field;
        }
        if (role is null || target is null) throw new Z8PostgresException("role access fields are missing");
        z8_field_set(role, z8_primary_box(roleId)); z8_field_set(target, z8_primary_box(targetId));
        z8_query_set_executor(access, new Z8PostgresQueryExecutor(connection, schema, tableName, registry));
        z8_native_call!Z8Guid("org.zenframework.z8.server.base.query.Query.m_create"w, access, z8_guid_create_random());
    }
    void roleCreated(Z8Guid recordId) {
        if (registry is null) return;
        if (recordId is null) throw new Z8PostgresException("role has no GUID");
        foreach (key; registry.tableKeys())
            createRoleAccess("org.zenframework.z8.server.base.table.system.RoleTableAccess"w, "SystemRoleTableAccess"w, "table"w, recordId, key);
        auto namespaceName = quoteIdentifier(schema);
        auto fields = connection.execute("SELECT \"RecordId\"::text FROM " ~ namespaceName ~ `."SystemFields" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid`);
        foreach (row; fields.rows)
            createRoleAccess("org.zenframework.z8.server.base.table.system.RoleFieldAccess"w, "SystemRoleFieldAccess"w, "field"w, recordId, z8_guid_literal(row[0].text));
        auto requests = connection.execute("SELECT \"RecordId\"::text FROM " ~ namespaceName ~ `."SystemRequests" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid`);
        foreach (row; requests.rows)
            createRoleAccess("org.zenframework.z8.server.base.table.system.RoleRequestAccess"w, "SystemRoleRequestAccess"w, "request"w, recordId, z8_guid_literal(row[0].text));
    }
    void roleDestroying(Z8Guid recordId) {
        if (registry is null) return;
        if (recordId is null) throw new Z8PostgresException("role has no GUID");
        auto namespaceName = quoteIdentifier(schema);
        auto parameter = Z8PostgresParameter.value(z8_guid_to_string(recordId).to!string);
        foreach (name; ["SystemRoleFieldAccess"w, "SystemRoleTableAccess"w, "SystemRoleRequestAccess"w])
            connection.execute("DELETE FROM " ~ namespaceName ~ "." ~ quoteIdentifier(name) ~
                ` WHERE "Role" = $1::uuid AND "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid`, [parameter]);
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
        if (!request.disableGrouping && z8_query_array(query, "aggregateBy"w).length) {
            auto linked = hasLinkedAggregateFields(query, request, true);
            auto plan = linked ? linkedRootAggregation(query, request, true) : rootAggregation(query, request, true);
            if (!linked && plan.deferredHaving.length) plan = linkedRootAggregation(query, request, true);
            auto rows = connection.execute("SELECT count(*) FROM (" ~ plan.sql ~ ") AS z8_count");
            if (rows.rows.length != 1 || rows.rows[0][0].isNull) throw new Z8PostgresException("invalid PostgreSQL count result");
            return rows.rows[0][0].text.to!long;
        }
        auto groups = request.disableGrouping ? null : request.groupFields.length ? request.groupFields : z8_query_array(query, "groupBy"w);
        auto plan = new Z8PostgresQueryPlan(query, schema, table);
        foreach (field; groups) plan.includeField(field);
        foreach (condition; [request.where, request.queryWhere, request.queryScope, request.having, request.queryHaving]) plan.includeExpression(condition);
        plan.finish(!request.byRecordId && !request.byRecordIds);
        auto previous = z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
        scope(exit) z8_sql_set_field_options(previous);
        string sql = groups.length ? "SELECT count(*) FROM (SELECT 1" : "SELECT count(0)";
        sql ~= " FROM " ~ plan.fromClause();
        string[] filters;
        foreach (condition; [request.where, request.queryWhere, request.queryScope] ~ plan.where)
            if (condition !is null) filters ~= "(" ~ z8_sql_bool_format(condition, true, Z8SqlVendor.Postgres).to!string ~ ")";
        auto key = z8_query_primary_key(query);
        if ((!groups.length || request.excludeNullRecord) && key !is null) {
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
        if (!request.disableGrouping && z8_query_array(query, "aggregateBy"w).length) {
            if (request.aggregateAll) return aggregateRootTotals(query, request);
            auto linked = hasLinkedAggregateFields(query, request, false);
            auto plan = linked ? linkedRootAggregation(query, request, false) : rootAggregation(query, request, false);
            if (!linked && plan.deferredHaving.length) { plan = linkedRootAggregation(query, request, false); linked = true; }
            return new Z8PostgresRows(plan.fields, plan.kinds, connection.execute(plan.sql), !linked || request.groupFields.length != 0 || z8_query_array(query, "groupBy"w).length != 0);
        }
        auto groups = request.disableGrouping ? null : request.groupFields.length ? request.groupFields : z8_query_array(query, "groupBy"w);
        bool grouped = groups.length != 0 || request.aggregateAll;
        if (!request.disableGrouping && !grouped && (!trivialTrue(request.having) || !trivialTrue(request.queryHaving)))
            throw new Z8PostgresException("PostgreSQL HAVING filters require grouped query support");
        if (request.start < 0) throw new Z8PostgresException("negative PostgreSQL query offset");
        auto plan = new Z8PostgresQueryPlan(query, schema, table);
        auto requested = request.fields;
        if (!requested.length && !request.aggregateAll) requested = z8_query_form_fields(query);
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
        plan.finish(!request.byRecordId && !request.byRecordIds);
        if (request.aggregateAll && !groups.length && plan.having.length) throw new Z8PostgresException("PostgreSQL linked HAVING filters are not supported for totals");
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
            if (kind == "none"w) throw new Z8PostgresException("unsupported PostgreSQL field type: " ~ kind.to!string);
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(grouped, false));
            auto expression = z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
            auto aggregation = z8_field_aggregation(field);
            if (grouped && kind == "int"w && aggregation == Z8FieldAggregation.average && !(request.aggregateAll && groups.length))
                expression = "trunc(" ~ expression ~ ")::bigint";
            bool raw = !grouped || aggregation == Z8FieldAggregation.none || aggregation == Z8FieldAggregation.bitwiseOr || aggregation == Z8FieldAggregation.bitwiseAnd;
            if (kind == "binary"w && raw) expression = "encode(" ~ expression ~ ", 'hex')";
            else if (kind == "geometry"w && raw) expression = "encode(ST_AsEWKB(" ~ expression ~ ", 'NDR'), 'hex')";
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
        if ((!grouped || request.excludeNullRecord) && key !is null) {
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
        if (groups.length) {
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
        if (request.aggregateAll && groups.length) {
            Z8Object[] totalsFields;
            wstring[] totalsKinds;
            string outer = "SELECT ";
            foreach (field; uniqueFields(requested)) {
                size_t position = size_t.max;
                foreach (i, projected; selected) if (projected is field) { position = i; break; }
                if (position == size_t.max) continue;
                auto aggregation = z8_field_aggregation(field);
                if (aggregation != Z8FieldAggregation.sum && aggregation != Z8FieldAggregation.average)
                    throw new Z8PostgresException("unsupported PostgreSQL grouped totals aggregation");
                auto kind = z8_field_type_id(field);
                auto expression = (aggregation == Z8FieldAggregation.sum ? "SUM(" : "AVG(") ~
                    "z8_groups." ~ quoteIdentifier(("z8_" ~ position.to!string).to!wstring) ~ ")";
                if (kind == "int"w && aggregation == Z8FieldAggregation.average)
                    expression = "trunc(" ~ expression ~ ")::bigint";
                if (totalsFields.length) outer ~= ", ";
                outer ~= expression ~ " AS " ~ quoteIdentifier(("z8_" ~ totalsFields.length.to!string).to!wstring);
                totalsFields ~= field; totalsKinds ~= kind;
            }
            if (!totalsFields.length) outer ~= "count(0) AS z8_0";
            sql = outer ~ " FROM (" ~ sql ~ ") AS z8_groups";
            selected = totalsFields; kinds = totalsKinds;
        }
        if (request.sortFields.length) {
            z8_sql_set_field_options(Z8SqlFieldFormatOptions(grouped, true));
            sql ~= " ORDER BY ";
            foreach (index, field; request.sortFields) {
                if (index) sql ~= ", ";
                auto direction = z8_field_sort_direction(field);
                if (direction != "asc"w && direction != "desc"w) throw new Z8PostgresException("invalid PostgreSQL sort direction");
                auto expression = z8_field_sql_format(field, Z8SqlVendor.Postgres).to!string;
                // A bare numeric constant in ORDER BY is interpreted as a
                // column ordinal by PostgreSQL, even when it is a BL expression.
                if (z8_native_is_instance("org.zenframework.z8.server.base.table.value.Expression"w, field))
                    expression = "(CASE WHEN TRUE THEN " ~ expression ~ " ELSE NULL END)";
                sql ~= expression ~ " " ~ direction.to!string;
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
