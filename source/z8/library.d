module z8.library;

import std.algorithm : canFind;
import std.conv : to;
import std.digest : toHexString;
import std.digest.sha : sha256Of, SHA256;
import std.file : exists, readText, dirEntries, SpanMode;
import std.json : JSONType, JSONValue, parseJSON;
import std.path : buildPath, absolutePath, relativePath, extension;
import std.string : startsWith, replace;
import z8.compiler_model : SourceUnit, LibraryType;

/// A compiled library keeps the BL declarations needed for semantic analysis,
/// its generated D interfaces, and a separately compiled static library.
struct CompiledLibrary {
    string id, prefix, directory, binary, dRoot, revision, runtimeRevision, compilerVersion;
    SourceUnit[] sources;
    LibraryType[string] types;
    string[string] requirements;
}

bool validLibraryId(string id) {
    if (!id.length) return false;
    foreach (ubyte c; id)
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_')) return false;
    return true;
}

string libraryRevision(string manifest) { return sha256Of(manifest).toHexString.idup; }

string libraryTarget() {
    version (Windows) enum os = "windows";
    else version (linux) enum os = "linux";
    else version (OSX) enum os = "macos";
    else enum os = "other";
    version (X86_64) enum arch = "x86_64";
    else version (X86) enum arch = "x86";
    else version (AArch64) enum arch = "aarch64";
    else enum arch = "other";
    return os ~ "-" ~ arch;
}

private void hashFile(ref SHA256 digest, string path) {
    import std.stdio : File;
    auto file = File(path, "rb");
    foreach (chunk; file.byChunk(64 * 1024)) digest.put(chunk);
}
string libraryFileRevision(string path) {
    SHA256 digest; digest.start(); hashFile(digest, path);
    return digest.finish().toHexString.idup;
}
string libraryTreeRevision(string root, string[] extensions) {
    import std.algorithm.sorting : sort;
    string[] paths;
    foreach (entry; dirEntries(root, SpanMode.depth))
        if (entry.isFile && extensions.canFind(extension(entry.name))) paths ~= entry.name;
    sort(paths);
    SHA256 digest; digest.start();
    foreach (path; paths) {
        auto name = relativePath(path, root).replace("\\", "/");
        digest.put(cast(const(ubyte)[])name); digest.put(cast(ubyte)0);
        hashFile(digest, path); digest.put(cast(ubyte)0);
    }
    return digest.finish().toHexString.idup;
}

CompiledLibrary loadLibrary(string directory, bool requireCurrentRegistry = true) {
    auto root = absolutePath(directory);
    auto manifestPath = buildPath(root, "z8-library.json");
    if (!exists(manifestPath)) throw new Exception("BL library manifest not found: " ~ manifestPath);
    auto text = readText(manifestPath);
    auto document = parseJSON(text);
    if (document.type != JSONType.object) throw new Exception("invalid BL library manifest");
    JSONValue field(string key, JSONType type) {
        auto value = key in document.object;
        if (value is null || value.type != type) throw new Exception("invalid BL library manifest field: " ~ key);
        return *value;
    }
    if (field("format", JSONType.string).str != "z8-d-library-1") throw new Exception("unsupported BL library format");
    if (field("target", JSONType.string).str != libraryTarget()) throw new Exception("BL library target does not match this compiler");
    CompiledLibrary library;
    library.id = field("id", JSONType.string).str;
    if (!validLibraryId(library.id)) throw new Exception("invalid BL library id");
    if (requireCurrentRegistry) {
        auto api = "registryApi" in document.object;
        if (api is null || api.type != JSONType.integer || api.integer != 3)
            throw new Exception("BL library registry API changed; rebuild " ~ library.id);
    }
    library.prefix = "z8lib.l_" ~ library.id;
    library.directory = root; library.dRoot = buildPath(root, "d");
    library.revision = libraryRevision(text);
    library.runtimeRevision = field("runtime", JSONType.string).str;
    if (auto compiler = "compiler" in document.object) {
        if (compiler.type != JSONType.string || !compiler.str.length) throw new Exception("invalid BL library compiler version");
        library.compilerVersion = compiler.str;
    }
    version (Windows) auto binaryName = "z8-library.lib";
    else auto binaryName = "libz8-library.a";
    library.binary = buildPath(root, binaryName);
    if (!exists(library.binary) || !exists(library.dRoot)) throw new Exception("BL library is missing its D modules or static library: " ~ root);
    if (field("archive", JSONType.string).str != libraryFileRevision(library.binary) ||
        field("interfaces", JSONType.string).str != libraryTreeRevision(library.dRoot, [".d"]))
        throw new Exception("BL library files do not match their manifest: " ~ root);
    foreach (item; field("sources", JSONType.array).array) {
        if (item.type != JSONType.object) throw new Exception("invalid BL library source");
        auto name = "name" in item.object, source = "source" in item.object;
        if (name is null || source is null || name.type != JSONType.string || source.type != JSONType.string || !name.str.length)
            throw new Exception("invalid BL library source");
        library.sources ~= SourceUnit(name.str, manifestPath ~ ":" ~ name.str, source.str);
    }
    foreach (item; field("types", JSONType.array).array) {
        if (item.type != JSONType.object) throw new Exception("invalid BL library type");
        auto name = "name" in item.object, moduleName = "module" in item.object, symbol = "symbol" in item.object;
        if (name is null || moduleName is null || symbol is null || name.type != JSONType.string ||
            moduleName.type != JSONType.string || symbol.type != JSONType.string || !name.str.length || !symbol.str.length ||
            !moduleName.str.startsWith(library.prefix ~ ".") || (name.str in library.types) !is null)
            throw new Exception("invalid BL library type");
        library.types[name.str] = LibraryType(moduleName.str, symbol.str);
    }
    foreach (item; field("requires", JSONType.array).array) {
        if (item.type != JSONType.object) throw new Exception("invalid BL library requirement");
        auto name = "id" in item.object, revision = "revision" in item.object;
        if (name is null || revision is null || name.type != JSONType.string || revision.type != JSONType.string ||
            !validLibraryId(name.str) || !revision.str.length || (name.str in library.requirements) !is null)
            throw new Exception("invalid BL library requirement");
        library.requirements[name.str] = revision.str;
    }
    return library;
}

