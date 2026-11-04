"""Compare every single-byte decoding and its re-encoding with Java."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java = temp / "EncodingOracle.java"
    java.write_text('''import java.nio.charset.Charset;
public class EncodingOracle {
    public static void main(String[] args) throws Exception {
        String[] encodings = {"CP866", "KOI8-R", "US-ASCII", "Windows-1250", "Windows-1251", "Windows-1252", "Windows-1253", "Windows-1254", "Windows-1257"};
        for (String name : encodings) {
            Charset cs = Charset.forName(name);
            for (int i = 0; i < 256; i++) {
                String decoded = new String(new byte[]{(byte)i}, cs);
                byte[] encoded = decoded.getBytes(cs);
                System.out.printf("%04X:%02X ", (int)decoded.charAt(0), encoded[0] & 255);
            }
            System.out.println();
        }
        int[][] inputs = {{0xC0,0x80}, {0xE0,0x80,0x80}, {0xED,0xA0,0x80}, {0xF0,0x9F}, {0xE1,0x80,0x41},
                          {0xFE,0xFF,0,65}, {0xFF,0xFE,65,0}, {0xD8,0,0,65}, {0xFF}};
        for (String name : new String[]{"UTF-8", "UTF-16", "UTF-16BE", "UTF-16LE"}) {
            Charset cs = Charset.forName(name);
            for (int[] input : inputs) {
                byte[] bytes = new byte[input.length];
                for (int i = 0; i < input.length; i++) bytes[i] = (byte)input[i];
                for (char c : new String(bytes, cs).toCharArray()) System.out.printf("%04X", (int)c);
                System.out.print(" ");
            }
            for (String text : new String[]{"", new String(new char[]{'A',0xD800,'B'}), "😀"}) {
                System.out.print("|");
                for (byte b : text.getBytes(cs)) System.out.printf("%02X", b & 255);
            }
            System.out.println();
        }
        for (String name : new String[]{"UTF-8", "UTF-16", "UTF-16BE", "UTF-16LE"}) {
            Charset cs = Charset.forName(name);
            int hash = 0;
            for (int i = 0; i < 65536; i++) {
                String text = new String(new byte[]{(byte)(i >> 8), (byte)i}, cs);
                hash = 31 * hash + text.length();
                for (char c : text.toCharArray()) hash = 31 * hash + c;
            }
            System.out.printf("%08X\\n", hash);
        }
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp), "EncodingOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    source = temp / "encoding.d"
    source.write_text('''import z8.runtime;
import std.stdio : writef, writeln;
void main() {
    foreach (id; [1, 2, 3, 8, 9, 10, 11, 12, 13]) {
        foreach (i; 0 .. 256) {
            auto value = z8_encoding_decode([cast(ubyte)i], z8_encoding_by_id(id));
            auto encoded = z8_encoding_encode(value, z8_encoding_by_id(id));
            writef("%04X:%02X ", cast(int)value[0], encoded[0]);
        }
        writeln();
    }
    foreach (id; [4, 5, 6, 7]) {
        ubyte[][] inputs = [[0xC0,0x80], [0xE0,0x80,0x80], [0xED,0xA0,0x80], [0xF0,0x9F], [0xE1,0x80,0x41],
                            [0xFE,0xFF,0,65], [0xFF,0xFE,65,0], [0xD8,0,0,65], [0xFF]];
        foreach (input; inputs) {
            foreach (wchar c; z8_encoding_decode(input, z8_encoding_by_id(id))) writef("%04X", cast(int)c);
            writef(" ");
        }
        wstring[] values = [""w, [cast(wchar)'A', cast(wchar)0xD800, cast(wchar)'B'].idup, "😀"w];
        foreach (value; values) {
            writef("|");
            foreach (b; z8_encoding_encode(value, z8_encoding_by_id(id))) writef("%02X", b);
        }
        writeln();
    }
    foreach (id; [4, 5, 6, 7]) {
        uint hash;
        foreach (i; 0 .. 65536) {
            auto value = z8_encoding_decode([cast(ubyte)(i >> 8), cast(ubyte)i], z8_encoding_by_id(id));
            hash = 31u * hash + cast(uint)value.length;
            foreach (wchar c; value) hash = 31u * hash + c;
        }
        writef("%08X\\n", hash);
    }
}
''', encoding="utf-8")
    executable = temp / ("encoding.exe" if os.name == "nt" else "encoding")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    names = ["CP866", "KOI8-R", "US-ASCII", "Windows-1250", "Windows-1251", "Windows-1252", "Windows-1253", "Windows-1254", "Windows-1257"]
    for name, left, right in zip(names, expected, actual):
        java_values, d_values = left.split(), right.split()
        differences = [(index, j, d) for index, (j, d) in enumerate(zip(java_values, d_values)) if j != d]
        assert not differences, f"{name}: {differences}"
    assert expected[9:] == actual[9:], f"UTF encodings differ: Java={expected[9:]!r}, D={actual[9:]!r}"
print("Single-byte encodings and all two-byte UTF inputs match Java")
