module z8.compiler_model;

import std.conv : to;
import std.string : replace, indexOf, split, strip;
import std.uni : toLower;
import z8.lexer : Position, Token, TokenKind, decodeStringLiteral;

class CompileException : Exception {
    Position position;
    string sourceName;
    this(string message, Position position) { super(message); this.position = position; }
}

public import z8.variable_type;
enum NullableStringMode { none, required, nullAsEmpty }
enum ExprKind { integer, decimalLiteral, boolean, stringLiteral, guidLiteral, binaryLiteral, datespanLiteral, dateLiteral, nullLiteral, arrayLiteral, mapEntry, variable, selfRef, superRef, containerRef, newSelf, field, call, memberCall, index, castExpr, instanceOf, unary, binary, conditional, elvis }
enum StmtKind { block, variable, assignment, expressionStmt, returnStmt, ifStmt,
                whileStmt, doWhileStmt, forStmt, forEachStmt, breakStmt, continueStmt, throwStmt, tryStmt }

class Expression {
    ExprKind kind;
    Token token;
    Expression left, right, third;
    Expression[] arguments;
    ValueType inferredType;
    string targetClass;
    bool isField, isCapture, instanceCall, staticInstanceCall, staticInstanceField, fieldInitialization, earlyFieldInitialization, newHasContainer;
    bool binaryNameField;
    string nativeField;
    bool makeFile, makeException, convertExceptionObject, convertStringPrimaryArray, convertToDate, convertToSqlBool, convertToSqlInt, convertToSqlDecimal, convertSqlIntToDecimal, convertToSqlString, convertToSqlGuid;
    bool sqlBoolOperator, sqlBoolPriority, sqlIntOperator, sqlIntComparison, sqlIntPriority, sqlDecimalOperator, sqlDecimalComparison, sqlDecimalPriority, sqlStringOperator, sqlStringComparison, sqlStringPriority;
    bool sqlGuidOperator, sqlGuidPriority;
    bool convertToSqlDate, sqlDatePriority, sqlDateOperator;
    bool convertToSqlDatespan, sqlDatespanPriority, sqlDatespanOperator, sqlDatespanComparison, sqlDateArithmetic;
    bool convertToSqlGeometry, sqlGeometryPriority, sqlGeometryOperator;
    bool sqlPrimaryCast, sqlPrimaryInstanceOf;
    bool dateBinary, fileBinary;
    bool primaryCast, primaryInstanceOf, objectInstanceOf, scalarInstanceOf, falseInstanceOf, exceptionInstanceOf, exceptionObjectCast, exceptionObjectInstanceOf;
    bool typedInitializer;
    size_t parenthesisCount;
    bool firstParenthesisIsConditional;
    Method priorityMethod;
    ValueType initializerType;
    string initializerObjectName;
    string[] initializerKeyObjectNames;
    bool promoteToDecimal;
    bool boxPrimary;
    ValueType convertToString;
    ValueType convertToBinary;
    ValueType castType;
    string emittedOperator;
    bool userUnaryOperator, userBinaryOperator;
    Method userConversion, namedConversion;
    string builtinCall;
    string emittedOverride;
    Program objectClass;
    Program[] keyObjectClasses;
    ValueType collectionConversionType;
    Program collectionConversionClass;
    Program[] collectionConversionKeyClasses;
    NullableStringMode nullableStringMode;
    bool nullableStringReceiver, nullableStringLeft, nonNullStringResult;
    bool enumConstant;
    bool optionalRequired, optionalNullComparison, optionalNullOnLeft, optionalWrap;
    bool optionalIntBinary, optionalIntLeft, optionalIntRight;
    bool optionalIntReceiver, optionalIntUnary, optionalElvis, optionalMixedIntDecimal, optionalMixedIntOnLeft;
    bool optionalBoolBinary, optionalBoolLeft, optionalBoolRight, optionalBoolUnary, optionalBoolReceiver;
    bool optionalDecimalBinary, optionalDecimalLeft, optionalDecimalRight, optionalDecimalUnary, optionalDecimalReceiver;
    this(ExprKind kind, Token token) { this.kind = kind; this.token = token; }
}
class Statement {
    StmtKind kind;
    Token token;
    ValueType type;
    Expression expression;
    Expression target, attributeTarget;
    TypeAttribute[] attributes;
    Statement[] children;
    Statement initial, step;
    string assignmentOperator;
    Token catchName;
    bool hasCatch, hasFinally, hasContainer;
    bool declaredFinal, catchDeclaredFinal;
    bool filePathAssignment, dateTickAssignment, userOperatorAssignment, userCompoundAssignment, isMemberInitializer;
    string objectName; string[] keyObjectNames;
    Program objectClass, nestedClass; Program[] keyObjectClasses;
    Method priorityMethod;
    bool sqlBoolReturnPriority, sqlIntReturnPriority, sqlDecimalReturnPriority, sqlStringReturnPriority;
    bool sqlGuidReturnPriority;
    bool sqlDateReturnPriority;
    bool sqlDatespanReturnPriority;
    bool sqlGeometryReturnPriority;
    this(StmtKind kind, Token token) { this.kind = kind; this.token = token; }
}
struct Parameter { ValueType type; Token name; string objectName; string[] keyObjectNames; Program objectClass; Program[] keyObjectClasses; bool declaredFinal; }
class Method {
    ValueType returnType;
    Token name;
    Parameter[] parameters;
    TypeAttribute[] attributes;
    Statement body;
    bool isPublic, isProtected;
    bool isStatic;
    string returnObjectName; string[] returnKeyObjectNames;
    Program returnObjectClass; Program[] returnKeyObjectClasses;
    Program owner;
    bool isVirtual, overrides;
    string operatorSymbol;
    bool isCastOperator;
    bool isPriorityOperator;
    bool isNativeDeclaration;
}
class Field { ValueType type; Token name; TypeAttribute[] attributes, recordAttributes; Expression initializer; bool isPublic, isProtected, isStatic, isAuto, isRecord, declaredFinal, userOperatorAssignment; string objectName; string[] keyObjectNames; Program objectClass; Program[] keyObjectClasses; Program owner, nestedClass; }
struct TypeAttribute { Token name; Token value; Expression expression, recordExpression; Field recordField; ValueType expressionType; long capturedDateTicks; bool hasValue, dateTickCaptured; }
// Match the original lexer and BigDecimal.toString, including preserved scale
// and its scientific notation for an adjusted exponent below -6.
package string canonicalDecimalLiteral(Token token) {
    auto spelling = token.text.replace(" ", "").replace("\t", "");
    bool negative = spelling.length && spelling[0] == '-';
    if (negative) spelling = spelling[1 .. $];
    auto exponentPosition = spelling.indexOf('e');
    if (exponentPosition < 0) exponentPosition = spelling.indexOf('E');
    if (exponentPosition >= 0) {
        // Lexer.getDegree concatenates two Java chars arithmetically before
        // appending the digits: 'e' + '+' becomes 144 and 'e' + '-' 146.
        auto sign = spelling[exponentPosition + 1];
        spelling = spelling[0 .. exponentPosition] ~ (sign == '+' ? "144" : "146") ~ spelling[exponentPosition + 2 .. $];
    }
    auto point = spelling.indexOf('.');
    assert(point >= 0);
    auto fractionalDigits = spelling.length - point - 1;
    auto scale = cast(long)fractionalDigits;
    if (scale < int.min || scale > int.max)
        throw new CompileException("decimal scale is out of range", token.position);
    auto digits = spelling[0 .. point] ~ spelling[point + 1 .. $];
    size_t first;
    while (first < digits.length && digits[first] == '0') ++first;
    digits = first == digits.length ? "0" : digits[first .. $];
    if (digits == "0") negative = false;
    auto adjusted = cast(long)digits.length - scale - 1;
    string result;
    if (scale >= 0 && adjusted >= -6) {
        auto pointAt = cast(long)digits.length - scale;
        if (pointAt <= 0) {
            result = "0.";
            foreach (_; 0 .. cast(size_t)(-pointAt)) result ~= "0";
            result ~= digits;
        } else if (scale == 0) result = digits;
        else result = digits[0 .. cast(size_t)pointAt] ~ "." ~ digits[cast(size_t)pointAt .. $];
    } else {
        result = digits[0 .. 1];
        if (digits.length > 1) result ~= "." ~ digits[1 .. $];
        result ~= "E" ~ (adjusted >= 0 ? "+" : "") ~ adjusted.to!string;
    }
    return negative ? "-" ~ result : result;
}

