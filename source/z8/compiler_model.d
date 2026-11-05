module z8.compiler_model;

import std.algorithm : canFind;
import std.conv : to;
import std.string : replace, indexOf, split, strip;
import std.uni : toLower;
import std.math : isFinite, abs;
import z8.lexer : Position, Token, TokenKind, decodeStringLiteral;

class CompileException : Exception {
    Position position;
    string sourceName;
    this(string message, Position position) { super(message); this.position = position; }
}

enum ValueType { voidType, intType, decimalType, boolType, stringType, guidType, binaryType, datespanType, dateType, geometryType, fileType, exceptionType, encodingType, primaryType, selfType, intArray, decimalArray, decimalMatrix, boolArray, stringArray, guidArray, binaryArray, datespanArray, dateArray, geometryArray, fileArray, exceptionArray, primaryArray, selfArray, stringMap, primaryStringMap, intStringMap, boolStringMap, decimalStringMap, guidStringMap, intIntMap, stringIntMap, primaryIntMap, boolIntMap, decimalIntMap, guidIntMap, stringGuidMap, primaryGuidMap, intGuidMap, boolGuidMap, decimalGuidMap, guidGuidMap, stringBoolMap, primaryBoolMap, intBoolMap, boolBoolMap, decimalBoolMap, guidBoolMap, stringDecimalMap, primaryDecimalMap, intDecimalMap, boolDecimalMap, decimalDecimalMap, guidDecimalMap, nullType, nullableString, enumType, enumArray, optionalInt, optionalBool, optionalDecimal }
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
    bool makeFile, makeException, convertToDate;
    bool dateBinary, fileBinary;
    bool primaryCast, primaryInstanceOf;
    bool typedInitializer;
    ValueType initializerType;
    string initializerObjectName;
    bool promoteToDecimal;
    bool boxPrimary;
    ValueType convertToString;
    ValueType convertToBinary;
    ValueType castType;
    string emittedOperator;
    bool userUnaryOperator, userBinaryOperator;
    Method userConversion;
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
    Expression target, attributeTarget;
    TypeAttribute[] attributes;
    Statement[] children;
    Statement initial, step;
    string assignmentOperator;
    Token catchName;
    bool hasCatch, hasFinally, hasContainer;
    bool declaredFinal, catchDeclaredFinal;
    bool filePathAssignment, dateTickAssignment, userOperatorAssignment, userCompoundAssignment, isMemberInitializer;
    string objectName;
    Program objectClass, nestedClass;
    this(StmtKind kind, Token token) { this.kind = kind; this.token = token; }
}
struct Parameter { ValueType type; Token name; string objectName; Program objectClass; bool declaredFinal; }
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
    string operatorSymbol;
    bool isCastOperator;
}
class Field { ValueType type; Token name; TypeAttribute[] attributes; Expression initializer; bool isPublic, isProtected, isStatic, isAuto, isRecord, declaredFinal, userOperatorAssignment; string objectName; Program objectClass; Program owner, nestedClass; }
struct TypeAttribute { Token name; Token value; Expression expression; ValueType expressionType; bool hasValue; }
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
struct Capture { string name; ValueType type; Program objectClass; }
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
    Program lexicalOwner;
    Program[] nestedPrograms, memberSpecializations;
    Token specializedName;
    Field specializedField;
    bool isFieldSpecialization;
    Capture[] captures;
    bool enclosingStatic;
    bool isFinal;
    bool isEnum;
    Token[] enumValues;
}
struct SourceUnit { string name, path, source; }
/// One generated D module and its path relative to the output directory.
struct GeneratedModule { string moduleName, relativePath, sourceName, source; }

