module z8.database.plan;

import std.conv : to;
import std.string : replace;
import z8.runtime;
import z8.database.postgres : Z8PostgresException;

package string quoteIdentifier(wstring value) {
    if (value is null || !value.length) throw new Z8PostgresException("empty PostgreSQL identifier");
    foreach (c; value) if (c == 0) throw new Z8PostgresException("PostgreSQL identifier contains a NUL byte");
    return `"` ~ value.to!string.replace(`"`, `""`) ~ `"`;
}

private bool containsField(Z8Object[] fields, Z8Object field) {
    foreach (item; fields) if (item is field) return true;
    return false;
}
private bool trivialTrue(Z8SqlBool condition) {
    return condition is null || (condition.kind == Z8SqlBoolKind.constant && condition.constant);
}

// Finds the links needed by selected fields and expression dependencies.
package class Z8PostgresQueryPlan {
    private struct Node {
        Z8Object query, link;
        Z8Object[] fields;
        size_t parent;
        bool active, filtersCollected;
    }
    private Node[] nodes;
    private Z8Object[] visitedFields;
    private wstring schema, rootTable;
    Z8SqlBool[] where, having;

    this(Z8Object root, wstring schema, wstring rootTable) {
        this.schema = schema; this.rootTable = rootTable;
        nodes ~= Node(root, null, z8_query_declared_fields(root), 0, true, false);
    }
    private size_t owner(Z8Object field) {
        auto container = z8_object_container(field);
        Z8Object[] path;
        while (container !is null && container !is nodes[0].query) {
            if (z8_native_is_instance("org.zenframework.z8.server.base.query.Query"w, container)) path ~= container;
            container = z8_object_container(container);
        }
        if (container is null) throw new Z8PostgresException("PostgreSQL field is not reachable through query links");
        size_t parent;
        for (size_t remaining = path.length; remaining > 0; --remaining) {
            auto target = path[remaining - 1];
            size_t index = size_t.max;
            foreach (candidate, node; nodes) if (node.query is target) { index = candidate; break; }
            if (index == size_t.max) {
                Z8Object link;
                foreach (fieldInParent; nodes[parent].fields) {
                    if ((z8_native_is_instance("org.zenframework.z8.server.base.table.value.Link"w, fieldInParent) ||
                        z8_native_is_instance("org.zenframework.z8.server.base.table.value.Join"w, fieldInParent)) &&
                        z8_link_query(fieldInParent) is target) { link = fieldInParent; break; }
                }
                if (link is null) throw new Z8PostgresException("PostgreSQL query path has no Link to target");
                index = nodes.length;
                nodes ~= Node(target, link, z8_query_declared_fields(target), parent, false, false);
            } else if (nodes[index].parent != parent) throw new Z8PostgresException("ambiguous PostgreSQL query path");
            parent = index;
        }
        if (!containsField(nodes[parent].fields, field)) throw new Z8PostgresException("PostgreSQL field is not declared by its query");
        return parent;
    }
    void includeField(Z8Object field) {
        if (field is null) throw new Z8PostgresException("null PostgreSQL query field");
        if (containsField(visitedFields, field)) return;
        visitedFields ~= field;
        auto index = owner(field);
        while (index != 0) { nodes[index].active = true; index = nodes[index].parent; }
        foreach (dependency; z8_field_query_dependencies(field)) if (dependency !is field) includeField(dependency);
    }
    void includeExpression(Z8SqlPrimary expression) {
        foreach (field; z8_sql_collect_fields(expression)) includeField(field);
    }
    void finish(bool includeTargetFilters) {
        // Target filters can themselves introduce additional joins.
        bool pending = true;
        while (pending) {
            pending = false;
            foreach (index; 1 .. nodes.length) {
                if (!nodes[index].active || nodes[index].filtersCollected) continue;
                nodes[index].filtersCollected = true; pending = true;
                if (z8_native_is_instance("org.zenframework.z8.server.base.table.value.Join"w, nodes[index].link))
                    includeExpression(z8_link_on(nodes[index].link));
                if (!includeTargetFilters) continue;
                auto query = nodes[index].query;
                foreach (condition; [z8_query_where(query), z8_query_scope(query)]) if (!trivialTrue(condition)) {
                    where ~= condition; includeExpression(condition);
                }
                auto condition = z8_query_having(query);
                if (!trivialTrue(condition)) { having ~= condition; includeExpression(condition); }
            }
        }
        foreach (index, node; nodes) if (node.active) foreach (field; node.fields) {
            auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field);
            z8_field_bind_sql(field, aliasOf(index), name);
        }
    }
    private wstring aliasOf(size_t index) { return index ? ("t" ~ index.to!string).to!wstring : "t"w; }
    Z8Object[] rightJoinKeys() {
        Z8Object[] keys;
        Z8JoinType[] effective = [Z8JoinType.inner];
        foreach (index; 1 .. nodes.length) {
            auto kind = z8_link_join_type(nodes[index].link);
            if (effective[nodes[index].parent] == Z8JoinType.left) kind = Z8JoinType.left;
            effective ~= kind;
            if (nodes[index].active && kind == Z8JoinType.right) {
                auto key = z8_query_primary_key(nodes[index].query);
                if (key is null) throw new Z8PostgresException("right join target has no primary key");
                keys ~= key;
            }
        }
        return keys;
    }
    Z8SqlBool[] joinConditions() {
        Z8SqlBool[] result;
        foreach (index; 1 .. nodes.length) if (nodes[index].active) result ~= z8_link_on(nodes[index].link);
        return result;
    }
    string fromClause(string rootSelect = null) {
        string result = rootSelect is null ? quoteIdentifier(schema) ~ "." ~ quoteIdentifier(rootTable) ~ " AS t" : "(" ~ rootSelect ~ ") AS t";
        Z8JoinType[] effective = [Z8JoinType.inner];
        foreach (index; 1 .. nodes.length) {
            auto kind = z8_link_join_type(nodes[index].link);
            if (effective[nodes[index].parent] == Z8JoinType.left) kind = Z8JoinType.left;
            effective ~= kind;
        }
        auto emitted = new bool[nodes.length]; emitted[0] = true;
        size_t remaining;
        foreach (index; 1 .. nodes.length) if (nodes[index].active) ++remaining;
        while (remaining) {
            bool progress;
            foreach (index; 1 .. nodes.length) {
                auto node = nodes[index];
                if (!node.active || emitted[index] || !emitted[node.parent]) continue;
                bool ready = true;
                Z8Object[] visited;
                void checkField(Z8Object field) {
                    if (containsField(visited, field)) return;
                    visited ~= field;
                    auto ownerIndex = owner(field);
                    if (ownerIndex != index && !emitted[ownerIndex]) ready = false;
                    foreach (dependency; z8_field_query_dependencies(field)) if (dependency !is field) checkField(dependency);
                }
                foreach (field; z8_sql_collect_fields(z8_link_on(node.link))) checkField(field);
                if (!ready) continue;
                string join;
                final switch (effective[index]) {
                    case Z8JoinType.inner: join = " INNER JOIN "; break;
                    case Z8JoinType.left: join = " LEFT JOIN "; break;
                    case Z8JoinType.right: join = " RIGHT JOIN "; break;
                    case Z8JoinType.full: join = " FULL JOIN "; break;
                }
                auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, node.query);
                result ~= join ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(name) ~ " AS " ~ aliasOf(index).to!string ~
                    " ON " ~ z8_sql_bool_format(z8_link_on(node.link), true, Z8SqlVendor.Postgres).to!string;
                emitted[index] = true; --remaining; progress = true;
            }
            if (!progress) throw new Z8PostgresException("cyclic PostgreSQL join dependencies");
        }
        return result;
    }
}
