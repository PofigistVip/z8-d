module z8.emitter;

import std.algorithm : canFind, sort;
import std.array : join;
import std.conv : to;
import std.format : format;
import std.string : replace, startsWith, split;
import std.regex : matchAll, regex;
import z8.compiler_model;
import z8.lexer : TokenKind, decodeStringLiteral;
import z8.d_writer : formatDSource;

private string operatorDName(string symbol) {
    switch (symbol) {
        case "!": return "z8op_not"; case "~": return "z8op_complement";
        case "+": return "z8op_add"; case "-": return "z8op_negate";
        case "*": return "z8op_multiply"; case "/": return "z8op_divide"; case "%": return "z8op_modulo";
        case "==": return "z8op_equal"; case "!=": return "z8op_not_equal";
        case "<": return "z8op_less"; case ">": return "z8op_greater";
        case "<=": return "z8op_less_equal"; case ">=": return "z8op_greater_equal";
        case "&": return "z8op_bit_and"; case "|": return "z8op_bit_or"; case "^": return "z8op_bit_xor";
        case "&&": return "z8op_and"; case "||": return "z8op_or";
        case "=": return "z8op_assign";
        default: assert(0, "unsupported operator");
    }
}
private string methodDName(Method method) {
    if (method.isCastOperator)
        return "z8cast_" ~ (method.returnType == ValueType.selfType ? method.returnObjectClass.emittedName : method.name.text[13 .. $]);
    return method.operatorSymbol.length ? operatorDName(method.operatorSymbol) : "m_" ~ method.name.text;
}

private string dType(ValueType type, Program objectClass = null) {
    if (isMap(type)) {
        auto key = mapKeyType(type), value = mapValueType(type);
        if (type == ValueType.stringMap) return "Z8StringMap";
        if (type == ValueType.primaryStringMap) return "Z8PrimaryMap";
        if (type == ValueType.intStringMap) return "Z8StringIntMap";
        auto templateName = key == ValueType.stringType ? "Z8StringValueMap" :
            key == ValueType.intType ? "Z8IntMap" : key == ValueType.boolType ? "Z8BoolMap" :
            key == ValueType.decimalType ? "Z8DecimalMap" : "Z8GuidMap";
        return templateName ~ "!" ~ dType(value);
    }
    switch (type) {
        case ValueType.intType: return "long"; case ValueType.boolType: return "bool";
        case ValueType.decimalType: return "Z8Decimal";
        case ValueType.voidType: return "void"; case ValueType.stringType: return "wstring";
        case ValueType.exceptionType: return "Throwable";
        case ValueType.encodingType: return "Z8Encoding";
        case ValueType.sqlBoolType: return "Z8SqlBool";
        case ValueType.sqlIntType: return "Z8SqlInt";
        case ValueType.sqlDecimalType: return "Z8SqlDecimal";
        case ValueType.sqlStringType: return "Z8SqlString";
        case ValueType.sqlGuidType: return "Z8SqlGuid";
        case ValueType.sqlDateType: return "Z8SqlDate";
        case ValueType.sqlDatespanType: return "Z8SqlDatespan";
        case ValueType.sqlBinaryType: return "Z8SqlBinary";
        case ValueType.sqlGeometryType: return "Z8SqlGeometry";
        case ValueType.sqlPrimaryType: return "Z8SqlPrimary";
        case ValueType.ftsType: return "Z8Fts";
        case ValueType.ftsQueryType: return "Z8FtsQueryType";
        case ValueType.guidType: return "Z8Guid";
        case ValueType.binaryType: return "Z8Binary";
        case ValueType.datespanType: return "Z8Datespan";
        case ValueType.dateType: return "Z8Date";
        case ValueType.geometryType: return "Z8Geometry";
        case ValueType.fileType: return "Z8File";
        case ValueType.primaryType: return "Z8Primary";
        case ValueType.selfType: assert(objectClass !is null); return objectClass.emittedName;
        case ValueType.selfArray: assert(objectClass !is null); return "Z8Array!(" ~ objectClass.emittedName ~ ")";
        case ValueType.selfMatrix: assert(objectClass !is null); return "Z8Array!(Z8Array!(" ~ objectClass.emittedName ~ "))";
        case ValueType.intArray: return "Z8Array!long";
        case ValueType.intMatrix: return "Z8Array!(Z8Array!long)";
        case ValueType.decimalArray: return "Z8Array!Z8Decimal";
        case ValueType.decimalMatrix: return "Z8Array!(Z8Array!Z8Decimal)";
        case ValueType.boolArray: return "Z8Array!bool";
        case ValueType.boolMatrix: return "Z8Array!(Z8Array!bool)";
        case ValueType.stringArray: return "Z8Array!wstring";
        case ValueType.stringMatrix: return "Z8Array!(Z8Array!wstring)";
        case ValueType.primaryArray: return "Z8Array!Z8Primary";
        case ValueType.primaryMatrix: return "Z8Array!(Z8Array!Z8Primary)";
        case ValueType.guidArray: return "Z8Array!Z8Guid";
        case ValueType.guidMatrix: return "Z8Array!(Z8Array!Z8Guid)";
        case ValueType.binaryArray: return "Z8Array!Z8Binary";
        case ValueType.binaryMatrix: return "Z8Array!(Z8Array!Z8Binary)";
        case ValueType.datespanArray: return "Z8Array!Z8Datespan";
        case ValueType.datespanMatrix: return "Z8Array!(Z8Array!Z8Datespan)";
        case ValueType.dateArray: return "Z8Array!Z8Date";
        case ValueType.dateMatrix: return "Z8Array!(Z8Array!Z8Date)";
        case ValueType.geometryArray: return "Z8Array!Z8Geometry";
        case ValueType.geometryMatrix: return "Z8Array!(Z8Array!Z8Geometry)";
        case ValueType.fileArray: return "Z8Array!Z8File";
        case ValueType.fileMatrix: return "Z8Array!(Z8Array!Z8File)";
        case ValueType.exceptionArray: return "Z8Array!Throwable";
        case ValueType.exceptionMatrix: return "Z8Array!(Z8Array!Throwable)";
        case ValueType.encodingArray: return "Z8Array!Z8Encoding";
        case ValueType.encodingMatrix: return "Z8Array!(Z8Array!Z8Encoding)";
        case ValueType.nullType: assert(0, "null has no concrete D type");
        case ValueType.nullableString: return "wstring";
        case ValueType.enumType: assert(objectClass !is null); return objectClass.emittedName;
        case ValueType.enumArray: assert(objectClass !is null); return "Z8Array!(" ~ objectClass.emittedName ~ ")";
        case ValueType.enumMatrix: assert(objectClass !is null); return "Z8Array!(Z8Array!(" ~ objectClass.emittedName ~ "))";
        case ValueType.optionalInt: return "Z8Optional!long";
        case ValueType.optionalBool: return "Z8Optional!bool";
        case ValueType.optionalDecimal: return "Z8Optional!Z8Decimal";
        default: assert(0, "unsupported D type");
    }
}
/// The Java runtime stores strings as UTF-16; preserve its code-unit ordering.
private string emitStringLiteral(string text) {
    return emitWStringLiteral(decodeStringLiteral(text));
}

/// Emit readable UTF-16 literals, falling back to code units for lone surrogates.
private string emitWStringLiteral(const(wchar)[] value) {
    string literal = `"`;
    for (size_t i = 0; i < value.length; ++i) {
        auto c = value[i];
        switch (c) {
            case '"': literal ~= `\"`; break;
            case '\\': literal ~= `\\`; break;
            case '\b': literal ~= `\b`; break;
            case '\f': literal ~= `\f`; break;
            case '\n': literal ~= `\n`; break;
            case '\r': literal ~= `\r`; break;
            case '\t': literal ~= `\t`; break;
            default:
                if (c >= 0xD800 && c <= 0xDBFF) {
                    if (i + 1 == value.length || value[i + 1] < 0xDC00 || value[i + 1] > 0xDFFF)
                        return emitWStringCodeUnits(value);
                    literal ~= value[i .. i + 2].to!string;
                    ++i;
                } else if (c >= 0xDC00 && c <= 0xDFFF) {
                    return emitWStringCodeUnits(value);
                } else if (c < 0x20 || c == 0x7F || c == 0x85 || c == 0x2028 || c == 0x2029) {
                    // formatDSource treats the Unicode separators as line breaks.
                    literal ~= format("\\u%04X", cast(uint)c);
                } else {
                    literal ~= value[i .. i + 1].to!string;
                }
                break;
        }
    }
    return `z8_string_new(` ~ literal ~ `"w)`;
}

