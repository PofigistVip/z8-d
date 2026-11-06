module app;

import std.file : readText, dirEntries, SpanMode, tempDir, mkdir, mkdirRecurse, exists, remove, copy, rmdirRecurse, thisExePath, writeFile = write;
import std.conv : to;
import std.algorithm : sort, canFind;
import std.array : join;
import std.path : extension, relativePath, stripExtension, absolutePath, buildPath, dirName, baseName;
import std.process : execute, environment;
import std.string : replace, startsWith;
import std.uuid : randomUUID;
import std.json : JSONValue;
import std.stdio : stderr, write, writeln;
import z8.lexer;
import z8.compiler : compile, compileSources, SourceUnit, GeneratedModule, CompileException;
import z8.nls : checkResources;

private SourceUnit[] readProject(string root) {
    root = fileSystemPath(absolutePath(root));
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

// Merge source roots deterministically: the main root shadows dependencies,
// and earlier dependencies shadow later ones in the generated module set.
private SourceUnit[] readProjectWithDependencies(string root, string[] dependencies) {
    SourceUnit[] units;
    bool[string] seen;
    foreach (path; [root] ~ dependencies) foreach (unit; readProject(path)) {
        if (unit.name in seen) continue;
        seen[unit.name] = true;
        units ~= unit;
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

// Windows APIs require the extended-length prefix even when each individual
// path component is valid but the complete generated path exceeds MAX_PATH.
private string fileSystemPath(string path) {
    version (Windows) {
        auto value = absolutePath(path).replace("/", "\\");
        if (value.startsWith(`\\?\`)) return value;
        if (value.startsWith(`\\`)) return `\\?\UNC\` ~ value[2 .. $];
        return `\\?\` ~ value;
    } else return path;
}

private string[] writeModules(GeneratedModule[] modules, string outputRoot) {
    auto root = absolutePath(outputRoot);
    string[] files;
    foreach (module_; modules) {
        auto path = buildPath(root, module_.relativePath);
        auto ioPath = fileSystemPath(path);
        mkdirRecurse(dirName(ioPath));
        writeFile(ioPath, module_.source);
        files ~= ioPath;
    }
    return files;
}

private void cleanupBuild(string directory, string tempRoot, string library) {
    try {
        if (library.length)
            foreach (path; [library, library ~ ".tmp"]) if (exists(path)) remove(path);
        // The directory is freshly created below the system temp root by this run.
        if (dirName(directory) == tempRoot && baseName(directory).startsWith("z8d-") && exists(fileSystemPath(directory)))
            rmdirRecurse(fileSystemPath(directory));
    } catch (Exception) { }
}

private string responseArgument(string value) {
    if (value.canFind('\n') || value.canFind('\r')) throw new Exception("newline in compiler argument");
    return "\"" ~ value.replace("\"", "\\\"") ~ "\"";
}

private int buildExecutable(GeneratedModule[] modules, string outputPath) {
    auto tempRoot = dirName(absolutePath(buildPath(tempDir(), "z8d-probe")));
    auto temporary = absolutePath(buildPath(tempRoot, "z8d-" ~ randomUUID().to!string));
    if (dirName(temporary) != tempRoot || !baseName(temporary).startsWith("z8d-"))
        throw new Exception("invalid temporary build directory");
    mkdir(temporary);
    string ownedLibrary;
    scope (exit) cleanupBuild(temporary, tempRoot, ownedLibrary);
    auto runtimeDirectory = runtimeRoot();
    auto runtime = buildPath(runtimeDirectory, "source");
    auto library = environment.get("Z8_RUNTIME_LIB", "");
    if (library.length) {
        library = absolutePath(library);
        if (!exists(library)) throw new Exception("runtime library not found: " ~ library);
    } else {
        auto libDirectory = buildPath(runtimeDirectory, "lib");
        mkdirRecurse(libDirectory);
        auto suffix = randomUUID().to!string;
        version (Windows) library = buildPath(libDirectory, "z8-runtime-" ~ suffix ~ ".lib");
        else library = buildPath(libDirectory, "libz8-runtime-" ~ suffix ~ ".a");
        ownedLibrary = library;
        auto runtimeModule = buildPath(runtime, "z8", "runtime.d");
        auto runtimeSource = buildPath(runtime, "z8", "runtime_source.d");
        auto builtRuntime = execute(["dmd", "-lib", "-I" ~ runtime, "-J" ~ runtime,
            runtimeModule, runtimeSource, "-od=" ~ temporary, "-of=" ~ library]);
        if (builtRuntime.status != 0) { stderr.write(builtRuntime.output); return 1; }
    }
    auto generatedRoot = buildPath(temporary, "generated");
    auto target = absolutePath(outputPath);
    auto linkerOutput = target;
    version (Windows) if (target.length >= 240) linkerOutput = buildPath(temporary, "z8d-output.exe");
    auto arguments = writeModules(modules, generatedRoot);
    arguments ~= ["-I" ~ generatedRoot, "-I" ~ runtime, "-J" ~ runtime,
                  "-oq", library, "-od=" ~ temporary, "-of=" ~ linkerOutput];
    string[] quoted;
    foreach (argument; arguments) quoted ~= responseArgument(argument);
    auto response = buildPath(temporary, "dmd.rsp");
    writeFile(response, quoted.join("\n") ~ "\n");
    auto result = execute(["dmd", "@" ~ response]);
    if (result.status != 0) { stderr.write(result.output); return 1; }
    if (linkerOutput != target) copy(fileSystemPath(linkerOutput), fileSystemPath(target));
    return 0;
}

int main(string[] args) {
    size_t required;
    if (args.length > 1) {
        if (args[1] == "lex" || args[1] == "compile") required = 3;
        else if (args[1] == "project") required = 4;
        else if (args[1] == "build" || args[1] == "check-resources") required = 5;
    }
    bool valid = required && args.length >= required;
    string[] dependencies;
    if (valid && (args[1] == "lex" || args[1] == "compile")) valid = args.length == required;
    else if (valid) {
        for (size_t i = required; i < args.length; i += 2) {
            if (args[i] != "--dependency" || i + 1 >= args.length || !args[i + 1].length) { valid = false; break; }
            dependencies ~= args[i + 1];
        }
    }
    if (!valid) {
        stderr.writeln("Usage: z8d <lex|compile> <file.bl> | z8d project <source-root> <output-dir> [--dependency <source-root>]... | z8d build <source-root> <class.method> <output> [--dependency <source-root>]... | z8d check-resources <source-root> <resources-dir> <language> [--dependency <source-root>]...");
        return 2;
    }
    try {
        if (args[1] == "check-resources") {
            auto units = readProjectWithDependencies(args[2], dependencies);
            compileSources(units);
            size_t count;
            auto missing = checkResources(units, args[3], args[4], count);
            foreach (item; missing)
                stderr.writefln("%s:%s:%s: missing resource '%s' for language '%s'", item.path,
                    item.token.position.line + 1, item.token.position.column + 1, item.key.to!string, args[4]);
            if (missing.length) return 1;
            writeln("Checked resources for ", units.length, " BL files against ", count, " bundles");
            return 0;
        }
        if (args[1] == "compile") { write(compile(readText(fileSystemPath(args[2])))); return 0; }
        if (args[1] == "project") {
            auto modules = compileSources(readProjectWithDependencies(args[2], dependencies));
            writeModules(modules, args[3]);
            writeln("Generated ", modules.length, " D modules in ", absolutePath(args[3]));
            return 0;
        }
        if (args[1] == "build") return buildExecutable(compileSources(readProjectWithDependencies(args[2], dependencies), args[3]), args[4]);
        auto lexer = new Lexer(readText(fileSystemPath(args[2])));
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
