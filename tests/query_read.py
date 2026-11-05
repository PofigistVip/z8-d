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
public class Report extends Query { public IntField amount; public StringField title; }
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
public class Probe {
    public static Report make() { Report query; query.limit = 7; return query; }
    public static void all(Report query) { Field[] fields = {query.amount, query.title}; query.read(fields); }
    public static void filtered(Report query) { Field[] fields = {query.amount}; query.read(fields, fields, query.amount > 3, 2, 1); }
    public static bool first(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields); }
    public static void readWhere(Report query) { Field[] fields = {query.amount}; query.read(fields, query.amount > 3); }
    public static void readSort(Report query) { Field[] fields = {query.amount}; query.read(fields, fields); }
    public static void readSortWhere(Report query) { Field[] fields = {query.amount}; query.read(fields, fields, query.amount > 3); }
    public static bool firstWhere(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields, query.amount > 3); }
    public static bool firstSort(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields, fields); }
    public static bool firstSortWhere(Report query) { Field[] fields = {query.amount}; return query.readFirst(fields, fields, query.amount > 3); }
    public static bool next(Report query) { return query.next(); }
    public static void close(Report query) { query.close(); }
    public static int amount(Report query) { return query.amount.get(); }
    public static string title(Report query) { return query.title.get(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
class Rows : IZ8QueryCursor {
    Z8Object amount, title;
    Z8Object[] selected;
    int position = -1, count = 2;
    bool closed;
    this(Z8Object amount, Z8Object title, Z8Object[] selected) { this.amount = amount; this.title = title; this.selected = selected; }
    Z8Object[] fields() { return selected; }
    bool isClosed() { return closed; }
    bool isGrouped() { return false; }
    bool next() { if (closed) throw new Exception("closed"); return ++position < count; }
    void close() { closed = true; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) {
        assert(!asArray && !closed && position >= 0 && position < count);
        if (field is amount) return z8_primary_box(position == 0 ? 10L : 20L);
        if (field is title) return z8_primary_box(position == 0 ? "first"w : "second"w);
        throw new Exception("unknown field");
    }
}
class Executor : IZ8QueryExecutor {
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
        cursor = new Rows(amount, title, selected); if (empty) cursor.count = 0;
        return cursor;
    }
}
void main() {
    alias P = Z8p_50726F6265;
    auto query = P.m_make(); z8_nonnull(query);
    bool missing; try { P.m_all(query); } catch (Exception) { missing = true; } assert(missing);
    auto executor = new Executor(query.f_amount, query.f_title); z8_query_set_executor(query, executor);
    P.m_all(query);
    assert(executor.last.fields.length == 2 && executor.last.limit == 7 && executor.last.start == 0);
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
    P.m_close(query);
}
''', encoding="utf-8")
    exe = temp / ("query-read.exe" if os.name == "nt" else "query-read")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Query read, iteration, replacement and failure handling verified")