private string emitAttributeValue(TypeAttribute attribute) {
    if (attribute.expression !is null) {
        auto value = emitExpr(attribute.expression);
        if (attribute.expressionType == ValueType.fileType)
            value = "z8_file_to_string(" ~ value ~ ")";
        else if (attribute.expressionType == ValueType.exceptionType)
            value = "z8_exception_to_java_string(" ~ value ~ ")";
        if (attribute.expression.convertToString == ValueType.selfType)
            value = "z8_attribute_from(" ~ value ~ ", " ~ emitWStringLiteral(attribute.name.text.to!wstring) ~ ")";
        return "z8_string_new(z8_string_required(" ~ value ~ "))";
    }
    if (attribute.hasValue && attribute.value.kind == TokenKind.dateLiteral) {
        if (attribute.dateTickCaptured)
            return emitWStringLiteral((attribute.capturedDateTicks.to!string ~ "L").to!wstring);
        return "z8_string_new((z8_date_ticks(z8_date_literal(z8_to_utf8(" ~
            emitWStringLiteral(attribute.value.text[1 .. $ - 1].to!wstring) ~
            ")))).to!string.to!wstring ~ \"L\"w)";
    }
    return emitWStringLiteral(attributeLiteralValue(attribute));
}

private string emitWStringCodeUnits(const(wchar)[] value) {
    string[] units;
    foreach (c; value) units ~= format("cast(wchar)0x%04X", cast(uint)c);
    return "z8_string_new([" ~ units.join(", ") ~ "].idup)";
}