/// Resolve the full graph once; a changed dependency requires rebuilding its
/// consumers rather than silently linking inconsistent generated symbols.
CompiledLibrary[] validateLibraries(CompiledLibrary[] libraries) {
    import std.algorithm.mutation : reverse;
    import std.uni : toLower;
    size_t[string] byId;
    foreach (i, library; libraries) {
        auto id = library.id.toLower;
        if (id in byId) throw new Exception("duplicate BL library id: " ~ library.id);
        byId[id] = i;
    }
    bool[string] active, done;
    CompiledLibrary[] ordered;
    void visit(CompiledLibrary library) {
        if (library.id in done) return;
        if (library.id in active) throw new Exception("cyclic BL library dependency: " ~ library.id);
        active[library.id] = true;
        foreach (id, revision; library.requirements) {
            auto index = id.toLower in byId;
            if (index is null || libraries[*index].id != id) throw new Exception("missing BL library dependency: " ~ id);
            if (libraries[*index].revision != revision) throw new Exception("BL library dependency changed; rebuild " ~ library.id ~ ": " ~ id);
            visit(libraries[*index]);
        }
        active.remove(library.id); done[library.id] = true; ordered ~= library;
    }
    foreach (library; libraries) visit(library);
    // Static linkers on Unix require consumers before their dependencies.
    reverse(ordered);
    return ordered;
}

string[] libraryRoots(CompiledLibrary[] libraries) {
    bool[string] referenced;
    foreach (library; libraries) foreach (id, revision; library.requirements) referenced[id] = true;
    string[] result;
    foreach (library; libraries) if (!(library.id in referenced)) result ~= library.prefix;
    return result;
}

string serializeLibrary(string id, SourceUnit[] sources, LibraryType[string] types, CompiledLibrary[] dependencies,
                        string runtimeRevision, string interfacesRevision, string archiveRevision, string compilerVersion) {
    import std.algorithm.sorting : sort;
    JSONValue[] sourceItems, typeItems, requirements;
    foreach (source; sources) sourceItems ~= JSONValue(["name": JSONValue(source.name), "source": JSONValue(source.source)]);
    auto names = types.keys; sort(names);
    foreach (name; names) {
        auto type = types[name];
        typeItems ~= JSONValue(["name": JSONValue(name), "module": JSONValue(type.moduleName), "symbol": JSONValue(type.symbol)]);
    }
    foreach (dependency; dependencies)
        requirements ~= JSONValue(["id": JSONValue(dependency.id), "revision": JSONValue(dependency.revision)]);
    return JSONValue(["format": JSONValue("z8-d-library-1"), "id": JSONValue(id), "target": JSONValue(libraryTarget()), "registryApi": JSONValue(3L),
        "runtime": JSONValue(runtimeRevision), "interfaces": JSONValue(interfacesRevision), "archive": JSONValue(archiveRevision), "compiler": JSONValue(compilerVersion),
        "sources": JSONValue(sourceItems), "types": JSONValue(typeItems), "requires": JSONValue(requirements)]).toPrettyString();
}
