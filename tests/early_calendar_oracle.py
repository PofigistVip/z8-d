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
        int[][] operations = {{1500,2,29,1,0}, {1500,2,29,-1,0}, {1500,1,31,1,1},
            {1582,9,10,1,1}, {1582,11,10,-1,1}, {1582,10,4,1,2}, {1582,10,15,-1,2},
            {1500,2,29,1,2}};
        for (int[] d : operations) {
            Calendar c = new GregorianCalendar(d[0],d[1]-1,d[2],12,0,0);
            c.add(d[4]==0 ? Calendar.YEAR : d[4]==1 ? Calendar.MONTH : Calendar.DAY_OF_MONTH, d[3]);
            System.out.println(f.format(c.getTime()) + " " + c.getTimeInMillis());
        }
        for (int[] d : new int[][]{{1500,2,29}, {1582,10,15}}) for (int mode=0; mode<3; mode++) {
            Calendar c = new GregorianCalendar(d[0], mode==0 ? 0 : d[1]-1, mode==2 ? d[2] : 1);
            System.out.println(f.format(c.getTime()) + " " + c.getTimeInMillis());
        }
        SimpleDateFormat weeks = new SimpleDateFormat("YYYY-ww W F u");
        for (int[] d : new int[][]{{1,1,1},{1,12,31},{1500,2,29},{1582,10,4},{1582,10,15},
                                    {1582,10,20},{1582,12,31},{1583,1,1},{1600,2,29}}) {
            Calendar c = new GregorianCalendar(d[0],d[1]-1,d[2],12,0,0);
            String formatted = weeks.format(c.getTime());
            c.setFirstDayOfWeek(Calendar.MONDAY); c.setMinimalDaysInFirstWeek(7);
            System.out.println(formatted + " " + c.get(Calendar.WEEK_OF_YEAR));
        }
        SimpleDateFormat allFields = new SimpleDateFormat("yyyy-MM-dd D EEEE YYYY-ww W F u");
        int hash = 0;
        for (int year : new int[]{1,4,100,400,1400,1499,1500,1581,1582,1583,1600}) {
            Calendar c = new GregorianCalendar(year,0,1,12,0,0);
            c.setFirstDayOfWeek(Calendar.MONDAY); c.setMinimalDaysInFirstWeek(7);
            while (c.get(Calendar.YEAR) == year) {
                String item = allFields.format(c.getTime()) + " " + c.get(Calendar.WEEK_OF_YEAR);
                for (char ch : item.toCharArray()) hash = 31 * hash + ch;
                hash = 31 * hash + '|';
                c.add(Calendar.DAY_OF_MONTH, 1);
            }
        }
        System.out.printf("%08X%n", hash);
        for (String pattern : new String[]{"yyyy-MM-dd", "YYYY-ww-u", "yyyy-MM-W-u", "yyyy-MM-F-u"})
            for (int[] d : new int[][]{{1500,2,29}, {1582,10,4}, {1582,10,15}, {1582,10,20}, {1582,12,31}}) {
                try {
                    SimpleDateFormat parser = new SimpleDateFormat(pattern);
                    Date parsed = parser.parse(parser.format(new GregorianCalendar(d[0],d[1]-1,d[2]).getTime()));
                    System.out.println(f.format(parsed) + " " + parsed.getTime());
                } catch (Exception e) { throw new RuntimeException(e); }
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
    int[][] operations = [[1500,2,29,1,0], [1500,2,29,-1,0], [1500,1,31,1,1],
        [1582,9,10,1,1], [1582,11,10,-1,1], [1582,10,4,1,2], [1582,10,15,-1,2],
        [1500,2,29,1,2]];
    foreach (d; operations) {
        auto date = z8_date_literal(format("%02d/%02d/%04d 12:00:00", d[2],d[1],d[0]));
        auto next = d[4] == 0 ? z8_date_addYear(date,d[3]) : d[4] == 1 ? z8_date_addMonth(date,d[3]) : z8_date_addDay(date,d[3]);
        writeln(z8_date_toString(next,"yyyy-MM-dd HH:mm:ss EEEE D"w).to!string," ",z8_date_ticks(next));
    }
    foreach (d; [[1500,2,29], [1582,10,15]]) foreach (mode; 0 .. 3) {
        auto date = z8_date_literal(format("%02d/%02d/%04d 12:00:00", d[2],d[1],d[0]));
        auto truncated = mode == 0 ? z8_date_truncYear(date) : mode == 1 ? z8_date_truncMonth(date) : z8_date_truncDay(date);
        writeln(z8_date_toString(truncated,"yyyy-MM-dd HH:mm:ss EEEE D"w).to!string," ",z8_date_ticks(truncated));
    }
    foreach (d; [[1,1,1],[1,12,31],[1500,2,29],[1582,10,4],[1582,10,15],
                 [1582,10,20],[1582,12,31],[1583,1,1],[1600,2,29]]) {
        auto date = z8_date_literal(format("%02d/%02d/%04d 12:00:00", d[2],d[1],d[0]));
        writeln(z8_date_toString(date,"YYYY-ww W F u"w).to!string," ",z8_date_weekOfYear(date));
    }
    uint hash;
    foreach (year; [1,4,100,400,1400,1499,1500,1581,1582,1583,1600]) {
        auto date = z8_date_literal(format("01/01/%04d 12:00:00", year));
        while (z8_date_year(date) == year) {
            auto item = z8_date_toString(date,"yyyy-MM-dd D EEEE YYYY-ww W F u"w) ~ " "w ~ z8_date_weekOfYear(date).to!wstring;
            foreach (wchar c; item) hash = 31u * hash + c;
            hash = 31u * hash + '|';
            date = z8_date_addDay(date, 1);
        }
    }
    writeln(format("%08X", hash));
    foreach (pattern; ["yyyy-MM-dd"w, "YYYY-ww-u"w, "yyyy-MM-W-u"w, "yyyy-MM-F-u"w])
        foreach (d; [[1500,2,29], [1582,10,4], [1582,10,15], [1582,10,20], [1582,12,31]]) {
            auto date = z8_date_literal(format("%02d/%02d/%04d 00:00:00", d[2],d[1],d[0]));
            auto parsed = z8_date_parse(z8_date_toString(date,pattern),pattern);
            writeln(z8_date_toString(parsed,"yyyy-MM-dd HH:mm:ss EEEE D"w).to!string," ",z8_date_ticks(parsed));
        }
}
''', encoding="utf-8")
    executable = temp / ("early_calendar.exe" if os.name == "nt" else "early_calendar")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    differences = [(i, j, d) for i, (j, d) in enumerate(zip(expected, actual)) if j != d]
    assert len(expected) == len(actual) and not differences, differences
print("Early calendar fields match Java GregorianCalendar")
