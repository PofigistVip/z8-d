"""Compare Eval with current expression and scalar sources plus the older server JAR.

The BIRT exception stub is only needed to compile an unused error path.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/eval_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang/src/bl"
server = original / "org.zenframework.z8.server"
sources = server / "src/main/java"
jar = server / "target/libs/org.zenframework.z8.server-1.3.0.jar"
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
antlr = list((cache / "org.antlr/antlr4-runtime").rglob("*.jar"))
if not language.is_dir() or not jar.is_file() or not antlr:
    raise SystemExit("Original BL library, server JAR or ANTLR 4 runtime not found")
jars = [jar, antlr[0]]
for dependency in (cache / "commons-logging/commons-logging", cache / "org.zenframework.z8.dependencies.commons",
                   cache / "commons-io/commons-io/2.7"):
    if dependency.exists():
        jars.extend(p for p in dependency.rglob("*.jar") if not p.name.endswith("-sources.jar"))
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    stub = temp / "IllegalOperationException.java"
    stub.write_text('package org.eclipse.birt.report.model.api; public class IllegalOperationException extends RuntimeException { public IllegalOperationException(String s) { super(s); } }', encoding="utf-8")
    java = temp / "EvalOracle.java"
    java.write_text('''
import org.zenframework.z8.server.base.eval.Eval;
import org.zenframework.z8.server.types.*;
public class EvalOracle {
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        Eval eval = new Eval(null);
        eval.z8_setVariable(new string("name"), new string("Ada"));
        eval.z8_setVariable(new string("count"), new integer(7));
        eval.z8_setVariable(new string("flag"), bool.True);
        eval.z8_setVariable(new string("nil"), (primary)null);
        String[] patterns = {"plain text", "${name}", "Hello ${name}!", "${count}", "Count ${count}", "${true}", "${missing}", "before ${missing} after", "${'literal'}", "${count + 2}", "twice ${count * 2}", "${'Hi ' + name}", "${missing + 2}", "${(missing)}", "result ${true && false}!", "${1.5 + 2}", "${2 * 1.25}", "${7.0 / 2}", "decimal=${1.25}", "large=${1234.5}", "negative=${0.0 - 0.001}", "${flag ? name : missing}", "${false ? missing : 'fallback'}", "${nil ?: name}", "${name ?: missing}", "${unknown ?: 'default'}", "${unknown ? 'yes' : 'no'}", "${count ? name : missing}"};
        for (String pattern : patterns) System.out.println(eval.z8_evaluateText(new string(pattern)).get());
        for (String expression : new String[]{"flag", "true", "false", "count > 5", "count + 2 == 9", "count + 2 == 9 && flag", "!(count < 3)", "'abc' + name == 'abcAda'", "-count + 10 == 3", "true || false && false", "1.5 + 2 == 3.5", "1 < 1.0", "1 <= 1.0", "1.0 == 1", "2 * 1.25 == 2.50", "nil ? false : true", "true ? true : missing"}) {
            try { System.out.println(eval.z8_evaluateBoolean(new string(expression)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        System.out.println(eval.z8_getContextInfo().get());
        System.out.println("errors=" + eval.z8_getErrors().size());
        eval.z8_clear(); System.out.println("clear=" + eval.z8_getErrors().size());
    }
}
''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [temp, *jars]))
    java_sources = [*sorted((sources / "org/zenframework/z8/server/expression").rglob("*.java")),
                    *(sources / "org/zenframework/z8/server/types" / (name + ".java") for name in ("decimal", "integer", "bool", "string", "date")),
                    sources / "org/zenframework/z8/server/base/eval/Eval.java", stub, java]
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, "-sourcepath", str(temp),
                    "-d", str(temp), *map(str, java_sources)], cwd=temp, check=True)
    config = temp / "server.properties"
    config.write_text("application.language=en\n", encoding="utf-8")
    expected = subprocess.check_output(["java", "-cp", classpath, "EvalOracle", str(config)],
                                       cwd=temp, text=True, encoding="utf-8").splitlines()
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "EvalProbe.bl").write_text('''
import org.zenframework.z8.base.eval.Eval;
public class EvalProbe {
    public static Eval make() { Eval e; e.setVariable("name", "Ada"); e.setVariable("count", 7); e.setVariable("flag", true); primary nil = null; e.setVariable("nil", nil); return e; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime; import z8gen.p_EvalProbe; import std.stdio : writeln; import std.conv : to;
void main() {
    auto eval = Z8p_4576616C50726F6265.m_make();
    foreach (pattern; ["plain text"w, "${name}"w, "Hello ${name}!"w, "${count}"w, "Count ${count}"w,
                       "${true}"w, "${missing}"w, "before ${missing} after"w, "${'literal'}"w,
                       "${count + 2}"w, "twice ${count * 2}"w, "${'Hi ' + name}"w, "${missing + 2}"w, "${(missing)}"w,
                       "result ${true && false}!"w, "${1.5 + 2}"w, "${2 * 1.25}"w, "${7.0 / 2}"w,
                       "decimal=${1.25}"w, "large=${1234.5}"w, "negative=${0.0 - 0.001}"w,
                       "${flag ? name : missing}"w, "${false ? missing : 'fallback'}"w, "${nil ?: name}"w,
                       "${name ?: missing}"w, "${unknown ?: 'default'}"w, "${unknown ? 'yes' : 'no'}"w, "${count ? name : missing}"w])
        writeln(eval.m_evaluateText(pattern).to!string);
    foreach (expression; ["flag"w, "true"w, "false"w, "count > 5"w, "count + 2 == 9"w, "count + 2 == 9 && flag"w,
                          "!(count < 3)"w, "'abc' + name == 'abcAda'"w, "-count + 10 == 3"w, "true || false && false"w,
                          "1.5 + 2 == 3.5"w, "1 < 1.0"w, "1 <= 1.0"w, "1.0 == 1"w, "2 * 1.25 == 2.50"w,
                          "nil ? false : true"w, "true ? true : missing"w])
        try { writeln(z8_optional_require(eval.m_evaluateBoolean(expression))); } catch (Exception) { writeln("error"); }
    writeln(eval.m_getContextInfo().to!string);
    writeln("errors=", eval.m_getErrors().z8_size()); eval.m_clear(); writeln("clear=", eval.m_getErrors().z8_size());
}
''', encoding="utf-8")
    executable = temp / ("eval-oracle.exe" if os.name == "nt" else "eval-oracle")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert expected == actual, (expected, actual)
print("Eval variables and text match the current original Z8 sources")
