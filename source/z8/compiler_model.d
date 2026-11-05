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

enum ValueType { voidType, stringObjectKeyMap, stringEnumKeyMap, primaryObjectKeyMap, primaryEnumKeyMap, intObjectKeyMap, intEnumKeyMap, boolObjectKeyMap, boolEnumKeyMap, decimalObjectKeyMap, decimalEnumKeyMap, guidObjectKeyMap, guidEnumKeyMap, binaryObjectKeyMap, binaryEnumKeyMap, datespanObjectKeyMap, datespanEnumKeyMap, dateObjectKeyMap, dateEnumKeyMap, geometryObjectKeyMap, geometryEnumKeyMap, fileObjectKeyMap, fileEnumKeyMap, exceptionObjectKeyMap, exceptionEnumKeyMap, encodingObjectKeyMap, encodingEnumKeyMap, selfObjectKeyMap, selfEnumKeyMap, enumObjectKeyMap, enumEnumKeyMap, sqlBoolObjectKeyMap, sqlBoolEnumKeyMap, sqlIntObjectKeyMap, sqlIntEnumKeyMap, sqlDecimalObjectKeyMap, sqlDecimalEnumKeyMap, sqlStringObjectKeyMap, sqlStringEnumKeyMap, sqlGuidObjectKeyMap, sqlGuidEnumKeyMap, sqlDateObjectKeyMap, sqlDateEnumKeyMap, sqlDatespanObjectKeyMap, sqlDatespanEnumKeyMap, sqlBinaryObjectKeyMap, sqlBinaryEnumKeyMap, sqlGeometryObjectKeyMap, sqlGeometryEnumKeyMap, sqlPrimaryObjectKeyMap, sqlPrimaryEnumKeyMap, stringArrayObjectKeyMap, stringArrayEnumKeyMap, primaryArrayObjectKeyMap, primaryArrayEnumKeyMap, intArrayObjectKeyMap, intArrayEnumKeyMap, boolArrayObjectKeyMap, boolArrayEnumKeyMap, decimalArrayObjectKeyMap, decimalArrayEnumKeyMap, guidArrayObjectKeyMap, guidArrayEnumKeyMap, binaryArrayObjectKeyMap, binaryArrayEnumKeyMap, datespanArrayObjectKeyMap, datespanArrayEnumKeyMap, dateArrayObjectKeyMap, dateArrayEnumKeyMap, geometryArrayObjectKeyMap, geometryArrayEnumKeyMap, fileArrayObjectKeyMap, fileArrayEnumKeyMap, exceptionArrayObjectKeyMap, exceptionArrayEnumKeyMap, encodingArrayObjectKeyMap, encodingArrayEnumKeyMap, selfArrayObjectKeyMap, selfArrayEnumKeyMap, enumArrayObjectKeyMap, enumArrayEnumKeyMap, sqlBoolArrayObjectKeyMap, sqlBoolArrayEnumKeyMap, sqlIntArrayObjectKeyMap, sqlIntArrayEnumKeyMap, sqlDecimalArrayObjectKeyMap, sqlDecimalArrayEnumKeyMap, sqlStringArrayObjectKeyMap, sqlStringArrayEnumKeyMap, sqlGuidArrayObjectKeyMap, sqlGuidArrayEnumKeyMap, sqlDateArrayObjectKeyMap, sqlDateArrayEnumKeyMap, sqlDatespanArrayObjectKeyMap, sqlDatespanArrayEnumKeyMap, sqlBinaryArrayObjectKeyMap, sqlBinaryArrayEnumKeyMap, sqlGeometryArrayObjectKeyMap, sqlGeometryArrayEnumKeyMap, sqlPrimaryArrayObjectKeyMap, sqlPrimaryArrayEnumKeyMap, stringDateMap, stringDatespanMap, stringBinaryMap, stringGeometryMap, stringFileMap, primaryDateMap, primaryDatespanMap, primaryBinaryMap, primaryGeometryMap, primaryFileMap, intDateMap, intDatespanMap, intBinaryMap, intGeometryMap, intFileMap, boolDateMap, boolDatespanMap, boolBinaryMap, boolGeometryMap, boolFileMap, decimalDateMap, decimalDatespanMap, decimalBinaryMap, decimalGeometryMap, decimalFileMap, guidDateMap, guidDatespanMap, guidBinaryMap, guidGeometryMap, guidFileMap, binaryDateMap, binaryDatespanMap, binaryBinaryMap, binaryGeometryMap, binaryFileMap, datespanDateMap, datespanDatespanMap, datespanBinaryMap, datespanGeometryMap, datespanFileMap, dateDateMap, dateDatespanMap, dateBinaryMap, dateGeometryMap, dateFileMap, geometryDateMap, geometryDatespanMap, geometryBinaryMap, geometryGeometryMap, geometryFileMap, fileDateMap, fileDatespanMap, fileBinaryMap, fileGeometryMap, fileFileMap, exceptionDateMap, exceptionDatespanMap, exceptionBinaryMap, exceptionGeometryMap, exceptionFileMap, encodingDateMap, encodingDatespanMap, encodingBinaryMap, encodingGeometryMap, encodingFileMap, selfDateMap, selfDatespanMap, selfBinaryMap, selfGeometryMap, selfFileMap, enumDateMap, enumDatespanMap, enumBinaryMap, enumGeometryMap, enumFileMap, sqlBoolDateMap, sqlBoolDatespanMap, sqlBoolBinaryMap, sqlBoolGeometryMap, sqlBoolFileMap, sqlIntDateMap, sqlIntDatespanMap, sqlIntBinaryMap, sqlIntGeometryMap, sqlIntFileMap, sqlDecimalDateMap, sqlDecimalDatespanMap, sqlDecimalBinaryMap, sqlDecimalGeometryMap, sqlDecimalFileMap, sqlStringDateMap, sqlStringDatespanMap, sqlStringBinaryMap, sqlStringGeometryMap, sqlStringFileMap, sqlGuidDateMap, sqlGuidDatespanMap, sqlGuidBinaryMap, sqlGuidGeometryMap, sqlGuidFileMap, sqlDateDateMap, sqlDateDatespanMap, sqlDateBinaryMap, sqlDateGeometryMap, sqlDateFileMap, sqlDatespanDateMap, sqlDatespanDatespanMap, sqlDatespanBinaryMap, sqlDatespanGeometryMap, sqlDatespanFileMap, sqlBinaryDateMap, sqlBinaryDatespanMap, sqlBinaryBinaryMap, sqlBinaryGeometryMap, sqlBinaryFileMap, sqlGeometryDateMap, sqlGeometryDatespanMap, sqlGeometryBinaryMap, sqlGeometryGeometryMap, sqlGeometryFileMap, sqlPrimaryDateMap, sqlPrimaryDatespanMap, sqlPrimaryBinaryMap, sqlPrimaryGeometryMap, sqlPrimaryFileMap, stringArrayDateMap, stringArrayDatespanMap, stringArrayBinaryMap, stringArrayGeometryMap, stringArrayFileMap, primaryArrayDateMap, primaryArrayDatespanMap, primaryArrayBinaryMap, primaryArrayGeometryMap, primaryArrayFileMap, intArrayDateMap, intArrayDatespanMap, intArrayBinaryMap, intArrayGeometryMap, intArrayFileMap, boolArrayDateMap, boolArrayDatespanMap, boolArrayBinaryMap, boolArrayGeometryMap, boolArrayFileMap, decimalArrayDateMap, decimalArrayDatespanMap, decimalArrayBinaryMap, decimalArrayGeometryMap, decimalArrayFileMap, guidArrayDateMap, guidArrayDatespanMap, guidArrayBinaryMap, guidArrayGeometryMap, guidArrayFileMap, binaryArrayDateMap, binaryArrayDatespanMap, binaryArrayBinaryMap, binaryArrayGeometryMap, binaryArrayFileMap, datespanArrayDateMap, datespanArrayDatespanMap, datespanArrayBinaryMap, datespanArrayGeometryMap, datespanArrayFileMap, dateArrayDateMap, dateArrayDatespanMap, dateArrayBinaryMap, dateArrayGeometryMap, dateArrayFileMap, geometryArrayDateMap, geometryArrayDatespanMap, geometryArrayBinaryMap, geometryArrayGeometryMap, geometryArrayFileMap, fileArrayDateMap, fileArrayDatespanMap, fileArrayBinaryMap, fileArrayGeometryMap, fileArrayFileMap, exceptionArrayDateMap, exceptionArrayDatespanMap, exceptionArrayBinaryMap, exceptionArrayGeometryMap, exceptionArrayFileMap, encodingArrayDateMap, encodingArrayDatespanMap, encodingArrayBinaryMap, encodingArrayGeometryMap, encodingArrayFileMap, selfArrayDateMap, selfArrayDatespanMap, selfArrayBinaryMap, selfArrayGeometryMap, selfArrayFileMap, enumArrayDateMap, enumArrayDatespanMap, enumArrayBinaryMap, enumArrayGeometryMap, enumArrayFileMap, sqlBoolArrayDateMap, sqlBoolArrayDatespanMap, sqlBoolArrayBinaryMap, sqlBoolArrayGeometryMap, sqlBoolArrayFileMap, sqlIntArrayDateMap, sqlIntArrayDatespanMap, sqlIntArrayBinaryMap, sqlIntArrayGeometryMap, sqlIntArrayFileMap, sqlDecimalArrayDateMap, sqlDecimalArrayDatespanMap, sqlDecimalArrayBinaryMap, sqlDecimalArrayGeometryMap, sqlDecimalArrayFileMap, sqlStringArrayDateMap, sqlStringArrayDatespanMap, sqlStringArrayBinaryMap, sqlStringArrayGeometryMap, sqlStringArrayFileMap, sqlGuidArrayDateMap, sqlGuidArrayDatespanMap, sqlGuidArrayBinaryMap, sqlGuidArrayGeometryMap, sqlGuidArrayFileMap, sqlDateArrayDateMap, sqlDateArrayDatespanMap, sqlDateArrayBinaryMap, sqlDateArrayGeometryMap, sqlDateArrayFileMap, sqlDatespanArrayDateMap, sqlDatespanArrayDatespanMap, sqlDatespanArrayBinaryMap, sqlDatespanArrayGeometryMap, sqlDatespanArrayFileMap, sqlBinaryArrayDateMap, sqlBinaryArrayDatespanMap, sqlBinaryArrayBinaryMap, sqlBinaryArrayGeometryMap, sqlBinaryArrayFileMap, sqlGeometryArrayDateMap, sqlGeometryArrayDatespanMap, sqlGeometryArrayBinaryMap, sqlGeometryArrayGeometryMap, sqlGeometryArrayFileMap, sqlPrimaryArrayDateMap, sqlPrimaryArrayDatespanMap, sqlPrimaryArrayBinaryMap, sqlPrimaryArrayGeometryMap, sqlPrimaryArrayFileMap, stringPrimaryMap, primaryPrimaryMap, intPrimaryMap, boolPrimaryMap, decimalPrimaryMap, guidPrimaryMap, binaryPrimaryMap, datespanPrimaryMap, datePrimaryMap, geometryPrimaryMap, filePrimaryMap, exceptionPrimaryMap, encodingPrimaryMap, selfPrimaryMap, enumPrimaryMap, sqlBoolPrimaryMap, sqlIntPrimaryMap, sqlDecimalPrimaryMap, sqlStringPrimaryMap, sqlGuidPrimaryMap, sqlDatePrimaryMap, sqlDatespanPrimaryMap, sqlBinaryPrimaryMap, sqlGeometryPrimaryMap, sqlPrimaryPrimaryMap, stringArrayPrimaryMap, primaryArrayPrimaryMap, intArrayPrimaryMap, boolArrayPrimaryMap, decimalArrayPrimaryMap, guidArrayPrimaryMap, binaryArrayPrimaryMap, datespanArrayPrimaryMap, dateArrayPrimaryMap, geometryArrayPrimaryMap, fileArrayPrimaryMap, exceptionArrayPrimaryMap, encodingArrayPrimaryMap, selfArrayPrimaryMap, enumArrayPrimaryMap, sqlBoolArrayPrimaryMap, sqlIntArrayPrimaryMap, sqlDecimalArrayPrimaryMap, sqlStringArrayPrimaryMap, sqlGuidArrayPrimaryMap, sqlDateArrayPrimaryMap, sqlDatespanArrayPrimaryMap, sqlBinaryArrayPrimaryMap, sqlGeometryArrayPrimaryMap, sqlPrimaryArrayPrimaryMap, intArrayStringMap, intArrayIntMap, intArrayGuidMap, intArrayBoolMap, intArrayDecimalMap, decimalArrayStringMap, decimalArrayIntMap, decimalArrayGuidMap, decimalArrayBoolMap, decimalArrayDecimalMap, boolArrayStringMap, boolArrayIntMap, boolArrayGuidMap, boolArrayBoolMap, boolArrayDecimalMap, stringArrayStringMap, stringArrayIntMap, stringArrayGuidMap, stringArrayBoolMap, stringArrayDecimalMap, guidArrayStringMap, guidArrayIntMap, guidArrayGuidMap, guidArrayBoolMap, guidArrayDecimalMap, binaryArrayStringMap, binaryArrayIntMap, binaryArrayGuidMap, binaryArrayBoolMap, binaryArrayDecimalMap, datespanArrayStringMap, datespanArrayIntMap, datespanArrayGuidMap, datespanArrayBoolMap, datespanArrayDecimalMap, dateArrayStringMap, dateArrayIntMap, dateArrayGuidMap, dateArrayBoolMap, dateArrayDecimalMap, geometryArrayStringMap, geometryArrayIntMap, geometryArrayGuidMap, geometryArrayBoolMap, geometryArrayDecimalMap, fileArrayStringMap, fileArrayIntMap, fileArrayGuidMap, fileArrayBoolMap, fileArrayDecimalMap, exceptionArrayStringMap, exceptionArrayIntMap, exceptionArrayGuidMap, exceptionArrayBoolMap, exceptionArrayDecimalMap, encodingArrayStringMap, encodingArrayIntMap, encodingArrayGuidMap, encodingArrayBoolMap, encodingArrayDecimalMap, primaryArrayStringMap, primaryArrayIntMap, primaryArrayGuidMap, primaryArrayBoolMap, primaryArrayDecimalMap, selfArrayStringMap, selfArrayIntMap, selfArrayGuidMap, selfArrayBoolMap, selfArrayDecimalMap, enumArrayStringMap, enumArrayIntMap, enumArrayGuidMap, enumArrayBoolMap, enumArrayDecimalMap, sqlBoolArrayStringMap, sqlBoolArrayIntMap, sqlBoolArrayGuidMap, sqlBoolArrayBoolMap, sqlBoolArrayDecimalMap, sqlIntArrayStringMap, sqlIntArrayIntMap, sqlIntArrayGuidMap, sqlIntArrayBoolMap, sqlIntArrayDecimalMap, sqlDecimalArrayStringMap, sqlDecimalArrayIntMap, sqlDecimalArrayGuidMap, sqlDecimalArrayBoolMap, sqlDecimalArrayDecimalMap, sqlStringArrayStringMap, sqlStringArrayIntMap, sqlStringArrayGuidMap, sqlStringArrayBoolMap, sqlStringArrayDecimalMap, sqlGuidArrayStringMap, sqlGuidArrayIntMap, sqlGuidArrayGuidMap, sqlGuidArrayBoolMap, sqlGuidArrayDecimalMap, sqlDateArrayStringMap, sqlDateArrayIntMap, sqlDateArrayGuidMap, sqlDateArrayBoolMap, sqlDateArrayDecimalMap, sqlDatespanArrayStringMap, sqlDatespanArrayIntMap, sqlDatespanArrayGuidMap, sqlDatespanArrayBoolMap, sqlDatespanArrayDecimalMap, sqlBinaryArrayStringMap, sqlBinaryArrayIntMap, sqlBinaryArrayGuidMap, sqlBinaryArrayBoolMap, sqlBinaryArrayDecimalMap, sqlGeometryArrayStringMap, sqlGeometryArrayIntMap, sqlGeometryArrayGuidMap, sqlGeometryArrayBoolMap, sqlGeometryArrayDecimalMap, sqlPrimaryArrayStringMap, sqlPrimaryArrayIntMap, sqlPrimaryArrayGuidMap, sqlPrimaryArrayBoolMap, sqlPrimaryArrayDecimalMap, binaryStringMap, binaryIntMap, binaryGuidMap, binaryBoolMap, binaryDecimalMap, datespanStringMap, datespanIntMap, datespanGuidMap, datespanBoolMap, datespanDecimalMap, dateStringMap, dateIntMap, dateGuidMap, dateBoolMap, dateDecimalMap, geometryStringMap, geometryIntMap, geometryGuidMap, geometryBoolMap, geometryDecimalMap, fileStringMap, fileIntMap, fileGuidMap, fileBoolMap, fileDecimalMap, exceptionStringMap, exceptionIntMap, exceptionGuidMap, exceptionBoolMap, exceptionDecimalMap, encodingStringMap, encodingIntMap, encodingGuidMap, encodingBoolMap, encodingDecimalMap, selfStringMap, selfIntMap, selfGuidMap, selfBoolMap, selfDecimalMap, enumStringMap, enumIntMap, enumGuidMap, enumBoolMap, enumDecimalMap, intType, decimalType, boolType, stringType, guidType, binaryType, datespanType, dateType, geometryType, fileType, exceptionType, encodingType, ftsType, ftsQueryType, sqlBoolType, sqlIntType, sqlDecimalType, sqlStringType, sqlGuidType, sqlDateType, sqlDatespanType, sqlBinaryType, sqlGeometryType, sqlPrimaryType, sqlBoolStringMap, sqlBoolIntMap, sqlBoolGuidMap, sqlBoolBoolMap, sqlBoolDecimalMap, sqlIntStringMap, sqlIntIntMap, sqlIntGuidMap, sqlIntBoolMap, sqlIntDecimalMap, sqlDecimalStringMap, sqlDecimalIntMap, sqlDecimalGuidMap, sqlDecimalBoolMap, sqlDecimalDecimalMap, sqlStringStringMap, sqlStringIntMap, sqlStringGuidMap, sqlStringBoolMap, sqlStringDecimalMap, sqlGuidStringMap, sqlGuidIntMap, sqlGuidGuidMap, sqlGuidBoolMap, sqlGuidDecimalMap, sqlDateStringMap, sqlDateIntMap, sqlDateGuidMap, sqlDateBoolMap, sqlDateDecimalMap, sqlDatespanStringMap, sqlDatespanIntMap, sqlDatespanGuidMap, sqlDatespanBoolMap, sqlDatespanDecimalMap, sqlBinaryStringMap, sqlBinaryIntMap, sqlBinaryGuidMap, sqlBinaryBoolMap, sqlBinaryDecimalMap, sqlGeometryStringMap, sqlGeometryIntMap, sqlGeometryGuidMap, sqlGeometryBoolMap, sqlGeometryDecimalMap, sqlPrimaryStringMap, sqlPrimaryIntMap, sqlPrimaryGuidMap, sqlPrimaryBoolMap, sqlPrimaryDecimalMap, sqlBoolArray, sqlBoolMatrix, sqlIntArray, sqlIntMatrix, sqlDecimalArray, sqlDecimalMatrix, sqlStringArray, sqlStringMatrix, sqlGuidArray, sqlGuidMatrix, sqlDateArray, sqlDateMatrix, sqlDatespanArray, sqlDatespanMatrix, sqlBinaryArray, sqlBinaryMatrix, sqlGeometryArray, sqlGeometryMatrix, sqlPrimaryArray, sqlPrimaryMatrix, primaryType, selfType, intArray, intMatrix, decimalArray, decimalMatrix, boolArray, boolMatrix, stringArray, stringMatrix, guidArray, guidMatrix, binaryArray, binaryMatrix, datespanArray, datespanMatrix, dateArray, dateMatrix, geometryArray, geometryMatrix, fileArray, fileMatrix, exceptionArray, exceptionMatrix, encodingArray, encodingMatrix, primaryArray, primaryMatrix, selfArray, selfMatrix, stringMap, primaryStringMap, intStringMap, boolStringMap, decimalStringMap, guidStringMap, intIntMap, stringIntMap, primaryIntMap, boolIntMap, decimalIntMap, guidIntMap, stringGuidMap, primaryGuidMap, intGuidMap, boolGuidMap, decimalGuidMap, guidGuidMap, stringBoolMap, primaryBoolMap, intBoolMap, boolBoolMap, decimalBoolMap, guidBoolMap, stringDecimalMap, primaryDecimalMap, intDecimalMap, boolDecimalMap, decimalDecimalMap, guidDecimalMap, nullType, nullableString, enumType, enumArray, enumMatrix, optionalInt, optionalBool, optionalDecimal }
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
    bool makeFile, makeException, convertToDate, convertToSqlBool, convertToSqlInt, convertToSqlDecimal, convertSqlIntToDecimal, convertToSqlString, convertToSqlGuid;
    bool sqlBoolOperator, sqlBoolPriority, sqlIntOperator, sqlIntComparison, sqlIntPriority, sqlDecimalOperator, sqlDecimalComparison, sqlDecimalPriority, sqlStringOperator, sqlStringComparison, sqlStringPriority;
    bool sqlGuidOperator, sqlGuidPriority;
    bool convertToSqlDate, sqlDatePriority, sqlDateOperator;
    bool convertToSqlDatespan, sqlDatespanPriority, sqlDatespanOperator, sqlDatespanComparison, sqlDateArithmetic;
    bool convertToSqlGeometry, sqlGeometryPriority, sqlGeometryOperator;
    bool sqlPrimaryCast, sqlPrimaryInstanceOf;
    bool dateBinary, fileBinary;
    bool primaryCast, primaryInstanceOf, objectInstanceOf, scalarInstanceOf, falseInstanceOf, exceptionInstanceOf;
    bool typedInitializer;
    size_t parenthesisCount;
    bool firstParenthesisIsConditional;
    Method priorityMethod;
    ValueType initializerType;
    string initializerObjectName, initializerKeyObjectName;
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
    Program objectClass, keyObjectClass;
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
    string objectName, keyObjectName;
    Program objectClass, keyObjectClass, nestedClass;
    Method priorityMethod;
    bool sqlBoolReturnPriority, sqlIntReturnPriority, sqlDecimalReturnPriority, sqlStringReturnPriority;
    bool sqlGuidReturnPriority;
    bool sqlDateReturnPriority;
    bool sqlDatespanReturnPriority;
    bool sqlGeometryReturnPriority;
    this(StmtKind kind, Token token) { this.kind = kind; this.token = token; }
}
struct Parameter { ValueType type; Token name; string objectName, keyObjectName; Program objectClass, keyObjectClass; bool declaredFinal; }
class Method {
    ValueType returnType;
    Token name;
    Parameter[] parameters;
    TypeAttribute[] attributes;
    Statement body;
    bool isPublic, isProtected;
    bool isStatic;
    string returnObjectName, returnKeyObjectName;
    Program returnObjectClass, returnKeyObjectClass;
    Program owner;
    bool isVirtual, overrides;
    string operatorSymbol;
    bool isCastOperator;
    bool isPriorityOperator;
}
class Field { ValueType type; Token name; TypeAttribute[] attributes; Expression initializer; bool isPublic, isProtected, isStatic, isAuto, isRecord, declaredFinal, userOperatorAssignment; string objectName, keyObjectName; Program objectClass, keyObjectClass; Program owner, nestedClass; }
struct TypeAttribute { Token name; Token value; Expression expression; ValueType expressionType; long capturedDateTicks; bool hasValue, dateTickCaptured; }
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
struct Capture { string name; ValueType type; Program objectClass, keyObjectClass; }
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

