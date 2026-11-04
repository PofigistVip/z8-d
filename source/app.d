module app;

import std.file : readText, dirEntries, SpanMode, tempDir, mkdir, mkdirRecurse, exists, remove, rmdir, thisExePath, writeFile = write;
import std.conv : to;
import std.algorithm : sort;
import std.path : extension, relativePath, stripExtension, absolutePath, buildPath, dirName;
import std.process : execute, environment;
import std.string : replace;
import std.uuid : randomUUID;
import std.json : JSONValue;
import std.stdio : stderr, write, writeln;
import z8.lexer;
import z8.compiler : compile, compileSources, SourceUnit, CompileException;

private SourceUnit[] readProject(string root) {
    root = absolutePath(root);
    string[] paths;
    foreach (entry; dirEntries(root, SpanMode.depth))
        if (entry.isFile && extension(entry.name) == ".bl") paths ~= entry.name;
    paths.sort();
    SourceUnit[] units;
    foreach (path; paths) {
        auto name = stripExtension(relativePath(path, root)).replace("\\", ".").replace("/", ".");
        units ~= SourceUnit(name, path, readText(path));
    }
    return units;
}

private string runtimeRoot() {
    auto configured = environment.get("Z8_RUNTIME_ROOT", "");
    auto root = configured.length ? absolutePath(configured) : buildPath(dirName(thisExePath()), "runtime");
    if (!exists(buildPath(root, "source", "z8", "runtime.d")))
        throw new Exception("runtime sources not found; set Z8_RUNTIME_ROOT to the runtime directory");
    return root;
}

private void cleanupBuild(string directory, string[] files) {
    try {
        foreach (path; files) if (exists(path)) remove(path);
        rmdir(directory);
    } catch (Exception) { }
}

private int buildExecutable(string source, string outputPath) {
    auto temporary = buildPath(tempDir(), "z8d-" ~ randomUUID().to!string);
    mkdir(temporary);
    auto generated = buildPath(temporary, "program.d");
    auto objectWindows = buildPath(temporary, "program.obj");
    auto objectOther = buildPath(temporary, "program.o");
    auto runtimeDirectory = runtimeRoot();
    auto libDirectory = buildPath(runtimeDirectory, "lib");
    mkdirRecurse(libDirectory);
    auto suffix = randomUUID().to!string;
    version (Windows) auto library = buildPath(libDirectory, "z8-runtime-" ~ suffix ~ ".lib");
    else auto library = buildPath(libDirectory, "libz8-runtime-" ~ suffix ~ ".a");
    scope (exit) cleanupBuild(temporary, [generated, objectWindows, objectOther, library, library ~ ".tmp"]);
    auto runtime = buildPath(runtimeDirectory, "source");
    auto runtimeModule = buildPath(runtime, "z8", "runtime.d");
    auto runtimeSource = buildPath(runtime, "z8", "runtime_source.d");
    auto builtRuntime = execute(["dmd", "-lib", "-I" ~ runtime, "-J" ~ runtime,
        runtimeModule, runtimeSource, "-od=" ~ temporary, "-of=" ~ library]);
    if (builtRuntime.status != 0) { stderr.write(builtRuntime.output); return 1; }
    writeFile(generated, source);
    auto result = execute(["dmd", generated, "-I" ~ runtime, "-J" ~ runtime,
        library, "-od=" ~ temporary, "-of=" ~ absolutePath(outputPath)]);
    if (result.status != 0) { stderr.write(result.output); return 1; }
    return 0;
}

int main(string[] args) {
    bool valid = args.length == 3 && (args[1] == "lex" || args[1] == "compile" || args[1] == "project") ||
                 args.length == 5 && args[1] == "build";
    if (!valid) {
        stderr.writeln("Usage: z8d <lex|compile> <file.bl> | z8d project <source-root> | z8d build <source-root> <class.method> <output>");
        return 2;
    }
    try {
        if (args[1] == "compile") { write(compile(readText(args[2]))); return 0; }
        if (args[1] == "project") { write(compileSources(readProject(args[2]))); return 0; }
        if (args[1] == "build") return buildExecutable(compileSources(readProject(args[2]), args[3]), args[4]);
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
