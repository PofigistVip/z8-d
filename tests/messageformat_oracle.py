"""Compare supported MessageFormat number styles with the Java runtime."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java = temp / "MessageFormatOracle.java"
    java.write_text('''import java.math.BigDecimal;
import java.text.MessageFormat;
class MessageFormatOracle {
    public static void main(String[] args) {
        String[] patterns = {"{0}", "{0,number}", "{0,number,integer}", "{0,number,percent}",
                             "{0,number,currency}", "{0,number,#,##0.00}", "{0,number,0.###}"};
        String[] numbers = {"0", "1.2", "-0.0005", "999999.9999", "1.2345", "0.00049", "-1234567.25"};
        for (String pattern : patterns)
            for (String number : numbers)
                System.out.println(MessageFormat.format(pattern, new BigDecimal(number)));
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "MessageFormatOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    source = temp / "messageformat.d"
    source.write_text('''import z8.runtime;
import std.stdio : writeln;
import std.conv : to;
void main() {
    wstring[] patterns = ["{0}"w, "{0,number}"w, "{0,number,integer}"w, "{0,number,percent}"w,
                           "{0,number,currency}"w, "{0,number,#,##0.00}"w, "{0,number,0.###}"w];
    string[] numbers = ["0", "1.2", "-0.0005", "999999.9999", "1.2345", "0.00049", "-1234567.25"];
    foreach (pattern; patterns) foreach (number; numbers) {
        auto values = new Z8Array!Z8Primary([z8_primary_box(z8_decimal(number))]);
        writeln(z8_string_format(pattern, values).to!string);
    }
}
''', encoding="utf-8")
    executable = temp / ("messageformat.exe" if os.name == "nt" else "messageformat")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    differences = [(i, j, d) for i, (j, d) in enumerate(zip(expected, actual)) if j != d]
    assert len(expected) == len(actual) and not differences, differences
print("MessageFormat number styles match Java")
