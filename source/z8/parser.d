module z8.parser;

import std.algorithm : canFind;
import z8.compiler_model;
import z8.lexer;

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
    private Token qualifiedIdentifier() {
        auto result = identifier();
        while (accept(".")) {
            auto part = identifier();
            result.text ~= "." ~ part.text;
            result.position.length = part.position.offset + part.position.length - result.position.offset;
        }
        return result;
    }
    // Look past a supported type without consuming it; zero means no type.
    private size_t afterType(size_t i = 0) {
        if (look(i).kind != TokenKind.identifier) return 0;
        ++i;
        while (look(i).text == "." && look(i + 1).kind == TokenKind.identifier) i += 2;
        while (look(i).text == "[") {
            ++i;
            if (look(i).text != "]") ++i;
            if (look(i).text != "]") return 0;
            ++i;
        }
        return i;
    }
    // A for-each initializer is a declarator, including optional final and array types.
    private bool isForEachStart() {
        auto i = afterType(current.text == "final" ? 1 : 0);
        return i != 0 && look(i).kind == TokenKind.identifier && look(i + 1).text == ":";
    }
    private bool isTypedInitializerStart() {
        auto i = afterType();
        return i != 0 && look(i - 1).text == "]" && look(i).text == "{";
    }
    private void error(string message) { throw new CompileException(message, current.position); }
    private ValueType parseType() {
        ValueType result;
        auto token = current.kind == TokenKind.identifier ? qualifiedIdentifier() : take();
        parsedObjectName = "";
        switch (token.text) {
            case "void": result = ValueType.voidType; break;
            case "int": result = ValueType.intType; break;
            case "decimal": result = ValueType.decimalType; break;
            case "bool": result = ValueType.boolType; break;
            case "string": result = ValueType.stringType; break;
            case "guid": result = ValueType.guidType; break;
            case "binary": result = ValueType.binaryType; break;
            case "datespan": result = ValueType.datespanType; break;
            case "date": result = ValueType.dateType; break;
            case "geometry": result = ValueType.geometryType; break;
            case "file": result = ValueType.fileType; break;
            case "exception": result = ValueType.exceptionType; break;
            case "encoding": result = ValueType.encodingType; break;
            case "primary": result = ValueType.primaryType; break;
            default:
                if (token.kind == TokenKind.identifier) { result = ValueType.selfType; parsedObjectName = token.text; }
                else throw new CompileException("unsupported type", token.position);
        }
        if (accept("[")) {
            if (current.text != "]") {
                if (accept("string") && (result == ValueType.stringType || result == ValueType.primaryType)) {
                    expect("]"); return result == ValueType.stringType ? ValueType.stringMap : ValueType.primaryStringMap;
                }
                if (accept("int") && (result == ValueType.intType || result == ValueType.stringType)) {
                    expect("]"); return result == ValueType.intType ? ValueType.intIntMap : ValueType.stringIntMap;
                }
                error("unsupported map key or value type");
            }
            expect("]");
            switch (result) {
                case ValueType.intType: return ValueType.intArray;
                case ValueType.decimalType:
                    if (accept("[")) { expect("]"); return ValueType.decimalMatrix; }
                    return ValueType.decimalArray;
                case ValueType.boolType: return ValueType.boolArray;
                case ValueType.stringType: return ValueType.stringArray;
                case ValueType.primaryType: return ValueType.primaryArray;
                case ValueType.guidType: return ValueType.guidArray;
                case ValueType.binaryType: return ValueType.binaryArray;
                case ValueType.datespanType: return ValueType.datespanArray;
                case ValueType.dateType: return ValueType.dateArray;
                case ValueType.geometryType: return ValueType.geometryArray;
                case ValueType.fileType: return ValueType.fileArray;
                case ValueType.exceptionType: return ValueType.exceptionArray;
                case ValueType.selfType: return ValueType.selfArray;
                default: error("this array element type is not supported"); assert(0);
            }
        }
        return result;
    }
    private void parseRecords(Program program) {
        expect("{");
        while (current.text != "}") {
            if (current.text == "[") error("record attributes are not supported yet");
            bool isPublic, isProtected, hasAccess;
            while (["public", "private", "protected"].canFind(current.text)) {
                if (hasAccess) error("duplicate access modifier");
                hasAccess = true; isPublic = current.text == "public"; isProtected = current.text == "protected";
                take();
            }
            if (current.text == "[") error("record attributes are not supported yet");
            auto name = identifier();
            expect("=");
            if (current.kind != TokenKind.guidLiteral) error("record requires a GUID literal");
            auto value = new Expression(ExprKind.guidLiteral, take());
            expect(";");
            auto field = new Field;
            field.type = ValueType.guidType; field.name = name; field.initializer = value;
            field.isStatic = true; field.isRecord = true; field.isPublic = isPublic || !hasAccess; field.isProtected = isProtected; field.owner = program;
            program.fields ~= field;
        }
        expect("}");
    }
    Program parse() {
        auto result = new Program;
        while (current.text == "import") {
            auto start = take();
            string name = identifier().text;
            while (accept(".")) name ~= "." ~ identifier().text;
            expect(";"); result.imports ~= Import(name, start);
        }
        bool nativeAttribute;
        if (accept("[")) {
            if (current.text != "native") error("only native enum attributes are supported");
            take();
            if (current.kind != TokenKind.stringLiteral) error("native attribute requires a string");
            take(); expect("]"); nativeAttribute = true;
        }
        accept("public"); result.isFinal = accept("final");
        result.isEnum = accept("enum");
        if (!result.isEnum) expect("class");
        if (nativeAttribute && !result.isEnum) error("native classes are not supported");
        result.name = identifier(); className = result.name.text;
        if (result.isEnum) {
            expect("{");
            if (current.text != "}") {
                do {
                    auto value = identifier();
                    foreach (old; result.enumValues) if (old.text == value.text) throw new CompileException("duplicate enum value", value.position);
                    result.enumValues ~= value;
                    if (!accept(",")) break;
                    // The original grammar accepts repeated separators after an enum value.
                    while (accept(",")) {}
                } while (current.text != "}");
            }
            expect("}");
            if (current.kind != TokenKind.endOfFile) error("only one type per file is supported");
            return result;
        }
        if (accept("extends")) { result.baseToken = qualifiedIdentifier(); result.baseName = result.baseToken.text; }
        expect("{");
        while (current.text != "}") {
            if (current.kind == TokenKind.endOfFile) error("expected '}'");
            bool isStatic, isAuto;
            bool isPublic = true, isProtected, hasAccess, isVirtual;
            while (["public", "private", "protected", "static", "virtual", "auto"].canFind(current.text)) {
                if (current.text == "static") { if (isStatic) error("duplicate static modifier"); isStatic = true; }
                else if (current.text == "auto") { if (isAuto) error("duplicate auto modifier"); isAuto = true; }
                else if (current.text == "virtual") { if (isVirtual) error("duplicate virtual modifier"); isVirtual = true; }
                else { if (hasAccess) error("duplicate access modifier"); hasAccess = true; isPublic = current.text == "public"; isProtected = current.text == "protected"; }
                take();
            }
            if (accept("records")) { parseRecords(result); continue; }
            auto declaredFinal = accept("final");
            auto declaredType = parseType(); auto declaredObjectName = parsedObjectName; auto name = identifier();
            if (current.text != "(") {
                if (isVirtual || declaredType == ValueType.voidType) error("this field type or modifier is not supported");
                if (isStatic && (declaredType == ValueType.selfArray || declaredType == ValueType.exceptionType || isMap(declaredType)))
                    error("static object fields are not supported");
                auto field = new Field; field.type = declaredType; field.name = name; field.isPublic = isPublic; field.isProtected = isProtected; field.isStatic = isStatic; field.isAuto = isAuto; field.declaredFinal = declaredFinal; field.objectName = declaredObjectName; field.owner = result;
                if (accept("=")) field.initializer = initializer();
                expect(";"); result.fields ~= field; continue;
            }
            if (isAuto) error("auto cannot be applied to a method");
            if (declaredFinal) error("final methods are not supported by BL");
            auto method = new Method;
            if (isVirtual && isStatic) error("a static method cannot be virtual");
            method.isPublic = isPublic; method.isProtected = isProtected; method.isStatic = isStatic; method.isVirtual = isVirtual; method.owner = result;
            method.returnType = declaredType; method.returnObjectName = declaredObjectName; method.name = name; expect("(");
            if (current.text != ")") {
                do {
                    Parameter p; p.declaredFinal = accept("final"); p.type = parseType(); p.objectName = parsedObjectName; p.name = identifier(); method.parameters ~= p;
                } while (accept(","));
            }
            expect(")");
            if (method.name.text == "constructor") {
                if (method.isStatic || method.returnType != ValueType.voidType || method.parameters.length)
                    throw new CompileException("constructor must be an instance void method without parameters", method.name.position);
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
                s.catchDeclaredFinal = accept("final");
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
            if (isForEachStart()) {
                s.kind = StmtKind.forEachStmt;
                auto item = new Statement(StmtKind.variable, current);
                item.declaredFinal = accept("final");
                item.type = parseType(); item.objectName = parsedObjectName; item.token = identifier(); s.initial = item;
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
        bool declaredFinal = accept("final");
        auto t = current;
        auto typeEnd = afterType();
        if (typeEnd != 0 && look(typeEnd).kind == TokenKind.identifier) {
            if (!allowDeclaration) error("variable declaration is not allowed here");
            auto s = new Statement(StmtKind.variable, t);
            s.declaredFinal = declaredFinal;
            s.type = parseType(); s.objectName = parsedObjectName; s.token = identifier();
            if (accept("=")) s.expression = initializer();
            return s;
        }
        if (declaredFinal) error("final must precede a variable declaration");
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
                init.arguments ~= initializerElement();
                if (current.text != ",") break;
                take();
            } while (current.text != "}");
        }
        expect("}"); return init;
    }
    private Expression initializerElement() {
        if (current.text == "(") {
            auto start = index;
            auto token = take();
            auto key = expression();
            if (accept(",")) {
                auto pair = new Expression(ExprKind.mapEntry, token);
                pair.left = key; pair.right = initializer();
                expect(")"); return pair;
            }
            index = start;
        }
        return initializer();
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
        else if (minPrecedence == 1 && current.text == "?:") {
            auto node = new Expression(ExprKind.elvis, take());
            node.left = left; node.right = initializer(); left = node;
        }
        if (minPrecedence == 1 && accept("instanceof")) {
            auto node = new Expression(ExprKind.instanceOf, qualifiedIdentifier());
            node.left = left; left = node;
        }
        return left;
    }
    private Expression unary() {
        auto t = current;
        if (["+", "-", "!", "~"].canFind(t.text)) {
            take(); auto result = new Expression(ExprKind.unary, t); result.left = unary(); return result;
        }
        auto castEnd = current.text == "(" ? afterType(1) : 0;
        bool primitiveCast = castEnd == 2 && ["int", "decimal", "bool", "string"].canFind(look(1).text);
        bool objectCast = castEnd != 0 && look(castEnd - 1).kind == TokenKind.identifier &&
            (look(castEnd + 1).kind == TokenKind.identifier || [TokenKind.integerLiteral, TokenKind.decimalLiteral, TokenKind.booleanLiteral, TokenKind.stringLiteral].canFind(look(castEnd + 1).kind) ||
             ["(", "this", "super", "new", "!", "~", "null"].canFind(look(castEnd + 1).text));
        if (castEnd != 0 && look(castEnd).text == ")" && (primitiveCast || objectCast)) {
            take(); auto castExpression = new Expression(ExprKind.castExpr, current);
            castExpression.castType = parseType();
            if (castExpression.castType == ValueType.selfType) {
                castExpression.token.text = parsedObjectName;
                auto last = tokens[index - 1];
                castExpression.token.position.length = last.position.offset + last.position.length - castExpression.token.position.offset;
            }
            expect(")"); castExpression.left = unary(); return castExpression;
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
        if (isTypedInitializerStart()) {
            auto declaredType = parseType();
            auto objectName = parsedObjectName;
            auto result = initializer();
            result.typedInitializer = true;
            result.initializerType = declaredType;
            result.initializerObjectName = objectName;
            return result;
        }
        if (accept("(")) { auto result = expression(); expect(")"); return result; }
        if (accept("this")) return new Expression(ExprKind.selfRef, t);
        if (accept("super")) return new Expression(ExprKind.superRef, t);
        if (accept("null")) return new Expression(ExprKind.nullLiteral, t);
        if (accept("new")) return new Expression(ExprKind.newSelf, identifier());
        if (t.kind == TokenKind.integerLiteral) { take(); return new Expression(ExprKind.integer, t); }
        if (t.kind == TokenKind.decimalLiteral) { take(); return new Expression(ExprKind.decimalLiteral, t); }
        if (t.kind == TokenKind.booleanLiteral) { take(); return new Expression(ExprKind.boolean, t); }
        if (t.kind == TokenKind.stringLiteral) { take(); return new Expression(ExprKind.stringLiteral, t); }
        if (t.kind == TokenKind.guidLiteral) { take(); return new Expression(ExprKind.guidLiteral, t); }
        if (t.kind == TokenKind.binaryLiteral) { take(); return new Expression(ExprKind.binaryLiteral, t); }
        if (t.kind == TokenKind.datespanLiteral) { take(); return new Expression(ExprKind.datespanLiteral, t); }
        if (t.kind == TokenKind.dateLiteral) { take(); return new Expression(ExprKind.dateLiteral, t); }
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

