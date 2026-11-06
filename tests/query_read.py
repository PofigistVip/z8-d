"""Exercise BL Query.read/next through a host-provided query executor."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/query_read.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Report.bl").write_text('''
import org.zenframework.z8.base.query.Query;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.GeometryField;
import org.zenframework.z8.base.table.value.GeometryExpression;
public class Report extends Query {
    public IntField amount; public StringField title;
    public GeometryField shape; public GeometryExpression calculatedShape;
    shape.srs = 4326; calculatedShape.srs = 3395;
    public string readEvents = ""; public bool filterFromHook = false; public bool observe = false; public int observed;
    virtual protected void beforeRead() { readEvents += "B"; if (observe) observed = amount.get(); if (filterFromHook) setWhere(amount > 9); }
    virtual protected void afterRead() { readEvents += "A"; }
    virtual protected sql_bool where() { return amount > 1; }
    virtual protected sql_bool having() { return amount < 100; }
    virtual protected sql_bool scope() { return amount > 0; }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.Aggregation;
public class Probe {
    public static Report make() { Report query; query.limit = 7; return query; }
    public static void whereJson(Report query, string json) { query.setWhere(json); }
    public static void all(Report query) { Field[] fields = {query.amount, query.title}; query.read(fields); }
    public static void filtered(Report query) { Field[] fields = {query.amount}; query.read(fields, fields, query.amount > 3, 2, 1); }
    public static bool first(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields); }
    public static void readWhere(Report query) { Field[] fields = {query.amount}; query.read(fields, query.amount > 3); }
    public static void readSort(Report query) { Field[] fields = {query.amount}; query.read(fields, fields); }
    public static void readSortWhere(Report query) { Field[] fields = {query.amount}; query.read(fields, fields, query.amount > 3); }
    public static bool firstWhere(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields, query.amount > 3); }
    public static bool firstSort(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields, fields); }
    public static bool firstSortWhere(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields, fields, query.amount > 3); }
    public static bool record(Report query, guid id) { Field[] fields = {query.amount}; return query.readRecord(id, fields); }
    public static void groupOne(Report query) { Field[] fields = {query.amount}; query.group(fields); }
    public static void groupWhere(Report query) { Field[] fields = {query.amount}; query.group(fields, query.amount > 3); }
    public static void groupFields(Report query) { Field[] fields = {query.amount}; query.group(fields, fields); }
    public static void groupFieldsWhere(Report query) { Field[] fields = {query.amount}; query.group(fields, fields, query.amount > 3); }
    public static void groupFieldsHaving(Report query) { Field[] fields = {query.amount}; query.group(fields, fields, query.amount > 3, query.amount < 50); }
    public static void groupSort(Report query) { Field[] fields = {query.amount}; query.group(fields, fields, fields); }
    public static void groupSortWhere(Report query) { Field[] fields = {query.amount}; query.group(fields, fields, fields, query.amount > 3); }
    public static void groupSortHaving(Report query) { Field[] fields = {query.amount}; query.group(fields, fields, fields, query.amount > 3, query.amount < 50); }
    public static void groupPaged(Report query) { Field[] fields = {query.amount}; query.group(fields, fields, fields, query.amount > 3, query.amount < 50, 4, 6); }
    public static int[] groupValues(Report query) { query.amount.aggregation = Aggregation.Array; return query.amount.array(); }
    public static void setFilter(Report query) { query.setWhere(query.amount > 5); }
    public static void addFilter(Report query) { query.addWhere(query.amount < 50); query.addHaving(query.amount > 2); }
    public static void resetFilter(Report query) { sql_bool empty = null; query.setWhere(empty); }
    public static bool next(Report query) { return query.next(); }
    public static void close(Report query) { query.close(); }
    public static int count(Report query) { return query.count(); }
    public static string events(Report query) { return query.readEvents; }
    public static void clearEvents(Report query) { query.readEvents = ""; }
    public static void enableHookFilter(Report query) { query.filterFromHook = true; }
    public static void observe(Report query) { query.observe = true; }
    public static int observed(Report query) { return query.observed; }
    public static void setAmount(Report query, int value) { query.amount = value; }
    public static int amount(Report query) { return query.amount.get(); }
    public static string title(Report query) { return query.title.get(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
import std.algorithm.searching : canFind;
import std.conv : to;
import std.json : JSONValue;
class Rows : IZ8QueryCursor {
    Z8Object amount, title;
    Z8Object[] selected;
    int position = -1, count = 2;
    bool closed, grouped;
    this(Z8Object amount, Z8Object title, Z8Object[] selected) { this.amount = amount; this.title = title; this.selected = selected; }
    Z8Object[] fields() { return selected; }
    bool isClosed() { return closed; }
    bool isGrouped() { return grouped; }
    bool next() { if (closed) throw new Exception("closed"); return ++position < count; }
    void close() { closed = true; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) {
        assert(!closed && position >= 0 && position < count);
        if (asArray) return z8_primary_box("[10,20]"w);
        if (field is amount) return z8_primary_box(position == 0 ? 10L : 20L);
        if (field is title) return z8_primary_box(position == 0 ? "first"w : "second"w);
        throw new Exception("unknown field");
    }
}
class Executor : IZ8QueryExecutor, IZ8QueryCounter {
    Z8Object amount, title;
    Z8QueryReadRequest last;
    Rows cursor;
    bool fail, empty, invalid;
    this(Z8Object amount, Z8Object title) { this.amount = amount; this.title = title; }
    IZ8QueryCursor read(Z8Object query, Z8QueryReadRequest request) {
        last = request;
        if (fail) throw new Exception("executor failure");
        auto selected = request.fields.length ? request.fields : [amount, title];
        if (invalid) selected = [query];
        cursor = new Rows(amount, title, selected); cursor.grouped = request.groupFields.length != 0; if (empty) cursor.count = 0;
        return cursor;
    }
    long count(Z8Object query, Z8QueryReadRequest request) { last = request; if (fail) throw new Exception("counter failure"); return 2; }
}
void main() {
    alias P = Z8p_50726F6265;
    auto query = P.m_make(); z8_nonnull(query);
    z8_field_bind_sql(query.f_amount, null, null, "T.amount"w);
    bool missing; try { P.m_all(query); } catch (Exception) { missing = true; } assert(missing);
    auto executor = new Executor(query.f_amount, query.f_title); z8_query_set_executor(query, executor);
    P.m_all(query);
    assert(executor.last.fields.length == 2 && executor.last.limit == 7 && executor.last.start == 0);
    assert(executor.last.queryWhere !is null && executor.last.queryHaving !is null && executor.last.queryScope !is null);
    assert(z8_sql_bool_format(executor.last.queryWhere, true).canFind(">1"w));
    assert(z8_sql_bool_format(executor.last.queryHaving, true).canFind("<100"w));
    assert(z8_sql_bool_format(executor.last.queryScope, true).canFind(">0"w));
    assert(z8_optional_require(P.m_next(query)) && z8_optional_require(P.m_amount(query)) == 10 && P.m_title(query) == "first"w);
    assert(z8_optional_require(P.m_next(query)) && z8_optional_require(P.m_amount(query)) == 20);
    assert(!z8_optional_require(P.m_next(query)) && executor.cursor.closed);
    assert(z8_optional_require(P.m_amount(query)) == 0);
    bool exhausted; try { P.m_next(query); } catch (Exception) { exhausted = true; } assert(exhausted);
    P.m_all(query); auto old = executor.cursor; P.m_filtered(query);
    assert(old.closed && executor.last.fields.length == 1 && executor.last.sortFields.length == 1);
    assert(executor.last.where !is null && executor.last.start == 2 && executor.last.limit == 1);
    assert(z8_optional_require(P.m_next(query)) && z8_optional_require(P.m_amount(query)) == 10);
    P.m_close(query); assert(executor.cursor.closed && z8_optional_require(P.m_amount(query)) == 0);
    assert(z8_optional_require(P.m_first(query)) && z8_optional_require(P.m_amount(query)) == 10);
    old = executor.cursor; executor.fail = true;
    bool failed; try { P.m_all(query); } catch (Exception) { failed = true; }
    assert(failed && old.closed && z8_optional_require(P.m_amount(query)) == 0);
    executor.fail = false; executor.invalid = true;
    bool invalid; try { P.m_all(query); } catch (Exception) { invalid = true; }
    assert(invalid && executor.cursor.closed);
    executor.invalid = false; executor.empty = true;
    assert(!z8_optional_require(P.m_first(query)) && executor.cursor.closed);
    executor.empty = false;
    P.m_readWhere(query); assert(executor.last.where !is null && executor.last.sortFields.length == 0 && executor.last.limit == 7);
    P.m_readSort(query); assert(executor.last.where is null && executor.last.sortFields.length == 1);
    P.m_readSortWhere(query); assert(executor.last.where !is null && executor.last.sortFields.length == 1);
    assert(z8_optional_require(P.m_firstWhere(query)) && executor.last.where !is null && executor.last.limit == 1);
    assert(z8_optional_require(P.m_firstSort(query)) && executor.last.sortFields.length == 1 && executor.last.where is null);
    assert(z8_optional_require(P.m_firstSortWhere(query)) && executor.last.sortFields.length == 1 && executor.last.where !is null);
    assert(z8_optional_require(P.m_record(query, z8_guid_create(5))) && executor.last.byRecordId && executor.last.recordId == z8_guid_create(5) && executor.last.limit == -1);
    assert(executor.last.queryWhere is null && executor.last.queryScope is null && executor.last.queryHaving is null);
    assert(z8_optional_require(P.m_record(query, null)) && !executor.last.byRecordId && executor.last.queryScope !is null);
    P.m_setFilter(query); P.m_addFilter(query); P.m_all(query);
    assert(executor.last.queryWhere.kind == Z8SqlBoolKind.and && executor.last.queryHaving.kind == Z8SqlBoolKind.and);
    P.m_resetFilter(query); P.m_all(query); assert(executor.last.queryWhere.kind != Z8SqlBoolKind.and);
    P.m_groupOne(query); assert(executor.last.groupFields.length == 1 && executor.last.fields.length == 0 && executor.last.limit == 7);
    P.m_groupWhere(query); assert(executor.last.where !is null && executor.last.fields.length == 0);
    P.m_groupFields(query); assert(executor.last.fields.length == 1 && executor.last.where is null);
    P.m_groupFieldsWhere(query); assert(executor.last.where !is null && executor.last.having is null);
    P.m_groupFieldsHaving(query); assert(executor.last.where !is null && executor.last.having !is null);
    P.m_groupSort(query); assert(executor.last.sortFields.length == 1 && executor.last.where is null);
    P.m_groupSortWhere(query); assert(executor.last.sortFields.length == 1 && executor.last.where !is null && executor.last.having is null);
    P.m_groupSortHaving(query); assert(executor.last.sortFields.length == 1 && executor.last.having !is null);
    P.m_groupPaged(query); assert(executor.last.start == 4 && executor.last.limit == 6);
    assert(z8_optional_require(P.m_next(query)));
    auto grouped = P.m_groupValues(query); assert(grouped.z8_size() == 2 && grouped.z8_get(0) == 10 && grouped.z8_get(1) == 20);
    P.m_close(query);
    P.m_clearEvents(query); P.m_enableHookFilter(query); P.m_all(query);
    assert(P.m_events(query) == "BA"w && z8_sql_bool_format(executor.last.queryWhere, true).canFind(">9"w));
    auto retained = executor.cursor; assert(z8_optional_require(P.m_next(query)));
    P.m_setAmount(query, z8_optional_wrap(91L)); P.m_observe(query);
    assert(z8_optional_require(P.m_count(query)) == 2 && P.m_events(query) == "BABA"w && !retained.closed);
    assert(z8_optional_require(P.m_observed(query)) == 0 && z8_optional_require(P.m_amount(query)) == 91);
    executor.fail = true;
    bool countFailed; try { P.m_count(query); } catch (Exception) { countFailed = true; }
    assert(countFailed && P.m_events(query) == "BABABA"w && !retained.closed && z8_optional_require(P.m_amount(query)) == 91);
    z8_field_reset(query.f_amount); assert(z8_optional_require(P.m_amount(query)) == 10);
    bool readFailed; try { P.m_all(query); } catch (Exception) { readFailed = true; }
    assert(readFailed && P.m_events(query) == "BABABABA"w && retained.closed);
    executor.fail = false;
    auto request = new Z8ApplicationRequest(); request.setEventsLevel(Z8EventsLevel.system);
    auto previous = z8_application_set_request(request);
    P.m_all(query); assert(z8_optional_require(P.m_count(query)) == 2 && P.m_events(query) == "BABABABA"w);
    P.m_close(query); z8_application_set_request(previous);
    auto point = JSONValue(`{"type":"Point","coordinates":[1,2]}`).toString();
    auto filter = `{"property":"shape","operator":"contains","value":` ~ point ~ `}`;
    P.m_whereJson(query, filter.to!wstring);
    auto condition = z8_query_where(query).left;
    assert(condition.kind == Z8SqlBoolKind.geometryCompare && condition.geometryOperator == "&&");
    assert(condition.geometryLeft.field is query.f_shape);
    assert(z8_geometry_srs(condition.geometryRight.constant) == 4326);
    assert(condition.geometryRight.constant.x == 1.0 && condition.geometryRight.constant.y == 2.0);
    z8_field_bind_sql(query.f_shape, null, null, "T.shape"w);
    assert(z8_sql_bool_format(condition, true).canFind("st_intersects("w));
    filter = `{"property":"calculatedShape","value":` ~ point ~ `}`;
    P.m_whereJson(query, filter.to!wstring);
    assert(z8_geometry_srs(z8_query_where(query).left.geometryRight.constant) == 3395);
    P.m_whereJson(query, `{"property":"shape"}`w);
    assert(z8_geometry_shape(z8_query_where(query).left.geometryRight.constant) == -1);
    bool badGeometry;
    try { P.m_whereJson(query, `{"property":"shape","value":"invalid"}`w); } catch (Exception) { badGeometry = true; }
    assert(badGeometry);
}
''', encoding="utf-8")
    exe = temp / ("query-read.exe" if os.name == "nt" else "query-read")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Query read, iteration, replacement and failure handling verified")
