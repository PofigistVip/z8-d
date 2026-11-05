module z8.variable_type;

import std.algorithm : canFind;
import std.conv : to;
import std.string : replace, indexOf;
import std.math : isFinite, abs;

enum ValueType : uint {
    voidType, intType, decimalType, boolType, stringType, guidType,
    binaryType, datespanType, dateType, geometryType, fileType, exceptionType,
    encodingType, ftsType, ftsQueryType, sqlBoolType, sqlIntType, sqlDecimalType,
    sqlStringType, sqlGuidType, sqlDateType, sqlDatespanType, sqlBinaryType, sqlGeometryType,
    sqlPrimaryType, sqlBoolArray, sqlBoolMatrix, sqlIntArray, sqlIntMatrix, sqlDecimalArray,
    sqlDecimalMatrix, sqlStringArray, sqlStringMatrix, sqlGuidArray, sqlGuidMatrix, sqlDateArray,
    sqlDateMatrix, sqlDatespanArray, sqlDatespanMatrix, sqlBinaryArray, sqlBinaryMatrix, sqlGeometryArray,
    sqlGeometryMatrix, sqlPrimaryArray, sqlPrimaryMatrix, primaryType, selfType, intArray,
    intMatrix, decimalArray, decimalMatrix, boolArray, boolMatrix, stringArray,
    stringMatrix, guidArray, guidMatrix, binaryArray, binaryMatrix, datespanArray,
    datespanMatrix, dateArray, dateMatrix, geometryArray, geometryMatrix, fileArray,
    fileMatrix, exceptionArray, exceptionMatrix, encodingArray, encodingMatrix, primaryArray,
    primaryMatrix, selfArray, selfMatrix, nullType, nullableString, enumType,
    enumArray, enumMatrix, optionalInt, optionalBool, optionalDecimal,
    mapStart = 65536,
    dynamicArrayStep = 1 << 20
}

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
// Additional sequence dimensions retain the complete inner type, including
// a map's key. The low bits hold the inner type and high bits its depth.
package bool isDynamicArray(ValueType type) {
    return cast(uint)type >= cast(uint)ValueType.dynamicArrayStep;
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
    if ((isArray(type) || isMap(type)) && cast(uint)type <= uint.max - cast(uint)ValueType.dynamicArrayStep)
        return cast(ValueType)(cast(uint)type + cast(uint)ValueType.dynamicArrayStep);
    return ValueType.voidType;
}
package bool isArray(ValueType type) {
    return isDynamicArray(type) || isSqlArray(type) || [ValueType.intArray, ValueType.intMatrix, ValueType.decimalArray, ValueType.decimalMatrix, ValueType.boolArray, ValueType.boolMatrix, ValueType.stringArray, ValueType.stringMatrix, ValueType.guidArray, ValueType.guidMatrix, ValueType.binaryArray, ValueType.binaryMatrix, ValueType.datespanArray, ValueType.datespanMatrix, ValueType.dateArray, ValueType.dateMatrix, ValueType.geometryArray, ValueType.geometryMatrix, ValueType.fileArray, ValueType.fileMatrix, ValueType.exceptionArray, ValueType.exceptionMatrix, ValueType.encodingArray, ValueType.encodingMatrix, ValueType.primaryArray, ValueType.primaryMatrix, ValueType.selfArray, ValueType.selfMatrix, ValueType.enumArray, ValueType.enumMatrix].canFind(type);
}
package bool isReferenceArray(ValueType type) { return isDynamicArray(type) || isSqlArray(type) || [ValueType.selfArray, ValueType.enumArray, ValueType.primaryArray, ValueType.guidArray, ValueType.binaryArray, ValueType.datespanArray, ValueType.dateArray, ValueType.geometryArray, ValueType.fileArray, ValueType.exceptionArray, ValueType.encodingArray, ValueType.intMatrix, ValueType.decimalMatrix, ValueType.boolMatrix, ValueType.stringMatrix, ValueType.guidMatrix, ValueType.binaryMatrix, ValueType.datespanMatrix, ValueType.dateMatrix, ValueType.geometryMatrix, ValueType.fileMatrix, ValueType.exceptionMatrix, ValueType.encodingMatrix, ValueType.primaryMatrix, ValueType.selfMatrix, ValueType.enumMatrix].canFind(type); }
// A map is identified by its value and key type, mirroring VariableType in Z8.
// Its encoded value is kept outside the range of named scalar and array types.
private enum ValueType[] mapValueTypes = [
    ValueType.stringType, ValueType.primaryType, ValueType.intType, ValueType.boolType,
    ValueType.decimalType, ValueType.guidType, ValueType.binaryType, ValueType.datespanType,
    ValueType.dateType, ValueType.geometryType, ValueType.fileType, ValueType.exceptionType,
    ValueType.encodingType, ValueType.selfType, ValueType.enumType, ValueType.sqlBoolType,
    ValueType.sqlIntType, ValueType.sqlDecimalType, ValueType.sqlStringType, ValueType.sqlGuidType,
    ValueType.sqlDateType, ValueType.sqlDatespanType, ValueType.sqlBinaryType, ValueType.sqlGeometryType,
    ValueType.sqlPrimaryType, ValueType.stringArray, ValueType.primaryArray, ValueType.intArray,
    ValueType.boolArray, ValueType.decimalArray, ValueType.guidArray, ValueType.binaryArray,
    ValueType.datespanArray, ValueType.dateArray, ValueType.geometryArray, ValueType.fileArray,
    ValueType.exceptionArray, ValueType.encodingArray, ValueType.selfArray, ValueType.enumArray,
    ValueType.sqlBoolArray, ValueType.sqlIntArray, ValueType.sqlDecimalArray, ValueType.sqlStringArray,
    ValueType.sqlGuidArray, ValueType.sqlDateArray, ValueType.sqlDatespanArray, ValueType.sqlBinaryArray,
    ValueType.sqlGeometryArray, ValueType.sqlPrimaryArray,
];
private enum ValueType[] mapKeyTypes = [
    ValueType.selfType, ValueType.enumType, ValueType.dateType, ValueType.datespanType,
    ValueType.binaryType, ValueType.geometryType, ValueType.fileType, ValueType.primaryType,
    ValueType.stringType, ValueType.intType, ValueType.guidType, ValueType.boolType,
    ValueType.decimalType,
];
package bool isMap(ValueType type) {
    auto id = cast(uint)type;
    return id >= cast(uint)ValueType.mapStart && id < cast(uint)ValueType.mapStart + mapValueTypes.length * mapKeyTypes.length;
}
package bool hasMapKeyClass(ValueType type) {
    if (isDynamicArray(type)) return hasMapKeyClass(elementType(type));
    return isMap(type) && [ValueType.selfType, ValueType.enumType].canFind(mapKeyType(type));
}
package ValueType mapKeyType(ValueType type) {
    assert(isMap(type), "not a map");
    auto index = cast(uint)type - cast(uint)ValueType.mapStart;
    return mapKeyTypes[index % mapKeyTypes.length];
}
package ValueType mapValueType(ValueType type) {
    assert(isMap(type), "not a map");
    auto index = cast(uint)type - cast(uint)ValueType.mapStart;
    return mapValueTypes[index / mapKeyTypes.length];
}
package ValueType mapType(ValueType value, ValueType key) {
    foreach (i, candidateValue; mapValueTypes) if (candidateValue == value)
        foreach (j, candidateKey; mapKeyTypes) if (candidateKey == key)
            return cast(ValueType)(cast(uint)ValueType.mapStart + i * mapKeyTypes.length + j);
    return ValueType.voidType;
}
unittest {
    foreach (value; mapValueTypes) foreach (key; mapKeyTypes) {
        auto type = mapType(value, key);
        assert(isMap(type));
        assert(mapValueType(type) == value && mapKeyType(type) == key);
    }
    foreach (i, value; mapValueTypes) foreach (other; mapValueTypes[i + 1 .. $]) assert(value != other);
    foreach (i, key; mapKeyTypes) foreach (other; mapKeyTypes[i + 1 .. $]) assert(key != other);
    assert(cast(uint)ValueType.optionalDecimal < cast(uint)ValueType.mapStart);
    assert(!isMap(ValueType.intType));
    assert(mapType(ValueType.intType, ValueType.exceptionType) == ValueType.voidType);
    auto nestedMap = arrayOf(arrayOf(mapType(ValueType.selfType, ValueType.enumType)));
    assert(isDynamicArray(nestedMap) && hasObjectClass(nestedMap) && hasMapKeyClass(nestedMap));
    assert(mapKeyType(elementType(elementType(nestedMap))) == ValueType.enumType);
    auto cube = arrayOf(ValueType.intMatrix);
    assert(isArray(cube) && elementType(cube) == ValueType.intMatrix);
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
package ValueType mapValueReadType(ValueType type) {
    auto value = mapValueType(type);
    return value == ValueType.stringType ? ValueType.nullableString : storedValueType(value);
}
package bool hasObjectClass(ValueType type) { return (isDynamicArray(type) && hasObjectClass(elementType(type))) || (isMap(type) && hasObjectClass(mapValueType(type))) || type == ValueType.selfType || type == ValueType.selfArray || type == ValueType.selfMatrix || type == ValueType.enumType || type == ValueType.enumArray || type == ValueType.enumMatrix; }
package bool containsUserReference(ValueType type) {
    if (isDynamicArray(type)) return containsUserReference(elementType(type));
    if (isMap(type)) return mapKeyType(type) == ValueType.selfType || containsUserReference(mapValueType(type));
    return [ValueType.selfType, ValueType.selfArray, ValueType.selfMatrix].canFind(type);
}
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
    if (isDynamicArray(type)) return cast(ValueType)(cast(uint)type - cast(uint)ValueType.dynamicArrayStep);
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

