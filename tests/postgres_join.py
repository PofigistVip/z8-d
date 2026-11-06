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
import org.zenframework.z8.base.table.value.IntExpression;
[name "Customers"] public class Customer extends Table {
    [name "Label"] public StringField label;
    public IntExpression labelLength = label.sql_string().length();
    public City city; [name "CityId"] public Link cityId = city;
}
''',
        "AggregateOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.IntField;
[name "AggregateOrders"] public class AggregateOrder extends Table {
    public Customer customer; [name "CustomerId"] public Link customerId = customer;
    [name "Amount"] public IntField amount;
    aggregateBy = {customerId};
}
''',
        "AggregateLeftOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
[name "AggregateLeftOrders"] public class AggregateLeftOrder extends Table {
    public Customer customer; [name "CustomerId"] public LeftLink customerId = customer;
    [name "Amount"] public IntField amount;
    aggregateBy = {customerId};
}
''',
        "AggregateFilteredOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.IntField;
[name "AggregateFilteredOrders"] public class AggregateFilteredOrder extends Table {
    public FilteredCustomer customer; [name "CustomerId"] public Link customerId = customer;
    [name "Amount"] public IntField amount;
    aggregateBy = {customerId};
}
''',
        "AggregateJoinCustomer": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Join;
[name "JoinCustomers"] public class AggregateJoinCustomer extends Table {
    public City city; public Join cityJoin = city;
}
''',
        "AggregateJoinOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.Link;
[name "AggregateJoinOrders"] public class AggregateJoinOrder extends Table {
    public AggregateJoinCustomer customer; [name "CustomerId"] public Link customerId = customer;
    [name "OtherId"] public GuidField otherId;
    aggregateBy = {customerId};
}
''',
        "AggregateDynamicOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.IntField;
[name "AggregateDynamicOrders"] public class AggregateDynamicOrder extends Table {
    public Customer customer; [name "CustomerId"] public Link customerId = customer;
    [name "Amount"] public IntField amount;
    aggregateBy = {customerId};
    virtual protected void beforeRead() { aggregateBy.clear(); }
}
''',
        "AverageOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.Aggregation;
[name "AverageOrders"] public class AverageOrder extends Table {
    public Customer customer; [name "CustomerId"] public Link customerId = customer;
    [name "Amount"] public IntField amount; amount.aggregation = Aggregation.Average;
    aggregateBy = {customerId};
}
''',
        "DecimalOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.DecimalField;
[name "DecimalOrders"] public class DecimalOrder extends Table {
    public Customer customer; [name "CustomerId"] public Link customerId = customer;
    [name "Amount"] public DecimalField amount;
    aggregateBy = {customerId};
}
''',
        "GroupCustomer": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[name "GroupCustomers"] public class GroupCustomer extends Table { [name "Label"] public StringField label; }
''',
        "GroupedOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.Aggregation;
