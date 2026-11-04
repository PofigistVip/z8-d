"""Compare UTF-16 string operations with java.lang.String."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
exe = root / ("z8d.exe" if os.name == "nt" else "z8d")
generated = subprocess.run([str(exe), "compile", str(root / "examples" / "math.bl")],
                           capture_output=True, text=True, encoding="utf-8", check=True).stdout
d_main = r'''
import std.stdio : writeln;
void main() {
    auto s = [cast(wchar)0x61, cast(wchar)0xD83D, cast(wchar)0xDE00, cast(wchar)0x62, cast(wchar)0xD83D, cast(wchar)0xDE00].idup;
    auto emoji = [cast(wchar)0xD83D, cast(wchar)0xDE00].idup;
    writeln(s.length);
    writeln(z8_str_indexOf(s, emoji, 2));
    writeln(z8_str_indexOf(s, ""w, 99));
    writeln(z8_str_indexOf(s, emoji, -8));
    writeln(z8_str_lastIndexOf(s, emoji, 3));
    writeln(z8_str_lastIndexOf(s, ""w, -1));
    writeln(z8_str_startsWith(s, emoji, 1));
    writeln(z8_str_startsWith(s, emoji, 4294967297L));
    writeln(z8_str_endsWith(s, emoji));
    writeln(z8_str_substring(s, 1, 2) == emoji);
    writeln(z8_str_substring(s, 4, 100).length);
    writeln(z8_str_charAt(s, 1).length);
    writeln(z8_str_compare("a"w, "abc"w));
    writeln(z8_str_compare("b"w, "a"w));
    writeln(z8_str_trim(" \tword\u00A0 "w) == "word\u00A0"w);
    writeln(z8_str_left("abc"w, 2) == "ab"w);
    writeln(z8_str_right("abc"w, 2) == "bc"w);
    writeln(z8_str_insert(s, 1, "X"w) == "aX"w ~ emoji ~ "b"w ~ emoji);
    writeln(z8_str_replace(s, 1, 2, "X"w) == "aXb"w ~ emoji);
    writeln(z8_str_replace("abcd"w, 2, -1, "X"w) == "abXbcd"w);
    writeln(z8_str_padLeft("ab"w, 7, "xy"w) == "xyxyxab"w);
    writeln(z8_str_padRight("ab"w, 5, ""w) == "ab   "w);
    writeln(z8_str_padLeft("abc"w, 4294967295L) == "abc"w);
    bool invalidReplace; try { z8_str_replace(s, 1, 100, ""w); } catch (Exception) { invalidReplace = true; }
    writeln(invalidReplace);
    writeln(z8_int_parse("-8000000000000000"w, 16));
    writeln(z8_int_parse("7FL"w, 16));
    foreach (n; [long.min, -256L, -1L, 0L, 1L, 255L, long.max]) {
        foreach (radix; [-1L, 2L, 8L, 10L, 16L, 36L, 37L, 4294967312L])
            writeln(z8_int_toString(n, radix));
        writeln(z8_int_toHexString(n));
        writeln(z8_int_toBinaryString(n));
        foreach (shift; [-65L, -1L, 0L, 1L, 63L, 64L, 65L]) {
            writeln(z8_int_leftShift(n, shift));
            writeln(z8_int_rightShift(n, shift));
        }
    }
    bool failed; try { z8_str_substring(s, -1, 1); } catch (Exception) { failed = true; }
    writeln(failed);
}
'''
java_main = r'''
public class StringOracle {
    public static void main(String[] args) {
        String s = "a\uD83D\uDE00b\uD83D\uDE00", emoji = "\uD83D\uDE00";
        System.out.println(s.length());
        System.out.println(s.indexOf(emoji, 2));
        System.out.println(s.indexOf("", 99));
        System.out.println(s.indexOf(emoji, -8));
        System.out.println(s.lastIndexOf(emoji, 3));
        System.out.println(s.lastIndexOf("", -1));
        System.out.println(s.startsWith(emoji, 1));
        System.out.println(s.startsWith(emoji, (int)4294967297L));
        System.out.println(s.endsWith(emoji));
        System.out.println(s.substring(1, 1 + 2).equals(emoji));
        System.out.println(s.substring(4, Math.min(s.length(), 4 + 100)).length());
        System.out.println(String.valueOf(s.charAt(1)).length());
        System.out.println("a".compareTo("abc"));
        System.out.println("b".compareTo("a"));
        System.out.println(" \tword\u00A0 ".trim().equals("word\u00A0"));
        System.out.println("abc".substring(0, 2).equals("ab"));
        System.out.println("abc".substring(1).equals("bc"));
        System.out.println((s.substring(0, 1) + "X" + s.substring(1)).equals("aX" + emoji + "b" + emoji));
        System.out.println((s.substring(0, 1) + "X" + s.substring(3)).equals("aXb" + emoji));
        System.out.println(("abcd".substring(0, 2) + "X" + "abcd".substring(1)).equals("abXbcd"));
        System.out.println("xyxyxab".equals("xyxyx" + "ab"));
        System.out.println("ab   ".equals("ab" + "   "));
        System.out.println((int)4294967295L <= "abc".length());
        boolean invalidReplace = false; try { s.substring(101); } catch (Exception e) { invalidReplace = true; }
        System.out.println(invalidReplace);
        System.out.println(Long.parseLong("-8000000000000000", 16));
        System.out.println(Long.parseLong("7F", 16));
        for (long n : new long[] { Long.MIN_VALUE, -256L, -1L, 0L, 1L, 255L, Long.MAX_VALUE }) {
            for (long radix : new long[] { -1L, 2L, 8L, 10L, 16L, 36L, 37L, 4294967312L })
                System.out.println(Long.toString(n, (int)radix));
            System.out.println(Long.toHexString(n));
            System.out.println(Long.toBinaryString(n));
            for (long shift : new long[] { -65L, -1L, 0L, 1L, 63L, 64L, 65L }) {
                System.out.println(n << shift);
                System.out.println(n >> shift);
            }
        }
        boolean failed = false; try { s.substring(-1, 0); } catch (Exception e) { failed = true; }
        System.out.println(failed);
    }
}
'''
with tempfile.TemporaryDirectory() as temporary, runtime_library() as runtime_lib:
    directory = Path(temporary)
    dfile, jfile = directory / "string_check.d", directory / "StringOracle.java"
    binary = directory / ("string_check.exe" if os.name == "nt" else "string_check")
    dfile.write_text(generated + d_main, encoding="utf-8")
    jfile.write_text(java_main, encoding="utf-8")
    subprocess.run(["dmd", str(dfile), *import_args(), str(runtime_lib), "-of=" + str(binary)], cwd=directory, check=True)
    subprocess.run(["javac", "-source", "8", "-target", "8", str(jfile)], cwd=directory, check=True)
    actual = subprocess.check_output([str(binary)], cwd=directory, text=True, encoding="utf-8")
    expected = subprocess.check_output(["java", "-cp", str(directory), "StringOracle"], cwd=directory, text=True, encoding="utf-8")
    assert actual == expected, f"D:\n{actual}\nJava:\n{expected}"
print("String results match Java UTF-16 reference")