unittest {
    assert(emitWStringLiteral([cast(wchar) 0xD800]) ==
        "z8_string_new([cast(wchar)0xD800].idup)");
    assert(emitWStringLiteral([cast(wchar) 0xDC00]) ==
        "z8_string_new([cast(wchar)0xDC00].idup)");
}
private string dStorageType(ValueType type, Program objectClass = null) {
    return type == ValueType.intType ? "Z8Optional!long" : type == ValueType.boolType ? "Z8Optional!bool" : type == ValueType.decimalType ? "Z8Optional!Z8Decimal" : dType(type, objectClass);
}
private string emitExpr(Expression e) {
    string value;
    bool deferArguments;
    if (!e.emittedOverride.length && e.kind == ExprKind.memberCall && !e.instanceCall && !e.targetClass.length)
        foreach (argument; e.arguments) if (argument.optionalRequired) deferArguments = true;
    if (e.emittedOverride.length) value = e.emittedOverride;
    else if (deferArguments) {
        auto suffix = e.token.position.offset.to!string;
        value = "(() { ";
        string savedReceiver;
        if (!e.builtinCall.length) {
            savedReceiver = e.left.emittedOverride;
            auto name = "z8_receiver_" ~ suffix;
            value ~= "auto " ~ name ~ " = " ~ emitExpr(e.left) ~ "; ";
            e.left.emittedOverride = name;
        }
        string[] savedOverrides;
        ValueType[] savedBinaryConversions;
        ValueType[] savedStringConversions;
        bool[] savedPromotions;
        bool[] savedFileConversions, savedExceptionConversions, savedDateConversions, savedSqlBoolConversions, savedSqlIntConversions, savedSqlDecimalConversions, savedSqlIntDecimalConversions, savedSqlStringConversions;
        Method[] savedUserConversions;
        foreach (i, argument; e.arguments) {
            savedOverrides ~= argument.emittedOverride;
            savedUserConversions ~= argument.userConversion;
            savedBinaryConversions ~= argument.convertToBinary;
            savedFileConversions ~= argument.makeFile;
            savedExceptionConversions ~= argument.makeException;
            savedDateConversions ~= argument.convertToDate;
            savedSqlBoolConversions ~= argument.convertToSqlBool;
            savedSqlIntConversions ~= argument.convertToSqlInt;
            savedSqlDecimalConversions ~= argument.convertToSqlDecimal;
            savedSqlIntDecimalConversions ~= argument.convertSqlIntToDecimal;
            savedSqlStringConversions ~= argument.convertToSqlString;
            auto required = argument.optionalRequired, promote = argument.promoteToDecimal;
            auto convert = argument.convertToString;
            savedPromotions ~= promote; savedStringConversions ~= convert;
            if (required) { argument.optionalRequired = false; argument.promoteToDecimal = false; argument.convertToString = ValueType.voidType; argument.convertToDate = false; argument.convertToSqlBool = false; argument.convertToSqlInt = false; argument.convertToSqlDecimal = false; argument.convertSqlIntToDecimal = false; argument.convertToSqlString = false; }
            auto name = "z8_arg_" ~ suffix ~ "_" ~ i.to!string;
            value ~= "auto " ~ name ~ " = " ~ emitExpr(argument) ~ "; ";
            argument.optionalRequired = required; argument.promoteToDecimal = required && promote;
            argument.convertToString = required ? convert : ValueType.voidType;
            argument.convertToBinary = ValueType.voidType;
            argument.makeFile = false; argument.makeException = false;
            argument.convertToDate = required ? savedDateConversions[$ - 1] : false;
            argument.convertToSqlBool = required && savedSqlBoolConversions[$ - 1];
            argument.convertToSqlInt = required && savedSqlIntConversions[$ - 1];
            argument.convertToSqlDecimal = required && savedSqlDecimalConversions[$ - 1];
            argument.convertSqlIntToDecimal = required && savedSqlIntDecimalConversions[$ - 1];
            argument.convertToSqlString = required && savedSqlStringConversions[$ - 1];
            argument.emittedOverride = name;
            argument.userConversion = null;
        }
        value ~= "return " ~ emitExprRaw(e) ~ "; })()";
        if (!e.builtinCall.length) e.left.emittedOverride = savedReceiver;
        foreach (i, argument; e.arguments) {
            argument.emittedOverride = savedOverrides[i];
            argument.userConversion = savedUserConversions[i];
            argument.promoteToDecimal = savedPromotions[i]; argument.convertToString = savedStringConversions[i];
            argument.convertToBinary = savedBinaryConversions[i];
            argument.makeFile = savedFileConversions[i]; argument.makeException = savedExceptionConversions[i];
            argument.convertToDate = savedDateConversions[i];
            argument.convertToSqlBool = savedSqlBoolConversions[i];
            argument.convertToSqlInt = savedSqlIntConversions[i];
            argument.convertToSqlDecimal = savedSqlDecimalConversions[i];
            argument.convertSqlIntToDecimal = savedSqlIntDecimalConversions[i];
            argument.convertToSqlString = savedSqlStringConversions[i];
        }
    } else value = emitExprRaw(e);
    if (!e.emittedOverride.length && e.kind == ExprKind.memberCall &&
        ((e.inferredType == ValueType.stringType && ["toString", "substring", "left", "right", "charAt", "trim", "trimLeft", "trimRight",
            "padLeft", "padRight", "insert", "replace", "toLowerCase", "toUpperCase", "replaceFirst", "replaceAll", "format", "getGroup"].canFind(e.token.text)) ||
         ["z8_string_replicate", "z8_string_concat", "z8_string_fromBinary",
          "z8_file_read", "z8_file_toJson", "z8_file_to_string", "z8_file_name", "z8_file_baseName",
          "z8_file_extension", "z8_file_fileName", "z8_file_folder", "z8_file_baseName_instance",
          "z8_file_extension_instance", "z8_binary_base_name", "z8_binary_extension", "z8_binary_to_string",
          "z8_guid_to_string", "z8_primary_to_string", "z8_geometry_to_string", "z8_geometry_toGeoJson",
          "z8_date_toString", "z8_date_toIsoString", "z8_datespan_to_string"].canFind(e.builtinCall)))
        value = "z8_string_new(" ~ value ~ ")";
    if (!e.emittedOverride.length && e.priorityMethod !is null) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_nonnull(" ~ value ~ ")." ~ methodDName(e.priorityMethod) ~ "()";
    }
    if (!e.emittedOverride.length && e.sqlBoolPriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_bool_group(" ~ value ~ ")";
    }
    if (!e.emittedOverride.length && e.sqlIntPriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_int_group(" ~ value ~ ")";
    }
    if (!e.emittedOverride.length && e.sqlDecimalPriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_decimal_group(" ~ value ~ ")";
    }
    if (!e.emittedOverride.length && e.sqlStringPriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_string_group(" ~ value ~ ")";
    }
    if (!e.emittedOverride.length && e.sqlGuidPriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_guid_group(" ~ value ~ ")";
    }
    if (!e.emittedOverride.length && e.sqlDatePriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_date_group(" ~ value ~ ")";
    }
    if (!e.emittedOverride.length && e.sqlDatespanPriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_datespan_group(" ~ value ~ ")";
    }
    if (!e.emittedOverride.length && e.sqlGeometryPriority) {
        auto count = e.parenthesisCount - (e.firstParenthesisIsConditional ? 1 : 0);
        foreach (_; 0 .. count) value = "z8_sql_geometry_group(" ~ value ~ ")";
    }
    if (e.userConversion !is null) value = "z8_nonnull(" ~ value ~ ")." ~ methodDName(e.userConversion) ~ "()";
    if (e.nonNullStringResult) value = "z8_string_or_empty(" ~ value ~ ")";
    if (e.optionalRequired) value = "z8_optional_require(" ~ value ~ ")";
    if (e.convertToSqlBool) value = "z8_sql_bool_const(" ~ value ~ ")";
    if (e.convertToSqlInt) value = "z8_sql_int_const(" ~ value ~ ")";
    if (e.convertToSqlDecimal) value = "z8_sql_decimal_const(" ~ value ~ ")";
    if (e.convertSqlIntToDecimal) value = "z8_sql_decimal_from_int(" ~ value ~ ")";
    if (e.convertToSqlString) value = "z8_sql_string_const(" ~ value ~ ")";
    if (e.convertToSqlGuid) value = "z8_sql_guid_const(" ~ value ~ ")";
    if (e.convertToSqlDate) value = "z8_sql_date_const(" ~ value ~ ")";
    if (e.convertToSqlDatespan) value = "z8_sql_datespan_const(" ~ value ~ ")";
    if (e.convertToSqlGeometry) value = "z8_sql_geometry_const(" ~ value ~ ")";
    if (e.nullableStringMode == NullableStringMode.required) value = "z8_string_required(" ~ value ~ ")";
    if (e.nullableStringMode == NullableStringMode.nullAsEmpty) value = "z8_string_or_empty(" ~ value ~ ")";
    if (e.kind == ExprKind.conditional && isNullableReference(e.inferredType))
        value = "cast(" ~ dType(e.inferredType, e.objectClass) ~ ")(" ~ value ~ ")";
    if (e.promoteToDecimal) value = "z8_decimal_from_int(" ~ value ~ ")";
    if (e.optionalWrap) value = "z8_optional_wrap(" ~ value ~ ")";
    if (e.boxPrimary) value = "z8_primary_box(" ~ value ~ ")";
    if (e.makeFile) value = "z8_file_from_path(" ~ value ~ ")";
    if (e.makeException) value = "new Z8Exception(z8_to_utf8(z8_string_required(" ~ value ~ ")))";
    if (e.convertToDate) value = "z8_date_from_ticks(" ~ value ~ ")";
    if (e.convertToBinary == ValueType.fileType) return "z8_file_to_binary(" ~ value ~ ")";
    if (e.convertToBinary == ValueType.stringType || e.convertToBinary == ValueType.nullableString) return "z8_binary_from_string(" ~ value ~ ")";
    if (e.convertToString == ValueType.intType) return "(" ~ value ~ ").to!string.to!wstring";
    if (e.convertToString == ValueType.boolType) return "(" ~ value ~ " ? \"true\"w : \"false\"w)";
    if (e.convertToString == ValueType.decimalType) return "(" ~ value ~ ").z8_string()";
    if (e.convertToString == ValueType.primaryType) return "z8_primary_to_string(" ~ value ~ ")";
    if (e.convertToString == ValueType.binaryType) return "z8_binary_to_string(" ~ value ~ ")";
    if (e.convertToString == ValueType.guidType) return "z8_guid_to_string(" ~ value ~ ")";
    if (e.convertToString == ValueType.datespanType) return "z8_datespan_to_string(" ~ value ~ ")";
    if (e.convertToString == ValueType.fileType) return "z8_file_path(" ~ value ~ ")";
    if (e.convertToString == ValueType.exceptionType) return "z8_string_or_empty(z8_message(z8_nonnull(" ~ value ~ ")))";
    if (e.convertToString == ValueType.dateType) return "z8_date_toString(" ~ value ~ ")";
    if (e.convertToString == ValueType.geometryType) return "z8_geometry_to_string(" ~ value ~ ")";
    return value;
}
private string emitReceiver(Expression e) {
    if (e.kind == ExprKind.superRef) return "(" ~ emitExpr(e) ~ ")";
    return "z8_nonnull(" ~ emitExpr(e) ~ (e.earlyFieldInitialization ? ", -1" : e.fieldInitialization ? ", 0" : "") ~ ")";
}
private string emitExprRaw(Expression e) {
    final switch (e.kind) {
        case ExprKind.integer:
            return "(cast(long)(" ~ e.token.text.replace(" ", "").replace("\t", "") ~ "))";
        case ExprKind.decimalLiteral:
            return "z8_decimal_literal(\"" ~ canonicalDecimalLiteral(e.token) ~ "\")";
        case ExprKind.boolean: return e.token.text;
        case ExprKind.stringLiteral: return emitStringLiteral(e.token.text);
        case ExprKind.guidLiteral: return "z8_guid_literal(\"" ~ e.token.text[1 .. $ - 1] ~ "\")";
        case ExprKind.binaryLiteral: return "z8_binary_literal(\"" ~ e.token.text[1 .. $ - 1] ~ "\")";
        case ExprKind.datespanLiteral: return "z8_datespan_literal(\"" ~ e.token.text[1 .. $ - 1] ~ "\")";
        case ExprKind.dateLiteral: return "z8_date_literal(\"" ~ e.token.text[1 .. $ - 1] ~ "\")";
        case ExprKind.nullLiteral: return isOptionalPrimitive(e.inferredType) ? dType(e.inferredType) ~ ".init" : e.inferredType == ValueType.voidType ? "null" : "cast(" ~ dType(e.inferredType, e.objectClass) ~ ")null";
        case ExprKind.arrayLiteral:
            if (isMap(e.inferredType)) {
                string body = "(() {\n";
                foreach (i, entry; e.arguments)
                    body ~= dStorageType(mapKeyType(e.inferredType)) ~ " z8_key_" ~ i.to!string ~ " = " ~ emitExpr(entry.left) ~ ";\n";
                auto valueType = dStorageType(mapValueType(e.inferredType));
                foreach (i, entry; e.arguments)
                    body ~= valueType ~ " z8_value_" ~ i.to!string ~ " = " ~ emitExpr(entry.right) ~ ";\n";
                body ~= "auto z8_result = new " ~ dType(e.inferredType) ~ "();\n";
                foreach (i, entry; e.arguments)
                    body ~= "z8_result.z8_add(z8_key_" ~ i.to!string ~ ", z8_value_" ~ i.to!string ~ ");\n";
                return body ~ "return z8_result;\n})()";
            }
            string[] elements; foreach (element; e.arguments)
                elements ~= (e.inferredType == ValueType.selfArray || e.inferredType == ValueType.enumArray) ? "cast(" ~ e.objectClass.emittedName ~ ")(" ~ emitExpr(element) ~ ")" : emitExpr(element);
            return "new " ~ dType(e.inferredType, e.objectClass) ~ "(" ~ (elements.length ? "[" ~ elements.join(", ") ~ "]" ~ ([ValueType.intArray, ValueType.boolArray, ValueType.decimalArray].canFind(e.inferredType) ? ", true" : "") : "") ~ ")";
        case ExprKind.mapEntry: assert(0, "map entries are emitted by their initializer");
        case ExprKind.variable: return e.isCapture ? "this.z8_capture_" ~ e.token.text : e.isField ? (e.targetClass.length ? e.targetClass ~ ".f_" : "this.f_") ~ e.token.text : "v_" ~ e.token.text;
        case ExprKind.selfRef: return "this";
        case ExprKind.superRef: return "super";
        case ExprKind.containerRef:
            return "z8_get_container!(" ~ e.objectClass.emittedName ~ ")(" ~ (e.left is null ? "this" : emitExpr(e.left)) ~ ")";
        case ExprKind.newSelf:
            if (e.inferredType == ValueType.ftsType) return "new Z8Fts()";
            if (e.inferredType == ValueType.sqlBoolType) return "z8_sql_bool_const(false)";
            if (e.inferredType == ValueType.sqlIntType) return "z8_sql_int_const(0L)";
            if (e.inferredType == ValueType.sqlDecimalType) return "z8_sql_decimal_const(z8_decimal_from_int(0))";
            if (e.inferredType == ValueType.sqlStringType) return "z8_sql_string_const(z8_string_new(\"\"w))";
            if (e.inferredType == ValueType.sqlGuidType) return "z8_sql_guid_const(z8_guid_zero())";
            if (e.inferredType == ValueType.sqlDateType) return "z8_sql_date_const(z8_date_now())";
            if (e.inferredType == ValueType.sqlDatespanType) return "z8_sql_datespan_const(new Z8Datespan())";
            if (e.inferredType == ValueType.sqlBinaryType) return "new Z8SqlBinary()";
            if (e.inferredType == ValueType.sqlGeometryType) return "z8_sql_geometry_const(new Z8Geometry())";
            if (e.inferredType == ValueType.sqlPrimaryType) return "new Z8SqlPrimary()";
            return "z8_new!(" ~ e.objectClass.emittedName ~ ")(" ~ (e.newHasContainer ? "this" : "") ~ ")";
        case ExprKind.field:
            if (e.nativeField.length) return "z8_nonnull(" ~ emitExpr(e.left) ~ ")." ~ e.nativeField;
            if (e.binaryNameField) return "z8_nonnull(" ~ emitExpr(e.left) ~ ").name";
            if (e.enumConstant) return e.targetClass ~ ".e_" ~ e.token.text;
            if (e.staticInstanceField)
                return "z8_static_field(" ~ emitReceiver(e.left) ~ ", " ~ e.targetClass ~ ".f_" ~ e.token.text ~ ")";
            return (e.targetClass.length ? e.targetClass : emitReceiver(e.left)) ~ ".f_" ~ e.token.text;
        case ExprKind.call:
            string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
            return (e.targetClass.length ? e.targetClass ~ "." : "") ~ "m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
        case ExprKind.memberCall:
            if (e.builtinCall.length) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                if (e.builtinCall == "z8_sql_geometry_point") return e.builtinCall ~ "(" ~ args.join(", ") ~ ")";
                if (e.builtinCall.startsWith("z8_regex_") || e.builtinCall == "z8_string_format" || e.builtinCall.startsWith("z8_sql_"))
                    return e.builtinCall ~ "(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
                if ((e.inferredType == ValueType.binaryType || e.inferredType == ValueType.datespanType || e.inferredType == ValueType.dateType || e.inferredType == ValueType.geometryType || e.inferredType == ValueType.fileType) && e.left !is null)
                    return e.builtinCall ~ "(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
                if (e.builtinCall == "z8_primary_to_string" || e.builtinCall == "z8_primary_hash" || e.builtinCall == "z8_primary_hash_value" ||
                    ["z8_guid_to_string", "z8_guid_hash", "z8_guid_major", "z8_guid_minor", "z8_guid_components"].canFind(e.builtinCall))
                    return e.builtinCall ~ "(" ~ emitExpr(e.left) ~ ")";
                return e.builtinCall ~ "(" ~ args.join(", ") ~ ")";
            }
            if (e.optionalDecimalReceiver) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_optional_decimal_call!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            if (e.optionalBoolReceiver) return "(z8_optional_require(" ~ emitExpr(e.left) ~ ") ? \"true\"w : \"false\"w)";
            if (e.optionalIntReceiver) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_optional_int_call!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            if (e.nullableStringReceiver) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_nullable_string_call!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            if (e.staticInstanceCall) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                auto call = e.targetClass ~ ".m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
                if (e.left.kind == ExprKind.superRef) return call;
                return "({ auto z8_receiver = " ~ emitReceiver(e.left) ~ "; return " ~ call ~ "; })()";
            }
            if (e.instanceCall) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return emitReceiver(e.left) ~ ".m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
            }
            if (e.targetClass.length) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return e.targetClass ~ ".m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
            }
            if (isArray(e.inferredType)) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_invoke!\"z8_" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            if (isMap(e.inferredType)) {
                if (e.token.text == "add" && e.arguments.length == 2 &&
                    e.arguments[0].kind == ExprKind.nullLiteral && e.arguments[1].kind == ExprKind.nullLiteral)
                    return "z8_map_add_null_pair!(" ~ dStorageType(mapValueType(e.inferredType)) ~ ")(" ~ emitExpr(e.left) ~ ")";
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_invoke!\"z8_" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            if (e.inferredType == ValueType.exceptionType) return (e.token.text == "getStackTrace" ? "z8_stacktrace(" : "z8_message(") ~ "z8_nonnull(" ~ emitExpr(e.left) ~ "))";
            if (e.inferredType == ValueType.decimalType) {
                auto receiver = "(" ~ emitExpr(e.left) ~ ")";
                if (e.token.text == "toString") return receiver ~ ".z8_string()";
                if (["signum", "ceil", "floor"].canFind(e.token.text)) return receiver ~ ".z8_" ~ e.token.text ~ "()";
                if (["abs", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "toRadians", "toDegrees", "exp", "ln", "log10", "sqrt", "cbrt", "power"].canFind(e.token.text)) {
                    string[] args; foreach (arg; e.arguments) args ~= emitExpr(arg);
                    return "z8_decimal_math!\"" ~ e.token.text ~ "\"(" ~ receiver ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
                }
                if (!e.arguments.length) return receiver ~ ".z8_round_int()";
                string[] args; foreach (arg; e.arguments) args ~= emitExpr(arg);
                return receiver ~ ".z8_round(" ~ args.join(", ") ~ ")";
            }
            if (e.inferredType == ValueType.intType) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_int_" ~ e.token.text ~ "(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            if (e.inferredType == ValueType.boolType) return "(" ~ emitExpr(e.left) ~ " ? \"true\"w : \"false\"w)";
            if (e.token.text == "toString") return emitExpr(e.left);
            if (e.token.text != "length" && e.token.text != "isEmpty") {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_str_" ~ e.token.text ~ "(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            auto value = "(" ~ emitExpr(e.left) ~ ").length";
            return e.token.text == "length" ? "cast(long)(" ~ value ~ ")" : "(" ~ value ~ " == 0)";
        case ExprKind.index:
            if (isMap(e.inferredType)) return "z8_invoke!\"z8_get\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            return "z8_array_at(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
        case ExprKind.castExpr:
            if (e.primaryCast) return "z8_primary_cast!(" ~ dType(e.castType) ~ ")(" ~ emitExpr(e.left) ~ ")";
            if (e.sqlPrimaryCast) return "z8_cast!(" ~ dType(e.castType) ~ ")(" ~ emitExpr(e.left) ~ ")";
            return e.castType == ValueType.selfType ? "z8_cast!(" ~ e.objectClass.emittedName ~ ")(" ~ emitExpr(e.left) ~ ")" : emitExpr(e.left);
        case ExprKind.instanceOf:
            if (e.sqlPrimaryInstanceOf) return "(cast(" ~ dType(e.castType) ~ ")(" ~ emitExpr(e.left) ~ ") !is null)";
            if (e.exceptionInstanceOf) return "(cast(Z8Exception)(" ~ emitExpr(e.left) ~ ") !is null)";
            if (e.falseInstanceOf) {
                if (e.inferredType == ValueType.nullType) return "false";
                return "(() { auto z8_value = " ~ emitExpr(e.left) ~ "; return false; })()";
            }
            if (e.scalarInstanceOf) {
                if (isOptionalPrimitive(e.inferredType)) return "(!z8_optional_is_null(" ~ emitExpr(e.left) ~ "))";
                if ([ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(e.inferredType))
                    return "(() { auto z8_value = " ~ emitExpr(e.left) ~ "; return true; })()";
                return "(" ~ emitExpr(e.left) ~ " !is null)";
            }
            if (e.primaryInstanceOf) return "z8_primary_is!(" ~ dType(e.castType) ~ ")(" ~ emitExpr(e.left) ~ ")";
            if (e.objectInstanceOf) return "(cast(" ~ e.objectClass.emittedName ~ ")(cast(Object)(" ~ emitExpr(e.left) ~ ")) !is null)";
            return "(cast(" ~ e.objectClass.emittedName ~ ")(" ~ emitExpr(e.left) ~ ") !is null)";
        case ExprKind.unary:
            if (e.sqlBoolOperator) return "z8_sql_bool_not(" ~ emitExpr(e.left) ~ ")";
            if (e.sqlIntOperator) return (e.token.text == "+" ? "z8_nonnull(" : e.token.text == "~" ? "z8_sql_int_bit_not(" : "z8_sql_int_negate(") ~ emitExpr(e.left) ~ ")";
            if (e.sqlDecimalOperator) return (e.token.text == "+" ? "z8_nonnull(" : "z8_sql_decimal_negate(") ~ emitExpr(e.left) ~ ")";
            if (e.userUnaryOperator) return emitReceiver(e.left) ~ "." ~ operatorDName(e.token.text) ~ "()";
            if (e.optionalDecimalUnary) return "(" ~ e.token.text ~ "z8_optional_require(" ~ emitExpr(e.left) ~ "))";
            if (e.optionalBoolUnary) return "(!z8_optional_require(" ~ emitExpr(e.left) ~ "))";
            if (e.optionalIntUnary) return "z8_optional_int_unary!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ")";
            return "(" ~ e.token.text ~ emitExpr(e.left) ~ ")";
        case ExprKind.binary:
            if (e.sqlBoolOperator) return "z8_sql_bool_binary!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlIntOperator) return (e.sqlIntComparison ? "z8_sql_int_compare!\"" : "z8_sql_int_binary!\"") ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlDecimalOperator) return (e.sqlDecimalComparison ? "z8_sql_numeric_compare!\"" : "z8_sql_decimal_binary!\"") ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlStringOperator) return (e.sqlStringComparison ? "z8_sql_string_compare!\"" ~ e.token.text ~ "\"(" : "z8_sql_string_concat(") ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlGuidOperator) return "z8_sql_guid_compare!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlDateOperator) return "z8_sql_date_compare!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlGeometryOperator) return "z8_sql_geometry_compare!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlDateArithmetic) return "z8_sql_date_arithmetic!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.sqlDatespanOperator) return (e.sqlDatespanComparison ? "z8_sql_datespan_compare!\"" : "z8_sql_datespan_binary!\"") ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.userBinaryOperator) return emitReceiver(e.left) ~ "." ~ operatorDName(e.token.text) ~ "(" ~ emitExpr(e.right) ~ ")";
            if (e.dateBinary) return "z8_date_binary!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.fileBinary) return "z8_file_compare!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.optionalNullComparison) {
                auto value = e.optionalNullOnLeft ? e.right : e.left;
                return (e.token.text == "==" ? "" : "!") ~ "z8_optional_is_null(" ~ emitExpr(value) ~ ")";
            }
            if (e.optionalBoolBinary) {
                auto left = emitExpr(e.left), right = emitExpr(e.right);
                if (!e.optionalBoolLeft) left = "z8_optional_wrap(" ~ left ~ ")";
                if (!e.optionalBoolRight) right = "z8_optional_wrap(" ~ right ~ ")";
                return "z8_optional_bool_binary!\"" ~ e.token.text ~ "\"(" ~ left ~ ", " ~ right ~ ")";
            }
            if (e.optionalIntBinary) {
                auto left = emitExpr(e.left), right = emitExpr(e.right);
                if (!e.optionalIntLeft) left = "z8_optional_wrap(" ~ left ~ ")";
                if (!e.optionalIntRight) right = "z8_optional_wrap(" ~ right ~ ")";
                return "z8_optional_int_binary!\"" ~ e.token.text ~ "\"(" ~ left ~ ", " ~ right ~ ")";
            }
            if (e.optionalDecimalBinary) {
                auto left = emitExpr(e.left), right = emitExpr(e.right);
                if (!e.optionalDecimalLeft) left = "z8_optional_wrap(" ~ left ~ ")";
                if (!e.optionalDecimalRight) right = "z8_optional_wrap(" ~ right ~ ")";
                return "z8_optional_decimal_binary!\"" ~ e.token.text ~ "\"(" ~ left ~ ", " ~ right ~ ")";
            }
            if (e.optionalMixedIntDecimal) {
                auto left = emitExpr(e.left), right = emitExpr(e.right);
                if (!(e.optionalIntLeft || e.optionalDecimalLeft)) left = "z8_optional_wrap(" ~ left ~ ")";
                if (!(e.optionalIntRight || e.optionalDecimalRight)) right = "z8_optional_wrap(" ~ right ~ ")";
                return "z8_optional_mixed!(\"" ~ e.token.text ~ "\", " ~ (e.optionalMixedIntOnLeft ? "true" : "false") ~ ")(" ~ left ~ ", " ~ right ~ ")";
            }
            if (e.inferredType == ValueType.nullType)
                return "(" ~ emitExpr(e.left) ~ (e.token.text == "==" ? " is " : " !is ") ~ emitExpr(e.right) ~ ")";
            if (e.inferredType == ValueType.guidType)
                return "z8_guid_compare!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.inferredType == ValueType.datespanType)
                return "z8_datespan_binary!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (isMap(e.inferredType))
                return "z8_map_union(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (isArray(e.inferredType))
                return "z8_array_union(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.nullableStringLeft)
                return "z8_nullable_string_binary!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.token.text == "+" && e.inferredType == ValueType.stringType)
                return "z8_string_new(" ~ emitExpr(e.left) ~ " ~ " ~ emitExpr(e.right) ~ ")";
            if ((e.token.text == "/" || e.token.text == "%") && e.inferredType != ValueType.decimalType)
                return (e.token.text == "/" ? "z8_div(" : "z8_mod(") ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            auto op = e.emittedOperator.length ? e.emittedOperator : e.token.text == "+" && e.inferredType == ValueType.stringType ? "~" : e.token.text;
            return "(" ~ emitExpr(e.left) ~ " " ~ op ~ " " ~ emitExpr(e.right) ~ ")";
        case ExprKind.conditional:
            return "(" ~ emitExpr(e.left) ~ " ? " ~ emitExpr(e.right) ~ " : " ~ emitExpr(e.third) ~ ")";
        case ExprKind.elvis:
            if (isOptionalPrimitive(e.inferredType))
                return (e.optionalElvis ? "z8_optional_elvis_optional(" : "z8_optional_elvis(") ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            return "z8_elvis!(" ~ dType(e.inferredType, e.objectClass) ~ ")(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
    }
}
private struct ControlContext {
    bool enabled;
    ValueType returnType;
    Program returnClass;
    size_t[] loops;
}