private struct SqlArrayDescriptor { ValueType element, array, matrix; }
private enum SqlArrayDescriptor[] sqlArrayDescriptors = [
    SqlArrayDescriptor(ValueType.sqlBoolType, ValueType.sqlBoolArray, ValueType.sqlBoolMatrix),
    SqlArrayDescriptor(ValueType.sqlIntType, ValueType.sqlIntArray, ValueType.sqlIntMatrix),
    SqlArrayDescriptor(ValueType.sqlDecimalType, ValueType.sqlDecimalArray, ValueType.sqlDecimalMatrix),
    SqlArrayDescriptor(ValueType.sqlStringType, ValueType.sqlStringArray, ValueType.sqlStringMatrix),
    SqlArrayDescriptor(ValueType.sqlGuidType, ValueType.sqlGuidArray, ValueType.sqlGuidMatrix),
    SqlArrayDescriptor(ValueType.sqlDateType, ValueType.sqlDateArray, ValueType.sqlDateMatrix),
    SqlArrayDescriptor(ValueType.sqlDatespanType, ValueType.sqlDatespanArray, ValueType.sqlDatespanMatrix),
    SqlArrayDescriptor(ValueType.sqlBinaryType, ValueType.sqlBinaryArray, ValueType.sqlBinaryMatrix),
    SqlArrayDescriptor(ValueType.sqlGeometryType, ValueType.sqlGeometryArray, ValueType.sqlGeometryMatrix),
    SqlArrayDescriptor(ValueType.sqlPrimaryType, ValueType.sqlPrimaryArray, ValueType.sqlPrimaryMatrix),
];
package bool isSqlArray(ValueType type) {
    foreach (d; sqlArrayDescriptors) if (d.array == type || d.matrix == type) return true;
    return false;
}
package ValueType sqlArrayType(ValueType element, bool matrix) {
    foreach (d; sqlArrayDescriptors) if (d.element == element) return matrix ? d.matrix : d.array;
    return ValueType.voidType;
}
private ValueType sqlArrayElement(ValueType type) {
    foreach (d; sqlArrayDescriptors) {
        if (d.array == type) return d.element;
        if (d.matrix == type) return d.array;
    }
    assert(0, "not a SQL array");
}
unittest {
    foreach (d; sqlArrayDescriptors) {
        assert(sqlArrayType(d.element, false) == d.array);
        assert(sqlArrayType(d.element, true) == d.matrix);
        assert(elementType(d.array) == d.element && elementType(d.matrix) == d.array);
        assert(isArray(d.array) && isArray(d.matrix));
    }
}
// Add one sequence dimension, preserving its element type.
package ValueType arrayOf(ValueType type) {
    if (type == ValueType.intType) return ValueType.intArray;
    if (type == ValueType.intArray) return ValueType.intMatrix;
    if (type == ValueType.decimalType) return ValueType.decimalArray;
    if (type == ValueType.decimalArray) return ValueType.decimalMatrix;
    if (type == ValueType.boolType) return ValueType.boolArray;
    if (type == ValueType.boolArray) return ValueType.boolMatrix;
    if (type == ValueType.stringType) return ValueType.stringArray;
    if (type == ValueType.stringArray) return ValueType.stringMatrix;
    if (type == ValueType.guidType) return ValueType.guidArray;
    if (type == ValueType.guidArray) return ValueType.guidMatrix;
    if (type == ValueType.binaryType) return ValueType.binaryArray;
    if (type == ValueType.binaryArray) return ValueType.binaryMatrix;
    if (type == ValueType.datespanType) return ValueType.datespanArray;
    if (type == ValueType.datespanArray) return ValueType.datespanMatrix;
    if (type == ValueType.dateType) return ValueType.dateArray;
    if (type == ValueType.dateArray) return ValueType.dateMatrix;
    if (type == ValueType.geometryType) return ValueType.geometryArray;
    if (type == ValueType.geometryArray) return ValueType.geometryMatrix;
    if (type == ValueType.fileType) return ValueType.fileArray;
    if (type == ValueType.fileArray) return ValueType.fileMatrix;
    if (type == ValueType.exceptionType) return ValueType.exceptionArray;
    if (type == ValueType.exceptionArray) return ValueType.exceptionMatrix;
    if (type == ValueType.encodingType) return ValueType.encodingArray;
    if (type == ValueType.encodingArray) return ValueType.encodingMatrix;
    if (type == ValueType.primaryType) return ValueType.primaryArray;
    if (type == ValueType.primaryArray) return ValueType.primaryMatrix;
    if (type == ValueType.selfType) return ValueType.selfArray;
    if (type == ValueType.selfArray) return ValueType.selfMatrix;
    if (type == ValueType.enumType) return ValueType.enumArray;
    if (type == ValueType.enumArray) return ValueType.enumMatrix;
    foreach (d; sqlArrayDescriptors) {
        if (type == d.element) return d.array;
        if (type == d.array) return d.matrix;
    }
    return ValueType.voidType;
}
package bool isArray(ValueType type) {
    return isSqlArray(type) || [ValueType.intArray, ValueType.intMatrix, ValueType.decimalArray, ValueType.decimalMatrix, ValueType.boolArray, ValueType.boolMatrix, ValueType.stringArray, ValueType.stringMatrix, ValueType.guidArray, ValueType.guidMatrix, ValueType.binaryArray, ValueType.binaryMatrix, ValueType.datespanArray, ValueType.datespanMatrix, ValueType.dateArray, ValueType.dateMatrix, ValueType.geometryArray, ValueType.geometryMatrix, ValueType.fileArray, ValueType.fileMatrix, ValueType.exceptionArray, ValueType.exceptionMatrix, ValueType.encodingArray, ValueType.encodingMatrix, ValueType.primaryArray, ValueType.primaryMatrix, ValueType.selfArray, ValueType.selfMatrix, ValueType.enumArray, ValueType.enumMatrix].canFind(type);
}
package bool isReferenceArray(ValueType type) { return isSqlArray(type) || [ValueType.selfArray, ValueType.enumArray, ValueType.primaryArray, ValueType.guidArray, ValueType.binaryArray, ValueType.datespanArray, ValueType.dateArray, ValueType.geometryArray, ValueType.fileArray, ValueType.exceptionArray, ValueType.encodingArray, ValueType.intMatrix, ValueType.decimalMatrix, ValueType.boolMatrix, ValueType.stringMatrix, ValueType.guidMatrix, ValueType.binaryMatrix, ValueType.datespanMatrix, ValueType.dateMatrix, ValueType.geometryMatrix, ValueType.fileMatrix, ValueType.exceptionMatrix, ValueType.encodingMatrix, ValueType.primaryMatrix, ValueType.selfMatrix, ValueType.enumMatrix].canFind(type); }
// Each supported map has a single description of its value and key types.
// VariableType in the original compiler likewise stores the value type and keys.
private struct MapDescriptor { ValueType type, value, key; }
private enum MapDescriptor[] mapDescriptors = [
    MapDescriptor(ValueType.stringObjectKeyMap, ValueType.stringType, ValueType.selfType),
    MapDescriptor(ValueType.stringEnumKeyMap, ValueType.stringType, ValueType.enumType),
    MapDescriptor(ValueType.primaryObjectKeyMap, ValueType.primaryType, ValueType.selfType),
    MapDescriptor(ValueType.primaryEnumKeyMap, ValueType.primaryType, ValueType.enumType),
    MapDescriptor(ValueType.intObjectKeyMap, ValueType.intType, ValueType.selfType),
    MapDescriptor(ValueType.intEnumKeyMap, ValueType.intType, ValueType.enumType),
    MapDescriptor(ValueType.boolObjectKeyMap, ValueType.boolType, ValueType.selfType),
    MapDescriptor(ValueType.boolEnumKeyMap, ValueType.boolType, ValueType.enumType),
    MapDescriptor(ValueType.decimalObjectKeyMap, ValueType.decimalType, ValueType.selfType),
    MapDescriptor(ValueType.decimalEnumKeyMap, ValueType.decimalType, ValueType.enumType),
    MapDescriptor(ValueType.guidObjectKeyMap, ValueType.guidType, ValueType.selfType),
    MapDescriptor(ValueType.guidEnumKeyMap, ValueType.guidType, ValueType.enumType),
    MapDescriptor(ValueType.binaryObjectKeyMap, ValueType.binaryType, ValueType.selfType),
    MapDescriptor(ValueType.binaryEnumKeyMap, ValueType.binaryType, ValueType.enumType),
    MapDescriptor(ValueType.datespanObjectKeyMap, ValueType.datespanType, ValueType.selfType),
    MapDescriptor(ValueType.datespanEnumKeyMap, ValueType.datespanType, ValueType.enumType),
    MapDescriptor(ValueType.dateObjectKeyMap, ValueType.dateType, ValueType.selfType),
    MapDescriptor(ValueType.dateEnumKeyMap, ValueType.dateType, ValueType.enumType),
    MapDescriptor(ValueType.geometryObjectKeyMap, ValueType.geometryType, ValueType.selfType),
    MapDescriptor(ValueType.geometryEnumKeyMap, ValueType.geometryType, ValueType.enumType),
    MapDescriptor(ValueType.fileObjectKeyMap, ValueType.fileType, ValueType.selfType),
    MapDescriptor(ValueType.fileEnumKeyMap, ValueType.fileType, ValueType.enumType),
    MapDescriptor(ValueType.exceptionObjectKeyMap, ValueType.exceptionType, ValueType.selfType),
    MapDescriptor(ValueType.exceptionEnumKeyMap, ValueType.exceptionType, ValueType.enumType),
    MapDescriptor(ValueType.encodingObjectKeyMap, ValueType.encodingType, ValueType.selfType),
    MapDescriptor(ValueType.encodingEnumKeyMap, ValueType.encodingType, ValueType.enumType),
    MapDescriptor(ValueType.selfObjectKeyMap, ValueType.selfType, ValueType.selfType),
    MapDescriptor(ValueType.selfEnumKeyMap, ValueType.selfType, ValueType.enumType),
    MapDescriptor(ValueType.enumObjectKeyMap, ValueType.enumType, ValueType.selfType),
    MapDescriptor(ValueType.enumEnumKeyMap, ValueType.enumType, ValueType.enumType),
    MapDescriptor(ValueType.sqlBoolObjectKeyMap, ValueType.sqlBoolType, ValueType.selfType),
    MapDescriptor(ValueType.sqlBoolEnumKeyMap, ValueType.sqlBoolType, ValueType.enumType),
    MapDescriptor(ValueType.sqlIntObjectKeyMap, ValueType.sqlIntType, ValueType.selfType),
    MapDescriptor(ValueType.sqlIntEnumKeyMap, ValueType.sqlIntType, ValueType.enumType),
    MapDescriptor(ValueType.sqlDecimalObjectKeyMap, ValueType.sqlDecimalType, ValueType.selfType),
    MapDescriptor(ValueType.sqlDecimalEnumKeyMap, ValueType.sqlDecimalType, ValueType.enumType),
    MapDescriptor(ValueType.sqlStringObjectKeyMap, ValueType.sqlStringType, ValueType.selfType),
    MapDescriptor(ValueType.sqlStringEnumKeyMap, ValueType.sqlStringType, ValueType.enumType),
    MapDescriptor(ValueType.sqlGuidObjectKeyMap, ValueType.sqlGuidType, ValueType.selfType),
    MapDescriptor(ValueType.sqlGuidEnumKeyMap, ValueType.sqlGuidType, ValueType.enumType),
    MapDescriptor(ValueType.sqlDateObjectKeyMap, ValueType.sqlDateType, ValueType.selfType),
    MapDescriptor(ValueType.sqlDateEnumKeyMap, ValueType.sqlDateType, ValueType.enumType),
    MapDescriptor(ValueType.sqlDatespanObjectKeyMap, ValueType.sqlDatespanType, ValueType.selfType),
    MapDescriptor(ValueType.sqlDatespanEnumKeyMap, ValueType.sqlDatespanType, ValueType.enumType),
    MapDescriptor(ValueType.sqlBinaryObjectKeyMap, ValueType.sqlBinaryType, ValueType.selfType),
    MapDescriptor(ValueType.sqlBinaryEnumKeyMap, ValueType.sqlBinaryType, ValueType.enumType),
    MapDescriptor(ValueType.sqlGeometryObjectKeyMap, ValueType.sqlGeometryType, ValueType.selfType),
    MapDescriptor(ValueType.sqlGeometryEnumKeyMap, ValueType.sqlGeometryType, ValueType.enumType),
    MapDescriptor(ValueType.sqlPrimaryObjectKeyMap, ValueType.sqlPrimaryType, ValueType.selfType),
    MapDescriptor(ValueType.sqlPrimaryEnumKeyMap, ValueType.sqlPrimaryType, ValueType.enumType),
    MapDescriptor(ValueType.stringArrayObjectKeyMap, ValueType.stringArray, ValueType.selfType),
    MapDescriptor(ValueType.stringArrayEnumKeyMap, ValueType.stringArray, ValueType.enumType),
    MapDescriptor(ValueType.primaryArrayObjectKeyMap, ValueType.primaryArray, ValueType.selfType),
    MapDescriptor(ValueType.primaryArrayEnumKeyMap, ValueType.primaryArray, ValueType.enumType),
    MapDescriptor(ValueType.intArrayObjectKeyMap, ValueType.intArray, ValueType.selfType),
    MapDescriptor(ValueType.intArrayEnumKeyMap, ValueType.intArray, ValueType.enumType),
    MapDescriptor(ValueType.boolArrayObjectKeyMap, ValueType.boolArray, ValueType.selfType),
    MapDescriptor(ValueType.boolArrayEnumKeyMap, ValueType.boolArray, ValueType.enumType),
    MapDescriptor(ValueType.decimalArrayObjectKeyMap, ValueType.decimalArray, ValueType.selfType),
    MapDescriptor(ValueType.decimalArrayEnumKeyMap, ValueType.decimalArray, ValueType.enumType),
    MapDescriptor(ValueType.guidArrayObjectKeyMap, ValueType.guidArray, ValueType.selfType),
    MapDescriptor(ValueType.guidArrayEnumKeyMap, ValueType.guidArray, ValueType.enumType),
    MapDescriptor(ValueType.binaryArrayObjectKeyMap, ValueType.binaryArray, ValueType.selfType),
    MapDescriptor(ValueType.binaryArrayEnumKeyMap, ValueType.binaryArray, ValueType.enumType),
    MapDescriptor(ValueType.datespanArrayObjectKeyMap, ValueType.datespanArray, ValueType.selfType),
    MapDescriptor(ValueType.datespanArrayEnumKeyMap, ValueType.datespanArray, ValueType.enumType),
    MapDescriptor(ValueType.dateArrayObjectKeyMap, ValueType.dateArray, ValueType.selfType),
    MapDescriptor(ValueType.dateArrayEnumKeyMap, ValueType.dateArray, ValueType.enumType),
    MapDescriptor(ValueType.geometryArrayObjectKeyMap, ValueType.geometryArray, ValueType.selfType),
    MapDescriptor(ValueType.geometryArrayEnumKeyMap, ValueType.geometryArray, ValueType.enumType),
    MapDescriptor(ValueType.fileArrayObjectKeyMap, ValueType.fileArray, ValueType.selfType),
    MapDescriptor(ValueType.fileArrayEnumKeyMap, ValueType.fileArray, ValueType.enumType),
    MapDescriptor(ValueType.exceptionArrayObjectKeyMap, ValueType.exceptionArray, ValueType.selfType),
    MapDescriptor(ValueType.exceptionArrayEnumKeyMap, ValueType.exceptionArray, ValueType.enumType),
    MapDescriptor(ValueType.encodingArrayObjectKeyMap, ValueType.encodingArray, ValueType.selfType),
    MapDescriptor(ValueType.encodingArrayEnumKeyMap, ValueType.encodingArray, ValueType.enumType),
    MapDescriptor(ValueType.selfArrayObjectKeyMap, ValueType.selfArray, ValueType.selfType),
    MapDescriptor(ValueType.selfArrayEnumKeyMap, ValueType.selfArray, ValueType.enumType),
    MapDescriptor(ValueType.enumArrayObjectKeyMap, ValueType.enumArray, ValueType.selfType),
    MapDescriptor(ValueType.enumArrayEnumKeyMap, ValueType.enumArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlBoolArrayObjectKeyMap, ValueType.sqlBoolArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlBoolArrayEnumKeyMap, ValueType.sqlBoolArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlIntArrayObjectKeyMap, ValueType.sqlIntArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlIntArrayEnumKeyMap, ValueType.sqlIntArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlDecimalArrayObjectKeyMap, ValueType.sqlDecimalArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlDecimalArrayEnumKeyMap, ValueType.sqlDecimalArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlStringArrayObjectKeyMap, ValueType.sqlStringArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlStringArrayEnumKeyMap, ValueType.sqlStringArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlGuidArrayObjectKeyMap, ValueType.sqlGuidArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlGuidArrayEnumKeyMap, ValueType.sqlGuidArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlDateArrayObjectKeyMap, ValueType.sqlDateArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlDateArrayEnumKeyMap, ValueType.sqlDateArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlDatespanArrayObjectKeyMap, ValueType.sqlDatespanArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlDatespanArrayEnumKeyMap, ValueType.sqlDatespanArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlBinaryArrayObjectKeyMap, ValueType.sqlBinaryArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlBinaryArrayEnumKeyMap, ValueType.sqlBinaryArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlGeometryArrayObjectKeyMap, ValueType.sqlGeometryArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlGeometryArrayEnumKeyMap, ValueType.sqlGeometryArray, ValueType.enumType),
    MapDescriptor(ValueType.sqlPrimaryArrayObjectKeyMap, ValueType.sqlPrimaryArray, ValueType.selfType),
    MapDescriptor(ValueType.sqlPrimaryArrayEnumKeyMap, ValueType.sqlPrimaryArray, ValueType.enumType),
    MapDescriptor(ValueType.stringDateMap, ValueType.stringType, ValueType.dateType),
    MapDescriptor(ValueType.stringDatespanMap, ValueType.stringType, ValueType.datespanType),
    MapDescriptor(ValueType.stringBinaryMap, ValueType.stringType, ValueType.binaryType),
    MapDescriptor(ValueType.stringGeometryMap, ValueType.stringType, ValueType.geometryType),
    MapDescriptor(ValueType.stringFileMap, ValueType.stringType, ValueType.fileType),
    MapDescriptor(ValueType.primaryDateMap, ValueType.primaryType, ValueType.dateType),
    MapDescriptor(ValueType.primaryDatespanMap, ValueType.primaryType, ValueType.datespanType),
    MapDescriptor(ValueType.primaryBinaryMap, ValueType.primaryType, ValueType.binaryType),
    MapDescriptor(ValueType.primaryGeometryMap, ValueType.primaryType, ValueType.geometryType),
    MapDescriptor(ValueType.primaryFileMap, ValueType.primaryType, ValueType.fileType),
    MapDescriptor(ValueType.intDateMap, ValueType.intType, ValueType.dateType),
    MapDescriptor(ValueType.intDatespanMap, ValueType.intType, ValueType.datespanType),
    MapDescriptor(ValueType.intBinaryMap, ValueType.intType, ValueType.binaryType),
    MapDescriptor(ValueType.intGeometryMap, ValueType.intType, ValueType.geometryType),
    MapDescriptor(ValueType.intFileMap, ValueType.intType, ValueType.fileType),
    MapDescriptor(ValueType.boolDateMap, ValueType.boolType, ValueType.dateType),
    MapDescriptor(ValueType.boolDatespanMap, ValueType.boolType, ValueType.datespanType),
    MapDescriptor(ValueType.boolBinaryMap, ValueType.boolType, ValueType.binaryType),
    MapDescriptor(ValueType.boolGeometryMap, ValueType.boolType, ValueType.geometryType),
    MapDescriptor(ValueType.boolFileMap, ValueType.boolType, ValueType.fileType),
    MapDescriptor(ValueType.decimalDateMap, ValueType.decimalType, ValueType.dateType),
    MapDescriptor(ValueType.decimalDatespanMap, ValueType.decimalType, ValueType.datespanType),
    MapDescriptor(ValueType.decimalBinaryMap, ValueType.decimalType, ValueType.binaryType),
    MapDescriptor(ValueType.decimalGeometryMap, ValueType.decimalType, ValueType.geometryType),
    MapDescriptor(ValueType.decimalFileMap, ValueType.decimalType, ValueType.fileType),
    MapDescriptor(ValueType.guidDateMap, ValueType.guidType, ValueType.dateType),
    MapDescriptor(ValueType.guidDatespanMap, ValueType.guidType, ValueType.datespanType),
    MapDescriptor(ValueType.guidBinaryMap, ValueType.guidType, ValueType.binaryType),
    MapDescriptor(ValueType.guidGeometryMap, ValueType.guidType, ValueType.geometryType),
    MapDescriptor(ValueType.guidFileMap, ValueType.guidType, ValueType.fileType),
    MapDescriptor(ValueType.binaryDateMap, ValueType.binaryType, ValueType.dateType),
    MapDescriptor(ValueType.binaryDatespanMap, ValueType.binaryType, ValueType.datespanType),
    MapDescriptor(ValueType.binaryBinaryMap, ValueType.binaryType, ValueType.binaryType),
    MapDescriptor(ValueType.binaryGeometryMap, ValueType.binaryType, ValueType.geometryType),
    MapDescriptor(ValueType.binaryFileMap, ValueType.binaryType, ValueType.fileType),
    MapDescriptor(ValueType.datespanDateMap, ValueType.datespanType, ValueType.dateType),
    MapDescriptor(ValueType.datespanDatespanMap, ValueType.datespanType, ValueType.datespanType),
    MapDescriptor(ValueType.datespanBinaryMap, ValueType.datespanType, ValueType.binaryType),
    MapDescriptor(ValueType.datespanGeometryMap, ValueType.datespanType, ValueType.geometryType),
    MapDescriptor(ValueType.datespanFileMap, ValueType.datespanType, ValueType.fileType),
    MapDescriptor(ValueType.dateDateMap, ValueType.dateType, ValueType.dateType),
    MapDescriptor(ValueType.dateDatespanMap, ValueType.dateType, ValueType.datespanType),
    MapDescriptor(ValueType.dateBinaryMap, ValueType.dateType, ValueType.binaryType),
    MapDescriptor(ValueType.dateGeometryMap, ValueType.dateType, ValueType.geometryType),
    MapDescriptor(ValueType.dateFileMap, ValueType.dateType, ValueType.fileType),
    MapDescriptor(ValueType.geometryDateMap, ValueType.geometryType, ValueType.dateType),
    MapDescriptor(ValueType.geometryDatespanMap, ValueType.geometryType, ValueType.datespanType),
    MapDescriptor(ValueType.geometryBinaryMap, ValueType.geometryType, ValueType.binaryType),
    MapDescriptor(ValueType.geometryGeometryMap, ValueType.geometryType, ValueType.geometryType),
    MapDescriptor(ValueType.geometryFileMap, ValueType.geometryType, ValueType.fileType),
    MapDescriptor(ValueType.fileDateMap, ValueType.fileType, ValueType.dateType),
    MapDescriptor(ValueType.fileDatespanMap, ValueType.fileType, ValueType.datespanType),
    MapDescriptor(ValueType.fileBinaryMap, ValueType.fileType, ValueType.binaryType),
    MapDescriptor(ValueType.fileGeometryMap, ValueType.fileType, ValueType.geometryType),
    MapDescriptor(ValueType.fileFileMap, ValueType.fileType, ValueType.fileType),
    MapDescriptor(ValueType.exceptionDateMap, ValueType.exceptionType, ValueType.dateType),
    MapDescriptor(ValueType.exceptionDatespanMap, ValueType.exceptionType, ValueType.datespanType),
    MapDescriptor(ValueType.exceptionBinaryMap, ValueType.exceptionType, ValueType.binaryType),
    MapDescriptor(ValueType.exceptionGeometryMap, ValueType.exceptionType, ValueType.geometryType),
    MapDescriptor(ValueType.exceptionFileMap, ValueType.exceptionType, ValueType.fileType),
    MapDescriptor(ValueType.encodingDateMap, ValueType.encodingType, ValueType.dateType),
    MapDescriptor(ValueType.encodingDatespanMap, ValueType.encodingType, ValueType.datespanType),
    MapDescriptor(ValueType.encodingBinaryMap, ValueType.encodingType, ValueType.binaryType),
    MapDescriptor(ValueType.encodingGeometryMap, ValueType.encodingType, ValueType.geometryType),
    MapDescriptor(ValueType.encodingFileMap, ValueType.encodingType, ValueType.fileType),
    MapDescriptor(ValueType.selfDateMap, ValueType.selfType, ValueType.dateType),
    MapDescriptor(ValueType.selfDatespanMap, ValueType.selfType, ValueType.datespanType),
    MapDescriptor(ValueType.selfBinaryMap, ValueType.selfType, ValueType.binaryType),
    MapDescriptor(ValueType.selfGeometryMap, ValueType.selfType, ValueType.geometryType),
    MapDescriptor(ValueType.selfFileMap, ValueType.selfType, ValueType.fileType),
    MapDescriptor(ValueType.enumDateMap, ValueType.enumType, ValueType.dateType),
    MapDescriptor(ValueType.enumDatespanMap, ValueType.enumType, ValueType.datespanType),
    MapDescriptor(ValueType.enumBinaryMap, ValueType.enumType, ValueType.binaryType),
    MapDescriptor(ValueType.enumGeometryMap, ValueType.enumType, ValueType.geometryType),
    MapDescriptor(ValueType.enumFileMap, ValueType.enumType, ValueType.fileType),
    MapDescriptor(ValueType.sqlBoolDateMap, ValueType.sqlBoolType, ValueType.dateType),
    MapDescriptor(ValueType.sqlBoolDatespanMap, ValueType.sqlBoolType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlBoolBinaryMap, ValueType.sqlBoolType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlBoolGeometryMap, ValueType.sqlBoolType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlBoolFileMap, ValueType.sqlBoolType, ValueType.fileType),
    MapDescriptor(ValueType.sqlIntDateMap, ValueType.sqlIntType, ValueType.dateType),
    MapDescriptor(ValueType.sqlIntDatespanMap, ValueType.sqlIntType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlIntBinaryMap, ValueType.sqlIntType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlIntGeometryMap, ValueType.sqlIntType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlIntFileMap, ValueType.sqlIntType, ValueType.fileType),
    MapDescriptor(ValueType.sqlDecimalDateMap, ValueType.sqlDecimalType, ValueType.dateType),
    MapDescriptor(ValueType.sqlDecimalDatespanMap, ValueType.sqlDecimalType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlDecimalBinaryMap, ValueType.sqlDecimalType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlDecimalGeometryMap, ValueType.sqlDecimalType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlDecimalFileMap, ValueType.sqlDecimalType, ValueType.fileType),
    MapDescriptor(ValueType.sqlStringDateMap, ValueType.sqlStringType, ValueType.dateType),
    MapDescriptor(ValueType.sqlStringDatespanMap, ValueType.sqlStringType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlStringBinaryMap, ValueType.sqlStringType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlStringGeometryMap, ValueType.sqlStringType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlStringFileMap, ValueType.sqlStringType, ValueType.fileType),
    MapDescriptor(ValueType.sqlGuidDateMap, ValueType.sqlGuidType, ValueType.dateType),
    MapDescriptor(ValueType.sqlGuidDatespanMap, ValueType.sqlGuidType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlGuidBinaryMap, ValueType.sqlGuidType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlGuidGeometryMap, ValueType.sqlGuidType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlGuidFileMap, ValueType.sqlGuidType, ValueType.fileType),
    MapDescriptor(ValueType.sqlDateDateMap, ValueType.sqlDateType, ValueType.dateType),
    MapDescriptor(ValueType.sqlDateDatespanMap, ValueType.sqlDateType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlDateBinaryMap, ValueType.sqlDateType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlDateGeometryMap, ValueType.sqlDateType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlDateFileMap, ValueType.sqlDateType, ValueType.fileType),
    MapDescriptor(ValueType.sqlDatespanDateMap, ValueType.sqlDatespanType, ValueType.dateType),
    MapDescriptor(ValueType.sqlDatespanDatespanMap, ValueType.sqlDatespanType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlDatespanBinaryMap, ValueType.sqlDatespanType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlDatespanGeometryMap, ValueType.sqlDatespanType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlDatespanFileMap, ValueType.sqlDatespanType, ValueType.fileType),
    MapDescriptor(ValueType.sqlBinaryDateMap, ValueType.sqlBinaryType, ValueType.dateType),
    MapDescriptor(ValueType.sqlBinaryDatespanMap, ValueType.sqlBinaryType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlBinaryBinaryMap, ValueType.sqlBinaryType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlBinaryGeometryMap, ValueType.sqlBinaryType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlBinaryFileMap, ValueType.sqlBinaryType, ValueType.fileType),
    MapDescriptor(ValueType.sqlGeometryDateMap, ValueType.sqlGeometryType, ValueType.dateType),
    MapDescriptor(ValueType.sqlGeometryDatespanMap, ValueType.sqlGeometryType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlGeometryBinaryMap, ValueType.sqlGeometryType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlGeometryGeometryMap, ValueType.sqlGeometryType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlGeometryFileMap, ValueType.sqlGeometryType, ValueType.fileType),
    MapDescriptor(ValueType.sqlPrimaryDateMap, ValueType.sqlPrimaryType, ValueType.dateType),
    MapDescriptor(ValueType.sqlPrimaryDatespanMap, ValueType.sqlPrimaryType, ValueType.datespanType),
    MapDescriptor(ValueType.sqlPrimaryBinaryMap, ValueType.sqlPrimaryType, ValueType.binaryType),
    MapDescriptor(ValueType.sqlPrimaryGeometryMap, ValueType.sqlPrimaryType, ValueType.geometryType),
    MapDescriptor(ValueType.sqlPrimaryFileMap, ValueType.sqlPrimaryType, ValueType.fileType),
    MapDescriptor(ValueType.stringArrayDateMap, ValueType.stringArray, ValueType.dateType),
    MapDescriptor(ValueType.stringArrayDatespanMap, ValueType.stringArray, ValueType.datespanType),
    MapDescriptor(ValueType.stringArrayBinaryMap, ValueType.stringArray, ValueType.binaryType),
    MapDescriptor(ValueType.stringArrayGeometryMap, ValueType.stringArray, ValueType.geometryType),
    MapDescriptor(ValueType.stringArrayFileMap, ValueType.stringArray, ValueType.fileType),
    MapDescriptor(ValueType.primaryArrayDateMap, ValueType.primaryArray, ValueType.dateType),
    MapDescriptor(ValueType.primaryArrayDatespanMap, ValueType.primaryArray, ValueType.datespanType),
    MapDescriptor(ValueType.primaryArrayBinaryMap, ValueType.primaryArray, ValueType.binaryType),
    MapDescriptor(ValueType.primaryArrayGeometryMap, ValueType.primaryArray, ValueType.geometryType),
    MapDescriptor(ValueType.primaryArrayFileMap, ValueType.primaryArray, ValueType.fileType),
    MapDescriptor(ValueType.intArrayDateMap, ValueType.intArray, ValueType.dateType),
    MapDescriptor(ValueType.intArrayDatespanMap, ValueType.intArray, ValueType.datespanType),
    MapDescriptor(ValueType.intArrayBinaryMap, ValueType.intArray, ValueType.binaryType),
    MapDescriptor(ValueType.intArrayGeometryMap, ValueType.intArray, ValueType.geometryType),
    MapDescriptor(ValueType.intArrayFileMap, ValueType.intArray, ValueType.fileType),
    MapDescriptor(ValueType.boolArrayDateMap, ValueType.boolArray, ValueType.dateType),
    MapDescriptor(ValueType.boolArrayDatespanMap, ValueType.boolArray, ValueType.datespanType),
    MapDescriptor(ValueType.boolArrayBinaryMap, ValueType.boolArray, ValueType.binaryType),
    MapDescriptor(ValueType.boolArrayGeometryMap, ValueType.boolArray, ValueType.geometryType),
    MapDescriptor(ValueType.boolArrayFileMap, ValueType.boolArray, ValueType.fileType),
    MapDescriptor(ValueType.decimalArrayDateMap, ValueType.decimalArray, ValueType.dateType),
    MapDescriptor(ValueType.decimalArrayDatespanMap, ValueType.decimalArray, ValueType.datespanType),
    MapDescriptor(ValueType.decimalArrayBinaryMap, ValueType.decimalArray, ValueType.binaryType),
    MapDescriptor(ValueType.decimalArrayGeometryMap, ValueType.decimalArray, ValueType.geometryType),
    MapDescriptor(ValueType.decimalArrayFileMap, ValueType.decimalArray, ValueType.fileType),
    MapDescriptor(ValueType.guidArrayDateMap, ValueType.guidArray, ValueType.dateType),
    MapDescriptor(ValueType.guidArrayDatespanMap, ValueType.guidArray, ValueType.datespanType),
    MapDescriptor(ValueType.guidArrayBinaryMap, ValueType.guidArray, ValueType.binaryType),
    MapDescriptor(ValueType.guidArrayGeometryMap, ValueType.guidArray, ValueType.geometryType),
    MapDescriptor(ValueType.guidArrayFileMap, ValueType.guidArray, ValueType.fileType),
    MapDescriptor(ValueType.binaryArrayDateMap, ValueType.binaryArray, ValueType.dateType),
    MapDescriptor(ValueType.binaryArrayDatespanMap, ValueType.binaryArray, ValueType.datespanType),
    MapDescriptor(ValueType.binaryArrayBinaryMap, ValueType.binaryArray, ValueType.binaryType),
    MapDescriptor(ValueType.binaryArrayGeometryMap, ValueType.binaryArray, ValueType.geometryType),
    MapDescriptor(ValueType.binaryArrayFileMap, ValueType.binaryArray, ValueType.fileType),
    MapDescriptor(ValueType.datespanArrayDateMap, ValueType.datespanArray, ValueType.dateType),
    MapDescriptor(ValueType.datespanArrayDatespanMap, ValueType.datespanArray, ValueType.datespanType),
    MapDescriptor(ValueType.datespanArrayBinaryMap, ValueType.datespanArray, ValueType.binaryType),
    MapDescriptor(ValueType.datespanArrayGeometryMap, ValueType.datespanArray, ValueType.geometryType),
    MapDescriptor(ValueType.datespanArrayFileMap, ValueType.datespanArray, ValueType.fileType),
    MapDescriptor(ValueType.dateArrayDateMap, ValueType.dateArray, ValueType.dateType),
    MapDescriptor(ValueType.dateArrayDatespanMap, ValueType.dateArray, ValueType.datespanType),
    MapDescriptor(ValueType.dateArrayBinaryMap, ValueType.dateArray, ValueType.binaryType),
    MapDescriptor(ValueType.dateArrayGeometryMap, ValueType.dateArray, ValueType.geometryType),
    MapDescriptor(ValueType.dateArrayFileMap, ValueType.dateArray, ValueType.fileType),
    MapDescriptor(ValueType.geometryArrayDateMap, ValueType.geometryArray, ValueType.dateType),
    MapDescriptor(ValueType.geometryArrayDatespanMap, ValueType.geometryArray, ValueType.datespanType),
    MapDescriptor(ValueType.geometryArrayBinaryMap, ValueType.geometryArray, ValueType.binaryType),
    MapDescriptor(ValueType.geometryArrayGeometryMap, ValueType.geometryArray, ValueType.geometryType),
    MapDescriptor(ValueType.geometryArrayFileMap, ValueType.geometryArray, ValueType.fileType),
    MapDescriptor(ValueType.fileArrayDateMap, ValueType.fileArray, ValueType.dateType),
    MapDescriptor(ValueType.fileArrayDatespanMap, ValueType.fileArray, ValueType.datespanType),
    MapDescriptor(ValueType.fileArrayBinaryMap, ValueType.fileArray, ValueType.binaryType),
    MapDescriptor(ValueType.fileArrayGeometryMap, ValueType.fileArray, ValueType.geometryType),
    MapDescriptor(ValueType.fileArrayFileMap, ValueType.fileArray, ValueType.fileType),
    MapDescriptor(ValueType.exceptionArrayDateMap, ValueType.exceptionArray, ValueType.dateType),
    MapDescriptor(ValueType.exceptionArrayDatespanMap, ValueType.exceptionArray, ValueType.datespanType),
    MapDescriptor(ValueType.exceptionArrayBinaryMap, ValueType.exceptionArray, ValueType.binaryType),
    MapDescriptor(ValueType.exceptionArrayGeometryMap, ValueType.exceptionArray, ValueType.geometryType),
    MapDescriptor(ValueType.exceptionArrayFileMap, ValueType.exceptionArray, ValueType.fileType),
    MapDescriptor(ValueType.encodingArrayDateMap, ValueType.encodingArray, ValueType.dateType),
    MapDescriptor(ValueType.encodingArrayDatespanMap, ValueType.encodingArray, ValueType.datespanType),
    MapDescriptor(ValueType.encodingArrayBinaryMap, ValueType.encodingArray, ValueType.binaryType),
    MapDescriptor(ValueType.encodingArrayGeometryMap, ValueType.encodingArray, ValueType.geometryType),
    MapDescriptor(ValueType.encodingArrayFileMap, ValueType.encodingArray, ValueType.fileType),
    MapDescriptor(ValueType.selfArrayDateMap, ValueType.selfArray, ValueType.dateType),
    MapDescriptor(ValueType.selfArrayDatespanMap, ValueType.selfArray, ValueType.datespanType),
    MapDescriptor(ValueType.selfArrayBinaryMap, ValueType.selfArray, ValueType.binaryType),
    MapDescriptor(ValueType.selfArrayGeometryMap, ValueType.selfArray, ValueType.geometryType),
    MapDescriptor(ValueType.selfArrayFileMap, ValueType.selfArray, ValueType.fileType),
    MapDescriptor(ValueType.enumArrayDateMap, ValueType.enumArray, ValueType.dateType),
    MapDescriptor(ValueType.enumArrayDatespanMap, ValueType.enumArray, ValueType.datespanType),
    MapDescriptor(ValueType.enumArrayBinaryMap, ValueType.enumArray, ValueType.binaryType),
    MapDescriptor(ValueType.enumArrayGeometryMap, ValueType.enumArray, ValueType.geometryType),
    MapDescriptor(ValueType.enumArrayFileMap, ValueType.enumArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlBoolArrayDateMap, ValueType.sqlBoolArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlBoolArrayDatespanMap, ValueType.sqlBoolArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlBoolArrayBinaryMap, ValueType.sqlBoolArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlBoolArrayGeometryMap, ValueType.sqlBoolArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlBoolArrayFileMap, ValueType.sqlBoolArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlIntArrayDateMap, ValueType.sqlIntArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlIntArrayDatespanMap, ValueType.sqlIntArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlIntArrayBinaryMap, ValueType.sqlIntArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlIntArrayGeometryMap, ValueType.sqlIntArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlIntArrayFileMap, ValueType.sqlIntArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlDecimalArrayDateMap, ValueType.sqlDecimalArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlDecimalArrayDatespanMap, ValueType.sqlDecimalArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlDecimalArrayBinaryMap, ValueType.sqlDecimalArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlDecimalArrayGeometryMap, ValueType.sqlDecimalArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlDecimalArrayFileMap, ValueType.sqlDecimalArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlStringArrayDateMap, ValueType.sqlStringArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlStringArrayDatespanMap, ValueType.sqlStringArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlStringArrayBinaryMap, ValueType.sqlStringArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlStringArrayGeometryMap, ValueType.sqlStringArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlStringArrayFileMap, ValueType.sqlStringArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlGuidArrayDateMap, ValueType.sqlGuidArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlGuidArrayDatespanMap, ValueType.sqlGuidArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlGuidArrayBinaryMap, ValueType.sqlGuidArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlGuidArrayGeometryMap, ValueType.sqlGuidArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlGuidArrayFileMap, ValueType.sqlGuidArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlDateArrayDateMap, ValueType.sqlDateArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlDateArrayDatespanMap, ValueType.sqlDateArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlDateArrayBinaryMap, ValueType.sqlDateArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlDateArrayGeometryMap, ValueType.sqlDateArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlDateArrayFileMap, ValueType.sqlDateArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlDatespanArrayDateMap, ValueType.sqlDatespanArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlDatespanArrayDatespanMap, ValueType.sqlDatespanArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlDatespanArrayBinaryMap, ValueType.sqlDatespanArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlDatespanArrayGeometryMap, ValueType.sqlDatespanArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlDatespanArrayFileMap, ValueType.sqlDatespanArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlBinaryArrayDateMap, ValueType.sqlBinaryArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlBinaryArrayDatespanMap, ValueType.sqlBinaryArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlBinaryArrayBinaryMap, ValueType.sqlBinaryArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlBinaryArrayGeometryMap, ValueType.sqlBinaryArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlBinaryArrayFileMap, ValueType.sqlBinaryArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlGeometryArrayDateMap, ValueType.sqlGeometryArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlGeometryArrayDatespanMap, ValueType.sqlGeometryArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlGeometryArrayBinaryMap, ValueType.sqlGeometryArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlGeometryArrayGeometryMap, ValueType.sqlGeometryArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlGeometryArrayFileMap, ValueType.sqlGeometryArray, ValueType.fileType),
    MapDescriptor(ValueType.sqlPrimaryArrayDateMap, ValueType.sqlPrimaryArray, ValueType.dateType),
    MapDescriptor(ValueType.sqlPrimaryArrayDatespanMap, ValueType.sqlPrimaryArray, ValueType.datespanType),
    MapDescriptor(ValueType.sqlPrimaryArrayBinaryMap, ValueType.sqlPrimaryArray, ValueType.binaryType),
    MapDescriptor(ValueType.sqlPrimaryArrayGeometryMap, ValueType.sqlPrimaryArray, ValueType.geometryType),
    MapDescriptor(ValueType.sqlPrimaryArrayFileMap, ValueType.sqlPrimaryArray, ValueType.fileType),
    MapDescriptor(ValueType.stringPrimaryMap, ValueType.stringType, ValueType.primaryType),
    MapDescriptor(ValueType.primaryPrimaryMap, ValueType.primaryType, ValueType.primaryType),
    MapDescriptor(ValueType.intPrimaryMap, ValueType.intType, ValueType.primaryType),
    MapDescriptor(ValueType.boolPrimaryMap, ValueType.boolType, ValueType.primaryType),
    MapDescriptor(ValueType.decimalPrimaryMap, ValueType.decimalType, ValueType.primaryType),
    MapDescriptor(ValueType.guidPrimaryMap, ValueType.guidType, ValueType.primaryType),
    MapDescriptor(ValueType.binaryPrimaryMap, ValueType.binaryType, ValueType.primaryType),
    MapDescriptor(ValueType.datespanPrimaryMap, ValueType.datespanType, ValueType.primaryType),
    MapDescriptor(ValueType.datePrimaryMap, ValueType.dateType, ValueType.primaryType),
    MapDescriptor(ValueType.geometryPrimaryMap, ValueType.geometryType, ValueType.primaryType),
    MapDescriptor(ValueType.filePrimaryMap, ValueType.fileType, ValueType.primaryType),
    MapDescriptor(ValueType.exceptionPrimaryMap, ValueType.exceptionType, ValueType.primaryType),
    MapDescriptor(ValueType.encodingPrimaryMap, ValueType.encodingType, ValueType.primaryType),
    MapDescriptor(ValueType.selfPrimaryMap, ValueType.selfType, ValueType.primaryType),
    MapDescriptor(ValueType.enumPrimaryMap, ValueType.enumType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlBoolPrimaryMap, ValueType.sqlBoolType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlIntPrimaryMap, ValueType.sqlIntType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlDecimalPrimaryMap, ValueType.sqlDecimalType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlStringPrimaryMap, ValueType.sqlStringType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlGuidPrimaryMap, ValueType.sqlGuidType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlDatePrimaryMap, ValueType.sqlDateType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlDatespanPrimaryMap, ValueType.sqlDatespanType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlBinaryPrimaryMap, ValueType.sqlBinaryType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlGeometryPrimaryMap, ValueType.sqlGeometryType, ValueType.primaryType),
    MapDescriptor(ValueType.sqlPrimaryPrimaryMap, ValueType.sqlPrimaryType, ValueType.primaryType),
    MapDescriptor(ValueType.stringArrayPrimaryMap, ValueType.stringArray, ValueType.primaryType),
    MapDescriptor(ValueType.primaryArrayPrimaryMap, ValueType.primaryArray, ValueType.primaryType),
    MapDescriptor(ValueType.intArrayPrimaryMap, ValueType.intArray, ValueType.primaryType),
    MapDescriptor(ValueType.boolArrayPrimaryMap, ValueType.boolArray, ValueType.primaryType),
    MapDescriptor(ValueType.decimalArrayPrimaryMap, ValueType.decimalArray, ValueType.primaryType),
    MapDescriptor(ValueType.guidArrayPrimaryMap, ValueType.guidArray, ValueType.primaryType),
    MapDescriptor(ValueType.binaryArrayPrimaryMap, ValueType.binaryArray, ValueType.primaryType),
    MapDescriptor(ValueType.datespanArrayPrimaryMap, ValueType.datespanArray, ValueType.primaryType),
    MapDescriptor(ValueType.dateArrayPrimaryMap, ValueType.dateArray, ValueType.primaryType),
    MapDescriptor(ValueType.geometryArrayPrimaryMap, ValueType.geometryArray, ValueType.primaryType),
    MapDescriptor(ValueType.fileArrayPrimaryMap, ValueType.fileArray, ValueType.primaryType),
    MapDescriptor(ValueType.exceptionArrayPrimaryMap, ValueType.exceptionArray, ValueType.primaryType),
    MapDescriptor(ValueType.encodingArrayPrimaryMap, ValueType.encodingArray, ValueType.primaryType),
    MapDescriptor(ValueType.selfArrayPrimaryMap, ValueType.selfArray, ValueType.primaryType),
    MapDescriptor(ValueType.enumArrayPrimaryMap, ValueType.enumArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlBoolArrayPrimaryMap, ValueType.sqlBoolArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlIntArrayPrimaryMap, ValueType.sqlIntArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlDecimalArrayPrimaryMap, ValueType.sqlDecimalArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlStringArrayPrimaryMap, ValueType.sqlStringArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlGuidArrayPrimaryMap, ValueType.sqlGuidArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlDateArrayPrimaryMap, ValueType.sqlDateArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlDatespanArrayPrimaryMap, ValueType.sqlDatespanArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlBinaryArrayPrimaryMap, ValueType.sqlBinaryArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlGeometryArrayPrimaryMap, ValueType.sqlGeometryArray, ValueType.primaryType),
    MapDescriptor(ValueType.sqlPrimaryArrayPrimaryMap, ValueType.sqlPrimaryArray, ValueType.primaryType),
    MapDescriptor(ValueType.intArrayStringMap, ValueType.intArray, ValueType.stringType),
    MapDescriptor(ValueType.intArrayIntMap, ValueType.intArray, ValueType.intType),
    MapDescriptor(ValueType.intArrayGuidMap, ValueType.intArray, ValueType.guidType),
    MapDescriptor(ValueType.intArrayBoolMap, ValueType.intArray, ValueType.boolType),
    MapDescriptor(ValueType.intArrayDecimalMap, ValueType.intArray, ValueType.decimalType),
    MapDescriptor(ValueType.decimalArrayStringMap, ValueType.decimalArray, ValueType.stringType),
    MapDescriptor(ValueType.decimalArrayIntMap, ValueType.decimalArray, ValueType.intType),
    MapDescriptor(ValueType.decimalArrayGuidMap, ValueType.decimalArray, ValueType.guidType),
    MapDescriptor(ValueType.decimalArrayBoolMap, ValueType.decimalArray, ValueType.boolType),
    MapDescriptor(ValueType.decimalArrayDecimalMap, ValueType.decimalArray, ValueType.decimalType),
    MapDescriptor(ValueType.boolArrayStringMap, ValueType.boolArray, ValueType.stringType),
    MapDescriptor(ValueType.boolArrayIntMap, ValueType.boolArray, ValueType.intType),
    MapDescriptor(ValueType.boolArrayGuidMap, ValueType.boolArray, ValueType.guidType),
    MapDescriptor(ValueType.boolArrayBoolMap, ValueType.boolArray, ValueType.boolType),
    MapDescriptor(ValueType.boolArrayDecimalMap, ValueType.boolArray, ValueType.decimalType),
    MapDescriptor(ValueType.stringArrayStringMap, ValueType.stringArray, ValueType.stringType),
    MapDescriptor(ValueType.stringArrayIntMap, ValueType.stringArray, ValueType.intType),
    MapDescriptor(ValueType.stringArrayGuidMap, ValueType.stringArray, ValueType.guidType),
    MapDescriptor(ValueType.stringArrayBoolMap, ValueType.stringArray, ValueType.boolType),
    MapDescriptor(ValueType.stringArrayDecimalMap, ValueType.stringArray, ValueType.decimalType),
    MapDescriptor(ValueType.guidArrayStringMap, ValueType.guidArray, ValueType.stringType),
    MapDescriptor(ValueType.guidArrayIntMap, ValueType.guidArray, ValueType.intType),
    MapDescriptor(ValueType.guidArrayGuidMap, ValueType.guidArray, ValueType.guidType),
    MapDescriptor(ValueType.guidArrayBoolMap, ValueType.guidArray, ValueType.boolType),
    MapDescriptor(ValueType.guidArrayDecimalMap, ValueType.guidArray, ValueType.decimalType),
    MapDescriptor(ValueType.binaryArrayStringMap, ValueType.binaryArray, ValueType.stringType),
    MapDescriptor(ValueType.binaryArrayIntMap, ValueType.binaryArray, ValueType.intType),
    MapDescriptor(ValueType.binaryArrayGuidMap, ValueType.binaryArray, ValueType.guidType),
    MapDescriptor(ValueType.binaryArrayBoolMap, ValueType.binaryArray, ValueType.boolType),
    MapDescriptor(ValueType.binaryArrayDecimalMap, ValueType.binaryArray, ValueType.decimalType),
    MapDescriptor(ValueType.datespanArrayStringMap, ValueType.datespanArray, ValueType.stringType),
    MapDescriptor(ValueType.datespanArrayIntMap, ValueType.datespanArray, ValueType.intType),
    MapDescriptor(ValueType.datespanArrayGuidMap, ValueType.datespanArray, ValueType.guidType),
    MapDescriptor(ValueType.datespanArrayBoolMap, ValueType.datespanArray, ValueType.boolType),
    MapDescriptor(ValueType.datespanArrayDecimalMap, ValueType.datespanArray, ValueType.decimalType),
    MapDescriptor(ValueType.dateArrayStringMap, ValueType.dateArray, ValueType.stringType),
    MapDescriptor(ValueType.dateArrayIntMap, ValueType.dateArray, ValueType.intType),
    MapDescriptor(ValueType.dateArrayGuidMap, ValueType.dateArray, ValueType.guidType),
    MapDescriptor(ValueType.dateArrayBoolMap, ValueType.dateArray, ValueType.boolType),
    MapDescriptor(ValueType.dateArrayDecimalMap, ValueType.dateArray, ValueType.decimalType),
    MapDescriptor(ValueType.geometryArrayStringMap, ValueType.geometryArray, ValueType.stringType),
    MapDescriptor(ValueType.geometryArrayIntMap, ValueType.geometryArray, ValueType.intType),
    MapDescriptor(ValueType.geometryArrayGuidMap, ValueType.geometryArray, ValueType.guidType),
    MapDescriptor(ValueType.geometryArrayBoolMap, ValueType.geometryArray, ValueType.boolType),
    MapDescriptor(ValueType.geometryArrayDecimalMap, ValueType.geometryArray, ValueType.decimalType),
    MapDescriptor(ValueType.fileArrayStringMap, ValueType.fileArray, ValueType.stringType),
    MapDescriptor(ValueType.fileArrayIntMap, ValueType.fileArray, ValueType.intType),
    MapDescriptor(ValueType.fileArrayGuidMap, ValueType.fileArray, ValueType.guidType),
    MapDescriptor(ValueType.fileArrayBoolMap, ValueType.fileArray, ValueType.boolType),
    MapDescriptor(ValueType.fileArrayDecimalMap, ValueType.fileArray, ValueType.decimalType),
    MapDescriptor(ValueType.exceptionArrayStringMap, ValueType.exceptionArray, ValueType.stringType),
    MapDescriptor(ValueType.exceptionArrayIntMap, ValueType.exceptionArray, ValueType.intType),
    MapDescriptor(ValueType.exceptionArrayGuidMap, ValueType.exceptionArray, ValueType.guidType),
    MapDescriptor(ValueType.exceptionArrayBoolMap, ValueType.exceptionArray, ValueType.boolType),
    MapDescriptor(ValueType.exceptionArrayDecimalMap, ValueType.exceptionArray, ValueType.decimalType),
    MapDescriptor(ValueType.encodingArrayStringMap, ValueType.encodingArray, ValueType.stringType),
    MapDescriptor(ValueType.encodingArrayIntMap, ValueType.encodingArray, ValueType.intType),
    MapDescriptor(ValueType.encodingArrayGuidMap, ValueType.encodingArray, ValueType.guidType),
    MapDescriptor(ValueType.encodingArrayBoolMap, ValueType.encodingArray, ValueType.boolType),
    MapDescriptor(ValueType.encodingArrayDecimalMap, ValueType.encodingArray, ValueType.decimalType),
    MapDescriptor(ValueType.primaryArrayStringMap, ValueType.primaryArray, ValueType.stringType),
    MapDescriptor(ValueType.primaryArrayIntMap, ValueType.primaryArray, ValueType.intType),
    MapDescriptor(ValueType.primaryArrayGuidMap, ValueType.primaryArray, ValueType.guidType),
    MapDescriptor(ValueType.primaryArrayBoolMap, ValueType.primaryArray, ValueType.boolType),
    MapDescriptor(ValueType.primaryArrayDecimalMap, ValueType.primaryArray, ValueType.decimalType),
    MapDescriptor(ValueType.selfArrayStringMap, ValueType.selfArray, ValueType.stringType),
    MapDescriptor(ValueType.selfArrayIntMap, ValueType.selfArray, ValueType.intType),
    MapDescriptor(ValueType.selfArrayGuidMap, ValueType.selfArray, ValueType.guidType),
    MapDescriptor(ValueType.selfArrayBoolMap, ValueType.selfArray, ValueType.boolType),
    MapDescriptor(ValueType.selfArrayDecimalMap, ValueType.selfArray, ValueType.decimalType),
    MapDescriptor(ValueType.enumArrayStringMap, ValueType.enumArray, ValueType.stringType),
    MapDescriptor(ValueType.enumArrayIntMap, ValueType.enumArray, ValueType.intType),
    MapDescriptor(ValueType.enumArrayGuidMap, ValueType.enumArray, ValueType.guidType),
    MapDescriptor(ValueType.enumArrayBoolMap, ValueType.enumArray, ValueType.boolType),
    MapDescriptor(ValueType.enumArrayDecimalMap, ValueType.enumArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlBoolArrayStringMap, ValueType.sqlBoolArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlBoolArrayIntMap, ValueType.sqlBoolArray, ValueType.intType),
    MapDescriptor(ValueType.sqlBoolArrayGuidMap, ValueType.sqlBoolArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlBoolArrayBoolMap, ValueType.sqlBoolArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlBoolArrayDecimalMap, ValueType.sqlBoolArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlIntArrayStringMap, ValueType.sqlIntArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlIntArrayIntMap, ValueType.sqlIntArray, ValueType.intType),
    MapDescriptor(ValueType.sqlIntArrayGuidMap, ValueType.sqlIntArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlIntArrayBoolMap, ValueType.sqlIntArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlIntArrayDecimalMap, ValueType.sqlIntArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlDecimalArrayStringMap, ValueType.sqlDecimalArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlDecimalArrayIntMap, ValueType.sqlDecimalArray, ValueType.intType),
    MapDescriptor(ValueType.sqlDecimalArrayGuidMap, ValueType.sqlDecimalArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlDecimalArrayBoolMap, ValueType.sqlDecimalArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlDecimalArrayDecimalMap, ValueType.sqlDecimalArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlStringArrayStringMap, ValueType.sqlStringArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlStringArrayIntMap, ValueType.sqlStringArray, ValueType.intType),
    MapDescriptor(ValueType.sqlStringArrayGuidMap, ValueType.sqlStringArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlStringArrayBoolMap, ValueType.sqlStringArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlStringArrayDecimalMap, ValueType.sqlStringArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlGuidArrayStringMap, ValueType.sqlGuidArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlGuidArrayIntMap, ValueType.sqlGuidArray, ValueType.intType),
    MapDescriptor(ValueType.sqlGuidArrayGuidMap, ValueType.sqlGuidArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlGuidArrayBoolMap, ValueType.sqlGuidArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlGuidArrayDecimalMap, ValueType.sqlGuidArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlDateArrayStringMap, ValueType.sqlDateArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlDateArrayIntMap, ValueType.sqlDateArray, ValueType.intType),
    MapDescriptor(ValueType.sqlDateArrayGuidMap, ValueType.sqlDateArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlDateArrayBoolMap, ValueType.sqlDateArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlDateArrayDecimalMap, ValueType.sqlDateArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlDatespanArrayStringMap, ValueType.sqlDatespanArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlDatespanArrayIntMap, ValueType.sqlDatespanArray, ValueType.intType),
    MapDescriptor(ValueType.sqlDatespanArrayGuidMap, ValueType.sqlDatespanArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlDatespanArrayBoolMap, ValueType.sqlDatespanArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlDatespanArrayDecimalMap, ValueType.sqlDatespanArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlBinaryArrayStringMap, ValueType.sqlBinaryArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlBinaryArrayIntMap, ValueType.sqlBinaryArray, ValueType.intType),
    MapDescriptor(ValueType.sqlBinaryArrayGuidMap, ValueType.sqlBinaryArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlBinaryArrayBoolMap, ValueType.sqlBinaryArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlBinaryArrayDecimalMap, ValueType.sqlBinaryArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlGeometryArrayStringMap, ValueType.sqlGeometryArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlGeometryArrayIntMap, ValueType.sqlGeometryArray, ValueType.intType),
    MapDescriptor(ValueType.sqlGeometryArrayGuidMap, ValueType.sqlGeometryArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlGeometryArrayBoolMap, ValueType.sqlGeometryArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlGeometryArrayDecimalMap, ValueType.sqlGeometryArray, ValueType.decimalType),
    MapDescriptor(ValueType.sqlPrimaryArrayStringMap, ValueType.sqlPrimaryArray, ValueType.stringType),
    MapDescriptor(ValueType.sqlPrimaryArrayIntMap, ValueType.sqlPrimaryArray, ValueType.intType),
    MapDescriptor(ValueType.sqlPrimaryArrayGuidMap, ValueType.sqlPrimaryArray, ValueType.guidType),
    MapDescriptor(ValueType.sqlPrimaryArrayBoolMap, ValueType.sqlPrimaryArray, ValueType.boolType),
    MapDescriptor(ValueType.sqlPrimaryArrayDecimalMap, ValueType.sqlPrimaryArray, ValueType.decimalType),
    MapDescriptor(ValueType.binaryStringMap, ValueType.binaryType, ValueType.stringType),
    MapDescriptor(ValueType.binaryIntMap, ValueType.binaryType, ValueType.intType),
    MapDescriptor(ValueType.binaryGuidMap, ValueType.binaryType, ValueType.guidType),
    MapDescriptor(ValueType.binaryBoolMap, ValueType.binaryType, ValueType.boolType),
    MapDescriptor(ValueType.binaryDecimalMap, ValueType.binaryType, ValueType.decimalType),
    MapDescriptor(ValueType.datespanStringMap, ValueType.datespanType, ValueType.stringType),
    MapDescriptor(ValueType.datespanIntMap, ValueType.datespanType, ValueType.intType),
    MapDescriptor(ValueType.datespanGuidMap, ValueType.datespanType, ValueType.guidType),
    MapDescriptor(ValueType.datespanBoolMap, ValueType.datespanType, ValueType.boolType),
    MapDescriptor(ValueType.datespanDecimalMap, ValueType.datespanType, ValueType.decimalType),
    MapDescriptor(ValueType.dateStringMap, ValueType.dateType, ValueType.stringType),
    MapDescriptor(ValueType.dateIntMap, ValueType.dateType, ValueType.intType),
    MapDescriptor(ValueType.dateGuidMap, ValueType.dateType, ValueType.guidType),
    MapDescriptor(ValueType.dateBoolMap, ValueType.dateType, ValueType.boolType),
    MapDescriptor(ValueType.dateDecimalMap, ValueType.dateType, ValueType.decimalType),
    MapDescriptor(ValueType.geometryStringMap, ValueType.geometryType, ValueType.stringType),
    MapDescriptor(ValueType.geometryIntMap, ValueType.geometryType, ValueType.intType),
    MapDescriptor(ValueType.geometryGuidMap, ValueType.geometryType, ValueType.guidType),
    MapDescriptor(ValueType.geometryBoolMap, ValueType.geometryType, ValueType.boolType),
    MapDescriptor(ValueType.geometryDecimalMap, ValueType.geometryType, ValueType.decimalType),
    MapDescriptor(ValueType.fileStringMap, ValueType.fileType, ValueType.stringType),
    MapDescriptor(ValueType.fileIntMap, ValueType.fileType, ValueType.intType),
    MapDescriptor(ValueType.fileGuidMap, ValueType.fileType, ValueType.guidType),
    MapDescriptor(ValueType.fileBoolMap, ValueType.fileType, ValueType.boolType),
    MapDescriptor(ValueType.fileDecimalMap, ValueType.fileType, ValueType.decimalType),
    MapDescriptor(ValueType.exceptionStringMap, ValueType.exceptionType, ValueType.stringType),
    MapDescriptor(ValueType.exceptionIntMap, ValueType.exceptionType, ValueType.intType),
    MapDescriptor(ValueType.exceptionGuidMap, ValueType.exceptionType, ValueType.guidType),
    MapDescriptor(ValueType.exceptionBoolMap, ValueType.exceptionType, ValueType.boolType),
    MapDescriptor(ValueType.exceptionDecimalMap, ValueType.exceptionType, ValueType.decimalType),
    MapDescriptor(ValueType.encodingStringMap, ValueType.encodingType, ValueType.stringType),
    MapDescriptor(ValueType.encodingIntMap, ValueType.encodingType, ValueType.intType),
    MapDescriptor(ValueType.encodingGuidMap, ValueType.encodingType, ValueType.guidType),
    MapDescriptor(ValueType.encodingBoolMap, ValueType.encodingType, ValueType.boolType),
    MapDescriptor(ValueType.encodingDecimalMap, ValueType.encodingType, ValueType.decimalType),
    MapDescriptor(ValueType.selfStringMap, ValueType.selfType, ValueType.stringType),
    MapDescriptor(ValueType.selfIntMap, ValueType.selfType, ValueType.intType),
    MapDescriptor(ValueType.selfGuidMap, ValueType.selfType, ValueType.guidType),
    MapDescriptor(ValueType.selfBoolMap, ValueType.selfType, ValueType.boolType),
    MapDescriptor(ValueType.selfDecimalMap, ValueType.selfType, ValueType.decimalType),
    MapDescriptor(ValueType.enumStringMap, ValueType.enumType, ValueType.stringType),
    MapDescriptor(ValueType.enumIntMap, ValueType.enumType, ValueType.intType),
    MapDescriptor(ValueType.enumGuidMap, ValueType.enumType, ValueType.guidType),
    MapDescriptor(ValueType.enumBoolMap, ValueType.enumType, ValueType.boolType),
    MapDescriptor(ValueType.enumDecimalMap, ValueType.enumType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlBoolStringMap, ValueType.sqlBoolType, ValueType.stringType),
    MapDescriptor(ValueType.sqlBoolIntMap, ValueType.sqlBoolType, ValueType.intType),
    MapDescriptor(ValueType.sqlBoolGuidMap, ValueType.sqlBoolType, ValueType.guidType),
    MapDescriptor(ValueType.sqlBoolBoolMap, ValueType.sqlBoolType, ValueType.boolType),
    MapDescriptor(ValueType.sqlBoolDecimalMap, ValueType.sqlBoolType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlIntStringMap, ValueType.sqlIntType, ValueType.stringType),
    MapDescriptor(ValueType.sqlIntIntMap, ValueType.sqlIntType, ValueType.intType),
    MapDescriptor(ValueType.sqlIntGuidMap, ValueType.sqlIntType, ValueType.guidType),
    MapDescriptor(ValueType.sqlIntBoolMap, ValueType.sqlIntType, ValueType.boolType),
    MapDescriptor(ValueType.sqlIntDecimalMap, ValueType.sqlIntType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlDecimalStringMap, ValueType.sqlDecimalType, ValueType.stringType),
    MapDescriptor(ValueType.sqlDecimalIntMap, ValueType.sqlDecimalType, ValueType.intType),
    MapDescriptor(ValueType.sqlDecimalGuidMap, ValueType.sqlDecimalType, ValueType.guidType),
    MapDescriptor(ValueType.sqlDecimalBoolMap, ValueType.sqlDecimalType, ValueType.boolType),
    MapDescriptor(ValueType.sqlDecimalDecimalMap, ValueType.sqlDecimalType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlStringStringMap, ValueType.sqlStringType, ValueType.stringType),
    MapDescriptor(ValueType.sqlStringIntMap, ValueType.sqlStringType, ValueType.intType),
    MapDescriptor(ValueType.sqlStringGuidMap, ValueType.sqlStringType, ValueType.guidType),
    MapDescriptor(ValueType.sqlStringBoolMap, ValueType.sqlStringType, ValueType.boolType),
    MapDescriptor(ValueType.sqlStringDecimalMap, ValueType.sqlStringType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlGuidStringMap, ValueType.sqlGuidType, ValueType.stringType),
    MapDescriptor(ValueType.sqlGuidIntMap, ValueType.sqlGuidType, ValueType.intType),
    MapDescriptor(ValueType.sqlGuidGuidMap, ValueType.sqlGuidType, ValueType.guidType),
    MapDescriptor(ValueType.sqlGuidBoolMap, ValueType.sqlGuidType, ValueType.boolType),
    MapDescriptor(ValueType.sqlGuidDecimalMap, ValueType.sqlGuidType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlDateStringMap, ValueType.sqlDateType, ValueType.stringType),
    MapDescriptor(ValueType.sqlDateIntMap, ValueType.sqlDateType, ValueType.intType),
    MapDescriptor(ValueType.sqlDateGuidMap, ValueType.sqlDateType, ValueType.guidType),
    MapDescriptor(ValueType.sqlDateBoolMap, ValueType.sqlDateType, ValueType.boolType),
    MapDescriptor(ValueType.sqlDateDecimalMap, ValueType.sqlDateType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlDatespanStringMap, ValueType.sqlDatespanType, ValueType.stringType),
    MapDescriptor(ValueType.sqlDatespanIntMap, ValueType.sqlDatespanType, ValueType.intType),
    MapDescriptor(ValueType.sqlDatespanGuidMap, ValueType.sqlDatespanType, ValueType.guidType),
    MapDescriptor(ValueType.sqlDatespanBoolMap, ValueType.sqlDatespanType, ValueType.boolType),
    MapDescriptor(ValueType.sqlDatespanDecimalMap, ValueType.sqlDatespanType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlBinaryStringMap, ValueType.sqlBinaryType, ValueType.stringType),
    MapDescriptor(ValueType.sqlBinaryIntMap, ValueType.sqlBinaryType, ValueType.intType),
    MapDescriptor(ValueType.sqlBinaryGuidMap, ValueType.sqlBinaryType, ValueType.guidType),
    MapDescriptor(ValueType.sqlBinaryBoolMap, ValueType.sqlBinaryType, ValueType.boolType),
    MapDescriptor(ValueType.sqlBinaryDecimalMap, ValueType.sqlBinaryType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlGeometryStringMap, ValueType.sqlGeometryType, ValueType.stringType),
    MapDescriptor(ValueType.sqlGeometryIntMap, ValueType.sqlGeometryType, ValueType.intType),
    MapDescriptor(ValueType.sqlGeometryGuidMap, ValueType.sqlGeometryType, ValueType.guidType),
    MapDescriptor(ValueType.sqlGeometryBoolMap, ValueType.sqlGeometryType, ValueType.boolType),
    MapDescriptor(ValueType.sqlGeometryDecimalMap, ValueType.sqlGeometryType, ValueType.decimalType),
    MapDescriptor(ValueType.sqlPrimaryStringMap, ValueType.sqlPrimaryType, ValueType.stringType),
    MapDescriptor(ValueType.sqlPrimaryIntMap, ValueType.sqlPrimaryType, ValueType.intType),
    MapDescriptor(ValueType.sqlPrimaryGuidMap, ValueType.sqlPrimaryType, ValueType.guidType),
    MapDescriptor(ValueType.sqlPrimaryBoolMap, ValueType.sqlPrimaryType, ValueType.boolType),
    MapDescriptor(ValueType.sqlPrimaryDecimalMap, ValueType.sqlPrimaryType, ValueType.decimalType),
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
package bool hasMapKeyClass(ValueType type) {
    return isMap(type) && [ValueType.selfType, ValueType.enumType].canFind(mapKeyType(type));
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
    auto result = arrayOf(mapKeyType(type));
    assert(result != ValueType.voidType, "map keys cannot be represented as an array");
    return result;
}
package ValueType mapValueArrayType(ValueType type) {
    auto result = arrayOf(mapValueType(type));
    assert(result != ValueType.voidType, "map values cannot be represented as an array");
    return result;
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
    assert(mapType(ValueType.intType, ValueType.exceptionType) == ValueType.voidType);
}
package ValueType mapValueReadType(ValueType type) {
    auto value = mapValueType(type);
    return value == ValueType.stringType ? ValueType.nullableString : storedValueType(value);
}
package bool hasObjectClass(ValueType type) { return (isMap(type) && hasObjectClass(mapValueType(type))) || type == ValueType.selfType || type == ValueType.selfArray || type == ValueType.selfMatrix || type == ValueType.enumType || type == ValueType.enumArray || type == ValueType.enumMatrix; }
package bool isSqlType(ValueType type) { return [ValueType.sqlPrimaryType, ValueType.sqlBoolType, ValueType.sqlIntType, ValueType.sqlDecimalType, ValueType.sqlStringType, ValueType.sqlGuidType, ValueType.sqlDateType, ValueType.sqlDatespanType, ValueType.sqlBinaryType, ValueType.sqlGeometryType].canFind(type); }
package bool isNullableReference(ValueType type) { return isSqlType(type) || type == ValueType.ftsType || type == ValueType.ftsQueryType || type == ValueType.selfType || type == ValueType.enumType || type == ValueType.exceptionType || type == ValueType.encodingType || type == ValueType.primaryType || type == ValueType.guidType || type == ValueType.binaryType || type == ValueType.datespanType || type == ValueType.dateType || type == ValueType.geometryType || type == ValueType.fileType || isMap(type) || type == ValueType.nullableString || type == ValueType.stringType || isArray(type); }
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
    if (isSqlArray(type)) return sqlArrayElement(type);
    switch (type) {
        case ValueType.intArray: return ValueType.intType;
        case ValueType.intMatrix: return ValueType.intArray;
        case ValueType.decimalArray: return ValueType.decimalType;
        case ValueType.decimalMatrix: return ValueType.decimalArray;
        case ValueType.boolArray: return ValueType.boolType;
        case ValueType.boolMatrix: return ValueType.boolArray;
        case ValueType.stringArray: return ValueType.stringType;
        case ValueType.stringMatrix: return ValueType.stringArray;
        case ValueType.primaryArray: return ValueType.primaryType;
        case ValueType.primaryMatrix: return ValueType.primaryArray;
        case ValueType.guidArray: return ValueType.guidType;
        case ValueType.guidMatrix: return ValueType.guidArray;
        case ValueType.binaryArray: return ValueType.binaryType;
        case ValueType.binaryMatrix: return ValueType.binaryArray;
        case ValueType.datespanArray: return ValueType.datespanType;
        case ValueType.datespanMatrix: return ValueType.datespanArray;
        case ValueType.dateArray: return ValueType.dateType;
        case ValueType.dateMatrix: return ValueType.dateArray;
        case ValueType.geometryArray: return ValueType.geometryType;
        case ValueType.geometryMatrix: return ValueType.geometryArray;
        case ValueType.fileArray: return ValueType.fileType;
        case ValueType.fileMatrix: return ValueType.fileArray;
        case ValueType.exceptionArray: return ValueType.exceptionType;
        case ValueType.exceptionMatrix: return ValueType.exceptionArray;
        case ValueType.encodingArray: return ValueType.encodingType;
        case ValueType.encodingMatrix: return ValueType.encodingArray;
        case ValueType.selfArray: return ValueType.selfType;
        case ValueType.selfMatrix: return ValueType.selfArray;
        case ValueType.enumArray: return ValueType.enumType;
        case ValueType.enumMatrix: return ValueType.enumArray;
        default: assert(0, "not an array");
    }
}

