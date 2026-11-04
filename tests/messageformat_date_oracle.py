"""Compare MessageFormat date/time formatting of epoch milliseconds with Java."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java = temp / "MessageDateOracle.java"
    java.write_text('''import java.math.BigDecimal;
import java.text.MessageFormat;
import java.util.TimeZone;
class MessageDateOracle {
    public static void main(String[] args) {
        TimeZone.setDefault(TimeZone.getTimeZone("Europe/Moscow"));
        String[] patterns = {"{0,date}", "{0,date,short}", "{0,date,medium}", "{0,date,long}",
            "{0,date,full}", "{0,time}", "{0,time,short}", "{0,time,medium}",
            "{0,time,long}", "{0,time,full}", "{0,date,yyyy-MM-dd HH:mm:ss}"};
        long[] ticks = {0L, 1709199045000L, 1723050000000L};
        for (String pattern : patterns) for (long tick : ticks)
            System.out.println(MessageFormat.format(pattern, tick));
        System.out.println(MessageFormat.format("{0,date,yyyy-MM-dd HH:mm:ss.SSS}", new BigDecimal("1709199045000.9")));
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "MessageDateOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    source = temp / "message_date.d"
    source.write_text('''import z8.runtime;
import std.stdio : writeln;
import std.conv : to;
void main() {
    wstring[] patterns = ["{0,date}"w, "{0,date,short}"w, "{0,date,medium}"w, "{0,date,long}"w,
        "{0,date,full}"w, "{0,time}"w, "{0,time,short}"w, "{0,time,medium}"w,
        "{0,time,long}"w, "{0,time,full}"w, "{0,date,yyyy-MM-dd HH:mm:ss}"w];
    long[] ticks = [0L, 1709199045000L, 1723050000000L];
    foreach (pattern; patterns) foreach (tick; ticks)
        writeln(z8_string_format(pattern, new Z8Array!Z8Primary([z8_primary_box(tick)])).to!string);
    writeln(z8_string_format("{0,date,yyyy-MM-dd HH:mm:ss.SSS}"w,
        new Z8Array!Z8Primary([z8_primary_box(z8_decimal("1709199045000.9"))])).to!string);
}
''', encoding="utf-8")
    executable = temp / ("message_date.exe" if os.name == "nt" else "message_date")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    differences = [(i, j, d) for i, (j, d) in enumerate(zip(expected, actual)) if j != d]
    assert len(expected) == len(actual) and not differences, differences
print("MessageFormat date and time styles match Java")
