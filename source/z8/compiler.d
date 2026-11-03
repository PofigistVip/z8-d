module z8.compiler;

import std.algorithm : canFind;
import std.array : join;
import std.conv : to;
import std.format : format;
import std.string : replace, lastIndexOf;
import z8.lexer;

class CompileException : Exception {
    Position position;
    string sourceName;
    this(string message, Position position) { super(message); this.position = position; }
}

enum ValueType { voidType, intType, boolType, stringType, exceptionType, selfType, intArray, boolArray, stringArray }
enum ExprKind { integer, boolean, stringLiteral, arrayLiteral, variable, selfRef, superRef, newSelf, field, call, memberCall, index, unary, binary, conditional }
enum StmtKind { block, variable, assignment, expressionStmt, returnStmt, ifStmt,
                whileStmt, doWhileStmt, forStmt, forEachStmt, breakStmt, continueStmt, throwStmt, tryStmt }

class Expression {
    ExprKind kind;
    Token token;
    Expression left, right, third;
    Expression[] arguments;
    ValueType inferredType;
    string targetClass;
    bool isField, instanceCall;
    Program objectClass;
    this(ExprKind kind, Token token) { this.kind = kind; this.token = token; }
}
class Statement {
    StmtKind kind;
    Token token;
    ValueType type;
    Expression expression;
    Expression target;
    Statement[] children;
    Statement initial, step;
    string assignmentOperator;
    Token catchName;
    bool hasCatch, hasFinally;
    string objectName;
    Program objectClass;
    this(StmtKind kind, Token token) { this.kind = kind; this.token = token; }
}
struct Parameter { ValueType type; Token name; string objectName; Program objectClass; }
class Method {
    ValueType returnType;
    Token name;
    Parameter[] parameters;
    Statement body;
    bool isPublic, isProtected;
    bool isStatic;
    string returnObjectName;
    Program returnObjectClass;
    Program owner;
    bool isVirtual, overrides;
}
class Field { ValueType type; Token name; Expression initializer; bool isPublic, isProtected; string objectName; Program objectClass; Program owner; }
struct Import { string name; Token token; }
class Program {
    Token name;
    Method[] methods;
    Field[] fields;
    Import[] imports;
    string qualifiedName, sourceName, emittedName;
    string baseName;
    Token baseToken;
    Program baseClass;
    bool isFinal;
}
struct SourceUnit { string name, path, source; }

private bool isArray(ValueType type) {
    return [ValueType.intArray, ValueType.boolArray, ValueType.stringArray].canFind(type);
}
private ValueType elementType(ValueType type) {
    switch (type) {
        case ValueType.intArray: return ValueType.intType;
        case ValueType.boolArray: return ValueType.boolType;
        case ValueType.stringArray: return ValueType.stringType;
        default: assert(0, "not an array");
    }
}