[name "GroupedOrders"] public class GroupedOrder extends Table {
    public GroupCustomer customer; [name "CustomerId"] public Link customerId = customer;
    [name "Amount"] public IntField amount;
    customer.label.aggregation = Aggregation.None;
    aggregateBy = {customerId}; groupBy = {customer.label};
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
        "HttpOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntExpression;
import org.zenframework.z8.base.form.Form;
import org.zenframework.z8.base.application.Application;
[name "Orders"] public class HttpOrder extends Table {
    [name "Title"] public StringField title;
    public Customer customer; [name "CustomerId"] public Link customerId = customer;
    public IntExpression nameLength = customer.label.sql_string().length();
    Form details; details.dependency = customerId; details.controls = {customer.label}; controls = {details};
    virtual protected void onReadAction() {
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "group") groupBy = {customer.label};
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "context-filter") addWhere(customer.label == customer.label.get());
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "changed-link") customer.label = "Changed in hook";
    }
}
''',
        "HttpRightOrder": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[name "RightOrders"] public class HttpRightOrder extends Table {
    [name "Title"] public StringField title;
    public Customer customer; [name "CustomerId"] public RightLink customerId = customer;
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
import org.zenframework.z8.base.table.value.Aggregation;
import org.zenframework.z8.base.table.SortDirection;
public class Probe {
    public static AggregateOrder aggregateOrder() { AggregateOrder value; return value; }
    public static AggregateLeftOrder aggregateLeftOrder() { AggregateLeftOrder value; return value; }
    public static AggregateFilteredOrder aggregateFilteredOrder() { AggregateFilteredOrder value; return value; }
    public static AggregateJoinOrder aggregateJoinOrder() { AggregateJoinOrder value; return value; }
    public static GroupedOrder groupedOrder() { GroupedOrder value; return value; }
    public static void readGroupedOrder(GroupedOrder order) { Field[] fields = {order.customer.label, order.amount}; order.read(fields); }
    public static void readExplicitGroupedOrder(GroupedOrder order) { Field[] groups = {order.customerId}; Field[] fields = {order.customerId, order.amount}; order.group(groups, fields); }
    public static int countGroupedOrder(GroupedOrder order) { return order.count(); }
    public static bool nextGroupedOrder(GroupedOrder order) { return order.next(); }
    public static string groupedOrderLabel(GroupedOrder order) { return order.customer.label.get(); }
    public static int groupedOrderAmount(GroupedOrder order) { return order.amount.get(); }
    public static void configureAggregateJoin(AggregateJoinOrder order) { order.customer.cityJoin = order.otherId.sql_guid() == order.customer.city.recordId.sql_guid(); }
    public static void readAggregateJoin(AggregateJoinOrder order) { Field[] fields = {order.customer.city.label}; order.read(fields); }
    public static void readAggregate(AggregateOrder order) { Field[] fields = {order.customerId, order.amount}; order.read(fields); }
    public static void readAggregateSorted(AggregateOrder order) { order.amount.sortDirection = SortDirection.Desc; Field[] fields = {order.customerId, order.amount}; Field[] sort = {order.amount}; order.read(fields, sort); }
    public static void readAggregateAverage(AggregateOrder order) { order.amount.aggregation = Aggregation.Average; Field[] fields = {order.customerId, order.amount}; Field[] sort = {order.amount}; order.read(fields, sort, null, 1, 1); }
    public static void readAggregateLinked(AggregateOrder order) { Field[] fields = {order.customer.label}; order.read(fields); }
    public static void readAggregateLinkedSorted(AggregateOrder order) { Field[] fields = {order.customer.label, order.amount}; Field[] sort = {order.customer.label}; order.read(fields, sort); }
    public static void readAggregateSortOnly(AggregateOrder order) { Field[] fields = {order.amount}; Field[] sort = {order.customer.label}; order.read(fields, sort); }
    public static void readAggregateNested(AggregateOrder order) { Field[] fields = {order.customer.city.label}; order.read(fields); }
    public static void readAggregateExpression(AggregateOrder order) { Field[] fields = {order.customer.labelLength, order.amount}; Field[] sort = {order.customer.labelLength}; order.read(fields, sort); }
    public static int aggregateCount(AggregateOrder order) { return order.count(); }
    public static int aggregateAlice(AggregateOrder order) { return order.count(order.customer.label == "Alice"); }
    public static bool nextAggregate(AggregateOrder order) { return order.next(); }
    public static guid aggregateCustomer(AggregateOrder order) { return order.customerId.get(); }
    public static int aggregateAmount(AggregateOrder order) { return order.amount.get(); }
    public static void aggregateHavingAmount(AggregateOrder order) { order.addHaving(order.amount > 9); }
    public static void aggregateHavingName(AggregateOrder order) { order.addHaving(order.customer.label == "Alice"); }
    public static string aggregateName(AggregateOrder order) { return order.customer.label.get(); }
    public static string aggregateCity(AggregateOrder order) { return order.customer.city.label.get(); }
    public static int aggregateLabelLength(AggregateOrder order) { return order.customer.labelLength.get(); }
    public static Field aggregateNameField(AggregateOrder order) { return order.customer.label; }
    public static void readAggregateLeft(AggregateLeftOrder order) { Field[] fields = {order.customer.label, order.amount}; order.read(fields); }
    public static bool nextAggregateLeft(AggregateLeftOrder order) { return order.next(); }
    public static string aggregateLeftName(AggregateLeftOrder order) { return order.customer.label.get(); }
    public static int aggregateLeftAmount(AggregateLeftOrder order) { return order.amount.get(); }
    public static void readAggregateLeftCity(AggregateLeftOrder order) { Field[] fields = {order.customer.city.label}; order.read(fields); }
    public static string aggregateLeftCity(AggregateLeftOrder order) { return order.customer.city.label.get(); }
    public static void readAggregateFiltered(AggregateFilteredOrder order) { Field[] fields = {order.customer.label}; order.read(fields); }
    public static bool nextAggregateFiltered(AggregateFilteredOrder order) { return order.next(); }
    public static string aggregateFilteredName(AggregateFilteredOrder order) { return order.customer.label.get(); }
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
import z8.database.connection;
import z8gen.p_Probe;
import std.conv : to;
import std.json : parseJSON;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto db = new Z8PostgresConnection(args[1]);
    db.execute(`CREATE TEMP TABLE "Cities" ("RecordId" uuid PRIMARY KEY, "Label" text)`);
    db.execute(`CREATE TEMP TABLE "Customers" ("RecordId" uuid PRIMARY KEY, "Label" text, "CityId" uuid)`);
    db.execute(`CREATE TEMP TABLE "Orders" ("RecordId" uuid PRIMARY KEY, "Title" text, "CustomerId" uuid, "CityId" uuid, "Lock" bigint DEFAULT 0)`);
    db.execute(`CREATE TEMP TABLE "AggregateOrders" ("RecordId" uuid PRIMARY KEY, "CustomerId" uuid, "Amount" bigint)`);
    db.execute(`INSERT INTO "AggregateOrders" VALUES ('00000000-0000-0000-0000-000000000311','00000000-0000-0000-0000-000000000201',4), ('00000000-0000-0000-0000-000000000312','00000000-0000-0000-0000-000000000201',6), ('00000000-0000-0000-0000-000000000313','00000000-0000-0000-0000-000000000202',7)`);
    db.execute(`CREATE TEMP TABLE "AverageOrders" ("RecordId" uuid PRIMARY KEY, "CustomerId" uuid, "Amount" bigint)`);
    db.execute(`INSERT INTO "AverageOrders" VALUES ('00000000-0000-0000-0000-000000000321','00000000-0000-0000-0000-000000000201',1), ('00000000-0000-0000-0000-000000000322','00000000-0000-0000-0000-000000000201',2), ('00000000-0000-0000-0000-000000000323','00000000-0000-0000-0000-000000000202',2), ('00000000-0000-0000-0000-000000000324','00000000-0000-0000-0000-000000000202',3)`);
    db.execute(`CREATE TEMP TABLE "DecimalOrders" ("RecordId" uuid PRIMARY KEY, "CustomerId" uuid, "Amount" numeric)`);
    db.execute(`INSERT INTO "DecimalOrders" VALUES ('00000000-0000-0000-0000-000000000331','00000000-0000-0000-0000-000000000201',1.25), ('00000000-0000-0000-0000-000000000332','00000000-0000-0000-0000-000000000201',2.5), ('00000000-0000-0000-0000-000000000333','00000000-0000-0000-0000-000000000202',3.125)`);
    db.execute(`CREATE TEMP TABLE "GroupCustomers" ("RecordId" uuid PRIMARY KEY, "Label" text)`);
    db.execute(`INSERT INTO "GroupCustomers" VALUES ('00000000-0000-0000-0000-000000000501','Alice'), ('00000000-0000-0000-0000-000000000502','Alice'), ('00000000-0000-0000-0000-000000000503','Bob')`);
    db.execute(`CREATE TEMP TABLE "GroupedOrders" ("RecordId" uuid PRIMARY KEY, "CustomerId" uuid, "Amount" bigint)`);
    db.execute(`INSERT INTO "GroupedOrders" VALUES ('00000000-0000-0000-0000-000000000511','00000000-0000-0000-0000-000000000501',4), ('00000000-0000-0000-0000-000000000512','00000000-0000-0000-0000-000000000501',6), ('00000000-0000-0000-0000-000000000513','00000000-0000-0000-0000-000000000502',3), ('00000000-0000-0000-0000-000000000514','00000000-0000-0000-0000-000000000503',7)`);
    db.execute(`CREATE TEMP TABLE "Nodes" ("RecordId" uuid PRIMARY KEY, "ParentId" uuid)`);
    db.execute(`INSERT INTO "Nodes" VALUES ('00000000-0000-0000-0000-000000000401','00000000-0000-0000-0000-000000000402'), ('00000000-0000-0000-0000-000000000402',NULL), ('00000000-0000-0000-0000-000000000403','00000000-0000-0000-0000-000000000401')`);
    db.execute(`INSERT INTO "Cities" VALUES ('00000000-0000-0000-0000-000000000101','Moscow')`);
    db.execute(`INSERT INTO "Customers" VALUES ('00000000-0000-0000-0000-000000000201','Alice','00000000-0000-0000-0000-000000000101'), ('00000000-0000-0000-0000-000000000202','Bob',NULL), ('00000000-0000-0000-0000-000000000203','Ghost',NULL), ('00000000-0000-0000-0000-000000000000','Sentinel',NULL)`);
    db.execute(`INSERT INTO "Orders" ("RecordId","Title","CustomerId","CityId") VALUES ('00000000-0000-0000-0000-000000000301','First','00000000-0000-0000-0000-000000000201','00000000-0000-0000-0000-000000000101'), ('00000000-0000-0000-0000-000000000302','Second','00000000-0000-0000-0000-000000000202',NULL), ('00000000-0000-0000-0000-000000000303','No customer',NULL,NULL), ('00000000-0000-0000-0000-000000000304','Missing customer','00000000-0000-0000-0000-000000000299',NULL)`);
    auto inner = P.m_inner(); auto left = P.m_left(); auto right = P.m_right(); auto full = P.m_full(); auto filtered = P.m_filtered(); auto recursive = P.m_recursive(); auto conditional = P.m_conditional(); auto cyclic = P.m_cyclic();
    auto aggregate = P.m_aggregateOrder();
    auto aggregateExecutor = new Z8PostgresQueryExecutor(db, "pg_temp"w, "AggregateOrders"w);
    z8_query_set_executor(aggregate, aggregateExecutor);
    assert(z8_optional_require(P.m_aggregateCount(aggregate)) == 2);
    assert(z8_optional_require(P.m_aggregateAlice(aggregate)) == 1);
    P.m_readAggregate(aggregate); long sum; int aggregateRows;
    while (z8_optional_require(P.m_nextAggregate(aggregate))) {
        auto customer = P.m_aggregateCustomer(aggregate); auto amount = z8_optional_require(P.m_aggregateAmount(aggregate));
        if (customer == z8_guid_create(0x201)) assert(amount == 10);
        else { assert(customer == z8_guid_create(0x202) && amount == 7); }
        sum += amount; ++aggregateRows;
    }
    assert(aggregateRows == 2 && sum == 17);
    auto groupedOrder = P.m_groupedOrder();
    z8_query_set_executor(groupedOrder, new Z8PostgresQueryExecutor(db, "pg_temp"w, "GroupedOrders"w));
    assert(z8_optional_require(P.m_countGroupedOrder(groupedOrder)) == 2);
    P.m_readGroupedOrder(groupedOrder); int groupedRows;
    while (z8_optional_require(P.m_nextGroupedOrder(groupedOrder))) {
        auto label = P.m_groupedOrderLabel(groupedOrder); auto amount = z8_optional_require(P.m_groupedOrderAmount(groupedOrder));
        if (label == "Alice"w) assert(amount == 13); else assert(label == "Bob"w && amount == 7);
        ++groupedRows;
    }
    assert(groupedRows == 2);
    P.m_readExplicitGroupedOrder(groupedOrder); groupedRows = 0; long explicitSum;
    while (z8_optional_require(P.m_nextGroupedOrder(groupedOrder))) { explicitSum += z8_optional_require(P.m_groupedOrderAmount(groupedOrder)); ++groupedRows; }
    assert(groupedRows == 3 && explicitSum == 20);
    P.m_readAggregateSorted(aggregate);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && z8_optional_require(P.m_aggregateAmount(aggregate)) == 10);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && z8_optional_require(P.m_aggregateAmount(aggregate)) == 7);
    P.m_readAggregateAverage(aggregate);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && z8_optional_require(P.m_aggregateAmount(aggregate)) == 5);
    assert(!z8_optional_require(P.m_nextAggregate(aggregate)));
    P.m_readAggregateExpression(aggregate);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && z8_optional_require(P.m_aggregateLabelLength(aggregate)) == 3 && z8_optional_require(P.m_aggregateAmount(aggregate)) == 7);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && z8_optional_require(P.m_aggregateLabelLength(aggregate)) == 5 && z8_optional_require(P.m_aggregateAmount(aggregate)) == 5);
    assert(!z8_optional_require(P.m_nextAggregate(aggregate)));
    P.m_readAggregateLinked(aggregate); int linkedAggregateRows;
    while (z8_optional_require(P.m_nextAggregate(aggregate))) { assert(P.m_aggregateName(aggregate).length); ++linkedAggregateRows; }
    assert(linkedAggregateRows == 2);
    P.m_readAggregateLinkedSorted(aggregate);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && P.m_aggregateName(aggregate) == "Alice"w && z8_optional_require(P.m_aggregateAmount(aggregate)) == 5);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && P.m_aggregateName(aggregate) == "Bob"w && z8_optional_require(P.m_aggregateAmount(aggregate)) == 7);
    assert(!z8_optional_require(P.m_nextAggregate(aggregate)));
    P.m_readAggregateSortOnly(aggregate);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && z8_optional_require(P.m_aggregateAmount(aggregate)) == 5);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && z8_optional_require(P.m_aggregateAmount(aggregate)) == 7);
    Z8QueryReadRequest countLinked; countLinked.fields = [cast(Z8Object)P.m_aggregateNameField(aggregate)];
    assert(countLinked.fields[0] !is null && aggregateExecutor.count(aggregate, countLinked) == 2);
    P.m_readAggregateNested(aggregate);
    assert(z8_optional_require(P.m_nextAggregate(aggregate)) && P.m_aggregateCity(aggregate) == "Moscow"w);
    assert(!z8_optional_require(P.m_nextAggregate(aggregate)));
    db.execute(`INSERT INTO "AggregateOrders" VALUES ('00000000-0000-0000-0000-000000000314','00000000-0000-0000-0000-000000000299',11)`);
    auto aggregateLeft = P.m_aggregateLeftOrder();
    z8_query_set_executor(aggregateLeft, new Z8PostgresQueryExecutor(db, "pg_temp"w, "AggregateOrders"w));
    P.m_readAggregateLeft(aggregateLeft); int leftAggregateRows, leftAggregateMissing;
    while (z8_optional_require(P.m_nextAggregateLeft(aggregateLeft))) {
        if (P.m_aggregateLeftName(aggregateLeft) == ""w) {
            ++leftAggregateMissing; assert(z8_optional_require(P.m_aggregateLeftAmount(aggregateLeft)) == 11);
        }
        ++leftAggregateRows;
    }
    assert(leftAggregateRows == 3 && leftAggregateMissing == 1);
    P.m_readAggregateLeftCity(aggregateLeft); int aggregateCityRows, aggregateCities;
    while (z8_optional_require(P.m_nextAggregateLeft(aggregateLeft))) {
        if (P.m_aggregateLeftCity(aggregateLeft) == "Moscow"w) ++aggregateCities;
        ++aggregateCityRows;
    }
    assert(aggregateCityRows == 3 && aggregateCities == 1);
    auto aggregateJoin = P.m_aggregateJoinOrder();
    z8_query_set_executor(aggregateJoin, new Z8PostgresQueryExecutor(db, "pg_temp"w, "AggregateOrders"w));
    P.m_configureAggregateJoin(aggregateJoin);
    bool unprojectedRootRejected;
    try { P.m_readAggregateJoin(aggregateJoin); } catch (Z8PostgresException) { unprojectedRootRejected = true; }
    assert(unprojectedRootRejected);
    assert(aggregateExecutor.count(aggregate, countLinked) == 2); // Inner join drops the unmatched group.
    auto aggregateHaving = P.m_aggregateOrder();
    z8_query_set_executor(aggregateHaving, new Z8PostgresQueryExecutor(db, "pg_temp"w, "AggregateOrders"w));
    P.m_aggregateHavingAmount(aggregateHaving);
    assert(z8_optional_require(P.m_aggregateCount(aggregateHaving)) == 2); // Alice and missing customer.
    P.m_readAggregate(aggregateHaving); int havingRows;
    while (z8_optional_require(P.m_nextAggregate(aggregateHaving))) { assert(z8_optional_require(P.m_aggregateAmount(aggregateHaving)) > 9); ++havingRows; }
    assert(havingRows == 2);
    auto aggregateNameHaving = P.m_aggregateOrder();
    z8_query_set_executor(aggregateNameHaving, new Z8PostgresQueryExecutor(db, "pg_temp"w, "AggregateOrders"w));
    P.m_aggregateHavingName(aggregateNameHaving);
    assert(z8_optional_require(P.m_aggregateCount(aggregateNameHaving)) == 1);
    P.m_readAggregate(aggregateNameHaving);
    assert(z8_optional_require(P.m_nextAggregate(aggregateNameHaving)) && z8_optional_require(P.m_aggregateAmount(aggregateNameHaving)) == 10);
    assert(!z8_optional_require(P.m_nextAggregate(aggregateNameHaving)));
    auto aggregateFiltered = P.m_aggregateFilteredOrder();
    z8_query_set_executor(aggregateFiltered, new Z8PostgresQueryExecutor(db, "pg_temp"w, "AggregateOrders"w));
    P.m_readAggregateFiltered(aggregateFiltered);
    assert(z8_optional_require(P.m_nextAggregateFiltered(aggregateFiltered)) && P.m_aggregateFilteredName(aggregateFiltered) == "Alice"w);
    assert(!z8_optional_require(P.m_nextAggregateFiltered(aggregateFiltered)));
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
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    auto session = new Z8ApplicationSession("join"w, user, user);
    auto priorBackend = z8_connection_set_current(new Z8PostgresDatabase(db, "pg_temp"w));
    wstring requestFields(wstring fields, wstring filter = null, wstring sort = null, wstring lookup = null, wstring lookupFields = null, wstring className = "HttpOrder"w, wstring action = "read"w, wstring groupSession = null, wstring having = null, wstring values = null, wstring totals = null, wstring count = null) {
        auto request = new Z8ApplicationRequest(); request.session = session; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("request"w, className); request.parameters.z8_add("action"w, action); request.parameters.z8_add("fields"w, fields);
        if (filter !is null) request.parameters.z8_add("filter"w, filter);
        if (sort !is null) request.parameters.z8_add("sort"w, sort);
        if (lookup !is null) request.parameters.z8_add("lookup"w, lookup);
        if (lookupFields !is null) request.parameters.z8_add("lookupFields"w, lookupFields);
        if (groupSession !is null) request.parameters.z8_add("session"w, groupSession);
        if (having !is null) request.parameters.z8_add("having"w, having);
        if (values !is null) request.parameters.z8_add("values"w, values);
        if (totals !is null) request.parameters.z8_add("totals"w, totals);
        if (count !is null) request.parameters.z8_add("count"w, count);
        auto priorRequest = z8_application_set_request(request); scope(exit) z8_application_set_request(priorRequest);
        z8_application_start_response(request, "HttpOrder"w); z8_application_dispatch_request();
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); return z8_application_response_text(request);
    }
    db.execute(`CREATE TEMP TABLE "RightOrders" AS SELECT * FROM "Orders"`);
    auto response = parseJSON(requestFields(`["title","customer.label","customer.city.label"]`w).to!string);
    assert(response["data"].array.length == 1 && response["data"][0]["customer.label"].str == "Alice" && response["data"][0]["customer.city.label"].str == "Moscow");
    assert(response["data"][0]["customerId"].str == "00000000-0000-0000-0000-000000000201");
    assert(response["data"][0]["customer.cityId"].str == "00000000-0000-0000-0000-000000000101");
    auto aggregateResponse = parseJSON(requestFields(`["customer.label","amount"]`w, null,
        `[{"property":"customer.label"}]`w, null, null, "AggregateOrder"w).to!string);
    assert(aggregateResponse["data"].array.length == 2);
    assert(aggregateResponse["data"][0]["customer.label"].str == "Alice" && aggregateResponse["data"][0]["amount"].integer == 10);
    assert(aggregateResponse["data"][1]["customer.label"].str == "Bob" && aggregateResponse["data"][1]["amount"].integer == 7);
    aggregateResponse = parseJSON(requestFields(`["customer.labelLength","amount"]`w, null, `[{"property":"customer.labelLength"}]`w, null, null, "AggregateOrder"w).to!string);
    assert(aggregateResponse["data"].array.length == 2 && aggregateResponse["data"][0]["customer.labelLength"].integer == 3 && aggregateResponse["data"][1]["customer.labelLength"].integer == 5);
    aggregateResponse = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null,
        `{"property":"amount","operator":"gt","value":"9"}`w).to!string);
    assert(aggregateResponse["data"].array.length == 1 && aggregateResponse["data"][0]["customer.label"].str == "Alice");
    aggregateResponse = parseJSON(requestFields(`["amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null,
        `{"property":"customer.label","value":"Alice"}`w).to!string);
    assert(aggregateResponse["data"].array.length == 1 && aggregateResponse["data"][0]["amount"].integer == 10);
    aggregateResponse = parseJSON(requestFields(`["amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null,
        `{"property":"customer.labelLength","operator":"gt","value":"3"}`w).to!string);
    assert(aggregateResponse["data"].array.length == 1 && aggregateResponse["data"][0]["amount"].integer == 10);
    auto totalResponse = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null, null, null, "true"w).to!string);
    assert(totalResponse["data"]["amount"].integer == 17);
    totalResponse = parseJSON(requestFields(`["customer.labelLength","amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null, null, null, "true"w).to!string);
    assert(totalResponse["data"]["customer.labelLength"].integer == 8 && totalResponse["data"]["amount"].integer == 17);
    totalResponse = parseJSON(requestFields(`["amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null,
        `{"property":"amount","operator":"gt","value":"9"}`w, null, "true"w).to!string);
    assert(totalResponse["data"]["amount"].integer == 21);
    totalResponse = parseJSON(requestFields(`["amount"]`w, null, null, null, null, "AverageOrder"w, "read"w, null, null, null, "true"w).to!string);
    assert(totalResponse["data"]["amount"].integer == 2); // Average 1.5 and 2.5 before rounding.
    aggregateResponse = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "AverageOrder"w, "read"w, null,
        `{"property":"amount","operator":"gt","value":"1"}`w).to!string);
    assert(aggregateResponse["data"].array.length == 2); // HAVING sees 1.5, not the displayed 1.
    totalResponse = parseJSON(requestFields(`["amount"]`w, null, null, null, null, "DecimalOrder"w, "read"w, null, null, null, "true"w).to!string);
    assert(totalResponse["data"]["amount"].floating == 6.875);
    totalResponse = parseJSON(requestFields(`["amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null,
        `{"property":"amount","operator":"gt","value":"1000"}`w, null, "true"w).to!string);
    assert(totalResponse["data"]["amount"].integer == 0);
    auto twiceGrouped = parseJSON(requestFields(`["customer.label","amount"]`w, null,
        `[{"property":"customer.label"}]`w, null, null, "GroupedOrder"w).to!string);
    assert(twiceGrouped["data"].array.length == 2 && twiceGrouped["data"][0]["customer.label"].str == "Alice" && twiceGrouped["data"][0]["amount"].integer == 13);
    assert(twiceGrouped["data"][1]["customer.label"].str == "Bob" && twiceGrouped["data"][1]["amount"].integer == 7);
    twiceGrouped = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "GroupedOrder"w, "read"w, null,
        `{"property":"amount","operator":"gt","value":"10"}`w).to!string);
    assert(twiceGrouped["data"].array.length == 1 && twiceGrouped["data"][0]["amount"].integer == 13);
    twiceGrouped = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "GroupedOrder"w, "read"w, null, null, null, null, "true"w).to!string);
    assert(twiceGrouped["total"].integer == 2);
    totalResponse = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "GroupedOrder"w, "read"w, null, null, null, "true"w).to!string);
    assert(totalResponse["data"]["amount"].integer == 20);
    totalResponse = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "GroupedOrder"w, "read"w, null,
        `{"property":"amount","operator":"gt","value":"10"}`w, null, "true"w).to!string);
    assert(totalResponse["data"]["amount"].integer == 13);
    auto aggregateMeta = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "AggregateOrder"w, "meta"w).to!string);
    assert(aggregateMeta["isQuery"].boolean && aggregateMeta["readOnly"].boolean && "primaryKey" !in aggregateMeta.object);
    aggregateResponse = parseJSON(requestFields(`["customer.label","amount"]`w, null, null, null, null, "AggregateOrder"w, null).to!string);
    assert(aggregateResponse["isQuery"].boolean && aggregateResponse["readOnly"].boolean && aggregateResponse["data"].array.length == 2);
    bool changedGroupingRejected;
    try { requestFields(`["amount"]`w, null, null, null, null, "AggregateDynamicOrder"w, "read"w); } catch (Exception) { changedGroupingRejected = true; }
    assert(changedGroupingRejected);
    changedGroupingRejected = false;
    try { requestFields(`["amount"]`w, null, null, null, null, "AggregateDynamicOrder"w, "meta"w); } catch (Exception) { changedGroupingRejected = true; }
    assert(changedGroupingRejected);
    auto linkedMeta = parseJSON(requestFields(`["customer.label","customer.city.label"]`w, null, null, null, null, "HttpOrder"w, "meta"w).to!string);
    bool customerMeta, cityMeta;
    foreach (field; linkedMeta["fields"].array) {
        if (field["name"].str == "customer.label") {
            customerMeta = field["isCombobox"].boolean && field["query"]["name"].str == "customer" && field["link"]["name"].str == "customerId";
        }
        if (field["name"].str == "customer.city.label") {
            cityMeta = field["isCombobox"].boolean && field["link"]["owner"].str == "customer.cityId";
        }
    }
    assert(customerMeta && cityMeta);
    assert(linkedMeta["controls"][0]["isForm"].boolean && linkedMeta["controls"][0]["link"]["name"].str == "customerId");
    assert(linkedMeta["controls"][0]["link"]["primaryKey"].str == "recordId" && linkedMeta["controls"][0]["link"]["query"]["primaryKey"].str == "customer.recordId");
    assert(linkedMeta["controls"][0]["controls"][0]["name"].str == "customer.label");
    linkedMeta = parseJSON(requestFields(`["customer.label"]`w, null, null, null, null, "HttpOrder"w, null).to!string);
    assert(linkedMeta["isQuery"].boolean && linkedMeta["data"].array.length == 2);
    response = parseJSON(requestFields(`["title"]`w, `{"property":"customer.label","value":"alice"}`w).to!string);
    assert(response["data"].array.length == 1 && response["data"][0]["title"].str == "First");
    response = parseJSON(requestFields(`["title"]`w, null, `[{"property":"customer.label","direction":"DESC"}]`w).to!string);
    assert(response["data"].array.length == 2 && response["data"][0]["title"].str == "Second");
    response = parseJSON(requestFields(`["title"]`w, null, null, "ob"w, `["customer.label"]`w).to!string);
    assert(response["data"].array.length == 1 && response["data"][0]["title"].str == "Second");
    response = parseJSON(requestFields(`["title","nameLength"]`w, `{"property":"nameLength","operator":"gt","value":"3"}`w).to!string);
    assert(response["data"].array.length == 1 && response["data"][0]["title"].str == "First" && response["data"][0]["nameLength"].integer == 5);
    response = parseJSON(requestFields(`["title","customer.label"]`w, null, null, null, null, "HttpOrder"w, "read"w, "context-filter"w, null,
        `{"customer.label":"Bob"}`w).to!string);
    assert(response["data"].array.length == 1 && response["data"][0]["title"].str == "Second" && response["data"][0]["customer.label"].str == "Bob", response.toString());
    response = parseJSON(requestFields(`["customer.label"]`w, null, `[ {"property":"customer.label"} ]`w, null, null, "HttpOrder"w, "read"w, null, null,
        `{"customer.label":"Changed only for context"}`w).to!string);
    assert(response["data"].array.length == 2 && response["data"][0]["customer.label"].str == "Alice" && response["data"][1]["customer.label"].str == "Bob", response.toString());
    response = parseJSON(requestFields(`["customer.label"]`w, null, `[{"property":"customer.label"}]`w, null, null, "HttpOrder"w, "read"w, "changed-link"w).to!string);
    assert(response["data"].array.length == 2 && response["data"][0]["customer.label"].str == "Alice" && response["data"][1]["customer.label"].str == "Bob", response.toString());
    response = parseJSON(requestFields(`["nameLength"]`w, null, `[{"property":"nameLength"}]`w, null, null, "HttpOrder"w, "read"w, null, null,
        `{"nameLength":999}`w).to!string);
    assert(response["data"].array.length == 2 && response["data"][0]["nameLength"].integer == 3 && response["data"][1]["nameLength"].integer == 5, response.toString());
    response = parseJSON(requestFields(`["title"]`w, null, `[{"property":"nameLength"}]`w).to!string);
    assert(response["data"].array.length == 2 && response["data"][0]["title"].str == "Second");
    response = parseJSON(requestFields(`["customer.label","nameLength"]`w, null, null, null, null, "HttpOrder"w, "read"w, "group"w,
        `{"property":"customer.label","value":"alice"}`w).to!string);
    assert(response["data"].array.length == 1 && response["data"][0]["customer.label"].str == "Alice" && response["data"][0]["nameLength"].integer == 5, response.toString());
    linkedMeta = parseJSON(requestFields(`["customer.label"]`w, null, null, null, null, "HttpOrder"w, "meta"w, "group"w).to!string);
    assert(linkedMeta["isQuery"].boolean && linkedMeta["fields"].array.length != 0);
    response = parseJSON(requestFields(`["title","customer.label"]`w, null, null, null, null, "HttpRightOrder"w).to!string);
    bool unmatched;
    foreach (row; response["data"].array) if (row["customer.label"].str == "Ghost") {
        unmatched = true;
        assert(row["customerId"].str == "00000000-0000-0000-0000-000000000203");
        assert(row["customer.recordId"].str == "00000000-0000-0000-0000-000000000203");
    }
    assert(unmatched);
    auto denied = Z8Access.init;
    user.privileges.setFieldAccess(z8_guid_create_name("AggregateOrders.CustomerId"w), denied);
    bool aggregateBlocked;
    try { requestFields(`["amount"]`w, null, null, null, null, "AggregateOrder"w); } catch (Exception) { aggregateBlocked = true; }
    assert(aggregateBlocked);
    aggregateBlocked = false;
    try { requestFields(`["amount"]`w, null, null, null, null, "AggregateOrder"w, "meta"w); } catch (Exception) { aggregateBlocked = true; }
    assert(aggregateBlocked);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    user.privileges.setTableAccess(z8_guid_create_name("Customers"w), denied);
    bool blocked; try { requestFields(`["customer.label"]`w); } catch (Exception) { blocked = true; } assert(blocked);
    blocked = false; try { requestFields(`["customer.label"]`w, null, null, null, null, "HttpOrder"w, "meta"w); } catch (Exception) { blocked = true; } assert(blocked);
    blocked = false; try { requestFields(`["title"]`w, null, null, null, null, "HttpOrder"w, "meta"w); } catch (Exception) { blocked = true; } assert(blocked);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    user.privileges.setFieldAccess(z8_guid_create_name("Orders.CustomerId"w), denied);
    blocked = false; try { requestFields(`["customer.label"]`w); } catch (Exception) { blocked = true; } assert(blocked);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    user.privileges.setFieldAccess(z8_guid_create_name("Customers.CityId"w), denied);
    blocked = false; try { requestFields(`["customer.city.label"]`w); } catch (Exception) { blocked = true; } assert(blocked);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    user.privileges.setFieldAccess(z8_guid_create_name("Customers.Label"w), denied);
    aggregateBlocked = false;
    try { requestFields(`["amount"]`w, null, null, null, null, "AggregateOrder"w, "read"w, null,
        `{"property":"customer.labelLength","operator":"gt","value":"3"}`w); } catch (Exception) { aggregateBlocked = true; }
    assert(aggregateBlocked);
    response = parseJSON(requestFields(`["customer.label"]`w).to!string);
    foreach (row; response["data"].array) assert("customer.label" !in row.object);
    linkedMeta = parseJSON(requestFields(`["customer.label"]`w, null, null, null, null, "HttpOrder"w, "meta"w).to!string);
    foreach (field; linkedMeta["fields"].array) assert(field["name"].str != "customer.label");
    assert("controls" !in linkedMeta["controls"][0].object);
    blocked = false; try { requestFields(`["title"]`w, `{"property":"customer.label","value":"alice"}`w); } catch (Exception) { blocked = true; } assert(blocked);
    blocked = false; try { requestFields(`["title"]`w, null, `[{"property":"customer.label"}]`w); } catch (Exception) { blocked = true; } assert(blocked);
    blocked = false; try { requestFields(`["title"]`w, null, null, "alice"w, `["customer.label"]`w); } catch (Exception) { blocked = true; } assert(blocked);
    blocked = false; try { requestFields(`["title"]`w, null, null, null, null, "HttpOrder"w, "read"w, "group"w); } catch (Exception) { blocked = true; } assert(blocked);
    blocked = false; try { requestFields(`["title"]`w, null, null, null, null, "HttpOrder"w, "meta"w, "group"w); } catch (Exception) { blocked = true; } assert(blocked);
    blocked = false; try { requestFields(`["title"]`w, null, null, null, null, "HttpOrder"w, "read"w, null, null, `{"customer.label":"Bob"}`w); } catch (Exception) { blocked = true; } assert(blocked);
    response = parseJSON(requestFields(`["nameLength"]`w).to!string);
    foreach (row; response["data"].array) assert("nameLength" !in row.object);
    blocked = false; try { requestFields(`["title"]`w, `{"property":"nameLength","operator":"gt","value":"3"}`w); } catch (Exception) { blocked = true; } assert(blocked);
    z8_connection_set_current(priorBackend);
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
