module app;

import std.file : readText, dirEntries, SpanMode;
import std.conv : to;
import std.algorithm : sort;
import std.path : extension, relativePath, stripExtension;
import std.string : replace;
import std.json : JSONValue;
import std.stdio : stderr, write, writeln;
import z8.lexer;
import z8.compiler : compile, compileSources, SourceUnit, CompileException;

int main(string[] args) {
    if (args.length != 3 || (args[1] != "lex" && args[1] != "compile" && args[1] != "project")) {
        stderr.writeln("Usage: z8d <lex|compile> <file.bl> | z8d project <source-root>");
        return 2;
    }
    try {
        if (args[1] == "compile") { write(compile(readText(args[2]))); return 0; }
        if (args[1] == "project") {
            string[] paths;
            foreach (entry; dirEntries(args[2], SpanMode.depth))
                if (entry.isFile && extension(entry.name) == ".bl") paths ~= entry.name;
            paths.sort();
            SourceUnit[] units;
            foreach (path; paths) {
                auto name = stripExtension(relativePath(path, args[2])).replace("\\", ".").replace("/", ".");
                units ~= SourceUnit(name, path, readText(path));
            }
            write(compileSources(units)); return 0;
        }
        auto lexer = new Lexer(readText(args[2]));
        while (true) {
            auto t = lexer.next();
            if (t.kind == TokenKind.endOfFile) break;
            JSONValue[string] item;
            item["kind"] = JSONValue(t.kind.to!string);
            item["text"] = JSONValue(t.text);
            item["offset"] = JSONValue(cast(long)t.position.offset);
            item["length"] = JSONValue(cast(long)t.position.length);
            item["line"] = JSONValue(cast(long)t.position.line);
            item["column"] = JSONValue(cast(long)t.position.column);
            writeln(JSONValue(item).toString());
        }
        return 0;
    } catch (CompileException e) {
        stderr.writefln("%s:%s:%s: %s", e.sourceName.length ? e.sourceName : args[2], e.position.line + 1, e.position.column + 1, e.msg);
    } catch (LexException e) {
        stderr.writefln("%s:%s:%s: %s", args[2], e.position.line + 1, e.position.column + 1, e.msg);
    } catch (Exception e) {
        stderr.writefln("%s: %s", args[2], e.msg);
    }
    return 1;
}
