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
    bool isField, instanceCall, staticInstanceCall, fieldInitialization, newHasContainer;
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
    Expression target;
    Statement[] children;
    Statement initial, step;
    string assignmentOperator;
    Token catchName;
    bool hasCatch, hasFinally, hasContainer;
    bool declaredFinal, catchDeclaredFinal;
    bool filePathAssignment, dateTickAssignment, userOperatorAssignment, userCompoundAssignment;
    string objectName;
    Program objectClass;
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
class Field { ValueType type; Token name; Expression initializer; bool isPublic, isProtected, isStatic, isAuto, isRecord, declaredFinal, userOperatorAssignment; string objectName; Program objectClass; Program owner, nestedClass; }
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
    Program lexicalOwner;
    Program[] nestedPrograms;
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

