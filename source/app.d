module app;

import std.file : readText;
import std.conv : to;
import std.json : JSONValue;
import std.stdio : stderr, write, writeln;
import z8.lexer;
import z8.compiler : compile, CompileException;

int main(string[] args) {
    if (args.length != 3 || (args[1] != "lex" && args[1] != "compile")) {
        stderr.writeln("Usage: z8d <lex|compile> <file.bl>");
        return 2;
    }
    try {
        if (args[1] == "compile") { write(compile(readText(args[2]))); return 0; }
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
        stderr.writefln("%s:%s:%s: %s", args[2], e.position.line + 1, e.position.column + 1, e.msg);
    } catch (LexException e) {
        stderr.writefln("%s:%s:%s: %s", args[2], e.position.line + 1, e.position.column + 1, e.msg);
    } catch (Exception e) {
        stderr.writefln("%s: %s", args[2], e.msg);
    }
    return 1;
}