private bool needsControlLowering(Statement s) {
    if (s.kind == StmtKind.tryStmt && s.hasFinally) return true;
    foreach (child; s.children) if (needsControlLowering(child)) return true;
    return false;
}

private string emitLoopBody(Statement loop, ControlContext context) {
    if (!context.enabled) return emitStatement(loop.children[0], context);
    auto id = loop.token.position.offset.to!string;
    auto nested = context;
    nested.loops = context.loops ~ loop.token.position.offset;
    auto signal = "z8_loop_signal_" ~ id;
    return "try " ~ emitStatement(loop.children[0], nested) ~
        "catch (Z8LoopControl " ~ signal ~ ") {\n" ~
        "if (" ~ signal ~ ".loopId != " ~ id ~ ") throw " ~ signal ~ ";\n" ~
        "if (" ~ signal ~ ".continuing) continue;\nbreak;\n}\n";
}

private string emitStatement(Statement s, ControlContext context = ControlContext.init) {
    final switch (s.kind) {
        case StmtKind.block:
            string result = "{\n"; foreach (child; s.children) result ~= emitStatement(child, context); return result ~ "}\n";
        case StmtKind.variable:
        case StmtKind.assignment:
        case StmtKind.expressionStmt: return emitSimple(s) ~ ";\n";
        case StmtKind.returnStmt:
            auto returned = s.expression is null ? "" : emitExpr(s.expression);
            if (s.priorityMethod !is null) returned = "z8_nonnull(" ~ returned ~ ")." ~ methodDName(s.priorityMethod) ~ "()";
            if (s.sqlBoolReturnPriority) returned = "z8_sql_bool_group(" ~ returned ~ ")";
            if (s.sqlIntReturnPriority) returned = "z8_sql_int_group(" ~ returned ~ ")";
            if (s.sqlDecimalReturnPriority) returned = "z8_sql_decimal_group(" ~ returned ~ ")";
            if (s.sqlStringReturnPriority) returned = "z8_sql_string_group(" ~ returned ~ ")";
            if (s.sqlGuidReturnPriority) returned = "z8_sql_guid_group(" ~ returned ~ ")";
            if (s.sqlDateReturnPriority) returned = "z8_sql_date_group(" ~ returned ~ ")";
            if (s.sqlDatespanReturnPriority) returned = "z8_sql_datespan_group(" ~ returned ~ ")";
            if (s.sqlGeometryReturnPriority) returned = "z8_sql_geometry_group(" ~ returned ~ ")";
            if (context.enabled) return s.expression is null ? "throw new Z8ReturnVoid();\n" :
                "throw new Z8Return!(" ~ dStorageType(context.returnType, context.returnClass) ~ ")(" ~ returned ~ ");\n";
            return "return" ~ (s.expression is null ? "" : " " ~ returned) ~ ";\n";
        case StmtKind.ifStmt:
            auto result = "if (" ~ emitExpr(s.expression) ~ ") {\n" ~ emitStatement(s.children[0], context) ~ "}\n";
            if (s.children.length == 2) result ~= "else {\n" ~ emitStatement(s.children[1], context) ~ "}\n";
            return result;
        case StmtKind.whileStmt:
            return "while (" ~ emitExpr(s.expression) ~ ") {\n" ~ emitLoopBody(s, context) ~ "}\n";
        case StmtKind.doWhileStmt:
            return "do {\n" ~ emitLoopBody(s, context) ~ "} while (" ~ emitExpr(s.expression) ~ ");\n";
        case StmtKind.forStmt:
            return "for (" ~ (s.initial is null ? "" : emitSimple(s.initial)) ~ "; " ~ emitExpr(s.expression) ~ "; " ~ emitSimple(s.step) ~ ") {\n" ~ emitLoopBody(s, context) ~ "}\n";
        case StmtKind.forEachStmt:
            auto suffix = s.token.position.offset.to!string;
            auto iter = "z8_iter_" ~ suffix, versionName = "z8_version_" ~ suffix, indexName = "z8_index_" ~ suffix;
            return "{\nauto " ~ iter ~ " = " ~ emitReceiver(s.expression) ~ ";\nauto " ~ versionName ~ " = " ~ iter ~ ".z8_version;\n" ~
                "for (long " ~ indexName ~ " = 0; " ~ indexName ~ " != " ~ iter ~ ".z8_size(); ++" ~ indexName ~ ") {\n" ~
                "if (" ~ versionName ~ " != " ~ iter ~ ".z8_version) throw new Exception(\"array modified during iteration\");\n" ~
                dStorageType(s.initial.type, s.initial.objectClass) ~ " v_" ~ s.initial.token.text ~ " = " ~ iter ~ ".z8_get(" ~ indexName ~ ");\n" ~
                emitLoopBody(s, context) ~ "}\n}\n";
        case StmtKind.breakStmt: case StmtKind.continueStmt:
            if (context.enabled) return "throw new Z8LoopControl(" ~ context.loops[$-1].to!string ~ ", " ~ (s.kind == StmtKind.continueStmt ? "true" : "false") ~ ");\n";
            return s.kind == StmtKind.breakStmt ? "break;\n" : "continue;\n";
        case StmtKind.throwStmt:
            return "throw " ~ (s.type == ValueType.stringType ? "new Z8Exception(z8_to_utf8(" ~ emitExpr(s.expression) ~ "))" : "z8_nonnull(" ~ emitExpr(s.expression) ~ ")") ~ ";\n";
        case StmtKind.tryStmt:
            auto result = (context.enabled && s.hasFinally && !s.hasCatch ? "" : "try ") ~ emitStatement(s.children[0], context);
            if (s.hasCatch) {
                auto caught = "z8_caught_" ~ s.token.position.offset.to!string;
                result ~= "catch (Throwable " ~ caught ~ ") {\n" ~
                    (context.enabled ? "if (cast(Z8ControlFlow)" ~ caught ~ " !is null) throw " ~ caught ~ ";\n" : "") ~
                    "Throwable v_" ~ s.catchName.text ~ " = new Z8Exception(" ~ caught ~ ".msg, " ~ caught ~ ");\n" ~
                    emitStatement(s.children[1], context) ~ "}\n";
            }
            if (s.hasFinally && context.enabled) {
                auto suffix = s.token.position.offset.to!string;
                auto pending = "z8_pending_" ~ suffix, caught = "z8_finally_caught_" ~ suffix;
                result = "{\nThrowable " ~ pending ~ ";\ntry {\n" ~ result ~ "} catch (Throwable " ~ caught ~ ") { " ~ pending ~ " = " ~ caught ~ "; }\n" ~
                    emitStatement(s.children[$-1], context) ~ "if (" ~ pending ~ " !is null) throw " ~ pending ~ ";\n}\n";
            } else if (s.hasFinally) result ~= "finally " ~ emitStatement(s.children[$-1], context);
            return result;
    }
}
private string emitSimple(Statement s) {
    if (s.kind == StmtKind.variable && s.nestedClass !is null) {
        auto temporary = "z8_nested_" ~ s.token.position.offset.to!string;
        auto creation = "z8_new!(" ~ s.nestedClass.emittedName ~ ")(" ~ (s.hasContainer ? "this" : "") ~ ")";
        if (!s.nestedClass.captures.length)
            return dStorageType(s.type, s.objectClass) ~ " v_" ~ s.token.text ~ " = " ~ creation;
        auto result = dStorageType(s.type, s.objectClass) ~ " v_" ~ s.token.text ~ " = (() { auto " ~ temporary ~ " = " ~ creation ~ "; ";
        foreach (capture; s.nestedClass.captures)
            result ~= temporary ~ ".z8_capture_" ~ capture.name ~ " = v_" ~ capture.name ~ "; ";
        return result ~ "return " ~ temporary ~ "; })()";
    }
    if (s.kind == StmtKind.variable && s.userOperatorAssignment) {
        auto temporary = "z8_initial_" ~ s.token.position.offset.to!string;
        return dStorageType(s.type, s.objectClass) ~ " v_" ~ s.token.text ~ " = (() { auto " ~ temporary ~ " = " ~
            defaultValue(s.type, s.objectClass, s.hasContainer) ~ "; z8_nonnull(" ~ temporary ~ ").z8op_assign(" ~
            emitExpr(s.expression) ~ "); return " ~ temporary ~ "; })()";
    }
    if (s.kind == StmtKind.variable)
        return dStorageType(s.type, s.objectClass) ~ " v_" ~ s.token.text ~ " = " ~
            (s.expression !is null ? emitExpr(s.expression) : s.type == ValueType.intType ? "z8_optional_wrap(0L)" : s.type == ValueType.boolType ? "z8_optional_wrap(false)" : s.type == ValueType.decimalType ? "z8_optional_wrap(z8_decimal_from_int(0))" : defaultValue(s.type, s.objectClass, s.hasContainer));
    if (s.kind == StmtKind.expressionStmt) return emitExpr(s.expression);
    assert(s.kind == StmtKind.assignment);
    if (s.userOperatorAssignment)
        return emitReceiver(s.target) ~ ".z8op_assign(" ~ emitExpr(s.expression) ~ ")";
    if (s.userCompoundAssignment)
        return "z8_object_assign(" ~ emitExpr(s.target) ~ ", " ~ emitExpr(s.expression) ~ ")";
    if (s.filePathAssignment) return "z8_file_assign(" ~ emitExpr(s.target) ~ ", " ~ emitExpr(s.expression) ~ ")";
    if (s.dateTickAssignment) return "z8_date_assign(" ~ emitExpr(s.target) ~ ", " ~ emitExpr(s.expression) ~ ")";
    if (s.target.kind == ExprKind.index && isMap(s.target.inferredType))
        return "z8_invoke!\"z8_add\"(" ~ emitExpr(s.target.left) ~ ", " ~ emitExpr(s.target.right) ~ ", " ~ emitExpr(s.expression) ~ ")";
    auto name = emitExpr(s.target);
    // The original BL backend evaluates a compound target again to read its
    // old value before evaluating the right operand. Indexed assignment is a
    // z8-d extension: the original Java backend cannot compile that form.
    auto oldValue = s.target.kind == ExprKind.index ? "" : name ~ ", ";
    if (isMap(s.type) && s.assignmentOperator == "+=")
        return "z8_map_add_assign(" ~ name ~ ", " ~ oldValue ~ emitExpr(s.expression) ~ ")";
    if (isArray(s.type) && s.assignmentOperator == "+=")
        return "z8_array_add_assign(" ~ name ~ ", " ~ oldValue ~ emitExpr(s.expression) ~ ")";
    if (s.type == ValueType.intType && s.assignmentOperator != "=")
        return "z8_optional_int_assign!\"" ~ s.assignmentOperator[0 .. $-1] ~ "\"(" ~ name ~ ", " ~ oldValue ~ emitExpr(s.expression) ~ ")";
    if (s.type == ValueType.decimalType && s.assignmentOperator != "=")
        return "z8_optional_decimal_assign!\"" ~ s.assignmentOperator[0 .. $-1] ~ "\"(" ~ name ~ ", " ~ oldValue ~ emitExpr(s.expression) ~ ")";
    if (s.type == ValueType.stringType && s.assignmentOperator == "+=")
        return "z8_string_add_assign(" ~ name ~ ", " ~ oldValue ~ emitExpr(s.expression) ~ ")";
    return name ~ " " ~ s.assignmentOperator ~ " " ~ emitExpr(s.expression);
}
private string defaultValue(ValueType type, Program objectClass = null, bool hasContainer = false) {
    if (type == ValueType.exceptionType) return "new Z8Exception(null)";
    if (type == ValueType.encodingType) return "null";
    if (type == ValueType.sqlBoolType) return "z8_sql_bool_const(false)";
    if (type == ValueType.sqlIntType) return "z8_sql_int_const(0L)";
    if (type == ValueType.sqlDecimalType) return "z8_sql_decimal_const(z8_decimal_from_int(0))";
    if (type == ValueType.sqlStringType) return "z8_sql_string_const(z8_string_new(\"\"w))";
    if (type == ValueType.sqlGuidType) return "z8_sql_guid_const(z8_guid_zero())";
    if (type == ValueType.sqlDateType) return "z8_sql_date_const(z8_date_now())";
    if (type == ValueType.sqlDatespanType) return "z8_sql_datespan_const(new Z8Datespan())";
    if (type == ValueType.sqlBinaryType) return "new Z8SqlBinary()";
    if (type == ValueType.sqlGeometryType) return "z8_sql_geometry_const(new Z8Geometry())";
    if (type == ValueType.sqlPrimaryType) return "new Z8SqlPrimary()";
    if (type == ValueType.ftsType) return "new Z8Fts()";
    if (type == ValueType.ftsQueryType) return "null";
    if (type == ValueType.enumType) return "null";
    if (type == ValueType.primaryType) return "null";
    if (type == ValueType.guidType) return "z8_guid_zero()";
    if (type == ValueType.binaryType) return "new Z8Binary()";
    if (type == ValueType.datespanType) return "new Z8Datespan()";
    if (type == ValueType.dateType) return "z8_date_now()";
    if (type == ValueType.geometryType) return "new Z8Geometry()";
    if (type == ValueType.fileType) return "new Z8File()";
    if (type == ValueType.decimalType) return "z8_decimal_from_int(0)";
    if (type == ValueType.selfType) return "z8_new!(" ~ dType(type, objectClass) ~ ")(" ~ (hasContainer ? "this" : "") ~ ")";
    if (isMap(type)) return "new " ~ dType(type) ~ "()";
    if (isArray(type)) return "new " ~ dType(type, objectClass) ~ "()";
    if (type == ValueType.intType) return "0";
    if (type == ValueType.stringType) return `z8_string_new(""w)`;
    assert(type == ValueType.boolType); return "false";
}
private string qualifiedFieldName(Expression expression) {
    if (expression is null) return "";
    if (expression.kind == ExprKind.variable) return expression.token.text;
    if (expression.kind != ExprKind.field) return "";
    auto left = qualifiedFieldName(expression.left);
    return left.length ? left ~ "." ~ expression.token.text : "";
}
private bool referencesField(Expression expression, string name) {
    if (expression is null) return false;
    auto path = qualifiedFieldName(expression);
    if (path.length) return path.startsWith(name);
    if (referencesField(expression.left, name) || referencesField(expression.right, name) || referencesField(expression.third, name)) return true;
    foreach (argument; expression.arguments) if (referencesField(argument, name)) return true;
    return false;
}
private struct ReferenceInitialization {
    string name;
    Expression value;
    Field field;
    Statement member;
}
private ReferenceInitialization[] orderedReferences(Program program) {
    ReferenceInitialization[] references;
    void collect(Program current) {
        if (current.baseClass !is null) collect(current.baseClass);
        ReferenceInitialization[] own;
        foreach (field; current.fields)
            if (!field.isStatic && field.type == ValueType.selfType && field.initializer !is null)
                own ~= ReferenceInitialization(field.name.text, field.initializer, field, null);
        foreach (init; current.memberInitializers)
            if (init.expression !is null && init.type == ValueType.selfType)
                own ~= ReferenceInitialization(qualifiedFieldName(init.target), init.expression, null, init);
        foreach (initializer; own) {
            auto value = initializer.value;
            if (value.kind != ExprKind.variable && value.kind != ExprKind.field && value.kind != ExprKind.newSelf && value.kind != ExprKind.containerRef) continue;
            ReferenceInitialization[] retained;
            foreach (previous; references)
                if (previous.name != initializer.name && !previous.name.startsWith(initializer.name ~ ".")) retained ~= previous;
            references = retained;
        }
        references ~= own;
    }
    collect(program);
    sort!((a, b) => a.name < b.name)(references);
    bool[] checked = new bool[references.length];
    for (size_t index = 0; index < references.length; ++index) {
        if (checked[index]) continue;
        auto right = references[index].value;
        for (size_t i = index + 1; i < references.length; ++i) {
            if (!referencesField(right, references[i].name)) continue;
            auto dependency = references[i];
            auto wasChecked = checked[i];
            for (size_t j = i; j > index; --j) { references[j] = references[j - 1]; checked[j] = checked[j - 1]; }
            references[index] = dependency; checked[index] = wasChecked; ++index;
        }
        checked[index] = true;
    }
    return references;
}

