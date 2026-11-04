"""Check numeric calendar formats across year and month boundaries against Java."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java = temp / "DateFormatOracle.java"
    java.write_text('''import java.text.SimpleDateFormat;
import java.util.*;
public class DateFormatOracle {
    public static void main(String[] args) {
        TimeZone.setDefault(TimeZone.getTimeZone("Europe/Moscow"));
        SimpleDateFormat format = new SimpleDateFormat("YYYY-ww W F u k K h D");
        int hash = 0;
        for (int year = 2015; year <= 2035; year++)
            for (int month = 0; month < 12; month++) {
                Calendar c = new GregorianCalendar(year, month, 1, 12, 30, 45);
                int days = c.getActualMaximum(Calendar.DAY_OF_MONTH);
                for (int day = 1; day <= days; day++) {
                    c.set(Calendar.DAY_OF_MONTH, day);
                    String value = format.format(c.getTime());
                    for (char ch : value.toCharArray()) hash = 31 * hash + ch;
                    hash = 31 * hash + '|';
                }
            }
        System.out.printf("%08X\\n", hash);
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp), "DateFormatOracle"], cwd=temp, text=True).strip()
    source = temp / "date_format.d"
    source.write_text('''import z8.runtime;
import std.format : format;
import std.stdio : writefln;
void main() {
    uint hash;
    foreach (year; 2015 .. 2036) foreach (month; 1 .. 13) {
        auto first = z8_date_literal(format("01/%02d/%04d 12:30:45", month, year));
        foreach (day; 1 .. cast(int)z8_date_daysInMonth(first) + 1) {
            auto date = z8_date_literal(format("%02d/%02d/%04d 12:30:45", day, month, year));
            auto value = z8_date_toString(date, "YYYY-ww W F u k K h D"w);
            foreach (wchar c; value) hash = 31u * hash + c;
            hash = 31u * hash + '|';
        }
    }
    writefln("%08X", hash);
}
''', encoding="utf-8")
    executable = temp / ("date_format.exe" if os.name == "nt" else "date_format")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True).strip()
    assert expected == actual, f"Java={expected}, D={actual}"
print("Numeric calendar formats match Java across 21 years")
