module z8.compiler;

import std.algorithm : canFind;
import std.array : join;
import std.conv : to;
import std.format : format;
import std.string : replace;
import z8.lexer;

class CompileException : Exception {
    Position position;
    this(string message, Position position) { super(message); this.position = position; }
}

enum ValueType { voidType, intType, boolType, stringType }
enum ExprKind { integer, boolean, stringLiteral, variable, call, memberCall, unary, binary }
enum StmtKind { block, variable, assignment, expressionStmt, returnStmt, ifStmt,
                whileStmt, doWhileStmt, forStmt, breakStmt, continueStmt }

class Expression {
    ExprKind kind;
    Token token;
    Expression left, right;
    Expression[] arguments;
    ValueType inferredType;
    this(ExprKind kind, Token token) { this.kind = kind; this.token = token; }
}
class Statement {
    StmtKind kind;
    Token token;
    ValueType type;
    Expression expression;
    Statement[] children;
    Statement initial, step;
    string assignmentOperator;
    this(StmtKind kind, Token token) { this.kind = kind; this.token = token; }
}
struct Parameter { ValueType type; Token name; }
class Method {
    ValueType returnType;
    Token name;
    Parameter[] parameters;
    Statement body;
}
class Program { Token name; Method[] methods; }

class Parser {
    private Token[] tokens;
    private size_t index;
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
        switch (take().text) {
            case "void": return ValueType.voidType;
            case "int": return ValueType.intType;
            case "bool": return ValueType.boolType;
            case "string": return ValueType.stringType;
            default: throw new CompileException("only void, int, bool and string are supported", tokens[index-1].position);
        }
    }
    Program parse() {
        auto result = new Program;
        accept("public"); accept("final"); expect("class"); result.name = identifier(); expect("{");
        while (current.text != "}") {
            if (current.kind == TokenKind.endOfFile) error("expected '}'");
            bool isStatic;
            bool isPublic;
            while (current.text == "public" || current.text == "static") {
                if (current.text == "static") { if (isStatic) error("duplicate static modifier"); isStatic = true; }
                else { if (isPublic) error("duplicate public modifier"); isPublic = true; }
                take();
            }
            if (!isStatic) error("only static methods are supported");
            auto method = new Method;
            method.returnType = parseType(); method.name = identifier(); expect("(");
            if (current.text != ")") {
                do {
                    Parameter p; p.type = parseType(); p.name = identifier(); method.parameters ~= p;
                } while (accept(","));
            }
            expect(")"); method.body = statement();
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
            if (current.text != ";") s.expression = expression();
            expect(";"); return s;
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
        if ((t.text == "int" || t.text == "bool" || t.text == "string") && look(1).kind == TokenKind.identifier) {
            if (!allowDeclaration) error("variable declaration is not allowed here");
            auto s = new Statement(StmtKind.variable, t);
            s.type = parseType(); s.token = identifier();
            if (accept("=")) s.expression = expression();
            return s;
        }
        if (t.kind == TokenKind.identifier && ["=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^="].canFind(look(1).text)) {
            auto s = new Statement(StmtKind.assignment, take());
            s.assignmentOperator = take().text; s.expression = expression(); return s;
        }
        auto e = expression();
        if (e.kind != ExprKind.call) throw new CompileException("only method calls may be used as expression statements", e.token.position);
        auto s = new Statement(StmtKind.expressionStmt, t); s.expression = e; return s;
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
        return left;
    }
    private Expression unary() {
        auto t = current;
        if (["+", "-", "!", "~"].canFind(t.text)) {
            take(); auto result = new Expression(ExprKind.unary, t); result.left = unary(); return result;
        }
        auto result = atom();
        while (accept(".")) {
            auto member = new Expression(ExprKind.memberCall, identifier());
            member.left = result; expect("(");
            if (current.text != ")") do { member.arguments ~= expression(); } while (accept(","));
            expect(")"); result = member;
        }
        return result;
    }
    private Expression atom() {
        auto t = current;
        if (accept("(")) { auto result = expression(); expect(")"); return result; }
        if (t.kind == TokenKind.integerLiteral) { take(); return new Expression(ExprKind.integer, t); }
        if (t.kind == TokenKind.booleanLiteral) { take(); return new Expression(ExprKind.boolean, t); }
        if (t.kind == TokenKind.stringLiteral) { take(); return new Expression(ExprKind.stringLiteral, t); }
        if (t.kind == TokenKind.identifier) {
            take();
            if (accept("(")) {
                auto call = new Expression(ExprKind.call, t);
                if (current.text != ")") do { call.arguments ~= expression(); } while (accept(","));
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
    private ValueType[string] variables;
    private ValueType returnType;
    private size_t loopDepth;
    private void fail(string message, Token t) { throw new CompileException(message, t.position); }
    void check(Program program) {
        methods = null;
        foreach (m; program.methods) {
            if (m.name.text in methods) fail("duplicate or overloaded method", m.name);
            methods[m.name.text] = m;
        }
        foreach (m; program.methods) {
            variables = null; returnType = m.returnType; loopDepth = 0;
            foreach (p; m.parameters) {
                if (p.type == ValueType.voidType) fail("parameter cannot be void", p.name);
                if (p.name.text in variables) fail("duplicate parameter", p.name);
                variables[p.name.text] = p.type;
            }
            auto returns = checkStatement(m.body);
            if (returnType != ValueType.voidType && !returns) fail("method may finish without returning a value", m.name);
        }
    }
    private ValueType typeOf(Expression e) {
        final switch (e.kind) {
            case ExprKind.integer: return ValueType.intType;
            case ExprKind.boolean: return ValueType.boolType;
            case ExprKind.stringLiteral: return ValueType.stringType;
            case ExprKind.variable:
                auto variable = e.token.text in variables;
                if (variable is null) fail("unknown variable '" ~ e.token.text ~ "'", e.token);
                return *variable;
            case ExprKind.call:
                auto method = e.token.text in methods;
                if (method is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                if (e.arguments.length != (*method).parameters.length) fail("incorrect argument count", e.token);
                foreach (i, arg; e.arguments)
                    if (typeOf(arg) != (*method).parameters[i].type) fail("argument type mismatch", arg.token);
                return (*method).returnType;
            case ExprKind.memberCall:
                if (typeOf(e.left) != ValueType.stringType) fail("only string member methods are supported", e.token);
                if (e.arguments.length != 0) fail("incorrect argument count", e.token);
                if (e.token.text == "length") return ValueType.intType;
                if (e.token.text == "isEmpty") return ValueType.boolType;
                fail("unsupported string method '" ~ e.token.text ~ "'", e.token); assert(0);
            case ExprKind.unary:
                auto operand = typeOf(e.left);
                if (e.token.text == "!" && operand == ValueType.boolType) return operand;
                if (["+", "-", "~"].canFind(e.token.text) && operand == ValueType.intType) return operand;
                fail("invalid unary operand", e.token); assert(0);
            case ExprKind.binary:
                auto left = typeOf(e.left), right = typeOf(e.right), op = e.token.text;
                if (left != right || left == ValueType.voidType) fail("operand type mismatch", e.token);
                if (["==", "!="].canFind(op)) return ValueType.boolType;
                if ((left == ValueType.intType || left == ValueType.stringType) && ["<", ">", "<=", ">="].canFind(op)) return ValueType.boolType;
                if (left == ValueType.stringType && op == "+") { e.inferredType = ValueType.stringType; return ValueType.stringType; }
                if (left == ValueType.intType && ["+", "-", "*", "/", "%", "&", "|", "^"].canFind(op)) return ValueType.intType;
                if (left == ValueType.boolType && ["&&", "||"].canFind(op)) return ValueType.boolType;
                fail("invalid binary operands", e.token); assert(0);
        }
    }
    private bool checkStatement(Statement s) {
        final switch (s.kind) {
            case StmtKind.block:
                auto old = variables.dup; bool returns;
                foreach (child; s.children) { auto childReturns = checkStatement(child); returns = returns || childReturns; }
                variables = old; return returns;
            case StmtKind.variable:
                if (s.token.text in variables) fail("duplicate or shadowed variable", s.token);
                if (s.expression !is null && typeOf(s.expression) != s.type) fail("initializer type mismatch", s.token);
                variables[s.token.text] = s.type; return false;
            case StmtKind.assignment:
                auto variable = s.token.text in variables;
                if (variable is null) fail("unknown variable '" ~ s.token.text ~ "'", s.token);
                if (typeOf(s.expression) != *variable) fail("assignment type mismatch", s.token);
                s.type = *variable;
                if (s.assignmentOperator != "=" && *variable != ValueType.intType &&
                    !(*variable == ValueType.stringType && s.assignmentOperator == "+="))
                    fail("invalid compound assignment operands", s.token);
                return false;
            case StmtKind.expressionStmt:
                typeOf(s.expression); return false;
            case StmtKind.returnStmt:
                if (s.expression is null) { if (returnType != ValueType.voidType) fail("return value required", s.token); }
                else if (returnType == ValueType.voidType || typeOf(s.expression) != returnType) fail("return type mismatch", s.token);
                return true;
            case StmtKind.ifStmt:
                if (typeOf(s.expression) != ValueType.boolType) fail("if condition must be bool", s.token);
                auto old = variables.dup;
                auto first = checkStatement(s.children[0]); variables = old.dup;
                bool second;
                if (s.children.length == 2) second = checkStatement(s.children[1]);
                variables = old; return first && second;
            case StmtKind.whileStmt:
            case StmtKind.doWhileStmt:
                if (typeOf(s.expression) != ValueType.boolType) fail("loop condition must be bool", s.token);
                auto old = variables.dup;
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; return false;
            case StmtKind.forStmt:
                auto old = variables.dup;
                if (s.initial !is null) checkStatement(s.initial);
                if (typeOf(s.expression) != ValueType.boolType) fail("loop condition must be bool", s.token);
                checkStatement(s.step);
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; return false;
            case StmtKind.breakStmt:
            case StmtKind.continueStmt:
                if (loopDepth == 0) fail(s.token.text ~ " outside loop", s.token);
                return false;
        }
    }
}

private string dType(ValueType type) {
    final switch (type) {
        case ValueType.intType: return "long"; case ValueType.boolType: return "bool";
        case ValueType.voidType: return "void"; case ValueType.stringType: return "wstring";
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
        case ExprKind.variable: return "v_" ~ e.token.text;
        case ExprKind.call:
            string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
            return "m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
        case ExprKind.memberCall:
            auto value = "(" ~ emitExpr(e.left) ~ ").length";
            return e.token.text == "length" ? "cast(long)(" ~ value ~ ")" : "(" ~ value ~ " == 0)";
        case ExprKind.unary: return "(" ~ e.token.text ~ emitExpr(e.left) ~ ")";
        case ExprKind.binary:
            if (e.token.text == "/" || e.token.text == "%")
                return (e.token.text == "/" ? "z8_div(" : "z8_mod(") ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            return "(" ~ emitExpr(e.left) ~ " " ~ (e.token.text == "+" && e.inferredType == ValueType.stringType ? "~" : e.token.text) ~ " " ~ emitExpr(e.right) ~ ")";
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
        case StmtKind.breakStmt: return "break;\n";
        case StmtKind.continueStmt: return "continue;\n";
    }
}
private string emitSimple(Statement s) {
    if (s.kind == StmtKind.variable)
        return dType(s.type) ~ " v_" ~ s.token.text ~ " = " ~
            (s.expression !is null ? emitExpr(s.expression) : s.type == ValueType.intType ? "0" : s.type == ValueType.stringType ? `""w` : "false");
    if (s.kind == StmtKind.expressionStmt) return emitExpr(s.expression);
    assert(s.kind == StmtKind.assignment);
    auto name = "v_" ~ s.token.text;
    if (s.assignmentOperator == "/=" || s.assignmentOperator == "%=")
        return name ~ " = " ~ (s.assignmentOperator == "/=" ? "z8_div(" : "z8_mod(") ~ name ~ ", " ~ emitExpr(s.expression) ~ ")";
    auto op = s.type == ValueType.stringType && s.assignmentOperator == "+=" ? "~=" : s.assignmentOperator;
    return name ~ " " ~ op ~ " " ~ emitExpr(s.expression);
}
string compile(string source) {
    auto program = (new Parser(source)).parse();
    (new Checker).check(program);
    string result = `// Generated by z8-d. Supported Z8 subset only.
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
class Z8_` ~ program.name.text ~ " {\n";
    foreach (m; program.methods) {
        string[] params;
        foreach (p; m.parameters) params ~= dType(p.type) ~ " v_" ~ p.name.text;
        result ~= "static " ~ dType(m.returnType) ~ " m_" ~ m.name.text ~ "(" ~ params.join(", ") ~ ")\n" ~ emitStatement(m.body);
    }
    return result ~ "}\n";
}