package string emitPrograms(Program[] programs) {
    string result = "// Generated by z8-d.\nimport std.conv : to;\nimport z8.runtime;\n\n";
    foreach (program; programs) {
        if (program.isEnum) {
            result ~= "class " ~ program.emittedName ~ " {\n";
            foreach (value; program.enumValues) result ~= "__gshared " ~ program.emittedName ~ " e_" ~ value.text ~ ";\n";
            if (program.enumValues.length) {
                result ~= "shared static this() {\n";
                foreach (value; program.enumValues) result ~= "e_" ~ value.text ~ " = new " ~ program.emittedName ~ "();\n";
                result ~= "}\n";
            }
            result ~= "}\n";
            continue;
        }
        result ~= "class " ~ program.emittedName ~ " : " ~ (program.baseClass is null ? "Z8Object" : program.baseClass.emittedName) ~ " {\n";
        result ~= "alias Z8Self = " ~ program.emittedName ~ ";\n";
        result ~= "override void z8_ensure_type_initialized() { Z8Self.z8_ensure_static(); }\n";
        if (program.attributes.length) {
            result ~= "override void z8_init_type_attributes() {\nsuper.z8_init_type_attributes();\n";
            foreach (attribute; program.attributes)
                result ~= "this.z8_set_attribute(" ~ emitWStringLiteral(attribute.name.text.to!wstring) ~ ", " ~
                    emitAttributeValue(attribute) ~ ");\n";
            result ~= "}\n";
        }
        foreach (capture; program.captures)
            result ~= dStorageType(capture.type, capture.objectClass) ~ " z8_capture_" ~ capture.name ~ ";\n";
        foreach (field; program.fields) {
            auto storageType = dStorageType(field.type, field.objectClass);
            if (field.isStatic) {
                result ~= "private __gshared " ~ storageType ~ " z8_static_storage_" ~ field.name.text ~ ";\n";
                result ~= "static @property ref " ~ storageType ~ " f_" ~ field.name.text ~ "() { z8_ensure_static(); return z8_static_storage_" ~ field.name.text ~ "; }\n";
            } else result ~= storageType ~ " f_" ~ field.name.text ~ ";\n";
        }
        result ~= "override void z8_allocate_fields() {\nsuper.z8_allocate_fields();\n";
        foreach (field; program.fields) if (!field.isStatic && (field.initializer is null || field.userOperatorAssignment)) {
            auto initial = field.nestedClass !is null ? "z8_new!(" ~ field.nestedClass.emittedName ~ ")(this)" :
                field.type == ValueType.intType ? "z8_optional_wrap(0L)" :
                field.type == ValueType.boolType ? "z8_optional_wrap(false)" :
                field.type == ValueType.decimalType ? "z8_optional_wrap(z8_decimal_from_int(0))" : defaultValue(field.type, field.objectClass, true);
            result ~= "this.f_" ~ field.name.text ~ " = " ~ initial ~ ";\n";
        }
        foreach (specialization; program.memberSpecializations)
            result ~= "this.f_" ~ specialization.specializedName.text ~ " = z8_new!(" ~ specialization.emittedName ~ ")(this);\n";
        result ~= "}\noverride void z8_init_references() {\n";
        foreach (reference; orderedReferences(program)) {
            if (reference.member !is null) result ~= emitSimple(reference.member) ~ ";\n";
            else if (reference.field.userOperatorAssignment)
                result ~= "z8_nonnull(this.f_" ~ reference.field.name.text ~ ", -1).z8op_assign(" ~ emitExpr(reference.value) ~ ");\n";
            else result ~= "this.f_" ~ reference.field.name.text ~ " = " ~ emitExpr(reference.value) ~ ";\n";
        }
        result ~= "}\n";
        string autoInitializers;
        foreach (field; program.fields) if (!field.isStatic && field.type == ValueType.selfType) {
            for (auto owner = program; owner !is null; owner = owner.baseClass) {
                foreach (array; owner.fields) if (array.isAuto) {
                    for (auto fieldClass = field.objectClass; fieldClass !is null; fieldClass = fieldClass.baseClass) {
                        if (fieldClass is array.objectClass) {
                            autoInitializers ~= "z8_nonnull(this.f_" ~ array.name.text ~ ").z8_add(this.f_" ~ field.name.text ~ ");\n";
                            break;
                        }
                    }
                }
            }
        }
        if (autoInitializers.length)
            result ~= "override void z8_init_members() {\nsuper.z8_init_members();\n" ~ autoInitializers ~ "}\n";
        result ~= "override void z8_init_values() {\nsuper.z8_init_values();\n";
        // TypeBody.rearrangeMembers puts declarations before standalone member initializers.
        foreach (field; program.fields) {
            if (field.isStatic) continue;
            if (field.type == ValueType.selfType)
                result ~= "if (this.f_" ~ field.name.text ~ " is null) throw new Exception(\"null object field initializer\");\n";
            else if (field.initializer !is null)
                result ~= "this.f_" ~ field.name.text ~ " = " ~ emitExpr(field.initializer) ~ ";\n";
            foreach (attribute; field.attributes)
                result ~= "this.f_" ~ field.name.text ~ ".z8_set_attribute(" ~ emitWStringLiteral(attribute.name.text.to!wstring) ~ ", " ~
                    emitAttributeValue(attribute) ~ ");\n";
        }
        foreach (init; program.memberInitializers) {
            if (init.expression !is null && init.type != ValueType.selfType) result ~= emitSimple(init) ~ ";\n";
            foreach (attribute; init.attributes)
                result ~= emitExpr(init.attributeTarget) ~ ".z8_set_attribute(" ~ emitWStringLiteral(attribute.name.text.to!wstring) ~ ", " ~
                    emitAttributeValue(attribute) ~ ");\n";
        }
        result ~= "}\n";
        foreach (method; program.methods) if (method.name.text == "constructor") {
            result ~= "override void z8_call_constructor() { this.m_constructor(); }\n";
            break;
        }
        result ~= "private __gshared int z8_static_state;\nprivate __gshared Throwable z8_static_failure;\nprivate __gshared Object z8_static_monitor;\n";
        result ~= "static void z8_ensure_static() {\nsynchronized (z8_static_class_lock(z8_static_monitor)) {\n";
        result ~= "if (z8_static_state == 2 || z8_static_state == 1) return;\n";
        result ~= "if (z8_static_state == 3) throw z8_static_failure;\n";
        result ~= "z8_static_state = 1;\ntry {\n";
        if (program.baseClass !is null) result ~= program.baseClass.emittedName ~ ".z8_ensure_static();\n";
        // Z8 first allocates default values for all static declarations, then
        // executes explicit initializers in declaration order.
        foreach (field; program.fields) if (field.isStatic && field.initializer is null)
            result ~= "z8_static_storage_" ~ field.name.text ~ " = " ~ (field.type == ValueType.intType ? "z8_optional_wrap(0L)" : field.type == ValueType.boolType ? "z8_optional_wrap(false)" : field.type == ValueType.decimalType ? "z8_optional_wrap(z8_decimal_from_int(0))" : defaultValue(field.type, field.objectClass)) ~ ";\n";
        foreach (field; program.fields) if (field.isStatic && field.initializer !is null)
            result ~= "z8_static_storage_" ~ field.name.text ~ " = " ~ emitExpr(field.initializer) ~ ";\n";
        result ~= "z8_static_state = 2;\n} catch (Throwable failure) { z8_static_failure = failure; z8_static_state = 3; throw failure; }\n}\n}\n";
        foreach (m; program.methods) {
            if (program.baseClass !is null) {
                bool hasInheritedName;
                for (auto base = program.baseClass; base !is null; base = base.baseClass)
                    foreach (candidate; base.methods) if (candidate.name.text == m.name.text && !candidate.isStatic) {
                        hasInheritedName = true;
                    }
                bool firstName = true;
                foreach (earlier; program.methods) { if (earlier is m) break; if (earlier.name.text == m.name.text) firstName = false; }
                if (firstName && hasInheritedName)
                    result ~= "alias " ~ methodDName(m) ~ " = " ~ program.baseClass.emittedName ~ "." ~ methodDName(m) ~ ";\n";
            }
            string[] params;
            foreach (p; m.parameters) params ~= dStorageType(p.type, p.objectClass) ~ " v_" ~ p.name.text;
            bool hasIntParameter;
            foreach (p; m.parameters) if (p.type == ValueType.intType || p.type == ValueType.boolType || p.type == ValueType.decimalType) hasIntParameter = true;
            if (hasIntParameter && !m.overrides) {
                string[] nativeParams, nativeArgs;
                foreach (p; m.parameters) {
                    nativeParams ~= dType(p.type, p.objectClass) ~ " v_" ~ p.name.text;
                    nativeArgs ~= (p.type == ValueType.intType || p.type == ValueType.boolType || p.type == ValueType.decimalType) ? "z8_optional_wrap(v_" ~ p.name.text ~ ")" : "v_" ~ p.name.text;
                }
                result ~= (m.isStatic ? "static " : "final ") ~ dStorageType(m.returnType, m.returnObjectClass) ~ " " ~ methodDName(m) ~ "(" ~ nativeParams.join(", ") ~ ") { " ~
                    (m.returnType == ValueType.voidType ? "" : "return ") ~ methodDName(m) ~ "(" ~ nativeArgs.join(", ") ~ "); }\n";
            }
            auto modifiers = m.isStatic ? "static " : m.overrides ? "override " : m.isVirtual ? "" : "final ";
            ControlContext context;
            context.enabled = needsControlLowering(m.body);
            context.returnType = m.returnType;
            context.returnClass = m.returnObjectClass;
            auto body = emitStatement(m.body, context);
            if (context.enabled) {
                auto returnSignal = m.returnType == ValueType.voidType ? "Z8ReturnVoid" : "Z8Return!(" ~ dStorageType(m.returnType, m.returnObjectClass) ~ ")";
                body = "{\ntry " ~ body ~ "catch (" ~ returnSignal ~ " z8_return) { " ~
                    (m.returnType == ValueType.voidType ? "return;" : "return z8_return.value;") ~ " }\n" ~
                    (m.returnType == ValueType.voidType ? "" : "assert(0, \"unreachable BL method exit\");\n") ~ "}\n";
            }
            if (m.isStatic) body = "{\nz8_ensure_static();\n" ~ body[1 .. $];
            result ~= modifiers ~ dStorageType(m.returnType, m.returnObjectClass) ~ " " ~ methodDName(m) ~ "(" ~ params.join(", ") ~ ")\n" ~ body;
        }
        result ~= "}\n";
    }
    return formatDSource(result);
}

