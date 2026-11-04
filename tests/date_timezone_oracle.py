"""Compare Moscow time-zone names and offsets with Java for multiple eras."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java = temp / "DateZoneOracle.java"
    java.write_text('''import java.text.SimpleDateFormat;
import java.util.*;
public class DateZoneOracle {
    public static void main(String[] args) {
        TimeZone.setDefault(TimeZone.getTimeZone("Europe/Moscow"));
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd HH:mm Z z zzzz");
        for (int year : new int[]{2000, 2010, 2012, 2014, 2024})
            for (int month : new int[]{0, 6})
                System.out.println(format.format(new GregorianCalendar(year, month, 15, 12, 0).getTime()));
        int[][] edge = {{2010,3,28,2,30}, {2010,10,31,2,30}, {2011,3,27,2,30},
                        {2014,10,26,1,30}, {1991,9,29,2,30}};
        for (int[] c : edge) {
            Calendar value = new GregorianCalendar(c[0], c[1]-1, c[2], c[3], c[4]);
            System.out.println(format.format(value.getTime()) + " " + value.getTimeInMillis());
        }
        int[][] dayAdd = {{2010,3,27,12,30,1}, {2010,3,27,2,30,1}, {2010,3,29,12,30,-1},
                          {2010,10,30,12,30,1}, {2010,11,1,12,30,-1}, {2014,10,25,12,30,1}};
        for (int[] c : dayAdd) {
            Calendar value = new GregorianCalendar(c[0], c[1]-1, c[2], c[3], c[4]);
            value.add(Calendar.DAY_OF_MONTH, c[5]);
            System.out.println(format.format(value.getTime()) + " " + value.getTimeInMillis());
        }
        int[][] calendarAdd = {{2010,2,28,2,30,1,0}, {2014,9,26,1,30,1,0},
                               {2009,3,28,2,30,1,1}, {2010,3,28,1,30,1,2}};
        for (int[] c : calendarAdd) {
            Calendar value = new GregorianCalendar(c[0], c[1]-1, c[2], c[3], c[4]);
            value.add(c[6] == 0 ? Calendar.MONTH : c[6] == 1 ? Calendar.YEAR : Calendar.HOUR_OF_DAY, c[5]);
            System.out.println(format.format(value.getTime()) + " " + value.getTimeInMillis());
        }
        int hash = 0;
        Calendar calendar = new GregorianCalendar();
        for (long tick = 0; tick < 1609459200000L; tick += 604800000L) {
            calendar.setTimeInMillis(tick);
            String value = format.format(calendar.getTime()) + "|" + calendar.get(Calendar.ZONE_OFFSET);
            for (char ch : value.toCharArray()) hash = 31 * hash + ch;
            hash = 31 * hash + '|';
        }
        System.out.printf("%08X%n", hash);
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "DateZoneOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    source = temp / "date_zone.d"
    source.write_text('''import z8.runtime;
import std.format : format;
import std.stdio : writeln;
import std.conv : to;
void main() {
    foreach (year; [2000, 2010, 2012, 2014, 2024]) foreach (month; [1, 7]) {
        auto date = z8_date_literal(format("15/%02d/%04d 12:00:00", month, year));
        writeln(z8_date_toString(date, "yyyy-MM-dd HH:mm Z z zzzz"w).to!string);
    }
    int[][] edge = [[2010,3,28,2,30], [2010,10,31,2,30], [2011,3,27,2,30],
                    [2014,10,26,1,30], [1991,9,29,2,30]];
    foreach (c; edge) {
        auto date = z8_date_literal(format("%02d/%02d/%04d %02d:%02d:00", c[2], c[1], c[0], c[3], c[4]));
        writeln(z8_date_toString(date, "yyyy-MM-dd HH:mm Z z zzzz"w).to!string, " ", z8_date_ticks(date));
    }
    int[][] dayAdd = [[2010,3,27,12,30,1], [2010,3,27,2,30,1], [2010,3,29,12,30,-1],
                      [2010,10,30,12,30,1], [2010,11,1,12,30,-1], [2014,10,25,12,30,1]];
    foreach (c; dayAdd) {
        auto date = z8_date_literal(format("%02d/%02d/%04d %02d:%02d:00", c[2], c[1], c[0], c[3], c[4]));
        auto added = z8_date_addDay(date, c[5]);
        writeln(z8_date_toString(added, "yyyy-MM-dd HH:mm Z z zzzz"w).to!string, " ", z8_date_ticks(added));
    }
    int[][] calendarAdd = [[2010,2,28,2,30,1,0], [2014,9,26,1,30,1,0],
                           [2009,3,28,2,30,1,1], [2010,3,28,1,30,1,2]];
    foreach (c; calendarAdd) {
        auto date = z8_date_literal(format("%02d/%02d/%04d %02d:%02d:00", c[2], c[1], c[0], c[3], c[4]));
        auto added = c[6] == 0 ? z8_date_addMonth(date, c[5]) : c[6] == 1 ? z8_date_addYear(date, c[5]) : z8_date_addHour(date, c[5]);
        writeln(z8_date_toString(added, "yyyy-MM-dd HH:mm Z z zzzz"w).to!string, " ", z8_date_ticks(added));
    }
    uint hash;
    for (long tick = 0; tick < 1609459200000L; tick += 604800000L) {
        auto date = z8_date_from_ticks(tick);
        auto value = z8_date_toString(date, "yyyy-MM-dd HH:mm Z z zzzz"w) ~ "|"w ~ z8_date_zoneOffset(date).to!wstring;
        foreach (wchar c; value) hash = 31u * hash + c;
        hash = 31u * hash + '|';
    }
    writeln(format("%08X", hash));
}
''', encoding="utf-8")
    executable = temp / ("date_zone.exe" if os.name == "nt" else "date_zone")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    differences = [(i, j, d) for i, (j, d) in enumerate(zip(expected, actual)) if j != d]
    assert len(expected) == len(actual) and not differences, differences
print("Moscow time-zone names and offsets match Java")
