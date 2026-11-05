"""Compare request-monitor JSON with the original Java JsonWriter."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/request_monitor_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
server = original / "org.zenframework.z8.server"
jars = list((server / "target/libs").glob("*.jar"))
jars += list((original / "org.zenframework.z8.boot/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
jars += [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar") if not p.name.endswith("-sources.jar")]
jars += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
if not jars: raise SystemExit("Original Z8 server JAR not found")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import std.stdio : writeln;
void main() {
    writeln(z8_monitor_info_json(null, null));
    Z8MonitorEntry[] messages = [Z8MonitorEntry(Z8MonitorLevel.info, "hello"w, null, z8_date_from_ticks(1234)),
        Z8MonitorEntry(Z8MonitorLevel.warning, "warning"w, "source"w, z8_date_from_ticks(5678)),
        Z8MonitorEntry(Z8MonitorLevel.error, "broken"w, null, z8_date_from_ticks(9012))];
    auto f = z8_file_from_path("report.txt"w);
    f.time = z8_date_from_ticks(4567); f.size = z8_optional_wrap(42L);
    f.details.z8_add("kind"w, "text"w);
    writeln(z8_monitor_info_json(messages, [f], "server"w));
}
''', encoding="utf-8")
    exe = temp / ("monitor.exe" if os.name == "nt" else "monitor")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(exe)], check=True)
    actual = [json.loads(line) for line in subprocess.check_output([str(exe)], text=True, encoding="utf-8").splitlines()]
    java = temp / "MonitorOracle.java"
    java.write_text('''
import java.util.*;
import org.zenframework.z8.server.json.JsonWriter;
import org.zenframework.z8.server.request.Message;
import org.zenframework.z8.server.types.*;
public class MonitorOracle {
    static Message timed(Message message, long time) throws Exception {
        java.lang.reflect.Field field = Message.class.getDeclaredField("time");
        field.setAccessible(true); field.set(message, new date(time)); return message;
    }
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        JsonWriter empty = new JsonWriter(true); empty.startObject();
        empty.writeInfo(Collections.emptyList(), Collections.emptyList(), null); empty.finishObject();
        System.out.println(empty.toString());
        file f = new file("report.txt"); f.time = new date(4567); f.size = new integer(42);
        f.details.put(new string("kind"), new string("text"));
        JsonWriter writer = new JsonWriter(true); writer.startObject();
        writer.writeInfo(Arrays.asList(timed(Message.info("hello", null), 1234),
            timed(Message.warning("warning", "source"), 5678),
            timed(Message.error(new RuntimeException("broken"), null), 9012)), Arrays.asList(f), "server");
        writer.finishObject(); System.out.println(writer.toString());
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, jars))
    base = server / "src/main/java/org/zenframework/z8/server"
    sources = [base / "json/JsonWriter.java", base / "request/Message.java", base / "geometry/parser/GeoJsonWriter.java",
               base / "types/decimal.java", base / "types/date.java", base / "types/file.java", base / "types/binary.java",
               base / "json/parser/JsonObject.java", java]
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", cp,
                    "-d", str(temp), *map(str, sources)], check=True)
    expected = [json.loads(line)["info"] for line in subprocess.check_output(
        ["java", "-cp", str(temp) + os.pathsep + cp, "MonitorOracle"], text=True, encoding="utf-8").splitlines()]
    if actual != expected: raise SystemExit(f"Monitor JSON differs:\nD: {actual}\nJava: {expected}")
print("Request monitor JSON matches the original Java writer")