/// Escape path segments without colliding with D keywords or escaped names.
package string moduleNameFor(string qualifiedName) {
    string[] parts = ["z8gen"];
    foreach (part; qualifiedName.split(".")) {
        string encoded = "p_";
        foreach (ubyte c; part) {
            if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9'))
                encoded ~= cast(char)c;
            else encoded ~= format("_%02X", c);
        }
        parts ~= encoded;
    }
    return parts.join(".");
}

/// Produce one module per Z8 type, importing only referenced generated types.
package GeneratedModule[] emitProjectModules(Program[] programs) {
    string[string] moduleByClass;
    Program rootOf(Program program) {
        while (program.lexicalOwner !is null) program = program.lexicalOwner;
        return program;
    }
    Program[][string] groupsByModule;
    foreach (program; programs) {
        auto name = moduleNameFor(rootOf(program).qualifiedName);
        moduleByClass[program.emittedName] = name;
        groupsByModule[name] ~= program;
    }
    auto symbolPattern = regex(`Z8p_[0-9A-F]+`);
    GeneratedModule[] modules;
    foreach (program; programs) {
        if (program.lexicalOwner !is null) continue;
        auto body = emitPrograms(groupsByModule[moduleByClass[program.emittedName]]);
        string[] dependencies;
        bool[string] seen;
        foreach (match; matchAll(body, symbolPattern)) {
            auto symbol = match.hit;
            auto dependency = symbol in moduleByClass;
            if (dependency !is null && *dependency != moduleByClass[program.emittedName] && !(*dependency in seen)) {
                seen[*dependency] = true;
                dependencies ~= *dependency;
            }
        }
        sort(dependencies);
        auto name = moduleByClass[program.emittedName];
        string source = "module " ~ name ~ ";\n\n";
        foreach (dependency; dependencies) source ~= "import " ~ dependency ~ ";\n";
        if (dependencies.length) source ~= "\n";
        source ~= body;
        modules ~= GeneratedModule(name, name.replace(".", "/") ~ ".d", program.sourceName, source);
    }
    return modules;
}
