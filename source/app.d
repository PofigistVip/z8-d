module app;

import std.file : readText, dirEntries, SpanMode, tempDir, mkdir, mkdirRecurse, exists, remove, copy, rename, rmdirRecurse, thisExePath, writeFile = write;
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
import z8.compiler : compile, compileSources, SourceUnit, GeneratedModule, CompileException, CompilationOptions;
import z8.nls : checkResources;
import z8.library : CompiledLibrary, validLibraryId, loadLibrary, validateLibraries, libraryRoots, serializeLibrary,
    libraryTreeRevision, libraryFileRevision;

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

private string dmdVersion() {
    import std.string : splitLines, strip;
    auto result = execute(["dmd", "--version"]);
    auto lines = result.output.splitLines();
    if (result.status != 0 || !lines.length || !lines[0].strip().length)
        throw new Exception("could not determine DMD version");
    return lines[0].strip().idup;
}
private void checkLibraryCompilers(CompiledLibrary[] libraries, string version_) {
    foreach (library; libraries) {
        if (!library.compilerVersion.length)
            throw new Exception("BL library has no DMD version; rebuild " ~ library.id);
        if (library.compilerVersion != version_)
            throw new Exception("BL library DMD version differs; rebuild " ~ library.id ~ " with " ~ version_);
    }
}

private int buildExecutable(GeneratedModule[] modules, string outputPath, CompiledLibrary[] libraries = null) {
    if (libraries.length) checkLibraryCompilers(libraries, dmdVersion());
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
                  "-oq", "-od=" ~ temporary, "-of=" ~ linkerOutput];
    foreach (dependency; libraries) arguments ~= ["-I" ~ dependency.dRoot, dependency.binary];
    arguments ~= library;
    string[] quoted;
    foreach (argument; arguments) quoted ~= responseArgument(argument);
    auto response = buildPath(temporary, "dmd.rsp");
    writeFile(response, quoted.join("\n") ~ "\n");
    auto result = execute(["dmd", "@" ~ response]);
    if (result.status != 0) { stderr.write(result.output); return 1; }
    if (linkerOutput != target) copy(fileSystemPath(linkerOutput), fileSystemPath(target));
    return 0;
}

private CompilationOptions configureLibraries(ref SourceUnit[] units, CompiledLibrary[] libraries) {
    auto options = new CompilationOptions();
    options.libraryPrefixes = libraryRoots(libraries);
    if (libraries.length) {
        auto expectedRuntime = libraryTreeRevision(buildPath(runtimeRoot(), "source"), [".d", ".txt"]);
        foreach (library; libraries) if (library.runtimeRevision != expectedRuntime)
            throw new Exception("BL library runtime changed; rebuild " ~ library.id);
    }
    bool[string] sourceNames;
    foreach (unit; units) sourceNames[unit.name] = true;
    foreach (library; libraries) {
        foreach (unit; library.sources) {
            if (unit.name in sourceNames) throw new Exception("BL class occurs in more than one project or library: " ~ unit.name);
            sourceNames[unit.name] = true; units ~= unit;
        }
        foreach (name, descriptor; library.types) {
            if (name in options.externalTypes) throw new Exception("BL class occurs in more than one library: " ~ name);
            options.externalTypes[name] = descriptor;
        }
    }
    return options;
}

