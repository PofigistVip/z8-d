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
        Eval jsonEval = new Eval(null);
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> obj = new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>();
        org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<org.zenframework.z8.server.base.json.parser.JsonArray> arr = new org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<>();
        obj.get().operatorAssign(new string("{\\\"count\\\":7,\\\"child\\\":{\\\"title\\\":\\\"Ada\\\"},\\\"items\\\":[3,\\\"tail\\\"],\\\"price\\\":1.25,\\\"yes\\\":true}"));
        arr.get().operatorAssign(new string("[3,\\\"tail\\\"]"));
        jsonEval.z8_setVariable(new string("obj"), obj);
        jsonEval.z8_setVariable(new string("arr"), arr);
        jsonEval.z8_setVariable(new string("nil"), (primary)null);
        obj.get().get().put("after", 42);
        obj.get().operatorAssign(new string("{}"));
        arr.get().operatorAssign(new string("[]"));
        for (String pattern : new String[]{"${obj.count}", "name=${obj.child.title}", "${obj.missing}", "${obj['count']}", "${arr[0]}", "${arr[1]}", "${obj.items[1]}", "${missing.field}", "${arr[0] + obj.count}", "${obj.missing ?: 'fallback'}", "${false ? obj.items[99] : 'safe'}", "${obj.price + 1}", "${obj.yes}", "${arr[0.6]}", "${arr[99]}", "${obj.after}", "${arr[missing]}", "${missing[0]}", "${nil[0]}", "${arr[nil]}", "${obj[0]}", "${arr['bad']}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        System.out.println("json-errors=" + jsonEval.z8_getErrors().size());
        System.out.println(jsonEval.z8_getErrors().get(jsonEval.z8_getErrors().size() - 2));
        System.out.println(jsonEval.z8_getErrors().get(jsonEval.z8_getErrors().size() - 1));
        org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<org.zenframework.z8.server.base.json.parser.JsonArray> rows = new org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<>();
        rows.get().operatorAssign(new string("[{\\\"n\\\":7},{\\\"n\\\":2},{\\\"n\\\":5}]"));
        jsonEval.z8_setVariable(new string("rows"), rows);
        org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<org.zenframework.z8.server.base.json.parser.JsonArray> decimals = new org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<>();
        decimals.get().operatorAssign(new string("[{\\\"n\\\":1.75},{\\\"n\\\":1.25},{\\\"n\\\":3}]"));
        jsonEval.z8_setVariable(new string("decimals"), decimals);
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> dictionary = new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>();
        dictionary.get().operatorAssign(new string("{\\\"a\\\":{\\\"n\\\":7},\\\"b\\\":{\\\"n\\\":2}}"));
        jsonEval.z8_setVariable(new string("dictionary"), dictionary);
        jsonEval.z8_setVariable(new string("day"), new date(2024, 2, 29));
        jsonEval.z8_setVariable(new string("span"), datespan.z8_parse(new string("1 02:03:04")));
        for (String pattern : new String[]{"${json.min(rows, 'n')}", "${json.max(rows, 'n')}", "${json.min(rows, 'missing')}", "${json.max(rows, 'missing')}", "${json.min(nil, 'n')}", "${json.min(decimals, 'n')}", "${json.max(decimals, 'n')}", "${json.min(dictionary, 'n')}", "${json.max(dictionary, 'n')}", "${json.min(rows, nil)}", "${false ? json.min(rows, 'n') : 42}", "${json.min(rows)}", "${json.unknown(rows, 'n')}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${format(42, 'unused')}", "${format('text', 'unused')}", "${format(nil, 'unused')}", "${format(1.25, '%.1f')}", "${format(1234.5, '% ,.2f')}", "${format(1.25, '%+08.2f')}", "${format(1.25, '%-8.2f')}", "${format(1.25, 'value=%.2f%%')}", "${format(1.25, nil)}", "${format(0.0 - 1.25, '%(08.2f')}", "${format(1.25, '%#.0f')}", "${format(1.25, '%.2f %<.1f')}", "${format(1.25, 'literal')}", "${format(day, 'yyyy-MM-dd')}", "${format(day, nil)}", "${format(missing, 'x')}", "${false ? format(1.25) : 'safe'}", "${format(1.25)}", "${unknown(1)}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${'  Ada  '.trim().toUpperCase()}", "${'abc'.length()}", "${''.isEmpty()}", "${'abc'.substring(1, 2)}", "${'abc'.startsWith('b', 1)}", "${'abc'.endsWith('bc')}", "${'abcabc'.indexOf('bc', 2)}", "${'abcabc'.lastIndexOf('bc')}", "${'Hello'.compareNoCase('hello')}", "${'abc'.replace(1, 1, 'X')}", "${'a'.padLeft(3, 'xy')}", "${'Hello'.firstToLowerCase()}", "${'abc'.charAt(1)}", "${'abc'.insert(1, 'XY')}", "${'abc'.matches('a.*')}", "${'banana'.replaceAll('a', 'X')}", "${'abc'.hashCode()}", "${(123).hashCode()}", "${(1.25).hashCode()}", "${true.hashCode()}", "${true.toString()}", "${guid.parse('00000000-0000-0000-0000-000000000001').toString()}", "${'abc'.substring(missing)}", "${missing.length()}", "${'abc'.substring(99)}", "${'abc'.substring('1')}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${true.get()}", "${true.toNumber()}", "${false.toNumber()}", "${guid.create(42).get().toString()}", "${guid.create(42).major()}", "${guid.create(42).minor()}", "${(4294967297).getInt()}", "${(42).decimal().scale()}", "${(0).date().ticks()}", "${decimal.parse('1.2300').scale()}", "${decimal.parse('1.2300').precision()}", "${(1.25).isNaN()}", "${(1.25).getDouble()}", "${(0.0 - 1.0).sqrt().get()}", "${(0.0 - 1.0).sqrt().getDouble().isNaN()}", "${(0.0 - 1.0).sqrt().precision()}", "${(2.5).power(3)}", "${(2.5).power(-2)}", "${(2).power(3)}", "${span.get()}", "${day.get().setDate(2023, 12, 31)}", "${day.year()}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${guid.create(42).components()}", "${guid.create(42).components()[1]}", "${guid.create(42).components()[4294967297]}", "${guid.create(42).components()[nil]}", "${'a,b'.split(',')[1]}", "${'a,b'.split(',').get(1)}", "${'a,b'.split(',').first()}", "${'a,b'.split(',').last()}", "${'a,b'.split(',').size()}", "${'a,b'.split(',').isEmpty()}", "${'a,b'.split(',').hashCode()}", "${'a,b'.split(',').join('-')}", "${'a,,'.split(',', -1).size()}", "${'a,b'.split(',') ?: 'empty'}", "${'x' + 'a,b'.split(',')}", "${'a,b'.split(',') ? 'yes' : 'no'}", "${json.min('a,b'.split(','), 'x')}", "${json.max('a,b'.split(','), 'x')}", "${format('a,b'.split(','), 'x')}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${'b,a,b'.split(',').reverse().join('-')}", "${'b,a,b'.split(',').sort().join('-')}", "${'b,a,b'.split(',').unique().join('-')}", "${'a,b'.split(',').removeAt(0)}", "${'b,a,b'.split(',').removeAll('b'.split(',')).join('-')}", "${'b,a,b'.split(',').remove('b'.split(','))}", "${'a,b'.split(',').clear()}", "${guid.create(42).components().reverse()[0]}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        jsonEval.z8_setVariable(new string("slashPath"), new string("folder" + (char)92 + "Report.XLSX"));
        for (String pattern : new String[]{"${'folder/Report.XLSX'.file().fileName()}", "${'folder/Report.XLSX'.file().baseName()}", "${'folder/Report.XLSX'.file().extension()}", "${'folder/Report.XLSX'.file().folder()}", "${'folder/Report.XLSX'.file().string()}", "${'folder/Report.XLSX'.file().getPath()}", "${slashPath.file().getPath()}", "${slashPath.file().string()}", "${'folder/Report.XLSX'.file().parent().fileName()}", "${'missing-file-uuid-72e8'.file().exists()}", "${'missing-file-uuid-72e8'.file().isEmpty()}", "${'missing-file-uuid-72e8'.file().isFolder()}", "${'missing-file-uuid-72e8'.file().lastModified().ticks()}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${'Привет'.binary().length()}", "${'abc'.binary().getName()}", "${'abc'.binary().setName('folder/Report.TXT').getName()}", "${'abc'.binary().setName('folder/Report.TXT').name}", "${'abc'.binary().setName('folder/Report.TXT').getBaseName()}", "${'abc'.binary().setName('folder/Report.TXT').getExtension()}", "${'abc'.binary().setName('name').toString()}", "${'folder/Report.XLSX'.file().name}", "${slashPath.file().path}", "${'file'.file().size}", "${'file'.file().id}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${1.25.abs()}", "${(-7).abs()}", "${(-7).signum()}", "${(5).not()}", "${(5).and(3)}", "${(5).xor(3)}", "${(8).rightShift(2)}", "${(255).toHexString()}", "${(255).toString(16)}", "${(9).sqrt()}", "${(2).sqrt()}", "${(1).sin()}", "${(2).power(3.0)}", "${(1.25).round(1)}", "${(1.25).round(1, 1)}", "${(1.25).round(1, 7)}", "${(1.5).round()}", "${(0.0 - 1.5).round()}", "${(1.25).abs()}", "${(0.1).abs()}", "${(1.25).ceil()}", "${(1.25).floor()}", "${(5).and('x')}", "${(1.25).round(missing)}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${int.parse('42')}", "${int.parse('ff', 16)}", "${decimal.parse('1.25')}", "${bool.parse('yes')}", "${bool.parse(nil)}", "${string.replicate('ab', 3)}", "${guid.parse('00000000-0000-0000-0000-000000000001')}", "${guid.create(42)}", "${guid.create('abc')}", "${format(date.parse('29/02/2024'), 'yyyy-MM-dd')}", "${format(date.parse('2024-02-29', 'yyyy-MM-dd'), 'dd.MM.yyyy')}", "${int.Min}", "${int.parse(missing)}", "${int.parse('x')}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${day.year()}", "${day.month()}", "${day.day()}", "${day.daysInMonth()}", "${day.dayOfWeek()}", "${day.weekOfYear()}", "${day.toString('yyyy-MM-dd')}", "${day.addDay(1).toString('yyyy-MM-dd')}", "${day.addMonth(1).toString('yyyy-MM-dd')}", "${day.truncMonth().toString('yyyy-MM-dd')}", "${day.truncWeek().toString('yyyy-MM-dd')}", "${datespan.parse('1 02:03:04').days()}", "${datespan.parse('1 02:03:04').hours()}", "${datespan.parse('1 02:03:04').totalMinutes()}", "${day.addDay('x')}", "${day.addDay(missing)}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        for (String pattern : new String[]{"${span.setTotalHours(50)}", "${span.days()}", "${span.hours()}", "${span.truncDay()}", "${span.totalHours()}", "${day.setDate(2023, 12, 31)}", "${day.year()}", "${day.month()}"})
            System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get());
        for (String pattern : new String[]{"${'' == nil}", "${'a' > nil}", "${'x' + nil}", "${true == nil}", "${true != nil}", "${1 == nil}", "${1 != nil}", "${1.0 == nil}", "${1.0 != nil}", "${nil == nil}", "${'x' + arr}"}) {
            try { System.out.println(jsonEval.z8_evaluateText(new string(pattern)).get()); }
            catch (Exception error) { System.out.println("error"); }
        }
        jsonEval.z8_setVariable(new string("int"), new integer(10));
        System.out.println(jsonEval.z8_evaluateText(new string("${int}")).get());
        try { System.out.println(jsonEval.z8_evaluateText(new string("${int.parse('42')}")).get()); }
        catch (Exception error) { System.out.println("error"); }
        jsonEval.z8_clear();
        System.out.println(jsonEval.z8_evaluateText(new string("${int.parse('42')}")).get());
    }
}
''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [temp, *jars]))
    java_sources = [*sorted((sources / "org/zenframework/z8/server/expression").rglob("*.java")),
                    *sorted((sources / "org/zenframework/z8/server/json/parser").glob("*.java")),
                    *(sources / "org/zenframework/z8/server/types" / (name + ".java") for name in ("decimal", "integer", "bool", "string", "date", "file", "binary")),
                    *(sources / "org/zenframework/z8/server/base/json/parser" / (name + ".java") for name in ("JsonObject", "JsonArray", "JsonUtil")),
                    original / "org.zenframework.z8.boot/src/main/java/org/zenframework/z8/rmi/ObjectIO.java",
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
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class EvalProbe {
    public static Eval make() { Eval e; e.setVariable("name", "Ada"); e.setVariable("count", 7); e.setVariable("flag", true); primary nil = null; e.setVariable("nil", nil); return e; }
    public static Eval withJson() { Eval e; JsonObject obj; JsonObject child; JsonArray arr; child.set("title", "Ada"); arr.add(3); arr.add("tail"); obj.set("count", 7); obj.set("child", child); obj.set("items", arr); obj.set("price", 1.25); obj.set("yes", true); e.setVariable("obj", obj); e.setVariable("arr", arr); primary nil = null; e.setVariable("nil", nil); obj.set("after", 42); obj = "{}"; arr = "[]"; return e; }
    public static Eval withRows(Eval e) { JsonArray rows; JsonArray decimals; JsonObject dictionary; rows = "[{\\\"n\\\":7},{\\\"n\\\":2},{\\\"n\\\":5}]"; decimals = "[{\\\"n\\\":1.75},{\\\"n\\\":1.25},{\\\"n\\\":3}]"; dictionary = "{\\\"a\\\":{\\\"n\\\":7},\\\"b\\\":{\\\"n\\\":2}}"; e.setVariable("rows", rows); e.setVariable("decimals", decimals); e.setVariable("dictionary", dictionary); date day = '29/02/2024'; e.setVariable("day", day); datespan span = datespan.parse("1 02:03:04"); e.setVariable("span", span); return e; }
    public static void shadow(Eval e) { e.setVariable("int", 10); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime; import z8gen.EvalProbe; import std.stdio : writeln; import std.conv : to;
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
    auto jsonEval = Z8p_4576616C50726F6265.m_withJson();
    foreach (pattern; ["${obj.count}"w, "name=${obj.child.title}"w, "${obj.missing}"w, "${obj['count']}"w,
                       "${arr[0]}"w, "${arr[1]}"w, "${obj.items[1]}"w, "${missing.field}"w,
                       "${arr[0] + obj.count}"w, "${obj.missing ?: 'fallback'}"w,
                       "${false ? obj.items[99] : 'safe'}"w, "${obj.price + 1}"w, "${obj.yes}"w,
                       "${arr[0.6]}"w, "${arr[99]}"w, "${obj.after}"w, "${arr[missing]}"w,
                       "${missing[0]}"w, "${nil[0]}"w, "${arr[nil]}"w, "${obj[0]}"w, "${arr['bad']}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    writeln("json-errors=", jsonEval.m_getErrors().z8_size());
    auto jsonErrors = jsonEval.m_getErrors();
    writeln(jsonErrors.z8_get(jsonErrors.z8_size() - 2).to!string);
    writeln(jsonErrors.z8_get(jsonErrors.z8_size() - 1).to!string);
    Z8p_4576616C50726F6265.m_withRows(jsonEval);
    foreach (pattern; ["${json.min(rows, 'n')}"w, "${json.max(rows, 'n')}"w, "${json.min(rows, 'missing')}"w,
                       "${json.max(rows, 'missing')}"w, "${json.min(nil, 'n')}"w, "${json.min(decimals, 'n')}"w,
                       "${json.max(decimals, 'n')}"w, "${json.min(dictionary, 'n')}"w, "${json.max(dictionary, 'n')}"w, "${json.min(rows, nil)}"w,
                       "${false ? json.min(rows, 'n') : 42}"w, "${json.min(rows)}"w, "${json.unknown(rows, 'n')}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${format(42, 'unused')}"w, "${format('text', 'unused')}"w, "${format(nil, 'unused')}"w,
                       "${format(1.25, '%.1f')}"w, "${format(1234.5, '% ,.2f')}"w, "${format(1.25, '%+08.2f')}"w,
                       "${format(1.25, '%-8.2f')}"w, "${format(1.25, 'value=%.2f%%')}"w, "${format(1.25, nil)}"w,
                       "${format(0.0 - 1.25, '%(08.2f')}"w, "${format(1.25, '%#.0f')}"w, "${format(1.25, '%.2f %<.1f')}"w,
                       "${format(1.25, 'literal')}"w, "${format(day, 'yyyy-MM-dd')}"w, "${format(day, nil)}"w,
                       "${format(missing, 'x')}"w, "${false ? format(1.25) : 'safe'}"w, "${format(1.25)}"w, "${unknown(1)}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${'  Ada  '.trim().toUpperCase()}"w, "${'abc'.length()}"w, "${''.isEmpty()}"w,
                       "${'abc'.substring(1, 2)}"w, "${'abc'.startsWith('b', 1)}"w, "${'abc'.endsWith('bc')}"w,
                       "${'abcabc'.indexOf('bc', 2)}"w, "${'abcabc'.lastIndexOf('bc')}"w, "${'Hello'.compareNoCase('hello')}"w,
                       "${'abc'.replace(1, 1, 'X')}"w, "${'a'.padLeft(3, 'xy')}"w, "${'Hello'.firstToLowerCase()}"w,
                       "${'abc'.charAt(1)}"w, "${'abc'.insert(1, 'XY')}"w, "${'abc'.matches('a.*')}"w,
                       "${'banana'.replaceAll('a', 'X')}"w, "${'abc'.hashCode()}"w, "${(123).hashCode()}"w,
                       "${(1.25).hashCode()}"w, "${true.hashCode()}"w, "${true.toString()}"w,
                       "${guid.parse('00000000-0000-0000-0000-000000000001').toString()}"w, "${'abc'.substring(missing)}"w,
                       "${missing.length()}"w, "${'abc'.substring(99)}"w, "${'abc'.substring('1')}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${true.get()}"w, "${true.toNumber()}"w, "${false.toNumber()}"w, "${guid.create(42).get().toString()}"w,
                       "${guid.create(42).major()}"w, "${guid.create(42).minor()}"w, "${(4294967297).getInt()}"w,
                       "${(42).decimal().scale()}"w, "${(0).date().ticks()}"w, "${decimal.parse('1.2300').scale()}"w,
                       "${decimal.parse('1.2300').precision()}"w, "${(1.25).isNaN()}"w, "${(1.25).getDouble()}"w,
                       "${(0.0 - 1.0).sqrt().get()}"w, "${(0.0 - 1.0).sqrt().getDouble().isNaN()}"w,
                       "${(0.0 - 1.0).sqrt().precision()}"w, "${(2.5).power(3)}"w,
                       "${(2.5).power(-2)}"w, "${(2).power(3)}"w, "${span.get()}"w,
                       "${day.get().setDate(2023, 12, 31)}"w, "${day.year()}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${guid.create(42).components()}"w, "${guid.create(42).components()[1]}"w,
                       "${guid.create(42).components()[4294967297]}"w, "${guid.create(42).components()[nil]}"w,
                       "${'a,b'.split(',')[1]}"w, "${'a,b'.split(',').get(1)}"w, "${'a,b'.split(',').first()}"w,
                       "${'a,b'.split(',').last()}"w, "${'a,b'.split(',').size()}"w, "${'a,b'.split(',').isEmpty()}"w, "${'a,b'.split(',').hashCode()}"w,
                       "${'a,b'.split(',').join('-')}"w, "${'a,,'.split(',', -1).size()}"w,
                       "${'a,b'.split(',') ?: 'empty'}"w, "${'x' + 'a,b'.split(',')}"w,
                       "${'a,b'.split(',') ? 'yes' : 'no'}"w, "${json.min('a,b'.split(','), 'x')}"w,
                       "${json.max('a,b'.split(','), 'x')}"w, "${format('a,b'.split(','), 'x')}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${'b,a,b'.split(',').reverse().join('-')}"w, "${'b,a,b'.split(',').sort().join('-')}"w,
                       "${'b,a,b'.split(',').unique().join('-')}"w, "${'a,b'.split(',').removeAt(0)}"w,
                       "${'b,a,b'.split(',').removeAll('b'.split(',')).join('-')}"w, "${'b,a,b'.split(',').remove('b'.split(','))}"w,
                       "${'a,b'.split(',').clear()}"w, "${guid.create(42).components().reverse()[0]}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    jsonEval.m_setVariable("slashPath"w, z8_primary_box("folder"w ~ cast(wchar)92 ~ "Report.XLSX"w));
    foreach (pattern; ["${'folder/Report.XLSX'.file().fileName()}"w, "${'folder/Report.XLSX'.file().baseName()}"w,
                       "${'folder/Report.XLSX'.file().extension()}"w, "${'folder/Report.XLSX'.file().folder()}"w,
                       "${'folder/Report.XLSX'.file().string()}"w, "${'folder/Report.XLSX'.file().getPath()}"w,
                       "${slashPath.file().getPath()}"w, "${slashPath.file().string()}"w,
                       "${'folder/Report.XLSX'.file().parent().fileName()}"w, "${'missing-file-uuid-72e8'.file().exists()}"w,
                       "${'missing-file-uuid-72e8'.file().isEmpty()}"w, "${'missing-file-uuid-72e8'.file().isFolder()}"w,
                       "${'missing-file-uuid-72e8'.file().lastModified().ticks()}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${'Привет'.binary().length()}"w, "${'abc'.binary().getName()}"w,
                       "${'abc'.binary().setName('folder/Report.TXT').getName()}"w, "${'abc'.binary().setName('folder/Report.TXT').name}"w,
                       "${'abc'.binary().setName('folder/Report.TXT').getBaseName()}"w,
                       "${'abc'.binary().setName('folder/Report.TXT').getExtension()}"w,
                       "${'abc'.binary().setName('name').toString()}"w, "${'folder/Report.XLSX'.file().name}"w,
                       "${slashPath.file().path}"w, "${'file'.file().size}"w, "${'file'.file().id}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${1.25.abs()}"w, "${(-7).abs()}"w, "${(-7).signum()}"w, "${(5).not()}"w, "${(5).and(3)}"w,
                       "${(5).xor(3)}"w, "${(8).rightShift(2)}"w, "${(255).toHexString()}"w, "${(255).toString(16)}"w,
                       "${(9).sqrt()}"w, "${(2).sqrt()}"w, "${(1).sin()}"w, "${(2).power(3.0)}"w, "${(1.25).round(1)}"w,
                       "${(1.25).round(1, 1)}"w, "${(1.25).round(1, 7)}"w, "${(1.5).round()}"w,
                       "${(0.0 - 1.5).round()}"w, "${(1.25).abs()}"w, "${(0.1).abs()}"w, "${(1.25).ceil()}"w, "${(1.25).floor()}"w,
                       "${(5).and('x')}"w, "${(1.25).round(missing)}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${int.parse('42')}"w, "${int.parse('ff', 16)}"w, "${decimal.parse('1.25')}"w, "${bool.parse('yes')}"w,
                       "${bool.parse(nil)}"w, "${string.replicate('ab', 3)}"w, "${guid.parse('00000000-0000-0000-0000-000000000001')}"w,
                       "${guid.create(42)}"w, "${guid.create('abc')}"w, "${format(date.parse('29/02/2024'), 'yyyy-MM-dd')}"w,
                       "${format(date.parse('2024-02-29', 'yyyy-MM-dd'), 'dd.MM.yyyy')}"w, "${int.Min}"w,
                       "${int.parse(missing)}"w, "${int.parse('x')}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${day.year()}"w, "${day.month()}"w, "${day.day()}"w, "${day.daysInMonth()}"w, "${day.dayOfWeek()}"w,
                       "${day.weekOfYear()}"w, "${day.toString('yyyy-MM-dd')}"w, "${day.addDay(1).toString('yyyy-MM-dd')}"w,
                       "${day.addMonth(1).toString('yyyy-MM-dd')}"w, "${day.truncMonth().toString('yyyy-MM-dd')}"w,
                       "${day.truncWeek().toString('yyyy-MM-dd')}"w,
                       "${datespan.parse('1 02:03:04').days()}"w, "${datespan.parse('1 02:03:04').hours()}"w,
                       "${datespan.parse('1 02:03:04').totalMinutes()}"w, "${day.addDay('x')}"w, "${day.addDay(missing)}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    foreach (pattern; ["${span.setTotalHours(50)}"w, "${span.days()}"w, "${span.hours()}"w, "${span.truncDay()}"w,
                       "${span.totalHours()}"w, "${day.setDate(2023, 12, 31)}"w, "${day.year()}"w, "${day.month()}"w])
        writeln(jsonEval.m_evaluateText(pattern).to!string);
    foreach (pattern; ["${'' == nil}"w, "${'a' > nil}"w, "${'x' + nil}"w, "${true == nil}"w, "${true != nil}"w,
                       "${1 == nil}"w, "${1 != nil}"w, "${1.0 == nil}"w, "${1.0 != nil}"w,
                       "${nil == nil}"w, "${'x' + arr}"w])
        try { writeln(jsonEval.m_evaluateText(pattern).to!string); } catch (Exception) { writeln("error"); }
    Z8p_4576616C50726F6265.m_shadow(jsonEval);
    writeln(jsonEval.m_evaluateText("${int}"w).to!string);
    try { writeln(jsonEval.m_evaluateText("${int.parse('42')}"w).to!string); } catch (Exception) { writeln("error"); }
    jsonEval.m_clear();
    writeln(jsonEval.m_evaluateText("${int.parse('42')}"w).to!string);
}
''', encoding="utf-8")
    executable = temp / ("eval-oracle.exe" if os.name == "nt" else "eval-oracle")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert expected == actual, [(i, expected[i] if i < len(expected) else "<missing>",
                                actual[i] if i < len(actual) else "<missing>")
                               for i in range(max(len(expected), len(actual)))
                               if i >= len(expected) or i >= len(actual) or expected[i] != actual[i]]
print("Eval variables and text match the current original Z8 sources")
