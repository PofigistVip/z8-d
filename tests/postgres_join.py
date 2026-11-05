"""Exercise BL query links and SQL joins against an isolated PostgreSQL cluster."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_join.py <original-z8-root> [postgres-bin-directory]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    declarations = {
        "City": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[name "Cities"] public class City extends Table { [name "Label"] public StringField label; }
''',
        "Customer": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.StringField;
[name "Customers"] public class Customer extends Table {
    [name "Label"] public StringField label;
    public City city; [name "CityId"] public Link cityId = city;
}
''',
        "FilteredCustomer": '''
public class FilteredCustomer extends Customer {
    virtual protected sql_bool scope() { return label != "Bob"; }
}
''',
        "LeftLink": '''
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
public class LeftLink extends Link { joinType = JoinType.Left; }
''',
        "RightLink": '''
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
public class RightLink extends Link { joinType = JoinType.Right; }
''',
        "FullLink": '''
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
public class FullLink extends Link { joinType = JoinType.Full; }
''',
        "InnerOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntExpression;
public class InnerOrder extends Table {
    [name "Title"] public StringField title;
    public Customer customer; [name "CustomerId"] public Link customerId = customer;
    public IntExpression nameLength = customer.label.sql_string().length();
}
''',
        "LeftOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
public class LeftOrder extends Table {
    [name "Title"] public StringField title;
    public Customer customer; [name "CustomerId"] public LeftLink customerId = customer;
}
''',
        "RightOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
public class RightOrder extends Table {
    [name "Title"] public StringField title;
    public Customer customer; [name "CustomerId"] public RightLink customerId = customer;
}
''',
        "FilteredOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
public class FilteredOrder extends Table {
    public FilteredCustomer customer; [name "CustomerId"] public Link customerId = customer;
}
''',
        "FullOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
public class FullOrder extends Table {
    [name "Title"] public StringField title;
    public Customer customer; [name "CustomerId"] public FullLink customerId = customer;
}
''',
        "RecursiveOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
[name "Nodes"] public class RecursiveOrder extends Table {
    public RecursiveOrder parent;
    [name "ParentId"] public Link parentId = parent;
}
''',
        "ConditionOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.Join;
import org.zenframework.z8.base.table.value.StringField;
public class ConditionOrder extends Table {
    [name "Title"] public StringField title;
    public City city; [name "CityId"] public Link cityId = city;
    public Customer customer; public Join matchingCustomer = customer;
}
''',
        "CyclicOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Join;
public class CyclicOrder extends Table {
    public City city; public Join cityJoin = city;
    public Customer customer; public Join customerJoin = customer;
}
''',
        "Probe": '''
import org.zenframework.z8.base.table.value.Field;
public class Probe {
    public static InnerOrder inner() { InnerOrder value; return value; }
    public static LeftOrder left() { LeftOrder value; return value; }
    public static RightOrder right() { RightOrder value; return value; }
    public static FullOrder full() { FullOrder value; return value; }
    public static FilteredOrder filtered() { FilteredOrder value; return value; }
    public static Customer customer() { Customer value; return value; }
    public static ConditionOrder conditional() { ConditionOrder value; return value; }
    public static CyclicOrder cyclic() { CyclicOrder value; return value; }
    public static void configureCycle(CyclicOrder order) {
        order.cityJoin = order.customer.cityId.sql_guid() == order.city.recordId.sql_guid();
        order.customerJoin = order.customer.cityId.sql_guid() == order.city.recordId.sql_guid();
    }
    public static void readCycle(CyclicOrder order) { Field[] fields = {order.customer.label}; order.read(fields); }
    public static void condition(ConditionOrder order) { order.matchingCustomer = order.customer.cityId.sql_guid() == order.city.recordId.sql_guid(); }
    public static void readCondition(ConditionOrder order) { Field[] fields = {order.title, order.customer.label}; order.read(fields); }
    public static bool nextCondition(ConditionOrder order) { return order.next(); }
    public static string conditionTitle(ConditionOrder order) { return order.title.get(); }
    public static string conditionCustomer(ConditionOrder order) { return order.customer.label.get(); }
    public static RecursiveOrder recursive() { RecursiveOrder value; return value; }
    public static int recursiveCount(RecursiveOrder order) { return order.count(); }
    public static void recursiveRead(RecursiveOrder order) { Field[] fields = {order.parent.parent.recordId}; order.read(fields); }
    public static bool recursiveNext(RecursiveOrder order) { return order.next(); }
    public static guid grandparentId(RecursiveOrder order) { return order.parent.parent.recordId.get(); }
    public static int all(InnerOrder order) { return order.count(); }
    public static int alice(InnerOrder order) { return order.count(order.customer.label == "Alice"); }
    public static void jsonAlice(InnerOrder order) { order.setWhere("{property:'" + order.customer.label.id() + "',value:'alice'}"); }
    public static void readInner(InnerOrder order) { Field[] fields = {order.title, order.customer.label}; order.read(fields); }
    public static void readSorted(InnerOrder order) { Field[] fields = {order.title}; Field[] sort = {order.customer.label}; order.read(fields, sort); }
    public static void readLength(InnerOrder order) { Field[] fields = {order.nameLength}; order.read(fields); }
    public static void readExternal(InnerOrder order, Customer other) { Field[] fields = {other.label}; order.read(fields); }
    public static int countLength(InnerOrder order) { return order.count(order.nameLength > 4); }
    public static int nameLength(InnerOrder order) { return order.nameLength.get(); }
    public static string innerTitle(InnerOrder order) { return order.title.get(); }
    public static void groupCustomer(InnerOrder order) { Field[] group = {order.customer.label}; order.groupBy = group; order.group(group, group); }
    public static void clearGroup(InnerOrder order) { order.groupBy.clear(); }
    public static void readLeft(LeftOrder order) { Field[] fields = {order.title, order.customer.label}; order.read(fields); }
    public static void readLeftCity(LeftOrder order) { Field[] fields = {order.title, order.customer.city.label}; order.read(fields); }
    public static void readRight(RightOrder order) { Field[] fields = {order.title, order.customer.label}; order.read(fields); }
    public static void readFull(FullOrder order) { Field[] fields = {order.title, order.customer.label}; order.read(fields); }
    public static int filteredCount(FilteredOrder order) { return order.count(order.customer.label != ""); }
    public static bool filteredRecord(FilteredOrder order, guid id) { Field[] fields = {order.customer.label}; return order.readRecord(id, fields); }
    public static string filteredName(FilteredOrder order) { return order.customer.label.get(); }
    public static int rightCount(RightOrder order) { return order.count(order.customer.label != ""); }
    public static bool nextInner(InnerOrder order) { return order.next(); }
    public static bool nextLeft(LeftOrder order) { return order.next(); }
    public static bool nextRight(RightOrder order) { return order.next(); }
    public static bool nextFull(FullOrder order) { return order.next(); }
    public static string innerName(InnerOrder order) { return order.customer.label.get(); }
    public static string leftName(LeftOrder order) { return order.customer.label.get(); }
    public static string leftCity(LeftOrder order) { return order.customer.city.label.get(); }
    public static string rightTitle(RightOrder order) { return order.title.get(); }
}
''',
    }
    for name, code in declarations.items():
        (source / (name + ".bl")).write_text(code, encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.query;
import z8gen.p_Probe;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto db = new Z8PostgresConnection(args[1]);
    db.execute(`CREATE TEMP TABLE "Cities" ("RecordId" uuid PRIMARY KEY, "Label" text)`);
    db.execute(`CREATE TEMP TABLE "Customers" ("RecordId" uuid PRIMARY KEY, "Label" text, "CityId" uuid)`);
    db.execute(`CREATE TEMP TABLE "Orders" ("RecordId" uuid PRIMARY KEY, "Title" text, "CustomerId" uuid, "CityId" uuid)`);
    db.execute(`CREATE TEMP TABLE "Nodes" ("RecordId" uuid PRIMARY KEY, "ParentId" uuid)`);
    db.execute(`INSERT INTO "Nodes" VALUES ('00000000-0000-0000-0000-000000000401','00000000-0000-0000-0000-000000000402'), ('00000000-0000-0000-0000-000000000402',NULL), ('00000000-0000-0000-0000-000000000403','00000000-0000-0000-0000-000000000401')`);
    db.execute(`INSERT INTO "Cities" VALUES ('00000000-0000-0000-0000-000000000101','Moscow')`);
    db.execute(`INSERT INTO "Customers" VALUES ('00000000-0000-0000-0000-000000000201','Alice','00000000-0000-0000-0000-000000000101'), ('00000000-0000-0000-0000-000000000202','Bob',NULL), ('00000000-0000-0000-0000-000000000203','Ghost',NULL), ('00000000-0000-0000-0000-000000000000','Sentinel',NULL)`);
    db.execute(`INSERT INTO "Orders" ("RecordId","Title","CustomerId","CityId") VALUES ('00000000-0000-0000-0000-000000000301','First','00000000-0000-0000-0000-000000000201','00000000-0000-0000-0000-000000000101'), ('00000000-0000-0000-0000-000000000302','Second','00000000-0000-0000-0000-000000000202',NULL), ('00000000-0000-0000-0000-000000000303','No customer',NULL,NULL), ('00000000-0000-0000-0000-000000000304','Missing customer','00000000-0000-0000-0000-000000000299',NULL)`);
    auto inner = P.m_inner(); auto left = P.m_left(); auto right = P.m_right(); auto full = P.m_full(); auto filtered = P.m_filtered(); auto recursive = P.m_recursive(); auto conditional = P.m_conditional(); auto cyclic = P.m_cyclic();
    foreach (query; [cast(Z8Object)inner, cast(Z8Object)left, cast(Z8Object)right, cast(Z8Object)full, cast(Z8Object)filtered, cast(Z8Object)conditional, cast(Z8Object)cyclic])
        z8_query_set_executor(query, new Z8PostgresQueryExecutor(db, "pg_temp"w, "Orders"w));
    z8_query_set_executor(recursive, new Z8PostgresQueryExecutor(db, "pg_temp"w, "Nodes"w));
    assert(z8_optional_require(P.m_recursiveCount(recursive)) == 3);
    P.m_recursiveRead(recursive); assert(z8_optional_require(P.m_recursiveNext(recursive)) && P.m_grandparentId(recursive) == z8_guid_create(0x402));
    assert(!z8_optional_require(P.m_recursiveNext(recursive)));
    assert(z8_optional_require(P.m_all(inner)) == 4);
    assert(z8_optional_require(P.m_alice(inner)) == 1);
    P.m_readInner(inner); int innerRows;
    while (z8_optional_require(P.m_nextInner(inner))) { assert(P.m_innerName(inner).length); ++innerRows; }
    assert(innerRows == 2);
    bool rejected; try { P.m_readExternal(inner, P.m_customer()); } catch (Z8PostgresException) { rejected = true; }
    assert(rejected);
    P.m_readSorted(inner);
    assert(z8_optional_require(P.m_nextInner(inner)) && P.m_innerTitle(inner) == "First"w);
    assert(z8_optional_require(P.m_nextInner(inner)) && P.m_innerTitle(inner) == "Second"w);
    assert(!z8_optional_require(P.m_nextInner(inner)));
    P.m_readLength(inner); int lengthSum, lengthRows;
    while (z8_optional_require(P.m_nextInner(inner))) { lengthSum += cast(int)z8_optional_require(P.m_nameLength(inner)); ++lengthRows; }
    assert(lengthRows == 2 && lengthSum == 8 && z8_optional_require(P.m_countLength(inner)) == 1);
    P.m_groupCustomer(inner); assert(z8_optional_require(P.m_all(inner)) == 2);
    int groupRows; while (z8_optional_require(P.m_nextInner(inner))) ++groupRows;
    assert(groupRows == 2); P.m_clearGroup(inner);
    P.m_jsonAlice(inner); assert(z8_optional_require(P.m_all(inner)) == 1);
    P.m_readLeft(left); int leftRows, missing;
    while (z8_optional_require(P.m_nextLeft(left))) { if (P.m_leftName(left) == ""w) ++missing; ++leftRows; }
    assert(leftRows == 4 && missing == 2);
    P.m_readLeftCity(left); leftRows = 0; int cities;
    while (z8_optional_require(P.m_nextLeft(left))) { if (P.m_leftCity(left) == "Moscow"w) ++cities; ++leftRows; }
    assert(leftRows == 4 && cities == 1);
    P.m_readRight(right); int rightRows, noOrder;
    while (z8_optional_require(P.m_nextRight(right))) { if (P.m_rightTitle(right) == ""w) ++noOrder; ++rightRows; }
    assert(rightRows == 3 && noOrder == 1);
    assert(z8_optional_require(P.m_rightCount(right)) == 3);
    P.m_readFull(full); int fullRows;
    while (z8_optional_require(P.m_nextFull(full))) ++fullRows;
    assert(fullRows == 4);
    assert(z8_optional_require(P.m_filteredCount(filtered)) == 1);
    assert(z8_optional_require(P.m_filteredRecord(filtered, z8_guid_create(0x302))) && P.m_filteredName(filtered) == "Bob"w);
    P.m_condition(conditional); P.m_readCondition(conditional);
    assert(z8_optional_require(P.m_nextCondition(conditional)) && P.m_conditionTitle(conditional) == "First"w && P.m_conditionCustomer(conditional) == "Alice"w);
    assert(!z8_optional_require(P.m_nextCondition(conditional)));
    P.m_configureCycle(cyclic); bool cycleRejected;
    try { P.m_readCycle(cyclic); } catch (Z8PostgresException error) { cycleRejected = error.msg == "cyclic PostgreSQL join dependencies"; }
    assert(cycleRejected);
    db.close();
}
''', encoding="utf-8")
    exe = temp / ("postgres-join.exe" if os.name == "nt" else "postgres-join")
    command = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
               *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
               str(harness), str(runtime)]
    command += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    subprocess.run([*command, "-of=" + str(exe)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        result = subprocess.run([str(exe), connection], env=environment, cwd=temp, capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise SystemExit(f"JOIN fixture failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
print("PostgreSQL inner, left, right, full and chained query links verified")
