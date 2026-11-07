"""Verify discarded generic map results against the original Java runtime.

Usage: python tests/primary_string_map_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/primary_string_map_oracle.py <original-z8-root>")
root = Path(sys.argv[1]).resolve()
jars = sorted((root / "org.zenframework.z8.server/target/libs").glob("org.zenframework.z8.server-*.jar"))
logging_jars = [p for p in (Path.home() / ".gradle/caches/modules-2/files-2.1/commons-logging/commons-logging").rglob("commons-logging-*.jar") if not p.name.endswith("-sources.jar")]
if not jars or not logging_jars:
    raise SystemExit("Original server JAR or commons-logging dependency not found")
jar, logging = jars[0], logging_jars[0]
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "Main.java"
    p.write_text('''import org.zenframework.z8.server.runtime.RLinkedHashMap;
import org.zenframework.z8.server.types.*;
public class Main {
  public static void main(String[] args) throws Exception {
    java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
    language.setAccessible(true); language.set(null, "ru");
    RLinkedHashMap<org.zenframework.z8.server.types.string, integer> typed = new RLinkedHashMap<>();
    org.zenframework.z8.server.types.string key = new org.zenframework.z8.server.types.string("key");
    RLinkedHashMap raw = typed;
    raw.z8_add(key, new org.zenframework.z8.server.types.string("wrong"));
    typed.z8_add(key, new integer(3));
    raw.z8_add(key, new org.zenframework.z8.server.types.string("wrong"));
    typed.z8_remove(key);
    raw.z8_add(key, new org.zenframework.z8.server.types.string("wrong"));
    try { integer value = typed.z8_add(key, new integer(5)); throw new RuntimeException("missing cast"); }
    catch (ClassCastException expected) { System.out.print(typed.z8_get(key).get()); }
  }
}''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", str(jar), str(p)], check=True, capture_output=True)
    actual = subprocess.check_output(["java", "-cp", os.pathsep.join((td, str(jar), str(logging))), "Main"], text=True)
    assert actual == "5", actual
print("Discarded and consumed map results match Java")