// Assemble in a fresh sibling directory. Only an existing package produced by
// this command may be replaced, and a failed installation restores the old one.
private int buildLibrary(SourceUnit[] owned, CompiledLibrary[] libraries, string outputPath, string id) {
    if (!validLibraryId(id)) throw new Exception("library id must contain only ASCII letters, digits and underscores");
    auto compilerVersion = dmdVersion();
    checkLibraryCompilers(libraries, compilerVersion);
    import std.uni : toLower;
    foreach (library; libraries) if (library.id.toLower == id.toLower) throw new Exception("library id conflicts with a dependency: " ~ id);
    auto units = owned.dup;
    auto options = configureLibraries(units, libraries);
    options.modulePrefix = "z8lib.l_" ~ id; options.libraryOutput = true;
    auto modules = compileSources(units, "", options);
    auto output = absolutePath(outputPath);
    auto parent = dirName(output), name = baseName(output);
    if (!name.length || name == "." || name == ".." || parent == output) throw new Exception("invalid BL library output path");
    bool insideOutput(string path) {
        import std.path : isAbsolute;
        version (Windows) {
            if (path.startsWith(`\\?\UNC\`)) path = `\\` ~ path[8 .. $];
            else if (path.startsWith(`\\?\`)) path = path[4 .. $];
        }
        auto rel = relativePath(absolutePath(path), output).replace("\\", "/");
        return rel == "." || (!isAbsolute(rel) && rel != ".." && !rel.startsWith("../"));
    }
    foreach (unit; owned) if (insideOutput(unit.path)) throw new Exception("library output cannot contain its source files");
    foreach (library; libraries) if (insideOutput(library.directory)) throw new Exception("library output cannot contain a dependency");
    if (insideOutput(runtimeRoot()) || insideOutput(thisExePath())) throw new Exception("library output cannot contain the compiler or runtime");
    if (exists(fileSystemPath(output))) {
        import std.file : isSymlink;
        if (isSymlink(fileSystemPath(output))) throw new Exception("library output cannot be a symbolic link");
        auto previous = loadLibrary(output, false);
        if (previous.id != id) throw new Exception("library output belongs to another library: " ~ previous.id);
        foreach (item; dirEntries(fileSystemPath(output), SpanMode.shallow)) {
            auto child = baseName(item.name);
            if (!["d", "z8-library.json", "z8-library.lib", "libz8-library.a", ".source-fingerprint"].canFind(child) || item.isSymlink)
                throw new Exception("library output contains an unmanaged file: " ~ child);
        }
        foreach (item; dirEntries(fileSystemPath(buildPath(output, "d")), SpanMode.depth))
            if (item.isSymlink || (!item.isDir && extension(item.name) != ".d"))
                throw new Exception("library output contains an unmanaged file: " ~ item.name);
    }
    mkdirRecurse(fileSystemPath(parent));
    auto suffix = randomUUID().to!string;
    auto staging = buildPath(parent, ".z8d-library-" ~ suffix);
    auto backup = buildPath(parent, ".z8d-library-backup-" ~ suffix);
    if (dirName(staging) != parent || dirName(backup) != parent) throw new Exception("invalid library staging directory");
    mkdir(fileSystemPath(staging));
    bool installed;
    scope(exit) if (!installed && exists(fileSystemPath(staging))) rmdirRecurse(fileSystemPath(staging));
    auto dRoot = buildPath(staging, "d");
    auto files = writeModules(modules, dRoot);
    auto runtime = buildPath(runtimeRoot(), "source");
    version (Windows) auto binaryName = "z8-library.lib";
    else auto binaryName = "libz8-library.a";
    auto binary = buildPath(staging, binaryName);
    auto objects = buildPath(staging, "objects"); mkdir(fileSystemPath(objects));
    string[] arguments = ["-lib", "-I" ~ dRoot, "-I" ~ runtime, "-J" ~ runtime, "-od=" ~ objects, "-of=" ~ binary];
    foreach (dependency; libraries) arguments ~= "-I" ~ dependency.dRoot;
    arguments ~= files;
    string[] quoted;
    foreach (argument; arguments) quoted ~= responseArgument(argument);
    auto response = buildPath(staging, "dmd.rsp");
    writeFile(fileSystemPath(response), quoted.join("\n") ~ "\n");
    auto result = execute(["dmd", "@" ~ response]);
    if (result.status != 0) { stderr.write(result.output); return 1; }
    remove(fileSystemPath(response)); rmdirRecurse(fileSystemPath(objects));
    auto runtimeRevision = libraryTreeRevision(runtime, [".d", ".txt"]);
    auto interfacesRevision = libraryTreeRevision(dRoot, [".d"]);
    auto archiveRevision = libraryFileRevision(binary);
    writeFile(fileSystemPath(buildPath(staging, "z8-library.json")),
        serializeLibrary(id, owned, options.exportedTypes, libraries, runtimeRevision, interfacesRevision, archiveRevision, compilerVersion));
    bool backedUp;
    if (exists(fileSystemPath(output))) { rename(fileSystemPath(output), fileSystemPath(backup)); backedUp = true; }
    try { rename(fileSystemPath(staging), fileSystemPath(output)); installed = true; }
    catch (Exception error) { if (backedUp) rename(fileSystemPath(backup), fileSystemPath(output)); throw error; }
    if (backedUp) rmdirRecurse(fileSystemPath(backup));
    writeln("Built BL library ", id, " in ", output);
    return 0;
}

int main(string[] args) {
    size_t required;
    if (args.length > 1) {
        if (args[1] == "lex" || args[1] == "compile") required = 3;
        else if (args[1] == "project") required = 4;
        else if (args[1] == "build" || args[1] == "check-resources" || args[1] == "library") required = 5;
    }
    bool valid = required && args.length >= required;
    string[] dependencies, libraryPaths;
    if (valid && (args[1] == "lex" || args[1] == "compile")) valid = args.length == required;
    else if (valid) {
        for (size_t i = required; i < args.length; i += 2) {
            if (i + 1 >= args.length || !args[i + 1].length) { valid = false; break; }
            if (args[i] == "--dependency") dependencies ~= args[i + 1];
            else if (args[i] == "--library") libraryPaths ~= args[i + 1];
            else { valid = false; break; }
        }
    }
    if (!valid) {
        stderr.writeln("Usage: z8d <lex|compile> <file.bl> | z8d project <source-root> <output-dir> [--dependency <source-root>]... [--library <library-dir>]... | z8d build <source-root> <class.method> <output> [--dependency <source-root>]... [--library <library-dir>]... | z8d library <source-root> <output-dir> <id> [--dependency <source-root>]... [--library <library-dir>]... | z8d check-resources <source-root> <resources-dir> <language> [--dependency <source-root>]... [--library <library-dir>]...");
        return 2;
    }
    try {
        CompiledLibrary[] libraries;
        foreach (path; libraryPaths) libraries ~= loadLibrary(path);
        libraries = validateLibraries(libraries);
        if (args[1] == "check-resources") {
            auto units = readProjectWithDependencies(args[2], dependencies);
            auto options = libraries.length ? configureLibraries(units, libraries) : null;
            compileSources(units, "", options);
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
        if (args[1] == "library") return buildLibrary(readProjectWithDependencies(args[2], dependencies), libraries, args[3], args[4]);
        if (args[1] == "project") {
            auto units = readProjectWithDependencies(args[2], dependencies);
            auto options = libraries.length ? configureLibraries(units, libraries) : null;
            auto modules = compileSources(units, "", options);
            writeModules(modules, args[3]);
            writeln("Generated ", modules.length, " D modules in ", absolutePath(args[3]));
            return 0;
        }
        if (args[1] == "build") {
            auto units = readProjectWithDependencies(args[2], dependencies);
            auto options = libraries.length ? configureLibraries(units, libraries) : null;
            return buildExecutable(compileSources(units, args[3], options), args[4], libraries);
        }
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