package bool isArray(ValueType type) {
    return [ValueType.intArray, ValueType.decimalArray, ValueType.decimalMatrix, ValueType.boolArray, ValueType.stringArray, ValueType.guidArray, ValueType.binaryArray, ValueType.datespanArray, ValueType.dateArray, ValueType.geometryArray, ValueType.fileArray, ValueType.exceptionArray, ValueType.primaryArray, ValueType.selfArray, ValueType.enumArray].canFind(type);
}
package bool isReferenceArray(ValueType type) { return [ValueType.selfArray, ValueType.enumArray, ValueType.primaryArray, ValueType.guidArray, ValueType.binaryArray, ValueType.datespanArray, ValueType.dateArray, ValueType.geometryArray, ValueType.fileArray, ValueType.exceptionArray, ValueType.decimalMatrix].canFind(type); }
// Each supported map has a single description of its value and key types.
// VariableType in the original compiler likewise stores the value type and keys.
private struct MapDescriptor { ValueType type, value, key; }
private enum MapDescriptor[] mapDescriptors = [
    MapDescriptor(ValueType.stringMap, ValueType.stringType, ValueType.stringType),
    MapDescriptor(ValueType.primaryStringMap, ValueType.primaryType, ValueType.stringType),
    MapDescriptor(ValueType.intStringMap, ValueType.intType, ValueType.stringType),
    MapDescriptor(ValueType.boolStringMap, ValueType.boolType, ValueType.stringType),
    MapDescriptor(ValueType.decimalStringMap, ValueType.decimalType, ValueType.stringType),
    MapDescriptor(ValueType.guidStringMap, ValueType.guidType, ValueType.stringType),
    MapDescriptor(ValueType.intIntMap, ValueType.intType, ValueType.intType),
    MapDescriptor(ValueType.stringIntMap, ValueType.stringType, ValueType.intType),
    MapDescriptor(ValueType.primaryIntMap, ValueType.primaryType, ValueType.intType),
    MapDescriptor(ValueType.boolIntMap, ValueType.boolType, ValueType.intType),
    MapDescriptor(ValueType.decimalIntMap, ValueType.decimalType, ValueType.intType),
    MapDescriptor(ValueType.guidIntMap, ValueType.guidType, ValueType.intType),
    MapDescriptor(ValueType.stringGuidMap, ValueType.stringType, ValueType.guidType),
    MapDescriptor(ValueType.primaryGuidMap, ValueType.primaryType, ValueType.guidType),
    MapDescriptor(ValueType.intGuidMap, ValueType.intType, ValueType.guidType),
    MapDescriptor(ValueType.boolGuidMap, ValueType.boolType, ValueType.guidType),
    MapDescriptor(ValueType.decimalGuidMap, ValueType.decimalType, ValueType.guidType),
    MapDescriptor(ValueType.guidGuidMap, ValueType.guidType, ValueType.guidType),
    MapDescriptor(ValueType.stringBoolMap, ValueType.stringType, ValueType.boolType),
    MapDescriptor(ValueType.primaryBoolMap, ValueType.primaryType, ValueType.boolType),
    MapDescriptor(ValueType.intBoolMap, ValueType.intType, ValueType.boolType),
    MapDescriptor(ValueType.boolBoolMap, ValueType.boolType, ValueType.boolType),
    MapDescriptor(ValueType.decimalBoolMap, ValueType.decimalType, ValueType.boolType),
    MapDescriptor(ValueType.guidBoolMap, ValueType.guidType, ValueType.boolType),
    MapDescriptor(ValueType.stringDecimalMap, ValueType.stringType, ValueType.decimalType),
    MapDescriptor(ValueType.primaryDecimalMap, ValueType.primaryType, ValueType.decimalType),
    MapDescriptor(ValueType.intDecimalMap, ValueType.intType, ValueType.decimalType),
    MapDescriptor(ValueType.boolDecimalMap, ValueType.boolType, ValueType.decimalType),
    MapDescriptor(ValueType.decimalDecimalMap, ValueType.decimalType, ValueType.decimalType),
    MapDescriptor(ValueType.guidDecimalMap, ValueType.guidType, ValueType.decimalType),
];
package bool isMap(ValueType type) {
    foreach (descriptor; mapDescriptors) if (descriptor.type == type) return true;
    return false;
}
package ValueType mapKeyType(ValueType type) {
    foreach (descriptor; mapDescriptors) if (descriptor.type == type) return descriptor.key;
    assert(0, "not a map");
}
package ValueType mapValueType(ValueType type) {
    foreach (descriptor; mapDescriptors) if (descriptor.type == type) return descriptor.value;
    assert(0, "not a map");
}
package ValueType mapKeyArrayType(ValueType type) {
    auto key = mapKeyType(type);
    return key == ValueType.decimalType ? ValueType.decimalArray : key == ValueType.boolType ? ValueType.boolArray : key == ValueType.intType ? ValueType.intArray : key == ValueType.guidType ? ValueType.guidArray : ValueType.stringArray;
}
package ValueType mapValueArrayType(ValueType type) {
    auto value = mapValueType(type);
    return value == ValueType.intType ? ValueType.intArray : value == ValueType.boolType ? ValueType.boolArray : value == ValueType.decimalType ? ValueType.decimalArray : value == ValueType.guidType ? ValueType.guidArray : value == ValueType.primaryType ? ValueType.primaryArray : ValueType.stringArray;
}
package ValueType mapType(ValueType value, ValueType key) {
    foreach (descriptor; mapDescriptors)
        if (descriptor.value == value && descriptor.key == key) return descriptor.type;
    return ValueType.voidType;
}

unittest {
    foreach (index, descriptor; mapDescriptors) {
        assert(isMap(descriptor.type));
        assert(mapType(descriptor.value, descriptor.key) == descriptor.type);
        assert(mapValueType(descriptor.type) == descriptor.value);
        assert(mapKeyType(descriptor.type) == descriptor.key);
        foreach (other; mapDescriptors[index + 1 .. $]) {
            assert(descriptor.type != other.type);
            assert(descriptor.value != other.value || descriptor.key != other.key);
        }
    }
    assert(!isMap(ValueType.intType));
    assert(mapType(ValueType.intType, ValueType.fileType) == ValueType.voidType);
}
package ValueType mapValueReadType(ValueType type) {
    auto value = mapValueType(type);
    return value == ValueType.stringType ? ValueType.nullableString : storedValueType(value);
}
package bool hasObjectClass(ValueType type) { return type == ValueType.selfType || type == ValueType.selfArray || type == ValueType.enumType || type == ValueType.enumArray; }
package bool isNullableReference(ValueType type) { return type == ValueType.selfType || type == ValueType.enumType || type == ValueType.exceptionType || type == ValueType.encodingType || type == ValueType.primaryType || type == ValueType.guidType || type == ValueType.binaryType || type == ValueType.datespanType || type == ValueType.dateType || type == ValueType.geometryType || type == ValueType.fileType || isMap(type) || type == ValueType.nullableString || type == ValueType.stringType || isArray(type); }
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
        case ValueType.decimalMatrix: return ValueType.decimalArray;
        case ValueType.boolArray: return ValueType.boolType;
        case ValueType.stringArray: return ValueType.stringType;
        case ValueType.primaryArray: return ValueType.primaryType;
        case ValueType.guidArray: return ValueType.guidType;
        case ValueType.binaryArray: return ValueType.binaryType;
        case ValueType.datespanArray: return ValueType.datespanType;
        case ValueType.dateArray: return ValueType.dateType;
        case ValueType.geometryArray: return ValueType.geometryType;
        case ValueType.fileArray: return ValueType.fileType;
        case ValueType.exceptionArray: return ValueType.exceptionType;
        case ValueType.selfArray: return ValueType.selfType;
        case ValueType.enumArray: return ValueType.enumType;
        default: assert(0, "not an array");
    }
}