class Parser {
    private Token[] tokens;
    private size_t index;
    private string className;
    private string parsedObjectName;
    this(string source) {
        auto lexer = new Lexer(source);
        do { tokens ~= lexer.next(); } while (tokens[$-1].kind != TokenKind.endOfFile);
    }
    private Token current() { return tokens[index]; }
    private Token look(size_t n) { return tokens[index + n < tokens.length ? index + n : $-1]; }
    private bool accept(string text) { if (current.text != text) return false; ++index; return true; }
    private Token take() { auto t = current; if (t.kind != TokenKind.endOfFile) ++index; return t; }
    private Token expect(string text) {
        if (current.text != text) error("expected '" ~ text ~ "'");
        return take();
    }
    private Token identifier() {
        if (current.kind != TokenKind.identifier) error("expected identifier");
        return take();
    }
    private void error(string message) { throw new CompileException(message, current.position); }
    private ValueType parseType() {
        ValueType result;
        auto token = take();
        parsedObjectName = "";
        switch (token.text) {
            case "void": result = ValueType.voidType; break;
            case "int": result = ValueType.intType; break;
            case "bool": result = ValueType.boolType; break;
            case "string": result = ValueType.stringType; break;
            case "exception": result = ValueType.exceptionType; break;
            default:
                if (token.kind == TokenKind.identifier) { result = ValueType.selfType; parsedObjectName = token.text; }
                else throw new CompileException("unsupported type", token.position);
        }
        if (accept("[")) {
            expect("]");
            switch (result) {
                case ValueType.intType: return ValueType.intArray;
                case ValueType.boolType: return ValueType.boolArray;
                case ValueType.stringType: return ValueType.stringArray;
                default: error("void arrays are not supported"); assert(0);
            }
        }
        return result;
    }
    Program parse() {
        auto result = new Program;
        while (current.text == "import") {
            auto start = take();
            string name = identifier().text;
            while (accept(".")) name ~= "." ~ identifier().text;
            expect(";"); result.imports ~= Import(name, start);
        }
        accept("public"); result.isFinal = accept("final"); expect("class"); result.name = identifier(); className = result.name.text;
        if (accept("extends")) { result.baseToken = identifier(); result.baseName = result.baseToken.text; }
        expect("{");
        while (current.text != "}") {
            if (current.kind == TokenKind.endOfFile) error("expected '}'");
            bool isStatic;
            bool isPublic = true, isProtected, hasAccess, isVirtual;
            while (["public", "private", "protected", "static", "virtual"].canFind(current.text)) {
                if (current.text == "static") { if (isStatic) error("duplicate static modifier"); isStatic = true; }
                else if (current.text == "virtual") { if (isVirtual) error("duplicate virtual modifier"); isVirtual = true; }
                else { if (hasAccess) error("duplicate access modifier"); hasAccess = true; isPublic = current.text == "public"; isProtected = current.text == "protected"; }
                take();
            }
            auto declaredType = parseType(); auto declaredObjectName = parsedObjectName; auto name = identifier();
            if (current.text != "(") {
                if (isStatic) error("static fields are not supported");
                if (isVirtual || declaredType == ValueType.voidType) error("this field type or modifier is not supported");
                auto field = new Field; field.type = declaredType; field.name = name; field.isPublic = isPublic; field.isProtected = isProtected; field.objectName = declaredObjectName; field.owner = result;
                if (accept("=")) field.initializer = initializer();
                expect(";"); result.fields ~= field; continue;
            }
            auto method = new Method;
            if (isVirtual && isStatic) error("a static method cannot be virtual");
            method.isPublic = isPublic; method.isProtected = isProtected; method.isStatic = isStatic; method.isVirtual = isVirtual; method.owner = result;
            method.returnType = declaredType; method.returnObjectName = declaredObjectName; method.name = name; expect("(");
            if (current.text != ")") {
                do {
                    Parameter p; p.type = parseType(); p.objectName = parsedObjectName; p.name = identifier(); method.parameters ~= p;
                } while (accept(","));
            }
            expect(")");
            if (method.name.text == "constructor") {
                if (method.isStatic || method.returnType != ValueType.voidType || method.parameters.length)
                    throw new CompileException("constructor must be an instance void method without parameters", method.name.position);
                method.isVirtual = true;
            }
            method.body = statement();
            if (method.body.kind != StmtKind.block)
                throw new CompileException("method body must be a block", method.body.token.position);
            result.methods ~= method;
        }
        expect("}");
        if (current.kind != TokenKind.endOfFile) error("only one class per file is supported");
        return result;
    }
    private Statement statement() {
        auto t = current;
        if (accept("{")) {
            auto s = new Statement(StmtKind.block, t);
            while (current.text != "}") {
                if (current.kind == TokenKind.endOfFile) error("expected '}'");
                s.children ~= statement();
            }
            expect("}"); return s;
        }
        if (accept("return")) {
            auto s = new Statement(StmtKind.returnStmt, t);
            if (current.text != ";") s.expression = initializer();
            expect(";"); return s;
        }
        if (accept("throw")) {
            auto s = new Statement(StmtKind.throwStmt, t); s.expression = expression(); expect(";"); return s;
        }
        if (accept("try")) {
            auto s = new Statement(StmtKind.tryStmt, t);
            if (current.text != "{") error("try requires a block");
            s.children ~= statement();
            if (accept("catch")) {
                s.hasCatch = true; expect("(");
                if (parseType() != ValueType.exceptionType) error("only exception catch is supported");
                s.catchName = identifier(); expect(")");
                if (current.text != "{") error("catch requires a block");
                s.children ~= statement();
            }
            if (accept("finally")) {
                s.hasFinally = true;
                if (current.text != "{") error("finally requires a block");
                s.children ~= statement();
            }
            if (!s.hasCatch && !s.hasFinally) error("try requires catch or finally");
            return s;
        }
        if (accept("if")) {
            auto s = new Statement(StmtKind.ifStmt, t);
            expect("("); s.expression = expression(); expect(")");
            s.children ~= statement();
            if (accept("else")) s.children ~= statement();
            return s;
        }
        if (accept("while")) {
            auto s = new Statement(StmtKind.whileStmt, t);
            expect("("); s.expression = expression(); expect(")"); s.children ~= statement(); return s;
        }
        if (accept("do")) {
            auto s = new Statement(StmtKind.doWhileStmt, t);
            s.children ~= statement(); expect("while"); expect("("); s.expression = expression(); expect(")"); expect(";");
            return s;
        }
        if (accept("for")) {
            auto s = new Statement(StmtKind.forStmt, t);
            expect("(");
            if (["int", "bool", "string"].canFind(current.text) && look(1).kind == TokenKind.identifier && look(2).text == ":") {
                s.kind = StmtKind.forEachStmt;
                auto item = new Statement(StmtKind.variable, current);
                item.type = parseType(); item.token = identifier(); s.initial = item;
                expect(":"); s.expression = expression(); expect(")"); s.children ~= statement(); return s;
            }
            if (current.text != ";") s.initial = simpleStatement(true);
            expect(";"); s.expression = expression(); expect(";");
            s.step = simpleStatement(false); expect(")"); s.children ~= statement(); return s;
        }
        if (accept("break")) { expect(";"); return new Statement(StmtKind.breakStmt, t); }
        if (accept("continue")) { expect(";"); return new Statement(StmtKind.continueStmt, t); }
        auto s = simpleStatement(true); expect(";"); return s;
    }
    private Statement simpleStatement(bool allowDeclaration) {
        auto t = current;
        if ((t.kind == TokenKind.identifier) &&
            (look(1).kind == TokenKind.identifier || (look(1).text == "[" && look(2).text == "]"))) {
            if (!allowDeclaration) error("variable declaration is not allowed here");
            auto s = new Statement(StmtKind.variable, t);
            s.type = parseType(); s.objectName = parsedObjectName; s.token = identifier();
            if (accept("=")) s.expression = initializer();
            return s;
        }
        auto e = expression();
        if (["=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^="].canFind(current.text)) {
            if (e.kind != ExprKind.variable && e.kind != ExprKind.index && e.kind != ExprKind.field)
                throw new CompileException("assignment target must be a variable or array element", e.token.position);
            auto s = new Statement(StmtKind.assignment, t);
            s.target = e; s.assignmentOperator = take().text; s.expression = initializer(); return s;
        }
        if (e.kind != ExprKind.call && e.kind != ExprKind.memberCall)
            throw new CompileException("only method calls may be used as expression statements", e.token.position);
        auto s = new Statement(StmtKind.expressionStmt, t); s.expression = e; return s;
    }
    private Expression initializer() {
        if (current.text != "{") return expression();
        auto init = new Expression(ExprKind.arrayLiteral, take());
        if (current.text != "}") {
            do {
                init.arguments ~= expression();
                if (current.text != ",") break;
                take();
            } while (current.text != "}");
        }
        expect("}"); return init;
    }
    private static int precedence(string op) {
        switch (op) {
            case "||": return 1; case "&&": return 2; case "|": return 3;
            case "^": return 4; case "&": return 5; case "==": case "!=": return 6;
            case "<": case ">": case "<=": case ">=": return 7;
            case "+": case "-": return 8; case "*": case "/": case "%": return 9;
            default: return 0;
        }
    }
    private Expression expression(int minPrecedence = 1) {
        auto left = unary();
        while (precedence(current.text) >= minPrecedence) {
            auto op = take(); auto p = precedence(op.text);
            auto node = new Expression(ExprKind.binary, op);
            node.left = left; node.right = expression(p + 1); left = node;
        }
        if (minPrecedence == 1 && current.text == "?") {
            auto node = new Expression(ExprKind.conditional, take());
            node.left = left; node.right = expression(); expect(":"); node.third = expression(); left = node;
        }
        return left;
    }
    private Expression unary() {
        auto t = current;
        if (["+", "-", "!", "~"].canFind(t.text)) {
            take(); auto result = new Expression(ExprKind.unary, t); result.left = unary(); return result;
        }
        auto result = atom();
        while (current.text == "." || current.text == "[") {
            if (accept("[")) {
                auto access = new Expression(ExprKind.index, tokens[index - 1]);
                access.left = result; access.right = expression(); expect("]"); result = access;
            } else {
                expect("."); auto member = new Expression(ExprKind.field, identifier());
                member.left = result;
                if (!accept("(")) { result = member; continue; }
                member.kind = ExprKind.memberCall;
                if (current.text != ")") do { member.arguments ~= initializer(); } while (accept(","));
                expect(")"); result = member;
            }
        }
        return result;
    }
    private Expression atom() {
        auto t = current;
        if (accept("(")) { auto result = expression(); expect(")"); return result; }
        if (accept("this")) return new Expression(ExprKind.selfRef, t);
        if (accept("super")) return new Expression(ExprKind.superRef, t);
        if (accept("new")) return new Expression(ExprKind.newSelf, identifier());
        if (t.kind == TokenKind.integerLiteral) { take(); return new Expression(ExprKind.integer, t); }
        if (t.kind == TokenKind.booleanLiteral) { take(); return new Expression(ExprKind.boolean, t); }
        if (t.kind == TokenKind.stringLiteral) { take(); return new Expression(ExprKind.stringLiteral, t); }
        if (t.kind == TokenKind.identifier) {
            take();
            if (accept("(")) {
                auto call = new Expression(ExprKind.call, t);
                if (current.text != ")") do { call.arguments ~= initializer(); } while (accept(","));
                expect(")"); return call;
            }
            return new Expression(ExprKind.variable, t);
        }
        error("unsupported expression"); assert(0);
    }
}

