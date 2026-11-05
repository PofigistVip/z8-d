"""Exercise BL Link initialization, assignment and join metadata."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/query_link.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Customer.bl").write_text('''
import org.zenframework.z8.base.table.Table;
public class Customer extends Table {}
''', encoding="utf-8")
    (source / "LeftLink.bl").write_text('''
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
public class LeftLink extends Link { joinType = JoinType.Left; }
''', encoding="utf-8")
    (source / "RightLink.bl").write_text('''
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
public class RightLink extends Link { joinType = JoinType.Right; }
''', encoding="utf-8")
    (source / "FullLink.bl").write_text('''
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.JoinType;
public class FullLink extends Link { joinType = JoinType.Full; }
''', encoding="utf-8")
    (source / "Orders.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
public class Orders extends Table {
    public Customer customer;
    [name "CustomerId"] public Link customerId = customer;
    public LeftLink optionalCustomer = customer;
    public RightLink reverseCustomer = customer;
    public FullLink fullCustomer = customer;
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static Orders make() { Orders value; return value; }
    public static Customer customer() { Customer value; return value; }
    public static void assign(Orders value, Customer target) { value.customerId = target; }
    public static bool indexed(Orders value) { return value.customerId.indexed; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() {
    alias P = Z8p_50726F6265;
    auto order = P.m_make(); z8_nonnull(order);
    auto link = z8_nonnull(order.f_customerId);
    auto optional = z8_nonnull(order.f_optionalCustomer);
    auto customer = z8_nonnull(order.f_customer);
    assert(z8_link_query(link) is customer && z8_link_query(optional) is customer);
    assert(z8_link_join_type(link) == Z8JoinType.inner && z8_link_join_type(optional) == Z8JoinType.left);
    assert(z8_link_join_type(order.f_reverseCustomer) == Z8JoinType.right && z8_link_join_type(order.f_fullCustomer) == Z8JoinType.full);
    assert(z8_optional_require(P.m_indexed(order)));
    assert(z8_query_declared_fields(order, true).length == 10);
    z8_field_bind_sql(link, "orders"w, "CustomerId"w);
    z8_field_bind_sql(customer.f_recordId(), "customers"w, "RecordId"w);
    assert(z8_sql_bool_format(z8_link_on(link), true) == `orders."CustomerId"=customers."RecordId"`w);
    auto replacement = P.m_customer(); P.m_assign(order, replacement);
    assert(z8_link_query(link) is replacement);
    P.m_assign(order, null); assert(z8_link_query(link) is null);
    bool failed; try { z8_link_on(link); } catch (Exception) { failed = true; } assert(failed);
}
''', encoding="utf-8")
    exe = temp / ("query-link.exe" if os.name == "nt" else "query-link")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Link target, join direction and SQL condition verified")
