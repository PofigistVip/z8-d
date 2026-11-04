"""Compare Z8 calendar fields before and around the 1582 cutover with Java."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java = temp / "EarlyCalendarOracle.java"
    java.write_text('''import java.text.SimpleDateFormat;
import java.util.*;
public class EarlyCalendarOracle {
    public static void main(String[] args) {
        TimeZone.setDefault(TimeZone.getTimeZone("Europe/Moscow"));
        int[][] dates = {{1,1,1}, {100,2,28}, {400,2,29}, {1500,2,29},
                         {1582,10,4}, {1582,10,15}, {1600,2,29}};
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss EEEE D");
        for (int[] d : dates) {
            Calendar c = new GregorianCalendar(d[0],d[1]-1,d[2],12,0,0);
            System.out.println(c.get(Calendar.YEAR)+" "+(c.get(Calendar.MONTH)+1)+" "+c.get(Calendar.DAY_OF_MONTH)+" "+
                c.get(Calendar.DAY_OF_YEAR)+" "+c.get(Calendar.DAY_OF_WEEK)+" "+c.getActualMaximum(Calendar.DAY_OF_MONTH)+" "+
                c.getTimeInMillis()+" "+f.format(c.getTime()));
        }
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "EarlyCalendarOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    source = temp / "early_calendar.d"
    source.write_text('''import z8.runtime;
import std.format : format;
import std.stdio : writeln;
import std.conv : to;
void main() {
    int[][] dates = [[1,1,1], [100,2,28], [400,2,29], [1500,2,29],
                     [1582,10,4], [1582,10,15], [1600,2,29]];
    foreach (d; dates) {
        auto date = z8_date_literal(format("%02d/%02d/%04d 12:00:00", d[2],d[1],d[0]));
        writeln(z8_date_year(date)," ",z8_date_month(date)," ",z8_date_day(date)," ",
            z8_date_dayOfYear(date)," ",z8_date_dayOfWeek(date)," ",z8_date_daysInMonth(date)," ",
            z8_date_ticks(date)," ",z8_date_toString(date,"yyyy-MM-dd HH:mm:ss EEEE D"w).to!string);
    }
}
''', encoding="utf-8")
    executable = temp / ("early_calendar.exe" if os.name == "nt" else "early_calendar")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    differences = [(i, j, d) for i, (j, d) in enumerate(zip(expected, actual)) if j != d]
    assert len(expected) == len(actual) and not differences, differences
print("Early calendar fields match Java GregorianCalendar")
