module z8.compiler_model;

import std.algorithm : canFind;
import std.conv : to;
import std.string : replace, indexOf;
import std.math : isFinite, abs;
import z8.lexer : Position, Token;

class CompileException : Exception {
    Position position;
    string sourceName;
    this(string message, Position position) { super(message); this.position = position; }
}

enum ValueType { voidType, intType, decimalType, boolType, stringType, guidType, binaryType, datespanType, dateType, exceptionType, primaryType, selfType, intArray, decimalArray, boolArray, stringArray, guidArray, binaryArray, datespanArray, dateArray, primaryArray, selfArray, stringMap, primaryStringMap, nullType, nullableString, enumType, enumArray, optionalInt, optionalBool, optionalDecimal }
enum NullableStringMode { none, required, nullAsEmpty }
enum ExprKind { integer, decimalLiteral, boolean, stringLiteral, guidLiteral, binaryLiteral, datespanLiteral, dateLiteral, nullLiteral, arrayLiteral, variable, selfRef, superRef, newSelf, field, call, memberCall, index, castExpr, instanceOf, unary, binary, conditional, elvis }
enum StmtKind { block, variable, assignment, expressionStmt, returnStmt, ifStmt,
                whileStmt, doWhileStmt, forStmt, forEachStmt, breakStmt, continueStmt, throwStmt, tryStmt }

class Expression {
    ExprKind kind;
    Token token;
    Expression left, right, third;
    Expression[] arguments;
    ValueType inferredType;
    string targetClass;
    bool isField, instanceCall, fieldInitialization, newHasContainer;
    bool binaryNameField;
    bool dateBinary;
    bool primaryCast, primaryInstanceOf;
    bool promoteToDecimal;
    bool boxPrimary;
    ValueType convertToString;
    ValueType castType;
    string emittedOperator;
    string builtinCall;
    string emittedOverride;
    Program objectClass;
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
    Expression target;
    Statement[] children;
    Statement initial, step;
    string assignmentOperator;
    Token catchName;
    bool hasCatch, hasFinally, hasContainer;
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
class Field { ValueType type; Token name; Expression initializer; bool isPublic, isProtected, isStatic; string objectName; Program objectClass; Program owner; }
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
    bool isEnum;
    Token[] enumValues;
}
struct SourceUnit { string name, path, source; }
/// One generated D module and its path relative to the output directory.
struct GeneratedModule { string moduleName, relativePath, sourceName, source; }

package bool isArray(ValueType type) {
    return [ValueType.intArray, ValueType.decimalArray, ValueType.boolArray, ValueType.stringArray, ValueType.guidArray, ValueType.binaryArray, ValueType.datespanArray, ValueType.dateArray, ValueType.primaryArray, ValueType.selfArray, ValueType.enumArray].canFind(type);
}
package bool isReferenceArray(ValueType type) { return [ValueType.selfArray, ValueType.enumArray, ValueType.primaryArray, ValueType.guidArray, ValueType.binaryArray, ValueType.datespanArray, ValueType.dateArray].canFind(type); }
package bool isMap(ValueType type) { return type == ValueType.stringMap || type == ValueType.primaryStringMap; }
package bool hasObjectClass(ValueType type) { return type == ValueType.selfType || type == ValueType.selfArray || type == ValueType.enumType || type == ValueType.enumArray; }
package bool isNullableReference(ValueType type) { return type == ValueType.selfType || type == ValueType.enumType || type == ValueType.exceptionType || type == ValueType.primaryType || type == ValueType.guidType || type == ValueType.binaryType || type == ValueType.datespanType || type == ValueType.dateType || isMap(type) || type == ValueType.nullableString || type == ValueType.stringType || isArray(type); }
package ValueType storedValueType(ValueType type) {
    if (type == ValueType.intType) return ValueType.optionalInt;
    if (type == ValueType.boolType) return ValueType.optionalBool;
    if (type == ValueType.decimalType) return ValueType.optionalDecimal;
    return type;
}
package bool isOptionalPrimitive(ValueType type) { return [ValueType.optionalInt, ValueType.optionalBool, ValueType.optionalDecimal].canFind(type); }
package ValueType optionalBaseType(ValueType type) {
    switch (type) {
        case ValueType.optionalInt: return ValueType.intType;
        case ValueType.optionalBool: return ValueType.boolType;
        case ValueType.optionalDecimal: return ValueType.decimalType;
        default: assert(0, "not an optional primitive");
    }
}
package ValueType optionalForArray(ValueType type) {
    switch (type) {
        case ValueType.intArray: return ValueType.optionalInt;
        case ValueType.boolArray: return ValueType.optionalBool;
        case ValueType.decimalArray: return ValueType.optionalDecimal;
        default: assert(0, "not a primitive array");
    }
}
// Until Java's legacy Double.toString conversion is fully reproduced, reject
// literal values for which a shorter D rendering may differ from the Java backend.
package bool safeDecimalLiteral(string text) {
    auto spelling = text.replace(" ", "").replace("\t", "");
    auto exponent = spelling.indexOf('e');
    if (exponent < 0) exponent = spelling.indexOf('E');
    auto mantissa = exponent < 0 ? spelling : spelling[0 .. exponent];
    string digits;
    foreach (c; mantissa) if (c >= '0' && c <= '9') digits ~= c;
    size_t first, last = digits.length;
    while (first < last && digits[first] == '0') ++first;
    while (last > first && digits[last - 1] == '0') --last;
    if (last - first > 15) return false;
    try {
        auto value = spelling.to!double;
        if (!value.isFinite) return false;
        if (first == last) return true;
        return value != 0 && value.abs >= 1e-15 && value.abs < 1e15;
    } catch (Exception) { return false; }
}
package ValueType elementType(ValueType type) {
    switch (type) {
        case ValueType.intArray: return ValueType.intType;
        case ValueType.decimalArray: return ValueType.decimalType;
        case ValueType.boolArray: return ValueType.boolType;
        case ValueType.stringArray: return ValueType.stringType;
        case ValueType.primaryArray: return ValueType.primaryType;
        case ValueType.guidArray: return ValueType.guidType;
        case ValueType.binaryArray: return ValueType.binaryType;
        case ValueType.datespanArray: return ValueType.datespanType;
        case ValueType.dateArray: return ValueType.dateType;
        case ValueType.selfArray: return ValueType.selfType;
        case ValueType.enumArray: return ValueType.enumType;
        default: assert(0, "not an array");
    }
}

