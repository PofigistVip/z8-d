module z8.compiler;

import std.format : format;
import std.string : lastIndexOf;
import z8.lexer : LexException, Position;
import z8.emitter : emitPrograms, emitProjectModules, moduleNameFor;
import z8.d_writer : formatDSource;
public import z8.compiler_model;
public import z8.parser : Parser;
public import z8.semantic : Checker;

// Encode only characters that cannot be used directly in a D identifier.
// Underscores are escaped too, making this mapping reversible.
private string identifierPart(string name) {
    string result;
    foreach (ubyte c; name) {
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9'))
            result ~= cast(char)c;
        else result ~= format("_%02X", c);
    }
    return result;
}

string compile(string source) {
    auto program = (new Parser(source)).parse();
    program.qualifiedName = program.name.text;
    program.emittedName = "Z8_" ~ program.name.text;
    Program[string] programs;
    programs[program.qualifiedName] = program;
    Program[] ordered = [program];
    void addNested(Program owner) {
        foreach (nested; owner.nestedPrograms) {
            nested.qualifiedName = owner.qualifiedName ~ "$" ~ nested.name.text;
            nested.emittedName = owner.emittedName ~ "_" ~ nested.name.text;
            programs[nested.qualifiedName] = nested;
            ordered ~= nested;
            addNested(nested);
        }
    }
    addNested(program);
    prepareInheritance(ordered, programs);
    foreach (unit; ordered) (new Checker).prepareDeclarations(unit, programs);
    foreach (unit; ordered) (new Checker).check(unit, programs);
    return emitPrograms(ordered);
}

private void prepareInheritance(Program[] ordered, Program[string] programs) {
    foreach (program; ordered) {
        try { (new Checker).bindBase(program, programs); }
        catch (CompileException e) { e.sourceName = program.sourceName; throw e; }
    }
    bool[string] active, finished;
    void visit(Program program) {
        if (program.qualifiedName in finished) return;
        if (program.qualifiedName in active) {
            auto error = new CompileException("cyclic inheritance", program.baseToken.position);
            error.sourceName = program.sourceName; throw error;
        }
        active[program.qualifiedName] = true;
        if (program.baseClass !is null) visit(program.baseClass);
        active.remove(program.qualifiedName);
        finished[program.qualifiedName] = true;
    }
    foreach (program; ordered) visit(program);
}

/// Each unit name is the dotted path of the .bl file relative to the source root.
GeneratedModule[] compileSources(SourceUnit[] units, string entry = "") {
    if (!units.length) throw new CompileException("no .bl source files found", Position.init);
    Program[] ordered;
    Program[string] programs;
    foreach (sourceIndex, unit; units) {
        Program program;
        try { program = (new Parser(unit.source)).parse(); }
        catch (LexException e) {
            auto wrapped = new CompileException(e.msg, e.position); wrapped.sourceName = unit.path; throw wrapped;
        } catch (CompileException e) { e.sourceName = unit.path; throw e; }
        auto dot = unit.name.lastIndexOf('.');
        auto simpleName = dot < 0 ? unit.name : unit.name[dot + 1 .. $];
        if (program.name.text != simpleName) {
            auto error = new CompileException("class name must match its file name", program.name.position);
            error.sourceName = unit.path; throw error;
        }
        if (unit.name in programs) {
            auto error = new CompileException("duplicate source '" ~ unit.name ~ "'", program.name.position);
            error.sourceName = unit.path; throw error;
        }
        program.sourceName = unit.path;
        program.sourceIndex = sourceIndex;
        program.qualifiedName = unit.name;
        programs[unit.name] = program;
        ordered ~= program;
    }
    void addNested(Program owner) {
        foreach (nested; owner.nestedPrograms) {
            nested.qualifiedName = owner.qualifiedName ~ "$" ~ nested.name.text;
            nested.sourceName = owner.sourceName;
            nested.sourceIndex = owner.sourceIndex;
            programs[nested.qualifiedName] = nested;
            ordered ~= nested;
            addNested(nested);
        }
    }
    // Keep each specialization in its containing BL source module.
    auto roots = ordered.dup;
    foreach (program; roots) addNested(program);
    // Use short readable names when they uniquely identify a type in the
    // project. The qualified fallback is reversible and globally unique.
    size_t[string] nameCounts;
    foreach (program; ordered) ++nameCounts[program.name.text];
    foreach (program; ordered) {
        program.emittedName = program.lexicalOwner is null && nameCounts[program.name.text] == 1 ?
            "Z8_" ~ identifierPart(program.name.text) : "Z8q_" ~ identifierPart(program.qualifiedName);
    }
    prepareInheritance(ordered, programs);
    foreach (program; ordered) {
        try { (new Checker).prepareDeclarations(program, programs); }
        catch (CompileException e) { e.sourceName = program.sourceName; throw e; }
    }
    bool[string] checked;
    void checkInOrder(Program program) {
        if (program.qualifiedName in checked) return;
        if (program.baseClass !is null) checkInOrder(program.baseClass);
        try { (new Checker).check(program, programs); }
        catch (CompileException e) { e.sourceName = program.sourceName; throw e; }
        checked[program.qualifiedName] = true;
    }
    foreach (program; ordered) checkInOrder(program);
    auto output = emitProjectModules(ordered);
    if (entry.length) {
        auto dot = entry.lastIndexOf('.');
        if (dot <= 0 || dot + 1 == entry.length)
            throw new CompileException("entry must be a qualified class and method name", Position.init);
        auto ownerName = entry[0 .. dot];
        auto methodName = entry[dot + 1 .. $];
        auto owner = ownerName in programs;
        if (owner is null) throw new CompileException("entry class not found: " ~ ownerName, Position.init);
        Method target;
        Method named;
        foreach (candidate; (*owner).methods) if (candidate.name.text == methodName) {
            named = candidate;
            if (candidate.parameters.length == 0) { target = candidate; break; }
        }
        if (target is null && named !is null) {
            auto error = new CompileException("entry must be a public static method with no parameters returning void or int", named.name.position);
            error.sourceName = (*owner).sourceName; throw error;
        }
        if (target is null) throw new CompileException("entry method not found: " ~ entry, Position.init);
        if (!target.isPublic || !target.isStatic || target.parameters.length != 0 ||
            (target.returnType != ValueType.voidType && target.returnType != ValueType.intType)) {
            auto error = new CompileException("entry must be a public static method with no parameters returning void or int", target.name.position);
            error.sourceName = (*owner).sourceName; throw error;
        }
        auto call = (*owner).emittedName ~ ".m_" ~ target.name.text ~ "()";
        auto entrySource = "module z8gen.entry;\n\nimport " ~ moduleNameFor(ownerName) ~ ";\n\n";
        entrySource ~= target.returnType == ValueType.voidType ? "void main() {\n" ~ call ~ ";\n}\n" :
            "int main() {\nreturn cast(int)(" ~ call ~ ");\n}\n";
        output ~= GeneratedModule("z8gen.entry", "z8gen/entry.d", "", formatDSource(entrySource));
    }
    return output;
}