// Attribute constants use ConstantToken.getValueString, including the Java
// integer suffix. This spelling is also used to compare [name] values.
package wstring attributeLiteralValue(TypeAttribute attribute) {
    if (!attribute.hasValue) return ""w;
    assert(attribute.expression is null);
    if (attribute.value.kind == TokenKind.stringLiteral) return decodeStringLiteral(attribute.value.text);
    if (attribute.value.kind == TokenKind.booleanLiteral) return attribute.value.text.to!wstring;
    if (attribute.value.kind == TokenKind.datespanLiteral) {
        auto parts = attribute.value.text[1 .. $ - 1].strip.split();
        auto clock = parts[1].split(":");
        auto days = parts[0].to!uint;
        // The compiler's Datespan uses int arithmetic before widening to long.
        uint ticks = days * 86_400_000u + clock[0].to!uint * 3_600_000u +
            clock[1].to!uint * 60_000u + clock[2].to!uint * 1_000u;
        return (cast(int)ticks).to!string.to!wstring ~ "L"w;
    }
    if (attribute.value.kind == TokenKind.guidLiteral) {
        auto uuid = attribute.value.text[1 .. $ - 1].toLower;
        auto digits = uuid.replace("-", "");
        auto high = cast(long)digits[0 .. 16].to!ulong(16);
        auto low = cast(long)digits[16 .. 32].to!ulong(16);
        return ("/* " ~ uuid ~ " */" ~ high.to!string ~ "L, " ~ low.to!string ~ "L").to!wstring;
    }
    if (attribute.value.kind == TokenKind.binaryLiteral) {
        auto text = attribute.value.text[1 .. $ - 1];
        string result = "new byte[] {";
        foreach (i, part; text.split(',')) {
            auto number = part.strip;
            auto value = number.length > 2 && number[0] == '0' && (number[1] == 'x' || number[1] == 'X') ?
                number[2 .. $].to!uint(16) : number.to!uint;
            if (i) result ~= ", ";
            result ~= (value < 128 ? cast(int)value : cast(int)value - 256).to!string;
        }
        return (result ~ "}").to!wstring;
    }
    if (attribute.value.kind == TokenKind.decimalLiteral)
        return canonicalDecimalLiteral(attribute.value).to!wstring;
    assert(attribute.value.kind == TokenKind.integerLiteral);
    auto spelling = attribute.value.text.replace(" ", "").replace("\t", "");
    long value;
    bool negative = spelling.length && spelling[0] == '-';
    auto magnitude = negative ? spelling[1 .. $] : spelling;
    if (magnitude.length > 2 && magnitude[0] == '0' && (magnitude[1] == 'x' || magnitude[1] == 'X')) {
        value = cast(long)magnitude[2 .. $].to!ulong(16);
        if (negative) value = -value;
    } else value = spelling.to!long;
    return (value.to!string ~ "L").to!wstring;
}
struct Import { string name; Token token; }
struct Capture { string name; ValueType type; Program objectClass; Program[] keyObjectClasses; }
class Program {
    Token name;
    Method[] methods;
    Field[] fields;
    Statement[] memberInitializers;
    Import[] imports;
    TypeAttribute[] attributes;
    string qualifiedName, sourceName, emittedName;
    size_t sourceIndex;
    string baseName;
    Token baseToken;
    Program baseClass;
    bool baseIsPrimary;
    bool baseIsException;
    Program lexicalOwner;
    Program[] nestedPrograms, memberSpecializations;
    Token specializedName;
    Field specializedField;
    bool isFieldSpecialization;
    Capture[] captures;
    bool enclosingStatic;
    bool isFinal;
    bool isEnum, isNative, isPrimary;
    wstring nativeName;
    Token[] enumValues;
}
package bool extendsBuiltinPrimary(Program program) {
    for (auto current = program; current !is null; current = current.baseClass)
        if (current.baseIsPrimary) return true;
    return false;
}
package bool extendsBuiltinException(Program program) {
    for (auto current = program; current !is null; current = current.baseClass)
        if (current.baseIsException) return true;
    return false;
}
// Z8 treats attributed primary types and their descendants as values even
// when their BL declaration does not derive from the built-in primary.
package bool isPrimaryClass(Program program) {
    for (auto current = program; current !is null; current = current.baseClass)
        if (current.isPrimary || current.baseIsPrimary) return true;
    return false;
}
struct SourceUnit { string name, path, source; }
/// One generated D module and its path relative to the output directory.
struct GeneratedModule { string moduleName, relativePath, sourceName, source; }