/// Checks the entire program before emitting code; unsupported constructs fail closed.
class Checker {
    private Method[string] methods;
    private Field[string] fields;
    private Program[string] visibleClasses;
    private Program[string] allClasses;
    private Program currentProgram;
    private bool staticContext;
    private ValueType[string] variables;
    private Program[string] objectVariables;
    private ValueType returnType;
    private Program returnObjectClass;
    private size_t loopDepth;
    private size_t finallyDepth;
    private void fail(string message, Token t) { throw new CompileException(message, t.position); }
    void bindBase(Program program, Program[string] programs) {
        currentProgram = program; allClasses = programs;
        if (program.baseName.length) {
            program.baseClass = resolveClass(program, program.baseName, program.baseToken);
            if (program.baseClass.isFinal) fail("cannot extend a final class", program.baseToken);
        }
    }
    private static Method lookupMethod(Program owner, string name) {
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (candidate; current.methods) if (candidate.name.text == name) return candidate;
        return null;
    }
    private static Field lookupField(Program owner, string name) {
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (candidate; current.fields) if (candidate.name.text == name) return candidate;
        return null;
    }
    private static bool isAssignable(Program actual, Program expected) {
        for (auto current = actual; current !is null; current = current.baseClass) if (current is expected) return true;
        return false;
    }
    private bool accessible(Program owner, bool isPublic, bool isProtected) {
        return owner is currentProgram || isPublic || (isProtected && isAssignable(currentProgram, owner));
    }
    private Program resolveClass(Program owner, string name, Token site) {
        if (name == owner.name.text) return owner;
        foreach (item; owner.imports) {
            auto found = item.name in allClasses;
            if (found !is null && (*found).name.text == name) return *found;
        }
        auto dot = owner.qualifiedName.lastIndexOf('.');
        auto qualified = (dot < 0 ? "" : owner.qualifiedName[0 .. dot + 1]) ~ name;
        auto found = qualified in allClasses;
        if (found is null) fail("unknown class '" ~ name ~ "'", site);
        return *found;
    }
    private bool matches(Expression e, ValueType expected, Program expectedClass = null) {
        auto actual = typeOf(e, expected);
        return actual == expected && (expected != ValueType.selfType || isAssignable(e.objectClass, expectedClass));
    }
    private ValueType checkCall(Method method, Program owner, Expression e) {
        if (e.arguments.length != method.parameters.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) {
            auto p = method.parameters[i];
            auto objectClass = p.type == ValueType.selfType ? resolveClass(owner, p.objectName, p.name) : null;
            if (!matches(arg, p.type, objectClass)) fail("argument type mismatch", arg.token);
        }
        if (method.returnType == ValueType.selfType)
            e.objectClass = resolveClass(owner, method.returnObjectName, method.name);
        return method.returnType;
    }
    void check(Program program, Program[string] allPrograms = null) {
        currentProgram = program;
        allClasses = allPrograms;
        visibleClasses = null;
        visibleClasses[program.name.text] = program;
        auto dot = program.qualifiedName.lastIndexOf('.');
        auto packageName = dot < 0 ? "" : program.qualifiedName[0 .. dot + 1];
        foreach (qualified, target; allPrograms) {
            auto targetDot = qualified.lastIndexOf('.');
            auto targetPackage = targetDot < 0 ? "" : qualified[0 .. targetDot + 1];
            if (targetPackage == packageName) visibleClasses[target.name.text] = target;
        }
        Program[string] imported;
        foreach (item; program.imports) {
            auto found = item.name in allPrograms;
            if (found is null) fail("unresolved import '" ~ item.name ~ "'", item.token);
            auto simpleName = (*found).name.text;
            auto oldImport = simpleName in imported;
            if (oldImport !is null && *oldImport !is *found) fail("ambiguous imports for '" ~ simpleName ~ "'", item.token);
            imported[simpleName] = *found;
            visibleClasses[simpleName] = *found;
        }
        methods = null;
        fields = null;
        for (auto base = program.baseClass; base !is null; base = base.baseClass) {
            foreach (field; base.fields) if (!(field.name.text in fields)) fields[field.name.text] = field;
            foreach (method; base.methods) if (!(method.name.text in methods)) methods[method.name.text] = method;
        }
        foreach (field; program.fields) {
            if (field.name.text in fields) fail("duplicate field", field.name);
            fields[field.name.text] = field;
        }
        foreach (m; program.methods) {
            auto inherited = m.name.text in methods;
            if (inherited !is null) {
                auto baseMethod = *inherited;
                if (baseMethod.owner is program) fail("duplicate or overloaded method", m.name);
                if (m.isStatic || baseMethod.isStatic || !baseMethod.isVirtual) fail("only virtual instance methods may be overridden", m.name);
                if (m.returnType != baseMethod.returnType || m.parameters.length != baseMethod.parameters.length)
                    fail("override signature mismatch", m.name);
                if (m.returnType == ValueType.selfType && resolveClass(program, m.returnObjectName, m.name) !is resolveClass(baseMethod.owner, baseMethod.returnObjectName, baseMethod.name))
                    fail("override return type mismatch", m.name);
                foreach (i, p; m.parameters) {
                    auto baseParam = baseMethod.parameters[i];
                    if (p.type != baseParam.type || (p.type == ValueType.selfType &&
                        resolveClass(program, p.objectName, p.name) !is resolveClass(baseMethod.owner, baseParam.objectName, baseParam.name)))
                        fail("override parameter type mismatch", p.name);
                }
                if (baseMethod.isPublic && !m.isPublic) fail("override cannot reduce public access", m.name);
                if (baseMethod.isProtected && !m.isPublic && !m.isProtected) fail("override cannot reduce protected access", m.name);
                m.isVirtual = true; m.overrides = true;
            }
            methods[m.name.text] = m;
        }
        variables = null; objectVariables = null; staticContext = false;
        foreach (field; program.fields)
            if (field.type == ValueType.selfType) field.objectClass = resolveClass(program, field.objectName, field.name);
        foreach (field; program.fields)
            if (field.initializer !is null && !matches(field.initializer, field.type, field.objectClass))
                fail("field initializer type mismatch", field.name);
        foreach (m; program.methods) {
            variables = null; objectVariables = null; returnType = m.returnType; loopDepth = 0; finallyDepth = 0; staticContext = m.isStatic;
            m.returnObjectClass = m.returnType == ValueType.selfType ? resolveClass(program, m.returnObjectName, m.name) : null;
            returnObjectClass = m.returnObjectClass;
            foreach (ref p; m.parameters) {
                if (p.type == ValueType.voidType) fail("parameter cannot be void", p.name);
                if (p.name.text in variables) fail("duplicate parameter", p.name);
                variables[p.name.text] = p.type;
                if (p.type == ValueType.selfType) {
                    p.objectClass = resolveClass(program, p.objectName, p.name);
                    objectVariables[p.name.text] = p.objectClass;
                }
            }
            auto returns = checkStatement(m.body);
            if (returnType != ValueType.voidType && !returns) fail("method may finish without returning a value", m.name);
        }
    }
    private ValueType typeOf(Expression e, ValueType expected = ValueType.voidType) {
        final switch (e.kind) {
            case ExprKind.integer: return ValueType.intType;
            case ExprKind.boolean: return ValueType.boolType;
            case ExprKind.stringLiteral: return ValueType.stringType;
            case ExprKind.arrayLiteral:
                if (!isArray(expected)) fail("array initializer requires an array type", e.token);
                foreach (element; e.arguments)
                    if (typeOf(element) != elementType(expected)) fail("array element type mismatch", element.token);
                e.inferredType = expected; return expected;
            case ExprKind.variable:
                auto variable = e.token.text in variables;
                if (variable is null) {
                    auto field = e.token.text in fields;
                    if (field is null) fail("unknown variable '" ~ e.token.text ~ "'", e.token);
                    if (!accessible((*field).owner, (*field).isPublic, (*field).isProtected)) fail("field is not accessible", e.token);
                    if (staticContext) fail("instance field in static context", e.token);
                    e.isField = true;
                    if ((*field).type == ValueType.selfType) e.objectClass = (*field).objectClass;
                    return (*field).type;
                }
                if (*variable == ValueType.selfType) e.objectClass = objectVariables[e.token.text];
                return *variable;
            case ExprKind.selfRef:
                if (staticContext) fail("this in static context", e.token);
                e.objectClass = currentProgram;
                return ValueType.selfType;
            case ExprKind.superRef:
                if (staticContext) fail("super in static context", e.token);
                if (currentProgram.baseClass is null) fail("super requires a base class", e.token);
                e.objectClass = currentProgram.baseClass;
                return ValueType.selfType;
            case ExprKind.newSelf:
                e.objectClass = resolveClass(currentProgram, e.token.text, e.token);
                return ValueType.selfType;
            case ExprKind.field:
                if (typeOf(e.left) != ValueType.selfType) fail("field access requires an object", e.token);
                auto field = lookupField(e.left.objectClass, e.token.text);
                if (field is null) fail("unknown field '" ~ e.token.text ~ "'", e.token);
                if (!accessible(field.owner, field.isPublic, field.isProtected)) fail("field is not accessible", e.token);
                if (field.type == ValueType.selfType)
                    e.objectClass = field.objectClass !is null ? field.objectClass : resolveClass(field.owner, field.objectName, field.name);
                return field.type;
            case ExprKind.call:
                auto method = e.token.text in methods;
                if (method is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                if (!accessible((*method).owner, (*method).isPublic, (*method).isProtected)) fail("method is not accessible", e.token);
                if (staticContext && !(*method).isStatic) fail("instance method in static context", e.token);
                return checkCall(*method, (*method).owner, e);
            case ExprKind.memberCall:
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields)) {
                    auto owner = e.left.token.text in visibleClasses;
                    if (owner is null) fail("unknown class or variable '" ~ e.left.token.text ~ "'", e.left.token);
                    auto target = lookupMethod(*owner, e.token.text);
                    if (target is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    if (!target.isStatic) fail("instance method cannot be called on a class", e.token);
                    e.targetClass = (*owner).emittedName;
                    return checkCall(target, target.owner, e);
                }
                auto receiver = typeOf(e.left);
                e.inferredType = receiver;
                if (receiver == ValueType.selfType) {
                    auto owner = e.left.objectClass;
                    auto target = lookupMethod(owner, e.token.text);
                    if (target is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    if (target.isStatic) fail("static method call through an instance is not supported", e.token);
                    e.instanceCall = true;
                    return checkCall(target, target.owner, e);
                } else if (receiver == ValueType.stringType) {
                    if (e.arguments.length != 0) fail("incorrect argument count", e.token);
                    if (e.token.text == "length") return ValueType.intType;
                    if (e.token.text == "isEmpty") return ValueType.boolType;
                } else if (receiver == ValueType.exceptionType) {
                    if (e.arguments.length != 0) fail("incorrect argument count", e.token);
                    if (e.token.text == "getMessage") return ValueType.stringType;
                } else if (isArray(receiver)) {
                    switch (e.token.text) {
                        case "size": case "isEmpty": case "clear":
                            if (e.arguments.length != 0) fail("incorrect argument count", e.token);
                            return e.token.text == "size" ? ValueType.intType : e.token.text == "isEmpty" ? ValueType.boolType : ValueType.voidType;
                        case "get":
                            if (e.arguments.length != 1 || typeOf(e.arguments[0]) != ValueType.intType) fail("get requires an int index", e.token);
                            return elementType(receiver);
                        case "add":
                            if (e.arguments.length != 1 || typeOf(e.arguments[0]) != elementType(receiver)) fail("add requires an element of the array type", e.token);
                            return receiver;
                        case "set":
                            if (e.arguments.length != 2 || typeOf(e.arguments[0]) != ValueType.intType ||
                                typeOf(e.arguments[1]) != elementType(receiver)) fail("set requires an int index and an element of the array type", e.token);
                            return ValueType.voidType;
                        default: break;
                    }
                }
                fail("unsupported member method '" ~ e.token.text ~ "'", e.token); assert(0);
            case ExprKind.index:
                auto array = typeOf(e.left);
                if (!isArray(array)) fail("indexing requires an array", e.token);
                if (typeOf(e.right) != ValueType.intType) fail("array index must be int", e.token);
                return elementType(array);
            case ExprKind.unary:
                auto operand = typeOf(e.left);
                if (e.token.text == "!" && operand == ValueType.boolType) return operand;
                if (["+", "-", "~"].canFind(e.token.text) && operand == ValueType.intType) return operand;
                fail("invalid unary operand", e.token); assert(0);
            case ExprKind.binary:
                auto left = typeOf(e.left), right = typeOf(e.right), op = e.token.text;
                if (left != right || left == ValueType.voidType || left == ValueType.exceptionType || left == ValueType.selfType || isArray(left)) fail("operand type mismatch", e.token);
                if (["==", "!="].canFind(op)) return ValueType.boolType;
                if ((left == ValueType.intType || left == ValueType.stringType) && ["<", ">", "<=", ">="].canFind(op)) return ValueType.boolType;
                if (left == ValueType.stringType && op == "+") { e.inferredType = ValueType.stringType; return ValueType.stringType; }
                if (left == ValueType.intType && ["+", "-", "*", "/", "%", "&", "|", "^"].canFind(op)) return ValueType.intType;
                if (left == ValueType.boolType && ["&&", "||"].canFind(op)) return ValueType.boolType;
                fail("invalid binary operands", e.token); assert(0);
            case ExprKind.conditional:
                if (typeOf(e.left) != ValueType.boolType) fail("conditional expression requires a bool condition", e.token);
                auto left = typeOf(e.right), right = typeOf(e.third);
                if (left == ValueType.voidType || left != right || (left == ValueType.selfType && e.right.objectClass !is e.third.objectClass))
                    fail("conditional branch type mismatch", e.token);
                if (left == ValueType.selfType) e.objectClass = e.right.objectClass;
                return left;
        }
    }
    private bool checkStatement(Statement s) {
        final switch (s.kind) {
            case StmtKind.block:
                auto old = variables.dup; auto oldObjects = objectVariables.dup; bool returns;
                foreach (child; s.children) { auto childReturns = checkStatement(child); returns = returns || childReturns; }
                variables = old; objectVariables = oldObjects; return returns;
            case StmtKind.variable:
                if (s.token.text in variables) fail("duplicate or shadowed variable", s.token);
                if (s.type == ValueType.voidType) fail("variable cannot be void", s.token);
                if (s.type == ValueType.selfType) s.objectClass = resolveClass(currentProgram, s.objectName, s.token);
                if (s.expression !is null && !matches(s.expression, s.type, s.objectClass)) fail("initializer type mismatch", s.token);
                variables[s.token.text] = s.type;
                if (s.type == ValueType.selfType) objectVariables[s.token.text] = s.objectClass;
                return false;
            case StmtKind.assignment:
                auto variableType = typeOf(s.target);
                if (!matches(s.expression, variableType, s.target.objectClass)) fail("assignment type mismatch", s.token);
                s.type = variableType;
                if (s.assignmentOperator != "=" && variableType != ValueType.intType &&
                    !(variableType == ValueType.stringType && s.assignmentOperator == "+="))
                    fail("invalid compound assignment operands", s.token);
                return false;
            case StmtKind.expressionStmt:
                typeOf(s.expression);
                if (s.expression.kind == ExprKind.memberCall && s.expression.inferredType == ValueType.stringType)
                    fail("string query cannot be used as a statement", s.token);
                return false;
            case StmtKind.returnStmt:
                if (finallyDepth) fail("return inside finally is not supported", s.token);
                if (s.expression is null) { if (returnType != ValueType.voidType) fail("return value required", s.token); }
                else if (returnType == ValueType.voidType || !matches(s.expression, returnType, returnObjectClass)) fail("return type mismatch", s.token);
                return true;
            case StmtKind.ifStmt:
                if (typeOf(s.expression) != ValueType.boolType) fail("if condition must be bool", s.token);
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                auto first = checkStatement(s.children[0]); variables = old.dup; objectVariables = oldObjects.dup;
                bool second;
                if (s.children.length == 2) second = checkStatement(s.children[1]);
                variables = old; objectVariables = oldObjects; return first && second;
            case StmtKind.whileStmt:
            case StmtKind.doWhileStmt:
                if (typeOf(s.expression) != ValueType.boolType) fail("loop condition must be bool", s.token);
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; return false;
            case StmtKind.forStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                if (s.initial !is null) checkStatement(s.initial);
                if (typeOf(s.expression) != ValueType.boolType) fail("loop condition must be bool", s.token);
                checkStatement(s.step);
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; return false;
            case StmtKind.forEachStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                auto array = typeOf(s.expression);
                if (!isArray(array) || elementType(array) != s.initial.type) fail("foreach element type mismatch", s.token);
                checkStatement(s.initial);
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; return false;
            case StmtKind.breakStmt:
            case StmtKind.continueStmt:
                if (loopDepth == 0) fail(s.token.text ~ " outside loop", s.token);
                if (finallyDepth) fail(s.token.text ~ " inside finally is not supported", s.token);
                return false;
            case StmtKind.throwStmt:
                s.type = typeOf(s.expression);
                if (s.type != ValueType.exceptionType && s.type != ValueType.stringType) fail("throw requires exception or string", s.token);
                return true;
            case StmtKind.tryStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                auto tryReturns = checkStatement(s.children[0]);
                bool catchReturns = true, finallyReturns;
                if (s.hasCatch) {
                    variables = old.dup; objectVariables = oldObjects.dup;
                    if (s.catchName.text in variables) fail("duplicate or shadowed variable", s.catchName);
                    variables[s.catchName.text] = ValueType.exceptionType;
                    catchReturns = checkStatement(s.children[1]);
                }
                variables = old.dup; objectVariables = oldObjects.dup;
                if (s.hasFinally) {
                    ++finallyDepth; finallyReturns = checkStatement(s.children[$-1]); --finallyDepth;
                }
                variables = old; objectVariables = oldObjects;
                return (tryReturns && catchReturns) || finallyReturns;
        }
    }
}

private string dType(ValueType type, Program objectClass = null) {
    final switch (type) {
        case ValueType.intType: return "long"; case ValueType.boolType: return "bool";
        case ValueType.voidType: return "void"; case ValueType.stringType: return "wstring";
        case ValueType.exceptionType: return "Throwable";
        case ValueType.selfType: assert(objectClass !is null); return objectClass.emittedName;
        case ValueType.intArray: return "Z8Array!long";
        case ValueType.boolArray: return "Z8Array!bool";
        case ValueType.stringArray: return "Z8Array!wstring";
    }
}
/// The Java runtime stores strings as UTF-16; preserve its code-unit ordering.
private string emitStringLiteral(string text) {
    auto raw = text.to!wstring;
    wchar[] value;
    for (size_t i = 1; i + 1 < raw.length; ++i) {
        wchar c = raw[i];
        if (c == '\\') {
            c = raw[++i];
            switch (c) {
                case 'b': c = '\b'; break; case 'f': c = '\f'; break;
                case 'n': c = '\n'; break; case 'r': c = '\r'; break; case 't': c = '\t'; break;
                default: break; // lexer has validated quotes and backslash
            }
            value ~= c;
        } else if (c >= ' ' || c == '\t' || c == '\r' || c == '\n') value ~= c;
    }
    if (value.length == 0) return `""w`;
    string[] units;
    foreach (c; value) units ~= format("cast(wchar)0x%04X", cast(uint)c);
    return "[" ~ units.join(", ") ~ "].idup";
}
private string emitExpr(Expression e) {
    final switch (e.kind) {
        case ExprKind.integer:
            return "(cast(long)(" ~ e.token.text.replace(" ", "").replace("\t", "") ~ "))";
        case ExprKind.boolean: return e.token.text;
        case ExprKind.stringLiteral: return emitStringLiteral(e.token.text);
        case ExprKind.arrayLiteral:
            string[] elements; foreach (element; e.arguments) elements ~= emitExpr(element);
            return "new " ~ dType(e.inferredType) ~ "(" ~ (elements.length ? "[" ~ elements.join(", ") ~ "]" : "") ~ ")";
        case ExprKind.variable: return e.isField ? "this.f_" ~ e.token.text : "v_" ~ e.token.text;
        case ExprKind.selfRef: return "this";
        case ExprKind.superRef: return "super";
        case ExprKind.newSelf: return "z8_new!(" ~ e.objectClass.emittedName ~ ")()";
        case ExprKind.field: return "(" ~ emitExpr(e.left) ~ ").f_" ~ e.token.text;
        case ExprKind.call:
            string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
            return "m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
        case ExprKind.memberCall:
            if (e.instanceCall) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "(" ~ emitExpr(e.left) ~ ").m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
            }
            if (e.targetClass.length) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return e.targetClass ~ ".m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
            }
            if (isArray(e.inferredType)) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "(" ~ emitExpr(e.left) ~ ").z8_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
            }
            if (e.inferredType == ValueType.exceptionType) return "z8_message(" ~ emitExpr(e.left) ~ ")";
            auto value = "(" ~ emitExpr(e.left) ~ ").length";
            return e.token.text == "length" ? "cast(long)(" ~ value ~ ")" : "(" ~ value ~ " == 0)";
        case ExprKind.index:
            return "(" ~ emitExpr(e.left) ~ ").z8_at(" ~ emitExpr(e.right) ~ ")";
        case ExprKind.unary: return "(" ~ e.token.text ~ emitExpr(e.left) ~ ")";
        case ExprKind.binary:
            if (e.token.text == "/" || e.token.text == "%")
                return (e.token.text == "/" ? "z8_div(" : "z8_mod(") ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            return "(" ~ emitExpr(e.left) ~ " " ~ (e.token.text == "+" && e.inferredType == ValueType.stringType ? "~" : e.token.text) ~ " " ~ emitExpr(e.right) ~ ")";
        case ExprKind.conditional:
            return "(" ~ emitExpr(e.left) ~ " ? " ~ emitExpr(e.right) ~ " : " ~ emitExpr(e.third) ~ ")";
    }
}
private string emitStatement(Statement s) {
    final switch (s.kind) {
        case StmtKind.block:
            string result = "{\n"; foreach (child; s.children) result ~= emitStatement(child); return result ~ "}\n";
        case StmtKind.variable:
        case StmtKind.assignment:
        case StmtKind.expressionStmt: return emitSimple(s) ~ ";\n";
        case StmtKind.returnStmt: return "return" ~ (s.expression is null ? "" : " " ~ emitExpr(s.expression)) ~ ";\n";
        case StmtKind.ifStmt:
            auto result = "if (" ~ emitExpr(s.expression) ~ ") {\n" ~ emitStatement(s.children[0]) ~ "}\n";
            if (s.children.length == 2) result ~= "else {\n" ~ emitStatement(s.children[1]) ~ "}\n";
            return result;
        case StmtKind.whileStmt:
            return "while (" ~ emitExpr(s.expression) ~ ") {\n" ~ emitStatement(s.children[0]) ~ "}\n";
        case StmtKind.doWhileStmt:
            return "do {\n" ~ emitStatement(s.children[0]) ~ "} while (" ~ emitExpr(s.expression) ~ ");\n";
        case StmtKind.forStmt:
            return "for (" ~ (s.initial is null ? "" : emitSimple(s.initial)) ~ "; " ~ emitExpr(s.expression) ~ "; " ~ emitSimple(s.step) ~ ") {\n" ~ emitStatement(s.children[0]) ~ "}\n";
        case StmtKind.forEachStmt:
            auto suffix = s.token.position.offset.to!string;
            auto iter = "z8_iter_" ~ suffix, versionName = "z8_version_" ~ suffix, indexName = "z8_index_" ~ suffix;
            return "{\nauto " ~ iter ~ " = " ~ emitExpr(s.expression) ~ ";\nauto " ~ versionName ~ " = " ~ iter ~ ".z8_version;\n" ~
                "for (long " ~ indexName ~ " = 0; " ~ indexName ~ " != " ~ iter ~ ".z8_size(); ++" ~ indexName ~ ") {\n" ~
                "if (" ~ versionName ~ " != " ~ iter ~ ".z8_version) throw new Exception(\"array modified during iteration\");\n" ~
                dType(s.initial.type) ~ " v_" ~ s.initial.token.text ~ " = " ~ iter ~ ".z8_get(" ~ indexName ~ ");\n" ~
                emitStatement(s.children[0]) ~ "}\n}\n";
        case StmtKind.breakStmt: return "break;\n";
        case StmtKind.continueStmt: return "continue;\n";
        case StmtKind.throwStmt:
            return "throw " ~ (s.type == ValueType.stringType ? "new Exception(z8_to_utf8(" ~ emitExpr(s.expression) ~ "))" : emitExpr(s.expression)) ~ ";\n";
        case StmtKind.tryStmt:
            auto result = "try " ~ emitStatement(s.children[0]);
            if (s.hasCatch) result ~= "catch (Throwable v_" ~ s.catchName.text ~ ") " ~ emitStatement(s.children[1]);
            if (s.hasFinally) result ~= "finally " ~ emitStatement(s.children[$-1]);
            return result;
    }
}
private string emitSimple(Statement s) {
    if (s.kind == StmtKind.variable)
        return dType(s.type, s.objectClass) ~ " v_" ~ s.token.text ~ " = " ~
            (s.expression !is null ? emitExpr(s.expression) : defaultValue(s.type, s.objectClass));
    if (s.kind == StmtKind.expressionStmt) return emitExpr(s.expression);
    assert(s.kind == StmtKind.assignment);
    auto name = emitExpr(s.target);
    if (s.assignmentOperator == "/=" || s.assignmentOperator == "%=")
        return (s.assignmentOperator == "/=" ? "z8_div_assign(" : "z8_mod_assign(") ~ name ~ ", " ~ emitExpr(s.expression) ~ ")";
    auto op = s.type == ValueType.stringType && s.assignmentOperator == "+=" ? "~=" : s.assignmentOperator;
    return name ~ " " ~ op ~ " " ~ emitExpr(s.expression);
}
private string defaultValue(ValueType type, Program objectClass = null) {
    if (type == ValueType.exceptionType) return "new Exception(null)";
    if (type == ValueType.selfType) return "z8_new!(" ~ dType(type, objectClass) ~ ")()";
    if (isArray(type)) return "new " ~ dType(type, objectClass) ~ "()";
    if (type == ValueType.intType) return "0";
    if (type == ValueType.stringType) return `""w`;
    assert(type == ValueType.boolType); return "false";
}
string compile(string source) {
    auto program = (new Parser(source)).parse();
    program.qualifiedName = program.name.text;
    program.emittedName = "Z8_" ~ program.name.text;
    Program[string] programs;
    programs[program.qualifiedName] = program;
    prepareInheritance([program], programs);
    (new Checker).check(program, programs);
    checkDefaultConstruction([program]);
    return emitPrograms([program]);
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

/// Prevent unbounded recursive allocation of automatically created object fields.
private void checkDefaultConstruction(Program[] programs) {
    bool[string] active, finished;
    void visit(Program program) {
        if (program.qualifiedName in finished) return;
        active[program.qualifiedName] = true;
        if (program.baseClass !is null) {
            if (program.baseClass.qualifiedName in active) {
                auto error = new CompileException("recursive automatic object construction", program.baseToken.position);
                error.sourceName = program.sourceName; throw error;
            }
            visit(program.baseClass);
        }
        foreach (field; program.fields) {
            if (field.type != ValueType.selfType) continue;
            Program target;
            if (field.initializer is null) target = field.objectClass;
            else if (field.initializer.kind == ExprKind.newSelf) target = field.initializer.objectClass;
            if (target is null) continue;
            if (target.qualifiedName in active) {
                auto error = new CompileException("recursive automatic object construction", field.name.position);
                error.sourceName = program.sourceName; throw error;
            }
            visit(target);
        }
        active.remove(program.qualifiedName);
        finished[program.qualifiedName] = true;
    }
    foreach (program; programs) visit(program);
}

/// Each unit name is the dotted path of the .bl file relative to the source root.
string compileSources(SourceUnit[] units, string entry = "") {
    if (!units.length) throw new CompileException("no .bl source files found", Position.init);
    Program[] ordered;
    Program[string] programs;
    foreach (unit; units) {
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
        program.qualifiedName = unit.name;
        program.emittedName = "Z8p_";
        foreach (i; 0 .. unit.name.length) program.emittedName ~= format("%02X", cast(ubyte)unit.name[i]);
        programs[unit.name] = program;
        ordered ~= program;
    }
    prepareInheritance(ordered, programs);
    bool[string] checked;
    void checkInOrder(Program program) {
        if (program.qualifiedName in checked) return;
        if (program.baseClass !is null) checkInOrder(program.baseClass);
        try { (new Checker).check(program, programs); }
        catch (CompileException e) { e.sourceName = program.sourceName; throw e; }
        checked[program.qualifiedName] = true;
    }
    foreach (program; ordered) checkInOrder(program);
    checkDefaultConstruction(ordered);
    auto output = emitPrograms(ordered);
    if (entry.length) {
        auto dot = entry.lastIndexOf('.');
        if (dot <= 0 || dot + 1 == entry.length)
            throw new CompileException("entry must be a qualified class and method name", Position.init);
        auto ownerName = entry[0 .. dot];
        auto methodName = entry[dot + 1 .. $];
        auto owner = ownerName in programs;
        if (owner is null) throw new CompileException("entry class not found: " ~ ownerName, Position.init);
        Method target;
        foreach (candidate; (*owner).methods) if (candidate.name.text == methodName) { target = candidate; break; }
        if (target is null) throw new CompileException("entry method not found: " ~ entry, Position.init);
        if (!target.isPublic || !target.isStatic || target.parameters.length != 0 ||
            (target.returnType != ValueType.voidType && target.returnType != ValueType.intType)) {
            auto error = new CompileException("entry must be a public static method with no parameters returning void or int", target.name.position);
            error.sourceName = (*owner).sourceName; throw error;
        }
        auto call = (*owner).emittedName ~ ".m_" ~ target.name.text ~ "()";
        output ~= target.returnType == ValueType.voidType ? "\nvoid main() { " ~ call ~ "; }\n" :
            "\nint main() { return cast(int)(" ~ call ~ "); }\n";
    }
    return output;
}

private string emitPrograms(Program[] programs) {
    string result = `// Generated by z8-d. Supported Z8 subset only.
private import std.conv : to;
private string z8_to_utf8(wstring value) { return value.to!string; }
private wstring z8_message(Throwable value) { return value.msg.to!wstring; }
private T z8_new(T)() {
    auto value = new T();
    static if (__traits(hasMember, T, "m_constructor")) value.m_constructor();
    return value;
}
private long z8_div(long a, long b) {
    if (b == 0) throw new Exception("division by zero");
    if (a == long.min && b == -1) return long.min;
    return a / b;
}
private long z8_mod(long a, long b) {
    if (b == 0) throw new Exception("division by zero");
    if (a == long.min && b == -1) return 0;
    return a % b;
}
private void z8_div_assign(ref long a, long b) { a = z8_div(a, b); }
private void z8_mod_assign(ref long a, long b) { a = z8_mod(a, b); }
class Z8Array(T) {
    private T[] items;
    size_t z8_version;
    this() {}
    this(T[] values) { items = values; }
    long z8_size() { return cast(long)items.length; }
    bool z8_isEmpty() { return items.length == 0; }
    void z8_clear() { ++z8_version; items.length = 0; }
    Z8Array!T z8_add(T value) { ++z8_version; items ~= value; return this; }
    ref T z8_at(long index) {
        auto i = cast(int)index;
        if (i < 0 || cast(size_t)i >= items.length) throw new Exception("array index out of bounds");
        return items[i];
    }
    T z8_get(long index) { return z8_at(index); }
    void z8_set(long index, T value) { z8_at(index) = value; }
}
`;
    foreach (program; programs) {
        result ~= "class " ~ program.emittedName ~ (program.baseClass is null ? "" : " : " ~ program.baseClass.emittedName) ~ " {\n";
        result ~= "alias Z8Self = " ~ program.emittedName ~ ";\n";
        foreach (field; program.fields) result ~= dType(field.type, field.objectClass) ~ " f_" ~ field.name.text ~ ";\n";
        if (program.fields.length) {
            result ~= "this() {\n";
            foreach (field; program.fields)
                if (field.initializer is null) result ~= "this.f_" ~ field.name.text ~ " = " ~ defaultValue(field.type, field.objectClass) ~ ";\n";
            foreach (field; program.fields)
                if (field.initializer !is null) result ~= "this.f_" ~ field.name.text ~ " = " ~ emitExpr(field.initializer) ~ ";\n";
            result ~= "}\n";
        }
        foreach (m; program.methods) {
            string[] params;
            foreach (p; m.parameters) params ~= dType(p.type, p.objectClass) ~ " v_" ~ p.name.text;
            auto modifiers = m.isStatic ? "static " : m.overrides ? "override " : m.isVirtual ? "" : "final ";
            result ~= modifiers ~ dType(m.returnType, m.returnObjectClass) ~ " m_" ~ m.name.text ~ "(" ~ params.join(", ") ~ ")\n" ~ emitStatement(m.body);
        }
        result ~= "}\n";
    }
    return result;
}
