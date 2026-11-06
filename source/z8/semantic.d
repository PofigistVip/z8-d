module z8.semantic;

import std.algorithm : canFind, sort;
import std.conv : to;
import std.string : lastIndexOf, indexOf, icmp;
import z8.compiler_model;
import z8.lexer : Token, TokenKind;

/// Checks the entire program before emitting code; unsupported constructs fail closed.
class Checker {
    private Method[string] methods;
    private Field[string] fields;
    private Program[string] visibleClasses;
    private Program[string] allClasses;
    private Program currentProgram;
    private bool staticContext, fieldInitialization;
    private bool importedMath;
    private ValueType[string] variables;
    private Program[string] objectVariables;
    private Program[][string] keyObjectVariables;
    private ValueType returnType;
    private Program returnObjectClass;
    private Program[] returnKeyObjectClasses;
    private size_t loopDepth;
    private ValueType[Expression] expressionSpineTypeCache;
    private void fail(string message, Token t) { throw new CompileException(message, t.position); }
    void bindBase(Program program, Program[string] programs) {
        currentProgram = program; allClasses = programs;
        if (program.isFieldSpecialization) {
            auto owner = program.lexicalOwner;
            auto field = lookupField(owner, program.specializedName.text);
            if (field is null || field.isStatic) fail("field specialization requires an instance field", program.specializedName);
            currentProgram = owner;
            if (!accessible(field.owner, field.isPublic, field.isProtected)) fail("field is not accessible", program.specializedName);
            if (field.type != ValueType.selfType) fail("field specialization requires an object field", program.specializedName);
            if (field.owner is owner && field.nestedClass !is null) fail("duplicate field specialization", program.specializedName);
            program.specializedField = field;
            for (auto base = owner.baseClass; base !is null && program.baseClass is null; base = base.baseClass) {
                foreach (candidate; base.memberSpecializations)
                    if (candidate.specializedName.text == program.specializedName.text) { program.baseClass = candidate; break; }
                if (program.baseClass is null)
                    foreach (candidate; base.fields)
                        if (candidate.name.text == program.specializedName.text && candidate.nestedClass !is null) {
                            program.baseClass = candidate.nestedClass; break;
                        }
            }
            if (program.baseClass is null) program.baseClass = resolveClass(field.owner, field.objectName, field.name);
        } else if (program.baseName == "primary" || program.baseName == "org.zenframework.z8.lang.primary") {
            program.baseIsPrimary = true;
        } else if (program.baseName == "exception" || program.baseName == "org.zenframework.z8.lang.exception") {
            program.baseIsException = true;
        } else if (program.baseName.length) program.baseClass = resolveClass(program, program.baseName, program.baseToken);
        if (program.baseClass !is null) {
            if (program.baseClass.isEnum) fail("cannot extend an enum", program.baseToken);
            if (program.baseClass.isFinal) fail("cannot extend a final class", program.baseToken);
        }
    }
    private static Method lookupMethod(Program owner, string name) {
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (candidate; current.methods) if (candidate.name.text == name) return candidate;
        return null;
    }
    private static Method lookupUnaryOperator(Program owner, string name) {
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (method; current.methods)
                if (method.name.text == name && !method.parameters.length) return method;
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
    private static int inheritanceDistance(Program actual, Program expected) {
        int distance;
        for (auto current = actual; current !is null; current = current.baseClass, ++distance)
            if (current is expected) return distance;
        return int.max;
    }
    private static bool hasStringConversion(ValueType type) {
        return [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.guidType,
                ValueType.datespanType, ValueType.dateType, ValueType.geometryType, ValueType.fileType,
                ValueType.exceptionType].canFind(type);
    }
    private bool isLexicallyBound(string name) {
        if (name in variables || name in fields) return true;
        foreach (capture; currentProgram.captures) if (capture.name == name) return true;
        return false;
    }
    private bool accessible(Program owner, bool isPublic, bool isProtected) {
        if (isPublic) return true;
        for (auto context = currentProgram; context !is null; context = context.lexicalOwner)
            if (owner is context || (isProtected && isAssignable(context, owner))) return true;
        return false;
    }
    private Program resolveClass(Program owner, string name, Token site) {
        if (name.indexOf('.') >= 0) {
            auto qualified = name in allClasses;
            if (qualified is null) fail("unknown class '" ~ name ~ "'", site);
            return *qualified;
        }
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
    private ValueType resolveDeclaredType(ValueType type, Program owner, string objectName, string[] keyObjectNames, Token site) {
        if (isDynamicArray(type))
            return arrayOf(resolveDeclaredType(elementType(type), owner, objectName, keyObjectNames, site));
        if (isMap(type)) {
            auto value = resolveDeclaredType(mapValueType(type), owner, objectName, innerMapKeyClasses(type, keyObjectNames), site);
            auto key = mapKeyType(type);
            if (key == ValueType.selfType && resolveClass(owner, outerMapKeyClass(type, keyObjectNames), site).isEnum) key = ValueType.enumType;
            return mapType(value, key);
        }
        if (type != ValueType.selfType && type != ValueType.selfArray && type != ValueType.selfMatrix) return type;
        auto target = resolveClass(owner, objectName, site);
        if (!target.isEnum) return type;
        return type == ValueType.selfMatrix ? ValueType.enumMatrix : type == ValueType.selfArray ? ValueType.enumArray : ValueType.enumType;
    }
    private Program[] resolveKeyClasses(Program owner, string[] names, Token site) {
        Program[] result;
        foreach (name; names) result ~= resolveClass(owner, name, site);
        return result;
    }
    private bool containsReferenceClass(ValueType type, Program valueClass, Program[] keyClasses) {
        if (isArray(type)) return containsReferenceClass(elementType(type), valueClass, keyClasses);
        if (isMap(type)) {
            if (mapKeyType(type) == ValueType.selfType && !isPrimaryClass(outerMapKeyClass(type, keyClasses))) return true;
            return containsReferenceClass(mapValueType(type), valueClass, innerMapKeyClasses(type, keyClasses));
        }
        return type == ValueType.selfType && !isPrimaryClass(valueClass);
    }
    private void checkAttributeNameConflicts(Program program, Program[string] programs) {
        Program sourceRoot(Program owner) {
            while (owner.lexicalOwner !is null) owner = owner.lexicalOwner;
            return owner;
        }
        bool sameName(TypeAttribute attribute, TypeAttribute[] others) {
            foreach (other; others)
                if (other.name.text == "name" && attributeLiteralValue(attribute) == attributeLiteralValue(other)) return true;
            return false;
        }
        foreach (attribute; program.attributes) if (attribute.name.text == "name" && attribute.hasValue) {
            foreach (candidate; programs)
                // Original Z8 checks types reconciled before the current unit.
                // A bare [name] performs no check of its own.
                if (candidate.lexicalOwner is null && candidate.sourceIndex < sourceRoot(program).sourceIndex && sameName(attribute, candidate.attributes))
                    fail("name attribute conflicts with another type", attribute.name);
        }
        void checkMember(TypeAttribute[] attributes, Field selfField, Statement selfInit) {
            foreach (attribute; attributes) if (attribute.name.text == "name" && attribute.hasValue) {
                for (auto owner = program; owner !is null; owner = owner.baseClass) {
                    foreach (field; owner.fields)
                        if (field !is selfField && sameName(attribute, field.attributes))
                            fail("name attribute conflicts with another member", attribute.name);
                    foreach (init; owner.memberInitializers)
                        if (init !is selfInit && sameName(attribute, init.attributes))
                            fail("name attribute conflicts with another member", attribute.name);
                }
            }
        }
        foreach (field; program.fields) checkMember(field.attributes, field, null);
        foreach (init; program.memberInitializers) checkMember(init.attributes, null, init);
        foreach (method; program.methods) checkMember(method.attributes, null, null);
    }
    void prepareDeclarations(Program program, Program[string] programs) {
        currentProgram = program; allClasses = programs;
        checkAttributeNameConflicts(program, programs);
        foreach (field; program.fields) {
            field.type = resolveDeclaredType(field.type, program, field.objectName, field.keyObjectNames, field.name);
            if (field.attributes.length && (field.type != ValueType.selfType ||
                isPrimaryClass(resolveClass(program, field.objectName, field.name))))
                fail("attributes require an object reference field", field.name);
            if (field.isAuto && (field.isStatic || field.type != ValueType.selfArray))
                fail("auto requires an instance array of object references", field.name);
            if (field.isStatic && containsUserReference(field.type)) {
                auto valueClass = hasObjectClass(field.type) ? resolveClass(program, field.objectName, field.name) : null;
                auto keyClasses = hasMapKeyClass(field.type) ? resolveKeyClasses(program, field.keyObjectNames, field.name) : null;
                if (containsReferenceClass(field.type, valueClass, keyClasses))
                    fail("static reference fields are not allowed", field.name);
            }
        }
        foreach (method; program.methods) {
            method.returnType = resolveDeclaredType(method.returnType, program, method.returnObjectName, method.returnKeyObjectNames, method.name);
            if (method.isCastOperator && [ValueType.selfType, ValueType.enumType].canFind(method.returnType)) {
                method.returnObjectClass = resolveClass(program, method.returnObjectName, method.name);
                method.name.text = "operatorCast:" ~ method.returnObjectClass.qualifiedName;
            }
            foreach (ref parameter; method.parameters)
                parameter.type = resolveDeclaredType(parameter.type, program, parameter.objectName, parameter.keyObjectNames, parameter.name);
        }
    }
    private Method findConversion(Program owner, ValueType target, Program targetClass = null) {
        Method best;
        size_t bestDistance = size_t.max;
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (method; current.methods) {
                if (!method.isCastOperator || method.returnType != target ||
                    !accessible(method.owner, method.isPublic, method.isProtected)) continue;
                if (target == ValueType.enumType) {
                    if (targetClass !is null && method.returnObjectClass is targetClass) return method;
                    continue;
                }
                if (target != ValueType.selfType) return method;
                if (targetClass is null) continue;
                size_t distance;
                for (auto result = method.returnObjectClass; result !is null; result = result.baseClass, ++distance) {
                    if (result !is targetClass) continue;
                    if (distance < bestDistance) { best = method; bestDistance = distance; }
                    break;
                }
            }
        return best;
    }
    // A conversion result may itself derive from primary (for example,
    // JsonArray.operator string() when passed to a primary parameter).
    private Method findPrimaryConversion(Program owner) {
        auto direct = findConversion(owner, ValueType.primaryType);
        if (direct !is null) return direct;
        Method best;
        size_t bestDistance = size_t.max;
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (method; current.methods) {
                if (!method.isCastOperator || !accessible(method.owner, method.isPublic, method.isProtected)) continue;
                size_t distance = size_t.max;
                if ([ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType,
                     ValueType.guidType, ValueType.binaryType, ValueType.datespanType, ValueType.geometryType,
                     ValueType.dateType, ValueType.fileType].canFind(method.returnType)) distance = 1;
                else if (method.returnType == ValueType.selfType) {
                    size_t depth;
                    for (auto result = method.returnObjectClass; result !is null; result = result.baseClass) {
                        ++depth;
                        if (result.baseIsPrimary) { distance = depth; break; }
                    }
                }
                if (distance < bestDistance) { best = method; bestDistance = distance; }
            }
        return best;
    }
    private int sqlIifConversionCost(Expression argument, ValueType actual, ValueType target) {
        if (actual == ValueType.nullType || actual == target) return 0;
        if (actual == ValueType.selfType && findConversion(argument.objectClass, target) !is null) return 100;
        if (target == ValueType.sqlBoolType && [ValueType.boolType, ValueType.optionalBool].canFind(actual)) return 100;
        if (target == ValueType.sqlIntType && [ValueType.intType, ValueType.optionalInt].canFind(actual)) return 100;
        if (target == ValueType.sqlDecimalType && [ValueType.decimalType, ValueType.optionalDecimal, ValueType.sqlIntType].canFind(actual)) return 100;
        if (target == ValueType.sqlStringType && [ValueType.stringType, ValueType.nullableString].canFind(actual)) return 100;
        if (target == ValueType.sqlGuidType && actual == ValueType.guidType) return 100;
        if (target == ValueType.sqlDateType && actual == ValueType.dateType) return 100;
        if (target == ValueType.sqlDatespanType && actual == ValueType.datespanType) return 100;
        if (target == ValueType.sqlGeometryType && actual == ValueType.geometryType) return 100;
        return -1;
    }
    // VariableType.getCastTo checks the value and each key independently.
    private bool covariantCollectionMatches(ValueType type, Program actualClass, Program[] actualKeys,
                                            Program expectedClass, Program[] expectedKeys) {
        if (isArray(type))
            return covariantCollectionMatches(elementType(type), actualClass, actualKeys, expectedClass, expectedKeys);
        if (isMap(type)) {
            auto key = mapKeyType(type);
            if (key == ValueType.selfType) {
                if (!isAssignable(outerMapKeyClass(type, actualKeys), outerMapKeyClass(type, expectedKeys))) return false;
            } else if (key == ValueType.enumType && outerMapKeyClass(type, actualKeys) !is outerMapKeyClass(type, expectedKeys)) return false;
            return covariantCollectionMatches(mapValueType(type), actualClass, innerMapKeyClasses(type, actualKeys),
                                              expectedClass, innerMapKeyClasses(type, expectedKeys));
        }
        if (actualKeys.length || expectedKeys.length) return false;
        if (type == ValueType.selfType) return isAssignable(actualClass, expectedClass);
        if (type == ValueType.enumType) return actualClass is expectedClass;
        return true;
    }
    private bool matches(Expression e, ValueType expected, Program expectedClass = null, Program[] expectedKeyClasses = null) {
        if (e.kind == ExprKind.arrayLiteral && hasObjectClass(expected)) e.objectClass = expectedClass;
        if (e.kind == ExprKind.arrayLiteral && hasMapKeyClass(expected)) e.keyObjectClasses = expectedKeyClasses;
        auto actual = typeOf(e, expected);
        if (expected == ValueType.primaryArray && [ValueType.stringArray, ValueType.guidArray, ValueType.intArray, ValueType.boolArray, ValueType.decimalArray, ValueType.fileArray].canFind(actual)) {
            e.convertScalarPrimaryArray = true;
            return true;
        }
        if (expected == ValueType.sqlBoolType && (actual == ValueType.boolType || actual == ValueType.optionalBool)) {
            e.convertToSqlBool = true;
            return true;
        }
        if (expected == ValueType.sqlIntType && (actual == ValueType.intType || actual == ValueType.optionalInt)) {
            e.convertToSqlInt = true;
            return true;
        }
        if (expected == ValueType.sqlDecimalType && (actual == ValueType.decimalType || actual == ValueType.optionalDecimal)) {
            e.convertToSqlDecimal = true;
            return true;
        }
        if (expected == ValueType.sqlDecimalType && actual == ValueType.sqlIntType) {
            e.convertSqlIntToDecimal = true;
            return true;
        }
        if (expected == ValueType.sqlStringType && [ValueType.stringType, ValueType.nullableString].canFind(actual)) {
            e.convertToSqlString = true;
            return true;
        }
        if (expected == ValueType.sqlGuidType && actual == ValueType.guidType) {
            e.convertToSqlGuid = true;
            return true;
        }
        if (expected == ValueType.sqlDateType && actual == ValueType.dateType) {
            e.convertToSqlDate = true;
            return true;
        }
        if (expected == ValueType.sqlDatespanType && actual == ValueType.datespanType) {
            e.convertToSqlDatespan = true;
            return true;
        }
        if (expected == ValueType.sqlGeometryType && actual == ValueType.geometryType) {
            e.convertToSqlGeometry = true;
            return true;
        }
        if (expected == ValueType.sqlPrimaryType && isSqlType(actual)) return true;
        if ((isArray(expected) || isMap(expected)) && actual == expected &&
            covariantCollectionMatches(expected, e.objectClass, e.keyObjectClasses, expectedClass, expectedKeyClasses)) {
            if (e.objectClass !is expectedClass || e.keyObjectClasses != expectedKeyClasses) {
                e.collectionConversionType = expected;
                e.collectionConversionClass = expectedClass;
                e.collectionConversionKeyClasses = expectedKeyClasses;
            } else e.collectionConversionType = ValueType.voidType;
            return true;
        }

        if (expected == ValueType.primaryType && actual == ValueType.selfType && extendsBuiltinPrimary(e.objectClass)) {
            e.boxPrimary = true;
            return true;
        }

        if (actual == ValueType.selfType) {
            if (expected == ValueType.selfType && isAssignable(e.objectClass, expectedClass)) return true;
            if (expected == ValueType.exceptionType && extendsBuiltinException(e.objectClass)) {
                e.convertExceptionObject = true;
                return true;
            }
            auto conversion = expected == ValueType.primaryType ? findPrimaryConversion(e.objectClass) : findConversion(e.objectClass, expected, expectedClass);
            if (conversion !is null) {
                e.userConversion = conversion;
                if (expected == ValueType.primaryType && conversion.returnType != ValueType.primaryType) e.boxPrimary = true;
                if ([ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(expected)) e.optionalRequired = true;
                return true;
            }
        }
        if (expected == ValueType.primaryType && [ValueType.intType, ValueType.boolType, ValueType.decimalType,
            ValueType.optionalInt, ValueType.optionalBool, ValueType.optionalDecimal, ValueType.stringType, ValueType.nullableString, ValueType.guidType, ValueType.binaryType, ValueType.datespanType, ValueType.geometryType, ValueType.dateType, ValueType.fileType].canFind(actual)) {
            e.boxPrimary = true; return true;
        }
        if (isOptionalPrimitive(actual) && optionalBaseType(actual) == expected) {
            e.optionalRequired = true; return true;
        }
        if (isOptionalPrimitive(actual)) {
            auto base = optionalBaseType(actual);
            if (base == ValueType.intType && expected == ValueType.decimalType) {
                e.optionalRequired = true; e.promoteToDecimal = true; return true;
            }
            if (base == ValueType.intType && expected == ValueType.dateType) {
                e.optionalRequired = true; e.convertToDate = true; return true;
            }
            if (expected == ValueType.stringType) {
                e.optionalRequired = true; e.convertToString = base; return true;
            }
        }
        if (actual == ValueType.nullableString && expected == ValueType.stringType) {
            return true;
        }
        if (actual == ValueType.nullType && isNullableReference(expected)) {
            e.inferredType = expected; e.objectClass = expectedClass; e.keyObjectClasses = expectedKeyClasses; return true;
        }
        if (actual == ValueType.intType && expected == ValueType.decimalType) { e.promoteToDecimal = true; return true; }
        if (actual == ValueType.intType && expected == ValueType.dateType) { e.convertToDate = true; return true; }
        if (expected == ValueType.binaryType && [ValueType.stringType, ValueType.nullableString, ValueType.fileType].canFind(actual)) {
            e.convertToBinary = actual; return true;
        }
        if (expected == ValueType.fileType && [ValueType.stringType, ValueType.nullableString].canFind(actual)) { e.makeFile = true; return true; }
        if (expected == ValueType.exceptionType && [ValueType.stringType, ValueType.nullableString].canFind(actual)) { e.makeException = true; return true; }
        if (expected == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(actual)) {
            e.convertToString = actual; return true;
        }
        if (expected == ValueType.stringType && actual == ValueType.guidType) { e.convertToString = actual; return true; }
        if (expected == ValueType.stringType && actual == ValueType.datespanType) { e.convertToString = actual; return true; }
        if (expected == ValueType.stringType && actual == ValueType.fileType) { e.convertToString = actual; return true; }
        if (expected == ValueType.stringType && actual == ValueType.exceptionType) { e.convertToString = actual; return true; }
        if (expected == ValueType.stringType && [ValueType.dateType, ValueType.geometryType].canFind(actual)) { e.convertToString = actual; return true; }
        return actual == expected && (expected == ValueType.selfType ? isAssignable(e.objectClass, expectedClass) :
            !hasObjectClass(expected) || e.objectClass is expectedClass) &&
            (!hasMapKeyClass(expected) || e.keyObjectClasses == expectedKeyClasses);
    }
    private bool matchesStored(Expression e, ValueType expected, Program expectedClass = null, Program[] expectedKeyClasses = null) {
        if (expected != ValueType.intType && expected != ValueType.boolType && expected != ValueType.decimalType) return matches(e, expected, expectedClass, expectedKeyClasses);
        auto optional = storedValueType(expected);
        auto actual = typeOf(e, expected);
        if (actual == ValueType.selfType) {
            auto conversion = findConversion(e.objectClass, expected);
            if (conversion !is null) { e.userConversion = conversion; return true; }
        }
        if (actual == ValueType.nullType) { e.inferredType = optional; return true; }
        if (actual == optional) return true;
        if (actual == expected) { e.optionalWrap = true; return true; }
        if (expected == ValueType.decimalType && matches(e, expected, expectedClass)) { e.optionalWrap = true; return true; }
        return false;
    }
    private bool matchesInitializer(Expression e, ValueType expected, Program expectedClass = null, Program[] expectedKeyClasses = null) {
        if (expected == ValueType.fileType && [ValueType.stringType, ValueType.nullableString].canFind(typeOf(e))) {
            e.makeFile = true; return true;
        }
        return matchesStored(e, expected, expectedClass, expectedKeyClasses);
    }
    private ValueType checkCall(Method method, Program owner, Expression e) {
        if (e.arguments.length != method.parameters.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) {
            auto p = method.parameters[i];
            if (arg.kind == ExprKind.arrayLiteral && !arg.typedInitializer) fail("array initializer requires a known target", arg.token);
            auto objectClass = hasObjectClass(p.type) ? resolveClass(owner, p.objectName, p.name) : null;
            auto keyObjectClasses = hasMapKeyClass(p.type) ? resolveKeyClasses(owner, p.keyObjectNames, p.name) : null;
            if (!matchesStored(arg, p.type, objectClass, keyObjectClasses)) fail("argument type mismatch", arg.token);
        }
        if (hasObjectClass(method.returnType))
            e.objectClass = resolveClass(owner, method.returnObjectName, method.name);
        if (hasMapKeyClass(method.returnType)) e.keyObjectClasses = resolveKeyClasses(owner, method.returnKeyObjectNames, method.name);
        return method.returnType == ValueType.stringType ? ValueType.nullableString : storedValueType(method.returnType);
    }
    private bool sameParameters(Method left, Method right) {
        if (left.parameters.length != right.parameters.length) return false;
        foreach (i, p; left.parameters) {
            auto q = right.parameters[i];
            if (p.type != q.type) return false;
            if (hasObjectClass(p.type) && resolveClass(left.owner, p.objectName, p.name) !is resolveClass(right.owner, q.objectName, q.name)) return false;
            if (hasMapKeyClass(p.type) && resolveKeyClasses(left.owner, p.keyObjectNames, p.name) != resolveKeyClasses(right.owner, q.keyObjectNames, q.name)) return false;
        }
        return true;
    }
    // Z8 ranks direct casts ahead of conversions defined by an operator.
    private Method selectOverload(Method first, Expression e, bool allowNoMatch = false, bool binaryOperator = false,
                                  int* selectedWeight = null, int* selectedDistance = null, bool* ambiguousResult = null) {
        ValueType[] actualTypes;
        foreach (arg; e.arguments) {
            if (arg.kind == ExprKind.arrayLiteral && !arg.typedInitializer) fail("array initializer requires a known target", arg.token);
            actualTypes ~= typeOf(arg);
        }
        Method best;
        int bestWeight = int.max, bestDistance = int.max;
        bool ambiguous;
        Method[] seen;
        for (auto owner = first.owner; owner !is null; owner = owner.baseClass) foreach (candidate; owner.methods) {
            if (candidate.name.text != first.name.text) continue;
            bool hidden;
            foreach (previous; seen) if (sameParameters(previous, candidate)) { hidden = true; break; }
            if (hidden) continue;
            seen ~= candidate;
            if (candidate.parameters.length != e.arguments.length) continue;
            if (!accessible(candidate.owner, candidate.isPublic, candidate.isProtected)) continue;
            int weight, distance; bool applicable = true;
            foreach (i, p; candidate.parameters) {
                auto actual = actualTypes[i];
                if (isOptionalPrimitive(actual)) actual = optionalBaseType(actual);
                if ((actual == ValueType.nullType && (isNullableReference(p.type) || p.type == ValueType.intType || p.type == ValueType.boolType || p.type == ValueType.decimalType)) ||
                    (actual == ValueType.nullableString && p.type == ValueType.stringType)) {
                    // Null is equally applicable to each supported reference type.
                } else if (actual == p.type) {
                    if (actual == ValueType.selfType) {
                        auto parameterClass = resolveClass(candidate.owner, p.objectName, p.name);
                        auto actualClass = e.arguments[i].objectClass;
                        if (isAssignable(actualClass, parameterClass)) {
                            if (binaryOperator) distance += inheritanceDistance(actualClass, parameterClass);
                        } else {
                            auto conversion = findConversion(actualClass, p.type, parameterClass);
                            if (conversion is null) applicable = false;
                            else {
                                weight += 100;
                                if (binaryOperator) distance += inheritanceDistance(conversion.returnObjectClass, parameterClass);
                            }
                        }
                    }
                    if (isMap(actual) || isArray(actual)) {
                        auto parameterClass = hasObjectClass(actual) ? resolveClass(candidate.owner, p.objectName, p.name) : null;
                        auto parameterKeys = hasMapKeyClass(actual) ? resolveKeyClasses(candidate.owner, p.keyObjectNames, p.name) : null;
                        if (!covariantCollectionMatches(actual, e.arguments[i].objectClass, e.arguments[i].keyObjectClasses, parameterClass, parameterKeys)) applicable = false;
                    } else {
                        if (actual != ValueType.selfType && hasObjectClass(actual)) {
                            auto parameterClass = resolveClass(candidate.owner, p.objectName, p.name);
                            if (e.arguments[i].objectClass !is parameterClass) applicable = false;
                        }
                        if (hasMapKeyClass(actual) && e.arguments[i].keyObjectClasses != resolveKeyClasses(candidate.owner, p.keyObjectNames, p.name)) applicable = false;
                    }
                } else if ([ValueType.stringArray, ValueType.guidArray, ValueType.intArray, ValueType.boolArray, ValueType.decimalArray, ValueType.fileArray].canFind(actual) && p.type == ValueType.primaryArray) {
                    ++weight;
                } else if (actual == ValueType.selfType && p.type == ValueType.primaryType && extendsBuiltinPrimary(e.arguments[i].objectClass)) {
                    if (binaryOperator) ++distance;
                } else if (actual == ValueType.selfType && p.type == ValueType.primaryType && findPrimaryConversion(e.arguments[i].objectClass) !is null) weight += 100;
                else if (actual == ValueType.selfType && findConversion(e.arguments[i].objectClass, p.type,
                            p.type == ValueType.enumType ? resolveClass(candidate.owner, p.objectName, p.name) : null) !is null) weight += 100;
                else if (actual == ValueType.intType && p.type == ValueType.decimalType) weight += 100;
                else if (actual == ValueType.intType && p.type == ValueType.dateType) weight += 100;
                else if (actual == ValueType.boolType && p.type == ValueType.sqlBoolType) weight += 100;
                else if (actual == ValueType.intType && p.type == ValueType.sqlIntType) weight += 100;
                else if ((actual == ValueType.decimalType || actual == ValueType.sqlIntType) && p.type == ValueType.sqlDecimalType) weight += 100;
                else if ([ValueType.stringType, ValueType.nullableString].canFind(actual) && p.type == ValueType.sqlStringType) weight += 100;
                else if (actual == ValueType.guidType && p.type == ValueType.sqlGuidType) weight += 100;
                else if (actual == ValueType.dateType && p.type == ValueType.sqlDateType) weight += 100;
                else if (actual == ValueType.datespanType && p.type == ValueType.sqlDatespanType) weight += 100;
                else if (actual == ValueType.geometryType && p.type == ValueType.sqlGeometryType) weight += 100;
                else if (p.type == ValueType.sqlPrimaryType && isSqlType(actual)) ++weight;
                else if (p.type == ValueType.binaryType && [ValueType.stringType, ValueType.nullableString, ValueType.fileType].canFind(actual)) weight += 100;
                else if ([ValueType.fileType, ValueType.exceptionType].canFind(p.type) && [ValueType.stringType, ValueType.nullableString].canFind(actual)) weight += 100;
                else if (p.type == ValueType.exceptionType && actual == ValueType.selfType && extendsBuiltinException(e.arguments[i].objectClass)) ++weight;
                else if (p.type == ValueType.primaryType && [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType, ValueType.nullableString, ValueType.guidType, ValueType.binaryType, ValueType.datespanType, ValueType.geometryType, ValueType.dateType, ValueType.fileType].canFind(actual)) { if (binaryOperator) ++distance; }
                else if (p.type == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(actual)) weight += 100;
                else if (p.type == ValueType.stringType && actual == ValueType.guidType) weight += 100;
                else if (p.type == ValueType.stringType && actual == ValueType.datespanType) weight += 100;
                else if (p.type == ValueType.stringType && actual == ValueType.fileType) weight += 100;
                else if (p.type == ValueType.stringType && actual == ValueType.exceptionType) weight += 100;
                else if (p.type == ValueType.stringType && [ValueType.dateType, ValueType.geometryType].canFind(actual)) weight += 100;
                else applicable = false;
                if (!applicable) break;
            }
            if (!applicable) continue;
            if (weight < bestWeight || (binaryOperator && weight == bestWeight && distance < bestDistance)) {
                best = candidate; bestWeight = weight; bestDistance = distance; ambiguous = false;
            } else if (weight == bestWeight && (!binaryOperator || distance == bestDistance)) ambiguous = true;
        }
        if (best is null) {
            if (allowNoMatch) return null;
            fail("no matching method overload", e.token);
        }
        if (selectedWeight !is null) *selectedWeight = bestWeight;
        if (selectedDistance !is null) *selectedDistance = bestDistance;
        if (ambiguousResult !is null) *ambiguousResult = ambiguous;
        else if (ambiguous) fail("ambiguous method overload", e.token);
        return best;
    }
    private bool supportsConvertedBinary(ValueType left, ValueType right, string op) {
        if (isOptionalPrimitive(right)) right = optionalBaseType(right);
        if (right == ValueType.nullableString) right = ValueType.stringType;
        if (left == ValueType.boolType)
            return right == ValueType.boolType && ["==", "!=", "&&", "||"].canFind(op);
        if (left == ValueType.intType)
            return (right == ValueType.intType && ["+", "-", "*", "/", "%", "&", "|", "^", "==", "!=", "<", ">", "<=", ">="].canFind(op)) ||
                   (right == ValueType.decimalType && ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="].canFind(op));
        if (left == ValueType.decimalType)
            return [ValueType.intType, ValueType.decimalType].canFind(right) && ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="].canFind(op);
        if (left == ValueType.stringType)
            return (right == ValueType.stringType || hasStringConversion(right)) && ["+", "==", "!=", "<", ">", "<=", ">="].canFind(op);
        if (left == ValueType.guidType || left == ValueType.fileType)
            return left == right && ["==", "!="].canFind(op);
        if (left == ValueType.dateType)
            return (right == ValueType.dateType && ["-", "==", "!=", "<", ">", "<=", ">="].canFind(op)) ||
                   (right == ValueType.datespanType && ["+", "-"].canFind(op));
        if (left == ValueType.datespanType)
            return (right == ValueType.datespanType && ["+", "-", "==", "!=", "<", ">", "<=", ">="].canFind(op)) ||
                   (right == ValueType.dateType && op == "+");
        return false;
    }
    private ValueType convertedBinaryOperand(ValueType left, Expression expression, ValueType right, string op) {
        if (right != ValueType.selfType)
            return supportsConvertedBinary(left, right, op) ? right : ValueType.voidType;
        // string operators take string, so a user conversion to another scalar
        // cannot be followed by a second implicit scalar-to-string conversion.
        if (left == ValueType.stringType)
            return ["+", "==", "!=", "<", ">", "<=", ">="].canFind(op) &&
                findConversion(expression.objectClass, ValueType.stringType) !is null ? ValueType.stringType : ValueType.voidType;
        ValueType selected = ValueType.voidType;
        foreach (target; [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType,
                          ValueType.guidType, ValueType.dateType, ValueType.datespanType, ValueType.fileType]) {
            if (!supportsConvertedBinary(left, target, op) || findConversion(expression.objectClass, target) is null) continue;
            if (selected != ValueType.voidType) fail("ambiguous binary operator", expression.token);
            selected = target;
        }
        return selected;
    }
    private bool canConvertSqlOperand(Expression expression, ValueType actual, ValueType expected) {
        if (actual == ValueType.selfType) return findConversion(expression.objectClass, expected) !is null;
        if (isOptionalPrimitive(actual)) actual = optionalBaseType(actual);
        if (actual == ValueType.nullableString) actual = ValueType.stringType;
        if (actual == expected) return true;
        if (expected == ValueType.sqlBoolType) return actual == ValueType.boolType;
        if (expected == ValueType.sqlIntType) return actual == ValueType.intType;
        if (expected == ValueType.sqlDecimalType) return actual == ValueType.decimalType || actual == ValueType.sqlIntType;
        if (expected == ValueType.sqlStringType) return actual == ValueType.stringType;
        if (expected == ValueType.sqlGuidType) return actual == ValueType.guidType;
        if (expected == ValueType.sqlDateType) return actual == ValueType.dateType;
        if (expected == ValueType.sqlDatespanType) return actual == ValueType.datespanType;
        if (expected == ValueType.sqlGeometryType) return actual == ValueType.geometryType;
        return false;
    }
    private ValueType sqlBinaryOperand(ValueType left, Expression expression, ValueType right, string op) {
        ValueType[] allowed;
        if (left == ValueType.sqlBoolType && ["&&", "||", "==", "!="].canFind(op)) allowed = [ValueType.sqlBoolType];
        else if (left == ValueType.sqlIntType && ["+", "-", "*", "/", "%", "&", "|", "^", "==", "!=", "<", ">", "<=", ">="].canFind(op)) {
            allowed = [ValueType.sqlIntType];
            if (!["&", "|", "^"].canFind(op)) allowed ~= ValueType.sqlDecimalType;
        } else if (left == ValueType.sqlDecimalType && ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="].canFind(op))
            allowed = [ValueType.sqlIntType, ValueType.sqlDecimalType];
        else if (left == ValueType.sqlStringType && ["+", "==", "!=", "<", ">", "<=", ">="].canFind(op)) allowed = [ValueType.sqlStringType];
        else if (left == ValueType.sqlGuidType && ["==", "!="].canFind(op)) allowed = [ValueType.sqlGuidType];
        else if (left == ValueType.sqlDateType) {
            if (["+", "-"].canFind(op)) allowed ~= ValueType.sqlDatespanType;
            if (["-", "==", "!=", "<", ">", "<=", ">="].canFind(op)) allowed ~= ValueType.sqlDateType;
        } else if (left == ValueType.sqlDatespanType) {
            if (["+", "-", "==", "!=", "<", ">", "<=", ">="].canFind(op)) allowed ~= ValueType.sqlDatespanType;
            if (op == "+") allowed ~= ValueType.sqlDateType;
        } else if (left == ValueType.sqlGeometryType && ["==", "!=", "&&"].canFind(op)) allowed = [ValueType.sqlGeometryType];
        ValueType selected = ValueType.voidType;
        foreach (target; allowed) if (canConvertSqlOperand(expression, right, target)) {
            // sql_int is also convertible to sql_decimal, but its exact
            // operator is preferred over the extra conversion.
            if (selected == ValueType.sqlIntType && target == ValueType.sqlDecimalType &&
                [ValueType.intType, ValueType.optionalInt, ValueType.sqlIntType].canFind(right)) continue;
            if (selected != ValueType.voidType) fail("ambiguous binary operator", expression.token);
            selected = target;
        }
        return selected;
    }
    private void checkArguments(Expression e, ValueType[] types) {
        if (e.arguments.length != types.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) if (!matches(arg, types[i])) fail("argument type mismatch", arg.token);
    }
    private void checkStoredArguments(Expression e, ValueType[] types, Program expectedClass = null) {
        if (e.arguments.length != types.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) if (!matchesStored(arg, types[i], expectedClass)) fail("argument type mismatch", arg.token);
    }
    void check(Program program, Program[string] allPrograms = null) {
        currentProgram = program;
        allClasses = allPrograms;
        importedMath = false;
        visibleClasses = null;
        visibleClasses[program.name.text] = program;
        auto dot = program.qualifiedName.lastIndexOf('.');
        auto packageName = dot < 0 ? "" : program.qualifiedName[0 .. dot + 1];
        foreach (qualified, target; allPrograms) {
            auto targetDot = qualified.lastIndexOf('.');
            auto targetPackage = targetDot < 0 ? "" : qualified[0 .. targetDot + 1];
            if (target.lexicalOwner is null && targetPackage == packageName) visibleClasses[target.name.text] = target;
        }
        Program[string] imported;
        foreach (item; program.imports) {
            if (item.name == "org.zenframework.z8.lang.encoding") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_bool") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_int") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_decimal") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_string") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_guid") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_date") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_datespan") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_binary") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_geometry") continue;
            if (item.name == "org.zenframework.z8.lang.sql.sql_primary") continue;
            if (item.name == "org.zenframework.z8.base.fts.Fts" || item.name == "org.zenframework.z8.base.fts.FtsQueryType") continue;
            if (item.name == "org.zenframework.z8.lang.Math") { importedMath = true; continue; }
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
        foreach (field; program.fields) if (field.isRecord) {
            for (auto owner = program; owner !is null; owner = owner.baseClass)
                foreach (other; owner.fields) if (other.isRecord && other !is field &&
                    icmp(field.initializer.token.text, other.initializer.token.text) == 0)
                    fail("duplicate record GUID", field.initializer.token);
        }
        Method[][string] ownOverloads;
        foreach (m; program.methods) {
            auto previousOverloads = m.name.text in ownOverloads;
            if (previousOverloads !is null) foreach (previous; *previousOverloads) {
                if (sameParameters(previous, m)) fail("duplicate method signature", m.name);
            }
            Method baseMethod;
            for (auto base = program.baseClass; base !is null && baseMethod is null; base = base.baseClass)
                foreach (candidate; base.methods)
                    if (candidate.name.text == m.name.text && sameParameters(candidate, m)) { baseMethod = candidate; break; }
            if (baseMethod !is null) {
                if (m.isStatic != baseMethod.isStatic || (!m.isStatic && !baseMethod.isVirtual))
                    fail("only virtual instance methods may be overridden", m.name);
                if (m.returnType != baseMethod.returnType || m.parameters.length != baseMethod.parameters.length)
                    fail("override signature mismatch", m.name);
                if (hasObjectClass(m.returnType) && resolveClass(program, m.returnObjectName, m.name) !is resolveClass(baseMethod.owner, baseMethod.returnObjectName, baseMethod.name))
                    fail("override return type mismatch", m.name);
                if (hasMapKeyClass(m.returnType) && resolveKeyClasses(program, m.returnKeyObjectNames, m.name) != resolveKeyClasses(baseMethod.owner, baseMethod.returnKeyObjectNames, baseMethod.name))
                    fail("override return type mismatch", m.name);
                foreach (i, p; m.parameters) {
                    auto baseParam = baseMethod.parameters[i];
                    if (p.type != baseParam.type || (hasObjectClass(p.type) &&
                        resolveClass(program, p.objectName, p.name) !is resolveClass(baseMethod.owner, baseParam.objectName, baseParam.name)))
                        fail("override parameter type mismatch", p.name);
                }
                if (!m.isStatic) { m.isVirtual = true; m.overrides = true; }
            }
            methods[m.name.text] = m;
            ownOverloads[m.name.text] ~= m;
        }
        if (isPrimaryClass(program) && !program.isNative) {
            bool hasAssignment;
            foreach (method; program.methods)
                if (method.operatorSymbol == "=" && method.parameters.length == 1 &&
                    method.parameters[0].type == ValueType.selfType &&
                    resolveClass(program, method.parameters[0].objectName, method.parameters[0].name) is program)
                    hasAssignment = true;
            if (!hasAssignment) fail("type extending primary must implement assignment from itself", program.name);
        }
        if (extendsBuiltinPrimary(program)) foreach (method; program.methods)
            if (!method.parameters.length && ["toString", "hashCode"].canFind(method.name.text))
                fail("only virtual instance methods may be overridden", method.name);
        variables = null; objectVariables = null; keyObjectVariables = null; staticContext = false;
        foreach (field; program.fields) {
            if (hasObjectClass(field.type)) field.objectClass = resolveClass(program, field.objectName, field.name);
            if (hasMapKeyClass(field.type)) field.keyObjectClasses = resolveKeyClasses(program, field.keyObjectNames, field.name);
        }
        // Record attributes name table fields and retain primary values, unlike
        // ordinary attributes, which become textual CLASS metadata.
        foreach (record; program.fields) if (record.isRecord) {
            staticContext = false; fieldInitialization = false;
            foreach (ref attribute; record.recordAttributes) {
                if (!attribute.hasValue) fail("record attribute requires a value", attribute.name);
                auto target = attribute.name.text in fields;
                if (target is null) fail("record attribute does not name a field", attribute.name);
                attribute.recordField = *target;
                if (attribute.expression !is null) attribute.recordExpression = attribute.expression;
                else {
                    ExprKind kind;
                    switch (attribute.value.kind) {
                        case TokenKind.integerLiteral: kind = ExprKind.integer; break;
                        case TokenKind.decimalLiteral: kind = ExprKind.decimalLiteral; break;
                        case TokenKind.booleanLiteral: kind = ExprKind.boolean; break;
                        case TokenKind.stringLiteral: kind = ExprKind.stringLiteral; break;
                        case TokenKind.guidLiteral: kind = ExprKind.guidLiteral; break;
                        case TokenKind.binaryLiteral: kind = ExprKind.binaryLiteral; break;
                        case TokenKind.datespanLiteral: kind = ExprKind.datespanLiteral; break;
                        case TokenKind.dateLiteral: kind = ExprKind.dateLiteral; break;
                        default: fail("unsupported record attribute value", attribute.name);
                    }
                    attribute.recordExpression = new Expression(kind, attribute.value);
                }
                auto actual = typeOf(attribute.recordExpression);
                if (isOptionalPrimitive(actual)) actual = optionalBaseType(actual);
                if (actual == ValueType.nullableString) actual = ValueType.stringType;
                ValueType sqlType;
                switch (actual) {
                    case ValueType.intType: sqlType = ValueType.sqlIntType; break;
                    case ValueType.boolType: sqlType = ValueType.sqlBoolType; break;
                    case ValueType.decimalType: sqlType = ValueType.sqlDecimalType; break;
                    case ValueType.stringType: sqlType = ValueType.sqlStringType; break;
                    case ValueType.guidType: sqlType = ValueType.sqlGuidType; break;
                    case ValueType.binaryType: sqlType = ValueType.sqlBinaryType; break;
                    case ValueType.datespanType: sqlType = ValueType.sqlDatespanType; break;
                    case ValueType.dateType: sqlType = ValueType.sqlDateType; break;
                    case ValueType.geometryType: sqlType = ValueType.sqlGeometryType; break;
                    default: fail("record attribute requires a supported primary value", attribute.name);
                }
                if (attribute.recordField.type != ValueType.selfType ||
                    findConversion(attribute.recordField.objectClass, sqlType) is null)
                    fail("record attribute value does not match the field type", attribute.name);
            }
        }
        foreach (attribute; program.attributes) if (attribute.expression !is null) {
            if (attribute.expression.kind != ExprKind.field || attribute.expression.left.kind != ExprKind.variable)
                fail("type attribute requires a qualified static field", attribute.name);
        }
        // Type attributes are evaluated in the generated CLASS constructor;
        // no instance or unqualified member is available there.
        auto savedFields = fields;
        fields = null; staticContext = true; fieldInitialization = false;
        checkAttributeExpressions(program.attributes);
        fields = savedFields; staticContext = false;
        foreach (field; program.fields) {
            staticContext = field.isStatic;
            fieldInitialization = !field.isStatic;
            if (field.initializer !is null) {
                if (program.enclosingStatic && !field.isStatic)
                    fail("instance field initializer in a static local specialization", field.name);
                auto direct = matchesInitializer(field.initializer, field.type, field.objectClass, field.keyObjectClasses);
                if (field.type == ValueType.selfType && !field.isStatic)
                    field.userOperatorAssignment = useAssignmentOperator(field.objectClass, field.initializer, field.name, direct);
                if (!direct && !field.userOperatorAssignment) fail("field initializer type mismatch", field.name);
            }
            if (field.attributes.length) {
                fieldInitialization = false;
                checkAttributeExpressions(field.attributes);
            }
        }
        string memberPath(Expression target) {
            return target.kind == ExprKind.variable ? target.token.text : memberPath(target.left) ~ "." ~ target.token.text;
        }
        void setTargetStage(Expression target, bool early) {
            if (target is null) return;
            target.fieldInitialization = false;
            target.earlyFieldInitialization = early;
            setTargetStage(target.left, early);
        }
        string[] initializedMembers;
        foreach (init; program.memberInitializers) {
            auto name = memberPath(init.target);
            if (initializedMembers.canFind(name)) fail("duplicate field initialization", init.token);
            initializedMembers ~= name;
            Field initializedDeclaration;
            if (init.target.kind == ExprKind.variable)
                foreach (field; program.fields)
                    if (field.name.text == name && (field.initializer !is null || field.nestedClass !is null))
                        initializedDeclaration = field;
            staticContext = false; fieldInitialization = true;
            if (init.expression is null) {
                init.type = typeOf(init.target);
                if (isOptionalPrimitive(init.type)) init.type = optionalBaseType(init.type);
                if (init.type == ValueType.nullableString) init.type = ValueType.stringType;
            } else checkStatement(init);
            // A nested type initializer creates a specialized reference; an
            // independent MemberInit for that reference is allowed by Z8.
            if (initializedDeclaration !is null && initializedDeclaration.nestedClass is null)
                fail("duplicate field initialization", init.token);
            auto root = init.target;
            while (root.kind == ExprKind.field) root = root.left;
            if (!root.isField) fail("field initialization requires a field", init.token);
            if (init.attributes.length) {
                if (init.type != ValueType.selfType) fail("attributes require an object reference field", init.token);
                // Attribute writes occur in constructor2, independently of the
                // earlier reference assignment and its receiver stages.
                init.attributeTarget = copyQualifiedTarget(init.target);
                fieldInitialization = false;
                typeOf(init.attributeTarget);
                checkAttributeExpressions(init.attributes);
                fieldInitialization = true;
            }
            setTargetStage(init.target, init.type == ValueType.selfType);
        }
        fieldInitialization = false;
        foreach (m; program.methods) {
            variables = null; objectVariables = null; keyObjectVariables = null; staticContext = false;
            // Z8 checks method attributes before opening the parameter scope.
            checkAttributeExpressions(m.attributes);
            returnType = m.returnType; loopDepth = 0; staticContext = m.isStatic;
            m.returnObjectClass = hasObjectClass(m.returnType) ? resolveClass(program, m.returnObjectName, m.name) : null;
            returnObjectClass = m.returnObjectClass;
            m.returnKeyObjectClasses = hasMapKeyClass(m.returnType) ? resolveKeyClasses(program, m.returnKeyObjectNames, m.name) : null;
            returnKeyObjectClasses = m.returnKeyObjectClasses;
            foreach (ref p; m.parameters) {
                if (p.type == ValueType.voidType) fail("parameter cannot be void", p.name);
                if (p.name.text in variables) fail("duplicate parameter", p.name);
                variables[p.name.text] = p.type;
                if (hasObjectClass(p.type)) {
                    p.objectClass = resolveClass(program, p.objectName, p.name);
                    objectVariables[p.name.text] = p.objectClass;
                }
                if (hasMapKeyClass(p.type)) {
                    p.keyObjectClasses = resolveKeyClasses(program, p.keyObjectNames, p.name);
                    keyObjectVariables[p.name.text] = p.keyObjectClasses;
                }
            }
            if (m.isNativeDeclaration) continue;
            checkStatement(m.body);
            auto returns = analyzeControlFlow(m.body);
            if (returnType != ValueType.voidType && !returns) fail("method may finish without returning a value", m.name);
        }
    }
    private void checkAttributeExpressions(TypeAttribute[] attributes) {
        foreach (ref attribute; attributes) if (attribute.expression !is null) {
            auto actual = typeOf(attribute.expression);
            if (isOptionalPrimitive(actual)) {
                attribute.expression.optionalRequired = true;
                actual = optionalBaseType(actual);
            }
            attribute.expressionType = actual;
            if ([ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.primaryType,
                 ValueType.guidType, ValueType.datespanType, ValueType.dateType,
                 ValueType.geometryType, ValueType.binaryType].canFind(actual))
                attribute.expression.convertToString = actual;
            else if (actual == ValueType.selfType)
                attribute.expression.convertToString = ValueType.selfType;
            else if (actual == ValueType.fileType || actual == ValueType.exceptionType) { }
            else if (actual != ValueType.stringType && actual != ValueType.nullableString)
                fail("this attribute expression type is not supported yet", attribute.name);
        }
    }
    // Follow the original compiler's return and reachability traversal. In
    // particular, a nested block containing break does not break its parent.
    private bool analyzeControlFlow(Statement s) {
        final switch (s.kind) {
            case StmtKind.block:
                foreach (i, child; s.children) {
                    auto returns = analyzeControlFlow(child);
                    auto breaks = child.kind == StmtKind.breakStmt || child.kind == StmtKind.continueStmt;
                    if (returns || breaks) {
                        if (i + 1 < s.children.length) fail("unreachable code", s.children[i + 1].token);
                        return returns;
                    }
                }
                return false;
            case StmtKind.returnStmt:
            case StmtKind.throwStmt: return true;
            case StmtKind.ifStmt:
                auto first = analyzeControlFlow(s.children[0]);
                return s.children.length == 2 && first && analyzeControlFlow(s.children[1]);
            case StmtKind.whileStmt:
            case StmtKind.doWhileStmt:
            case StmtKind.forStmt:
            case StmtKind.forEachStmt:
                analyzeControlFlow(s.children[0]);
                return false;
            case StmtKind.tryStmt:
                bool catchesReturn = true, finallyReturns;
                if (s.hasCatch) catchesReturn = analyzeControlFlow(s.children[1]);
                if (s.hasFinally) finallyReturns = analyzeControlFlow(s.children[$-1]);
                return (analyzeControlFlow(s.children[0]) && catchesReturn) || finallyReturns;
            case StmtKind.variable:
            case StmtKind.assignment:
            case StmtKind.expressionStmt:
            case StmtKind.breakStmt:
            case StmtKind.continueStmt: return false;
        }
    }
    private ValueType typeOf(Expression e, ValueType expected = ValueType.voidType) {
        if (auto cached = e in expressionSpineTypeCache) return *cached;
        // Walk left-associative operators and fluent receivers iteratively to
        // avoid a typeOfRaw stack frame per node in long expressions.
        if ((e.kind == ExprKind.binary || e.kind == ExprKind.memberCall)) {
            Expression[] chain;
            for (auto node = e; (node.kind == ExprKind.binary || node.kind == ExprKind.memberCall) && node.left !is null && !(node in expressionSpineTypeCache); node = node.left)
                chain ~= node;
            if (chain.length > 1) {
                scope (exit) foreach (node; chain) expressionSpineTypeCache.remove(node);
                foreach_reverse (node; chain)
                    expressionSpineTypeCache[node] = typeOfSingle(node, node is e ? expected : ValueType.voidType);
                return expressionSpineTypeCache[e];
            }
        }
        return typeOfSingle(e, expected);
    }
    private ValueType typeOfSingle(Expression e, ValueType expected) {
        e.fieldInitialization = fieldInitialization;
        auto result = typeOfRaw(e, expected);
        if (e.parenthesisCount && result == ValueType.selfType && e.objectClass !is null)
            e.priorityMethod = lookupUnaryOperator(e.objectClass, "operatorPriority");
        if (e.parenthesisCount && result == ValueType.sqlBoolType) e.sqlBoolPriority = true;
        if (e.parenthesisCount && result == ValueType.sqlIntType) e.sqlIntPriority = true;
        if (e.parenthesisCount && result == ValueType.sqlDecimalType) e.sqlDecimalPriority = true;
        if (e.parenthesisCount && result == ValueType.sqlStringType) e.sqlStringPriority = true;
        if (e.parenthesisCount && result == ValueType.sqlGuidType) e.sqlGuidPriority = true;
        if (e.parenthesisCount && result == ValueType.sqlDateType) e.sqlDatePriority = true;
        if (e.parenthesisCount && result == ValueType.sqlDatespanType) e.sqlDatespanPriority = true;
        if (e.parenthesisCount && result == ValueType.sqlGeometryType) e.sqlGeometryPriority = true;
        if (result == ValueType.stringType && (e.kind == ExprKind.memberCall || e.kind == ExprKind.binary))
            e.nonNullStringResult = true;
        return result;
    }
    private ValueType typeOfRaw(Expression e, ValueType expected = ValueType.voidType) {
        final switch (e.kind) {
            case ExprKind.integer: return ValueType.intType;
            case ExprKind.decimalLiteral:
                if (!safeDecimalLiteral(canonicalDecimalLiteral(e.token))) fail("decimal literal cannot yet be converted reliably; use decimal.parse with a string", e.token);
                return ValueType.decimalType;
            case ExprKind.boolean: return ValueType.boolType;
            case ExprKind.stringLiteral: return ValueType.stringType;
            case ExprKind.guidLiteral: return ValueType.guidType;
            case ExprKind.binaryLiteral: return ValueType.binaryType;
            case ExprKind.datespanLiteral: return ValueType.datespanType;
            case ExprKind.dateLiteral:
                if (e.token.text.indexOf('/') < 0 && !e.emittedOverride.length) {
                    import std.datetime : Clock, SysTime, UTC;
                    auto now = Clock.currTime(UTC());
                    auto ticks = (now - SysTime.fromUnixTime(0, UTC())).total!"msecs";
                    // The original lexer ignores the written time and captures its current instant.
                    e.emittedOverride = "z8_date_from_ticks(" ~ ticks.to!string ~ "L)";
                }
                return ValueType.dateType;
            case ExprKind.nullLiteral: return ValueType.nullType;
            case ExprKind.arrayLiteral:
                if (e.typedInitializer) {
                    expected = resolveDeclaredType(e.initializerType, currentProgram, e.initializerObjectName, e.initializerKeyObjectNames, e.token);
                    if (hasObjectClass(expected)) e.objectClass = resolveClass(currentProgram, e.initializerObjectName, e.token);
                    if (hasMapKeyClass(expected)) e.keyObjectClasses = resolveKeyClasses(currentProgram, e.initializerKeyObjectNames, e.token);
                }
                if (isMap(expected)) {
                    auto keyType = mapKeyType(expected);
                    auto valueType = mapValueType(expected);
                    foreach (entry; e.arguments) {
                        if (entry.kind != ExprKind.mapEntry) fail("map initializer requires key-value pairs", entry.token);
                        if (entry.left.kind == ExprKind.nullLiteral || entry.right.kind == ExprKind.nullLiteral)
                            fail("null literal is not supported in a map initializer pair", entry.token);
                        if ([ValueType.dateType, ValueType.datespanType, ValueType.binaryType, ValueType.geometryType, ValueType.fileType].canFind(keyType) && typeOf(entry.left) != keyType)
                            fail("map key type mismatch", entry.left.token);
                        if ([ValueType.exceptionType, ValueType.encodingType].canFind(keyType) && typeOf(entry.left) != keyType)
                            fail("map key type mismatch", entry.left.token);
                        if (isSqlType(keyType)) {
                            auto actualKey = typeOf(entry.left);
                            if (actualKey != keyType && !(keyType == ValueType.sqlPrimaryType && isSqlType(actualKey)))
                                fail("map key type mismatch", entry.left.token);
                        }
                        if ([ValueType.selfType, ValueType.enumType].canFind(keyType)) {
                            auto actualKey = typeOf(entry.left);
                            if (actualKey != keyType || (keyType == ValueType.selfType ?
                                !isAssignable(entry.left.objectClass, outerMapKeyClass(expected, e.keyObjectClasses)) : entry.left.objectClass !is outerMapKeyClass(expected, e.keyObjectClasses)))
                                fail("map key type mismatch", entry.left.token);
                        }
                        if (keyType == ValueType.stringType) {
                            if (![ValueType.stringType, ValueType.nullableString].canFind(typeOf(entry.left)))
                                fail("map key type mismatch", entry.left.token);
                        } else if (!matchesStored(entry.left, keyType, outerMapKeyClass(expected, e.keyObjectClasses))) fail("map key type mismatch", entry.left.token);
                        if (valueType == ValueType.stringType) {
                            if (![ValueType.stringType, ValueType.nullableString].canFind(typeOf(entry.right)))
                                fail("map value type mismatch", entry.right.token);
                        } else {
                            // Array/map type casts in the original use inheritance,
                            // not scalar conversion operators such as int -> decimal.
                            if (valueType == ValueType.decimalType &&
                                ![ValueType.decimalType, ValueType.optionalDecimal].canFind(typeOf(entry.right)))
                                fail("map value type mismatch", entry.right.token);
                            if ([ValueType.selfType, ValueType.enumType].canFind(valueType)) {
                                auto actualValue = typeOf(entry.right);
                                if (actualValue != valueType || (valueType == ValueType.selfType ?
                                    !isAssignable(entry.right.objectClass, e.objectClass) : entry.right.objectClass !is e.objectClass))
                                    fail("map value type mismatch", entry.right.token);
                            }
                            if ([ValueType.binaryType, ValueType.datespanType, ValueType.dateType, ValueType.geometryType,
                                ValueType.fileType, ValueType.exceptionType, ValueType.encodingType].canFind(valueType) && typeOf(entry.right) != valueType)
                                fail("map value type mismatch", entry.right.token);
                            if (isSqlType(valueType)) {
                                auto actualValue = typeOf(entry.right);
                                if (actualValue != valueType && !(valueType == ValueType.sqlPrimaryType && isSqlType(actualValue)))
                                    fail("map value type mismatch", entry.right.token);
                            }
                            if (!matchesStored(entry.right, valueType, e.objectClass, innerMapKeyClasses(expected, e.keyObjectClasses))) fail("map value type mismatch", entry.right.token);
                        }
                    }
                    e.inferredType = expected; return expected;
                }
                if (!isArray(expected)) fail("array initializer requires an array type", e.token);
                foreach (element; e.arguments)
                    if (!matchesStored(element, elementType(expected), e.objectClass, e.keyObjectClasses)) fail("array element type mismatch", element.token);
                e.inferredType = expected; return expected;
            case ExprKind.mapEntry: fail("key-value pair requires a map initializer", e.token); assert(0);
            case ExprKind.variable:
                auto variable = e.token.text in variables;
                if (variable is null) {
                    auto field = e.token.text in fields;
                    if (field is null) {
                        foreach (capture; currentProgram.captures) if (capture.name == e.token.text) {
                            e.isCapture = true;
                            e.objectClass = capture.objectClass; e.keyObjectClasses = capture.keyObjectClasses;
                            return capture.type == ValueType.stringType ? ValueType.nullableString : storedValueType(capture.type);
                        }
                        fail("unknown variable '" ~ e.token.text ~ "'", e.token);
                    }
                    if (!accessible((*field).owner, (*field).isPublic, (*field).isProtected)) fail("field is not accessible", e.token);
                    if (staticContext && !(*field).isStatic) fail("instance field in static context", e.token);
                    e.isField = true;
                    if ((*field).isStatic) e.targetClass = (*field).owner.emittedName;
                    if (hasObjectClass((*field).type)) e.objectClass = (*field).objectClass;
                    if (hasMapKeyClass((*field).type)) e.keyObjectClasses = (*field).keyObjectClasses;
                    return (*field).type == ValueType.stringType ? ValueType.nullableString : storedValueType((*field).type);
                }
                if (hasObjectClass(*variable)) e.objectClass = objectVariables[e.token.text];
                if (hasMapKeyClass(*variable)) e.keyObjectClasses = keyObjectVariables[e.token.text];
                return *variable == ValueType.stringType ? ValueType.nullableString : storedValueType(*variable);
            case ExprKind.selfRef:
                if (staticContext) fail("this in static context", e.token);
                e.objectClass = currentProgram;
                return ValueType.selfType;
            case ExprKind.superRef:
                if (staticContext) fail("super in static context", e.token);
                if (currentProgram.baseClass is null) fail("super requires a base class", e.token);
                e.objectClass = currentProgram.baseClass;
                return ValueType.selfType;
            case ExprKind.containerRef:
                if (staticContext) fail("container in static context", e.token);
                auto containerOwner = currentProgram;
                if (e.left !is null) {
                    if (e.left.kind != ExprKind.containerRef || typeOf(e.left) != ValueType.selfType)
                        fail("invalid container chain", e.token);
                    containerOwner = e.left.objectClass;
                }
                if (containerOwner.lexicalOwner is null) fail("container requires an enclosing type", e.token);
                e.objectClass = containerOwner.lexicalOwner;
                return ValueType.selfType;
            case ExprKind.newSelf:
                switch (e.token.text) {
                    case "int": e.inferredType = ValueType.intType; return e.inferredType;
                    case "bool": e.inferredType = ValueType.boolType; return e.inferredType;
                    case "decimal": e.inferredType = ValueType.decimalType; return e.inferredType;
                    case "string": e.inferredType = ValueType.stringType; return e.inferredType;
                    case "guid": e.inferredType = ValueType.guidType; return e.inferredType;
                    case "binary": e.inferredType = ValueType.binaryType; return e.inferredType;
                    case "datespan": e.inferredType = ValueType.datespanType; return e.inferredType;
                    case "date": e.inferredType = ValueType.dateType; return e.inferredType;
                    case "geometry": e.inferredType = ValueType.geometryType; return e.inferredType;
                    case "file": e.inferredType = ValueType.fileType; return e.inferredType;
                    case "exception": e.inferredType = ValueType.exceptionType; return e.inferredType;
                    default: break;
                }
                if (e.token.text == "Fts") { e.inferredType = ValueType.ftsType; return ValueType.ftsType; }
                if (e.token.text == "sql_bool") { e.inferredType = ValueType.sqlBoolType; return ValueType.sqlBoolType; }
                if (e.token.text == "sql_int") { e.inferredType = ValueType.sqlIntType; return ValueType.sqlIntType; }
                if (e.token.text == "sql_decimal") { e.inferredType = ValueType.sqlDecimalType; return ValueType.sqlDecimalType; }
                if (e.token.text == "sql_string") { e.inferredType = ValueType.sqlStringType; return ValueType.sqlStringType; }
                if (e.token.text == "sql_guid") { e.inferredType = ValueType.sqlGuidType; return ValueType.sqlGuidType; }
                if (e.token.text == "sql_date") { e.inferredType = ValueType.sqlDateType; return ValueType.sqlDateType; }
                if (e.token.text == "sql_datespan") { e.inferredType = ValueType.sqlDatespanType; return ValueType.sqlDatespanType; }
                if (e.token.text == "sql_binary") { e.inferredType = ValueType.sqlBinaryType; return ValueType.sqlBinaryType; }
                if (e.token.text == "sql_geometry") { e.inferredType = ValueType.sqlGeometryType; return ValueType.sqlGeometryType; }
                if (e.token.text == "sql_primary") { e.inferredType = ValueType.sqlPrimaryType; return ValueType.sqlPrimaryType; }
                e.objectClass = resolveClass(currentProgram, e.token.text, e.token);
                e.newHasContainer = !staticContext && !isPrimaryClass(e.objectClass);
                if (e.objectClass.isEnum) fail("cannot instantiate an enum", e.token);
                return ValueType.selfType;
            case ExprKind.field:
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text)) {
                    if (e.left.token.text == "int" && ["Min", "Max"].canFind(e.token.text)) {
                        e.emittedOverride = "z8_int_" ~ e.token.text; return ValueType.optionalInt;
                    }
                    if (e.left.token.text == "decimal") {
                        if (["Min", "Max"].canFind(e.token.text)) {
                            e.emittedOverride = "z8_decimal_" ~ e.token.text;
                            e.enumConstant = true; return ValueType.optionalDecimal;
                        }
                        if (["RoundUp", "RoundDown", "RoundCeiling", "RoundFloor", "RoundHalfUp", "RoundHalfDown", "RoundHalfEven", "RoundUnnecessary"].canFind(e.token.text)) {
                            e.emittedOverride = "z8_decimal_" ~ e.token.text; return ValueType.optionalInt;
                        }
                        fail("unknown decimal constant", e.token);
                    }
                    if (e.left.token.text == "guid" && e.token.text == "Null") {
                        e.emittedOverride = "z8_guid_zero()"; return ValueType.guidType;
                    }
                    if (e.left.token.text == "FtsQueryType") {
                        if (!["Query", "Plain", "Phrase"].canFind(e.token.text)) fail("unknown Fts query type", e.token);
                        e.emittedOverride = "z8_fts_query_" ~ e.token.text; e.enumConstant = true; return ValueType.ftsQueryType;
                    }
                    if (e.left.token.text == "Fts") {
                        auto names = ["NormDefault", "NormLenLog", "NormLen", "NormHarmonic", "NormUniqueWords", "NormUniqueWordsLog", "NormDivSelf"];
                        auto values = [0, 1, 2, 4, 8, 16, 32];
                        foreach (i, name; names) if (e.token.text == name) {
                            e.emittedOverride = "z8_optional_wrap(" ~ values[i].to!string ~ "L)"; e.enumConstant = true; return ValueType.optionalInt;
                        }
                        fail("unknown Fts constant", e.token);
                    }
                    if (e.left.token.text == "Math" && importedMath) {
                        if (e.token.text != "PI") fail("unknown Math field", e.token);
                        e.emittedOverride = "z8_math_pi()"; e.enumConstant = true; return ValueType.decimalType;
                    }
                    if (e.left.token.text == "date" && ["Min", "Max"].canFind(e.token.text)) {
                        e.emittedOverride = e.token.text == "Min" ? "z8_date_min" : "z8_date_max";
                        return ValueType.dateType;
                    }
                    if (e.left.token.text == "encoding") {
                        auto names = ["Default", "Cp866", "KOI8R", "USASCII", "UTF8", "UTF16", "UTF16BE", "UTF16LE", "Windows1250", "Windows1251", "Windows1252", "Windows1253", "Windows1254", "Windows1257"];
                        foreach (i, name; names) if (e.token.text == name) {
                            e.emittedOverride = "z8_encoding_by_id(" ~ i.to!string ~ ")"; e.enumConstant = true; return ValueType.encodingType;
                        }
                        fail("unknown encoding", e.token);
                    }
                    if (e.left.token.text == "geometry") {
                        auto names = ["None", "Ring", "Point", "Line", "Polygon", "MultiPoint", "MultiLine", "MultiPolygon", "Collection", "DefaultSRS"];
                        foreach (i, name; names) if (e.token.text == name) {
                            e.emittedOverride = (i == 9 ? 3857 : cast(int)i - 1).to!string ~ "L";
                            e.enumConstant = true; return ValueType.intType;
                        }
                        auto stringNames = ["StrNone", "StrRing", "StrPoint", "StrLine", "StrPolygon", "StrMultiPoint", "StrMultiLine", "StrMultiPolygon", "StrCollection"];
                        auto values = ["NONE", "RING", "POINT", "LINE", "POLYGON", "MULTIPOINT", "MULTILINE", "MULTIPOLYGON", "GEOMETRYCOLLECTION"];
                        foreach (i, name; stringNames) if (e.token.text == name) {
                            e.emittedOverride = "\"" ~ values[i] ~ "\"w";
                            e.enumConstant = true; return ValueType.stringType;
                        }
                        fail("unknown geometry constant", e.token);
                    }
                    auto owner = e.left.token.text in visibleClasses;
                    if (owner is null) fail("unknown class or variable '" ~ e.left.token.text ~ "'", e.left.token);
                    if ((*owner).isEnum) {
                        foreach (value; (*owner).enumValues) if (value.text == e.token.text) {
                            e.targetClass = (*owner).emittedName;
                            e.objectClass = *owner;
                            e.enumConstant = true;
                            return ValueType.enumType;
                        }
                        fail("unknown enum value '" ~ e.token.text ~ "'", e.token);
                    }
                    auto staticField = lookupField(*owner, e.token.text);
                    if (staticField is null) fail("unknown field '" ~ e.token.text ~ "'", e.token);
                    if (!staticField.isStatic) fail("instance field cannot be accessed on a class", e.token);
                    if (!accessible(staticField.owner, staticField.isPublic, staticField.isProtected)) fail("field is not accessible", e.token);
                    e.targetClass = staticField.owner.emittedName;
                    if (hasObjectClass(staticField.type))
                        e.objectClass = staticField.objectClass !is null ? staticField.objectClass : resolveClass(staticField.owner, staticField.objectName, staticField.name);
                    if (hasMapKeyClass(staticField.type))
                        e.keyObjectClasses = staticField.keyObjectClasses.length ? staticField.keyObjectClasses : resolveKeyClasses(staticField.owner, staticField.keyObjectNames, staticField.name);
                    return staticField.type == ValueType.stringType ? ValueType.nullableString : storedValueType(staticField.type);
                }
                auto receiverType = typeOf(e.left);
                if (receiverType == ValueType.ftsType) {
                    e.nativeField = e.token.text;
                    switch (e.token.text) {
                        case "configuration": return ValueType.nullableString;
                        case "queryType": return ValueType.ftsQueryType;
                        case "weight": return ValueType.decimalArray;
                        case "normalization": return ValueType.optionalInt;
                        case "coatingDensity": return ValueType.optionalBool;
                        default: fail("unknown Fts field", e.token);
                    }
                }
                if (receiverType == ValueType.binaryType && e.token.text == "name") {
                    e.binaryNameField = true; return ValueType.nullableString;
                }
                if (receiverType == ValueType.fileType) {
                    e.nativeField = e.token.text;
                    switch (e.token.text) {
                        case "id": case "user": return ValueType.guidType;
                        case "name": case "path": case "author": return ValueType.nullableString;
                        case "time": return ValueType.dateType;
                        case "size": return ValueType.optionalInt;
                        case "details": return mapType(ValueType.stringType, ValueType.stringType);
                        default: fail("unknown file field", e.token);
                    }
                }
                if (receiverType != ValueType.selfType) fail("field access requires an object", e.token);
                auto field = lookupField(e.left.objectClass, e.token.text);
                if (field is null) fail("unknown field '" ~ e.token.text ~ "'", e.token);
                if (!accessible(field.owner, field.isPublic, field.isProtected)) fail("field is not accessible", e.token);
                if (field.isStatic) {
                    e.targetClass = field.owner.emittedName;
                    e.staticInstanceField = e.left.kind != ExprKind.superRef;
                }
                if (hasObjectClass(field.type))
                    e.objectClass = field.objectClass !is null ? field.objectClass : resolveClass(field.owner, field.objectName, field.name);
                if (hasMapKeyClass(field.type))
                    e.keyObjectClasses = field.keyObjectClasses.length ? field.keyObjectClasses : resolveKeyClasses(field.owner, field.keyObjectNames, field.name);
                return field.type == ValueType.stringType ? ValueType.nullableString : storedValueType(field.type);
            case ExprKind.call:
                auto method = e.token.text in methods;
                if (method is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                auto selected = selectOverload(*method, e);
                if (staticContext && !selected.isStatic) fail("instance method in static context", e.token);
                if (!accessible(selected.owner, selected.isPublic, selected.isProtected)) fail("method is not accessible", e.token);
                if (selected.isStatic) e.targetClass = selected.owner.emittedName;
                return checkCall(selected, selected.owner, e);
            case ExprKind.memberCall:
                if (e.left.kind == ExprKind.variable && e.left.token.text == "Math" && importedMath &&
                    !isLexicallyBound(e.left.token.text)) {
                    if (e.token.text == "random") {
                        checkArguments(e, []); e.builtinCall = "z8_math_random"; return ValueType.decimalType;
                    }
                    if (["sin", "cos", "hypot"].canFind(e.token.text)) {
                        checkArguments(e, e.token.text == "hypot" ? [ValueType.decimalType, ValueType.decimalType] : [ValueType.decimalType]);
                        e.builtinCall = "z8_math_" ~ e.token.text; return ValueType.decimalType;
                    }
                    if (["min", "max"].canFind(e.token.text)) {
                        if (e.arguments.length != 2) fail("incorrect argument count", e.token);
                        auto a = typeOf(e.arguments[0]), b = typeOf(e.arguments[1]);
                        if (isOptionalPrimitive(a)) a = optionalBaseType(a);
                        if (isOptionalPrimitive(b)) b = optionalBaseType(b);
                        if (a == ValueType.dateType && b == ValueType.dateType) {
                            checkArguments(e, [a, b]); e.builtinCall = "z8_math_" ~ e.token.text; return ValueType.dateType;
                        }
                        if (![ValueType.intType, ValueType.decimalType].canFind(a) || ![ValueType.intType, ValueType.decimalType].canFind(b))
                            fail("argument type mismatch", e.token);
                        checkArguments(e, [a, b]); e.builtinCall = "z8_math_" ~ e.token.text;
                        return a == ValueType.intType && b == ValueType.intType ? ValueType.intType : ValueType.decimalType;
                    }
                    fail("unsupported Math method", e.token);
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "string") {
                    if (e.token.text == "replicate") {
                        checkArguments(e, [ValueType.stringType, ValueType.intType]); e.builtinCall = "z8_string_replicate"; return ValueType.stringType;
                    }
                    if (e.token.text == "concat") {
                        checkArguments(e, [ValueType.stringArray, ValueType.stringType]); e.builtinCall = "z8_string_concat"; return ValueType.stringType;
                    }
                    if (e.token.text == "fromBinary") {
                        checkArguments(e, e.arguments.length == 1 ? [ValueType.binaryType] : [ValueType.binaryType, ValueType.encodingType]); e.builtinCall = "z8_string_fromBinary"; return ValueType.stringType;
                    }
                    fail("unsupported static string method", e.token);
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "file") {
                    if (e.token.text == "createTempFile") {
                        checkArguments(e, [ValueType.stringType, ValueType.stringType]); e.builtinCall = "z8_file_createTempFile"; return ValueType.fileType;
                    }
                    if (e.token.text == "parse") {
                        checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_file_parse"; return ValueType.fileArray;
                    }
                    if (e.token.text == "toJson") {
                        checkArguments(e, [ValueType.fileArray]); e.builtinCall = "z8_file_toJson"; return ValueType.stringType;
                    }
                    if (!["name", "baseName", "extension"].canFind(e.token.text)) fail("unsupported static file method", e.token);
                    checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_file_" ~ e.token.text; return ValueType.stringType;
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "binary") {
                    if (e.token.text != "zip" || e.arguments.length != 1) fail("unsupported static binary method", e.token);
                    auto source = typeOf(e.arguments[0]);
                    auto expectedSource = source == ValueType.fileType ? ValueType.fileType : ValueType.binaryArray;
                    checkArguments(e, [expectedSource]); e.builtinCall = "z8_binary_zip"; return ValueType.binaryType;
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "geometry") {
                    if (e.token.text == "fromHexString") {
                        checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_geometry_fromHexString"; return ValueType.geometryType;
                    }
                    if (e.token.text == "fromGeoJson") {
                        checkArguments(e, [ValueType.stringType, ValueType.intType]); e.builtinCall = "z8_geometry_fromGeoJson"; return ValueType.geometryType;
                    }
                    if (e.token.text == "none") {
                        checkArguments(e, [ValueType.intType]); e.builtinCall = "z8_geometry_none"; return ValueType.geometryType;
                    }
                    if (e.token.text == "point") {
                        checkArguments(e, [ValueType.decimalType, ValueType.decimalType, ValueType.intType]);
                        e.builtinCall = "z8_geometry_point"; return ValueType.geometryType;
                    }
                    if (e.token.text == "pointOnLine" || e.token.text == "perpendicularToLine") {
                        if (e.token.text == "pointOnLine") checkArguments(e, [ValueType.geometryType, ValueType.decimalType]);
                        else checkArguments(e, [ValueType.geometryType, ValueType.decimalType, ValueType.decimalType]);
                        e.builtinCall = "z8_geometry_" ~ e.token.text; return ValueType.geometryType;
                    }
                    if (["line", "multiLine", "ring", "polygon", "collection", "fromArray"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.geometryArray]);
                        e.builtinCall = "z8_geometry_" ~ e.token.text; return ValueType.geometryType;
                    }
                    fail("unsupported static geometry method", e.token);
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "sql_geometry") {
                    if (e.token.text != "point") fail("unsupported static SQL geometry method", e.token);
                    checkArguments(e, [ValueType.sqlDecimalType, ValueType.sqlDecimalType, ValueType.sqlIntType]);
                    e.builtinCall = "z8_sql_geometry_point"; return ValueType.sqlGeometryType;
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "date") {
                    if (["now", "today", "tomorrow", "yesterday"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_date_" ~ e.token.text; return ValueType.dateType;
                    }
                    if (e.token.text == "isEqualDate") {
                        checkArguments(e, [ValueType.dateType, ValueType.dateType]); e.builtinCall = "z8_date_isEqualDate"; return ValueType.boolType;
                    }
                    if (e.token.text == "parse" || e.token.text == "parseIsoString") {
                        checkArguments(e, e.token.text == "parse" && e.arguments.length == 2 ?
                            [ValueType.stringType, ValueType.stringType] : [ValueType.stringType]);
                        e.builtinCall = e.token.text == "parse" ? "z8_date_parse" : "z8_date_parseIsoString";
                        return ValueType.dateType;
                    }
                    fail("unsupported static date method", e.token);
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "datespan") {
                    if (e.token.text != "parse") fail("unsupported static datespan method", e.token);
                    checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_datespan_parse"; return ValueType.datespanType;
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) && e.left.token.text == "guid") {
                    if (e.token.text == "parse") {
                        checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_guid_parse"; return ValueType.guidType;
                    }
                    if (e.token.text == "create") {
                        if (!e.arguments.length) e.builtinCall = "z8_guid_create_random";
                        else if (e.arguments.length == 1 && [ValueType.stringType, ValueType.nullableString, ValueType.guidType].canFind(typeOf(e.arguments[0]))) {
                            checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_guid_create_name";
                        } else {
                            checkArguments(e, e.arguments.length == 1 ? [ValueType.intType] : [ValueType.intType, ValueType.intType]);
                            e.builtinCall = "z8_guid_create";
                        }
                        return ValueType.guidType;
                    }
                    fail("unsupported static guid method", e.token);
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text) &&
                    (e.left.token.text == "int" || e.left.token.text == "decimal" || e.left.token.text == "bool")) {
                    if (e.token.text != "parse") fail("unsupported static type method", e.token);
                    if (e.left.token.text == "bool") {
                        checkArguments(e, [ValueType.stringType]);
                        if (typeOf(e.arguments[0]) == ValueType.nullableString) e.arguments[0].nullableStringMode = NullableStringMode.none;
                        e.builtinCall = "z8_bool_parse"; return ValueType.boolType;
                    }
                    if (e.left.token.text == "decimal") {
                        checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_decimal_parse"; return ValueType.decimalType;
                    }
                    checkArguments(e, e.arguments.length == 1 ? [ValueType.stringType] : [ValueType.stringType, ValueType.intType]);
                    if (typeOf(e.arguments[0]) == ValueType.nullableString) e.arguments[0].nullableStringMode = NullableStringMode.none;
                    e.builtinCall = "z8_int_parse_optional"; return ValueType.optionalInt;
                }
                if (e.left.kind == ExprKind.variable && !isLexicallyBound(e.left.token.text)) {
                    auto owner = e.left.token.text in visibleClasses;
                    if (owner is null) fail("unknown class or variable '" ~ e.left.token.text ~ "'", e.left.token);
                    auto target = lookupMethod(*owner, e.token.text);
                    if (target is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                    target = selectOverload(target, e);
                    if (!target.isStatic) fail("instance method cannot be called on a class", e.token);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    e.targetClass = target.owner.emittedName;
                    return checkCall(target, target.owner, e);
                }
                auto receiver = typeOf(e.left);
                auto scalarReceiver = isOptionalPrimitive(receiver) ? optionalBaseType(receiver) :
                    receiver == ValueType.nullableString ? ValueType.stringType : receiver;
                ValueType namedSqlType;
                string namedSqlCall;
                switch (e.token.text) {
                    case "sql_bool": if (scalarReceiver == ValueType.boolType) { namedSqlType = ValueType.sqlBoolType; namedSqlCall = "z8_sql_bool_const"; } break;
                    case "sql_int": if (scalarReceiver == ValueType.intType) { namedSqlType = ValueType.sqlIntType; namedSqlCall = "z8_sql_int_const"; } break;
                    case "sql_decimal":
                        if (scalarReceiver == ValueType.decimalType) { namedSqlType = ValueType.sqlDecimalType; namedSqlCall = "z8_sql_decimal_const"; }
                        else if (scalarReceiver == ValueType.sqlIntType) { namedSqlType = ValueType.sqlDecimalType; namedSqlCall = "z8_sql_decimal_from_int"; }
                        break;
                    case "sql_string": if (scalarReceiver == ValueType.stringType) { namedSqlType = ValueType.sqlStringType; namedSqlCall = "z8_sql_string_const"; } break;
                    case "sql_guid": if (scalarReceiver == ValueType.guidType) { namedSqlType = ValueType.sqlGuidType; namedSqlCall = "z8_sql_guid_const"; } break;
                    case "sql_date": if (scalarReceiver == ValueType.dateType) { namedSqlType = ValueType.sqlDateType; namedSqlCall = "z8_sql_date_const"; } break;
                    case "sql_datespan": if (scalarReceiver == ValueType.datespanType) { namedSqlType = ValueType.sqlDatespanType; namedSqlCall = "z8_sql_datespan_const"; } break;
                    case "sql_geometry": if (scalarReceiver == ValueType.geometryType) { namedSqlType = ValueType.sqlGeometryType; namedSqlCall = "z8_sql_geometry_const"; } break;
                    default: break;
                }
                if (namedSqlCall.length) {
                    checkArguments(e, []); e.builtinCall = namedSqlCall; return namedSqlType;
                }
                if (isSqlType(receiver) && receiver != ValueType.sqlStringType && e.token.text == "toString") {
                    checkArguments(e, []);
                    e.builtinCall = receiver == ValueType.sqlBoolType ? "z8_sql_bool_toString" :
                        receiver == ValueType.sqlIntType ? "z8_sql_int_toString" : receiver == ValueType.sqlGuidType ? "z8_sql_guid_toString" : receiver == ValueType.sqlDateType ? "z8_sql_date_toString" : receiver == ValueType.sqlDatespanType ? "z8_sql_datespan_toString" : receiver == ValueType.sqlBinaryType ? "z8_sql_binary_toString" : receiver == ValueType.sqlGeometryType ? "z8_sql_geometry_toString" : receiver == ValueType.sqlPrimaryType ? "z8_sql_primary_toString" : "z8_sql_decimal_toString";
                    return ValueType.sqlStringType;
                }
                if (receiver == ValueType.sqlBoolType) {
                    if (e.token.text == "IIF") {
                        if (e.arguments.length != 2) fail("incorrect argument count", e.token);
                        auto first = typeOf(e.arguments[0]), second = typeOf(e.arguments[1]);
                        if (first == ValueType.nullType && second == ValueType.nullType)
                            fail("ambiguous SQL IIF overload", e.token);
                        auto type = ValueType.voidType;
                        int best = int.max;
                        bool ambiguous;
                        foreach (candidate; [ValueType.sqlBoolType, ValueType.sqlIntType, ValueType.sqlDecimalType, ValueType.sqlStringType,
                                            ValueType.sqlGuidType, ValueType.sqlDateType, ValueType.sqlDatespanType, ValueType.sqlGeometryType]) {
                            auto leftCost = sqlIifConversionCost(e.arguments[0], first, candidate);
                            auto rightCost = sqlIifConversionCost(e.arguments[1], second, candidate);
                            if (leftCost < 0 || rightCost < 0) continue;
                            auto cost = leftCost + rightCost;
                            if (cost < best) { type = candidate; best = cost; ambiguous = false; }
                            else if (cost == best) ambiguous = true;
                        }
                        if (ambiguous) fail("ambiguous SQL IIF overload", e.token);
                        if (type == ValueType.voidType) fail("no matching SQL IIF overload", e.token);
                        checkArguments(e, [type, type]);
                        e.builtinCall = type == ValueType.sqlStringType ? "z8_sql_string_iif" : type == ValueType.sqlDecimalType ? "z8_sql_decimal_iif" : type == ValueType.sqlIntType ? "z8_sql_int_iif" : type == ValueType.sqlGuidType ? "z8_sql_guid_iif" : type == ValueType.sqlDateType ? "z8_sql_date_iif" : type == ValueType.sqlDatespanType ? "z8_sql_datespan_iif" : type == ValueType.sqlGeometryType ? "z8_sql_geometry_iif" : "z8_sql_bool_iif"; return type;
                    }
                    fail("unsupported SQL boolean method", e.token);
                }
                if (receiver == ValueType.sqlIntType) {
                    if (["sign", "abs"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_int_" ~ e.token.text; return ValueType.sqlIntType;
                    }
                    if (e.token.text == "power") {
                        checkArguments(e, [ValueType.sqlIntType]); e.builtinCall = "z8_sql_int_power"; return ValueType.sqlIntType;
                    }
                    fail("unsupported SQL integer method", e.token);
                }
                if (receiver == ValueType.sqlGeometryType) {
                    if (["x", "xMax", "xMin", "y", "yMax", "yMin", "length"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_geometry_" ~ e.token.text; return ValueType.sqlDecimalType;
                    }
                    if (e.token.text == "collectionSize") {
                        checkArguments(e, []); e.builtinCall = "z8_sql_geometry_collectionSize"; return ValueType.sqlIntType;
                    }
                    if (["isEmpty", "isValid"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_geometry_" ~ e.token.text; return ValueType.sqlBoolType;
                    }
                    if (["strType", "asGeoJSON"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_geometry_" ~ e.token.text; return ValueType.sqlStringType;
                    }
                    if (["startPoint", "endPoint", "union", "centroid", "envelope", "homogenize", "makeValid"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_geometry_" ~ e.token.text; return ValueType.sqlGeometryType;
                    }
                    if (["intersects", "intersect", "split", "distance"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.sqlGeometryType]); e.builtinCall = "z8_sql_geometry_" ~ e.token.text;
                        return e.token.text == "intersects" ? ValueType.sqlBoolType : e.token.text == "distance" ? ValueType.sqlDecimalType : ValueType.sqlGeometryType;
                    }
                    if (["element", "extract"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.sqlIntType]); e.builtinCall = "z8_sql_geometry_" ~ e.token.text; return ValueType.sqlGeometryType;
                    }
                    if (["interpolatePoint", "buffer"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.sqlDecimalType]); e.builtinCall = "z8_sql_geometry_" ~ e.token.text; return ValueType.sqlGeometryType;
                    }
                    fail("unsupported SQL geometry method", e.token);
                }
                if (receiver == ValueType.sqlDateType) {
                    if (["toInt", "minute", "hour", "day", "month", "year"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_date_" ~ e.token.text; return ValueType.sqlIntType;
                    }
                    if (["truncDay", "truncHour", "truncMinute", "truncSecond"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_date_" ~ e.token.text; return ValueType.sqlDateType;
                    }
                    if (["addDay", "addHour", "addMinute", "addSecond"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.sqlIntType]); e.builtinCall = "z8_sql_date_" ~ e.token.text; return ValueType.sqlDateType;
                    }
                    fail("unsupported SQL date method", e.token);
                }
                if (receiver == ValueType.sqlDatespanType) {
                    if (["days", "hours", "minutes", "seconds", "totalHours", "totalMinutes", "totalSeconds"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_datespan_" ~ e.token.text; return ValueType.sqlIntType;
                    }
                    if (["truncHour", "truncMinute", "truncSecond"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_datespan_" ~ e.token.text; return ValueType.sqlDatespanType;
                    }
                    if (["addDay", "addHour", "addMinute", "addSecond"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.sqlIntType]); e.builtinCall = "z8_sql_datespan_" ~ e.token.text; return ValueType.sqlDatespanType;
                    }
                    fail("unsupported SQL datespan method", e.token);
                }
                if (receiver == ValueType.sqlDecimalType) {
                    if (["abs", "exp", "ln"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_decimal_" ~ e.token.text; return ValueType.sqlDecimalType;
                    }
                    if (["sign", "ceil", "floor"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_decimal_" ~ e.token.text; return ValueType.sqlIntType;
                    }
                    if (e.token.text == "isNaN") {
                        checkArguments(e, []); e.builtinCall = "z8_sql_decimal_isNaN"; return ValueType.sqlBoolType;
                    }
                    if (["power", "round", "truncate"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.sqlIntType]); e.builtinCall = "z8_sql_decimal_" ~ e.token.text; return ValueType.sqlDecimalType;
                    }
                    fail("unsupported SQL decimal method", e.token);
                }
                if (receiver == ValueType.sqlStringType) {
                    if (["toLower", "toUpper", "trimLeft", "trimRight", "trimAll", "reverse", "quote", "toString"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_string_" ~ e.token.text; return ValueType.sqlStringType;
                    }
                    if (e.token.text == "json") {
                        if (e.arguments.length != 1) fail("incorrect argument count", e.token);
                        auto argument = typeOf(e.arguments[0]);
                        if (argument == ValueType.nullType) fail("ambiguous SQL json overload", e.token);
                        bool numeric = [ValueType.intType, ValueType.optionalInt, ValueType.sqlIntType].canFind(argument);
                        checkArguments(e, [numeric ? ValueType.sqlIntType : ValueType.sqlStringType]);
                        e.builtinCall = numeric ? "z8_sql_string_jsonInt" : "z8_sql_string_jsonString"; return ValueType.sqlStringType;
                    }
                    if (e.token.text == "replace" || e.token.text == "replaceAll") {
                        if (e.token.text == "replaceAll" && e.arguments.length == 3)
                            checkArguments(e, [ValueType.sqlStringType, ValueType.sqlStringType, ValueType.sqlStringType]);
                        else checkArguments(e, [ValueType.sqlStringType, ValueType.sqlStringType]);
                        e.builtinCall = "z8_sql_string_" ~ e.token.text; return ValueType.sqlStringType;
                    }
                    if (e.token.text == "substring") {
                        checkArguments(e, [ValueType.sqlIntType, ValueType.sqlIntType]);
                        e.builtinCall = "z8_sql_string_substring"; return ValueType.sqlStringType;
                    }
                    if (e.token.text == "padLeft" || e.token.text == "padRight") {
                        checkArguments(e, e.arguments.length == 2 ? [ValueType.sqlIntType, ValueType.sqlStringType] : [ValueType.sqlIntType]);
                        e.builtinCall = "z8_sql_string_" ~ e.token.text; return ValueType.sqlStringType;
                    }
                    if (e.token.text == "like" || e.token.text == "regLike") {
                        checkArguments(e, e.token.text == "like" && e.arguments.length == 2 ? [ValueType.sqlStringType, ValueType.sqlStringType] : [ValueType.sqlStringType]);
                        e.builtinCall = "z8_sql_string_" ~ e.token.text; return ValueType.sqlBoolType;
                    }
                    if (e.token.text == "length") {
                        checkArguments(e, []); e.builtinCall = "z8_sql_string_length"; return ValueType.sqlIntType;
                    }
                    if (e.token.text == "isEmpty") {
                        checkArguments(e, []); e.builtinCall = "z8_sql_string_isEmpty"; return ValueType.sqlBoolType;
                    }
                    if (["isInt", "isNumeric"].canFind(e.token.text)) {
                        checkArguments(e, []); e.builtinCall = "z8_sql_string_" ~ e.token.text; return ValueType.sqlBoolType;
                    }
                    if (e.token.text == "toInt" || e.token.text == "toDecimal") {
                        checkArguments(e, []); e.builtinCall = "z8_sql_string_" ~ e.token.text;
                        return e.token.text == "toInt" ? ValueType.sqlIntType : ValueType.sqlDecimalType;
                    }
                    if (e.token.text == "toDate") {
                        checkArguments(e, []); e.builtinCall = "z8_sql_string_toDate"; return ValueType.sqlDateType;
                    }
                    if (e.token.text == "indexOf" || e.token.text == "contains") {
                        checkArguments(e, e.arguments.length == 2 ? [ValueType.sqlStringType, ValueType.sqlIntType] : [ValueType.sqlStringType]);
                        e.builtinCall = "z8_sql_string_" ~ e.token.text;
                        return e.token.text == "indexOf" ? ValueType.sqlIntType : ValueType.sqlBoolType;
                    }
                    if (e.token.text == "patIndexOf") {
                        checkArguments(e, [ValueType.sqlStringType]);
                        e.builtinCall = "z8_sql_string_patIndexOf"; return ValueType.sqlIntType;
                    }
                    if (["ftsLike", "ftsRank"].canFind(e.token.text)) {
                        checkArguments(e, e.arguments.length == 2 ? [ValueType.sqlStringType, ValueType.ftsType] : [ValueType.sqlStringType]);
                        e.builtinCall = "z8_sql_string_" ~ e.token.text;
                        return e.token.text == "ftsLike" ? ValueType.sqlBoolType : ValueType.sqlDecimalType;
                    }
                    fail("unsupported SQL string method", e.token);
                }
                if (receiver == ValueType.optionalInt) {
                    e.optionalIntReceiver = true;
                    receiver = ValueType.intType;
                }
                if (receiver == ValueType.optionalBool) {
                    e.optionalBoolReceiver = true;
                    receiver = ValueType.boolType;
                }
                if (receiver == ValueType.optionalDecimal) {
                    e.optionalDecimalReceiver = true;
                    receiver = ValueType.decimalType;
                }
                if (receiver == ValueType.nullableString) {
                    e.nullableStringReceiver = true;
                    receiver = ValueType.stringType;
                }
                e.inferredType = receiver;
                if (receiver == ValueType.fileType) {
                    if (e.token.text == "zip" || e.token.text == "unzip") {
                        checkArguments(e, e.token.text == "unzip" && e.arguments.length == 2 ?
                            [ValueType.fileType, ValueType.encodingType] : [ValueType.fileType]);
                        e.builtinCall = "z8_file_" ~ e.token.text; return ValueType.fileType;
                    }
                    if (["write", "append"].canFind(e.token.text)) {
                        if (e.arguments.length != 1 && e.arguments.length != 2) fail("incorrect argument count", e.token);
                        auto contentType = typeOf(e.arguments[0]);
                        auto expectedContent = contentType == ValueType.binaryType ? ValueType.binaryType : ValueType.stringType;
                        if (!matches(e.arguments[0], expectedContent)) fail("argument type mismatch", e.token);
                        if (e.arguments.length == 2 && (expectedContent != ValueType.stringType || !matches(e.arguments[1], ValueType.encodingType))) fail("argument type mismatch", e.token);
                        e.builtinCall = "z8_file_" ~ e.token.text; return ValueType.fileType;
                    }
                    if (e.token.text == "read" && e.arguments.length == 1) {
                        checkArguments(e, [ValueType.encodingType]); e.builtinCall = "z8_file_read"; return ValueType.stringType;
                    }
                    if (e.token.text == "delete") {
                        checkArguments(e, e.arguments.length == 0 ? [] : [ValueType.boolType]);
                        e.builtinCall = "z8_file_delete"; return ValueType.voidType;
                    }
                    checkArguments(e, []);
                    if (["exists", "isEmpty", "isFolder"].canFind(e.token.text)) {
                        e.builtinCall = "z8_file_" ~ e.token.text; return ValueType.boolType;
                    }
                    if (e.token.text == "binary") { e.builtinCall = "z8_file_to_binary"; return ValueType.binaryType; }
                    if (e.token.text == "string") { e.builtinCall = "z8_file_path"; return ValueType.stringType; }
                    if (e.token.text == "read") { e.builtinCall = "z8_file_read"; return ValueType.stringType; }
                    if (e.token.text == "lastModified") { e.builtinCall = "z8_file_lastModified"; return ValueType.dateType; }
                    if (e.token.text == "hashCode") { e.builtinCall = "z8_file_hashCode"; return ValueType.intType; }
                    if (e.token.text == "toString") { e.builtinCall = "z8_file_to_string"; return ValueType.stringType; }
                    if (e.token.text == "parent") { e.builtinCall = "z8_file_parent"; return ValueType.fileType; }
                    if (e.token.text == "listFiles") { e.builtinCall = "z8_file_listFiles"; return ValueType.fileArray; }
                    if (["fileName", "baseName", "extension", "folder"].canFind(e.token.text)) {
                        e.builtinCall = "z8_file_" ~ e.token.text ~ (e.token.text == "baseName" || e.token.text == "extension" ? "_instance" : "");
                        return ValueType.stringType;
                    }
                    fail("unsupported file method", e.token);
                }
                if (receiver == ValueType.geometryType) {
                    checkArguments(e, []);
                    if (e.token.text == "shape" || e.token.text == "srs" || e.token.text == "hashCode") {
                        e.builtinCall = "z8_geometry_" ~ e.token.text; return ValueType.intType;
                    }
                    if (["x", "y", "x1", "y1", "x2", "y2", "width", "height", "length"].canFind(e.token.text)) {
                        e.builtinCall = "z8_geometry_" ~ e.token.text; return ValueType.decimalType;
                    }
                    if (e.token.text == "center") { e.builtinCall = "z8_geometry_center"; return ValueType.geometryType; }
                    if (e.token.text == "extent") { e.builtinCall = "z8_geometry_extent"; return ValueType.decimalMatrix; }
                    if (e.token.text == "points") { e.builtinCall = "z8_geometry_points"; return ValueType.geometryArray; }
                    if (e.token.text == "toString") { e.builtinCall = "z8_geometry_to_string"; return ValueType.stringType; }
                    if (e.token.text == "toGeoJson") { e.builtinCall = "z8_geometry_toGeoJson"; return ValueType.stringType; }
                    fail("unsupported geometry method", e.token);
                }
                if (receiver == ValueType.dateType) {
                    if (e.token.text == "toString" && e.arguments.length == 1) {
                        checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_date_toString"; return ValueType.stringType;
                    }
                    if (e.token.text == "setZoneOffset") {
                        checkArguments(e, [ValueType.intType]); e.builtinCall = "z8_date_setZoneOffset"; return ValueType.voidType;
                    }
                    if (["set", "setDate", "setTime"].canFind(e.token.text)) {
                        auto count = e.arguments.length;
                        if ((e.token.text == "set" && count != 6 && count != 7) ||
                            (e.token.text == "setDate" && count != 3) ||
                            (e.token.text == "setTime" && count != 3 && count != 4))
                            fail("incorrect argument count", e.token);
                        foreach (argument; e.arguments) if (!matches(argument, ValueType.intType)) fail("argument type mismatch", argument.token);
                        e.builtinCall = "z8_date_" ~ e.token.text; return ValueType.voidType;
                    }
                    if (["addYear", "addQuarter", "addMonth", "addDay", "addHour", "addMinute", "addSecond", "addMillisecond"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.intType]); e.builtinCall = "z8_date_" ~ e.token.text; return ValueType.dateType;
                    }
                    checkArguments(e, []);
                    if (["ticks", "year", "quarter", "month", "weekOfYear", "day", "dayOfWeek", "dayOfYear", "daysInMonth", "hours", "minutes", "seconds", "milliseconds", "zoneOffset", "hashCode"].canFind(e.token.text)) {
                        e.builtinCall = "z8_date_" ~ e.token.text; return ValueType.intType;
                    }
                    if (["truncYear", "truncQuarter", "truncMonth", "truncDay", "truncHour", "truncMinute", "truncSecond"].canFind(e.token.text)) {
                        e.builtinCall = "z8_date_" ~ e.token.text; return ValueType.dateType;
                    }
                    if (e.token.text == "toString" || e.token.text == "toIsoString") {
                        e.builtinCall = "z8_date_" ~ e.token.text; return ValueType.stringType;
                    }
                    fail("unsupported date method", e.token);
                }
                if (receiver == ValueType.datespanType) {
                    if (e.token.text == "set") {
                        if (![1, 4, 5].canFind(e.arguments.length)) fail("incorrect argument count", e.token);
                        foreach (argument; e.arguments) if (!matches(argument, ValueType.intType)) fail("argument type mismatch", argument.token);
                        e.builtinCall = "z8_datespan_set"; return ValueType.voidType;
                    }
                    if (["setTotalHours", "setTotalMinutes", "setTotalSeconds"].canFind(e.token.text)) {
                        checkArguments(e, [ValueType.intType]); e.builtinCall = "z8_datespan_" ~ e.token.text; return ValueType.voidType;
                    }
                    if (e.token.text == "toString") {
                        checkArguments(e, e.arguments.length == 0 ? [] : [ValueType.stringType]);
                        e.builtinCall = "z8_datespan_to_string"; return ValueType.stringType;
                    }
                    checkArguments(e, []);
                    if (["days", "hours", "minutes", "seconds", "milliseconds", "totalHours", "totalMinutes", "totalSeconds", "hashCode"].canFind(e.token.text)) {
                        e.builtinCall = "z8_datespan_" ~ e.token.text; return ValueType.intType;
                    }
                    if (["truncDay", "truncHour", "truncMinute"].canFind(e.token.text)) {
                        e.builtinCall = "z8_datespan_" ~ e.token.text; return ValueType.voidType;
                    }
                    fail("unsupported datespan method", e.token);
                }
                if (receiver == ValueType.binaryType) {
                    if (e.token.text == "unzip") {
                        checkArguments(e, e.arguments.length == 2 ? [ValueType.fileType, ValueType.encodingType] : [ValueType.fileType]);
                        e.builtinCall = "z8_binary_unzip"; return ValueType.voidType;
                    }
                    if (e.token.text == "setName") {
                        checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_binary_set_name"; return ValueType.binaryType;
                    }
                    checkArguments(e, []);
                    if (e.token.text == "getName") { e.builtinCall = "z8_binary_get_name"; return ValueType.nullableString; }
                    if (e.token.text == "getBaseName" || e.token.text == "getExtension" || e.token.text == "toString") {
                        e.builtinCall = e.token.text == "getBaseName" ? "z8_binary_base_name" : e.token.text == "getExtension" ? "z8_binary_extension" : "z8_binary_to_string";
                        return ValueType.stringType;
                    }
                    if (e.token.text == "length") { e.builtinCall = "z8_binary_length"; return ValueType.intType; }
                    if (e.token.text == "hashCode") { e.builtinCall = "z8_binary_hash"; return ValueType.intType; }
                    fail("unsupported binary method", e.token);
                }
                if (receiver == ValueType.guidType) {
                    checkArguments(e, []);
                    if (e.token.text == "toString") { e.builtinCall = "z8_guid_to_string"; return ValueType.stringType; }
                    if (e.token.text == "hashCode") { e.builtinCall = "z8_guid_hash"; return ValueType.intType; }
                    if (e.token.text == "major" || e.token.text == "minor") { e.builtinCall = "z8_guid_" ~ e.token.text; return ValueType.intType; }
                    if (e.token.text == "components") { e.builtinCall = "z8_guid_components"; return ValueType.intArray; }
                    fail("unsupported guid method", e.token);
                }
                if ([ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType].canFind(receiver) && e.token.text == "hashCode") {
                    checkArguments(e, []); e.builtinCall = "z8_primary_hash_value"; return ValueType.intType;
                }
                if (receiver == ValueType.selfType) {
                    auto owner = e.left.objectClass;
                    auto target = lookupMethod(owner, e.token.text);
                    if (target is null && !e.arguments.length) {
                        target = lookupMethod(owner, "operatorCast:" ~ e.token.text);
                        if (target !is null) e.namedConversion = target;
                    }
                    if (target is null && extendsBuiltinPrimary(owner) && ["toString", "hashCode"].canFind(e.token.text)) {
                        checkArguments(e, []);
                        e.builtinCall = e.token.text == "toString" ? "z8_user_primary_string" : "z8_user_primary_hash";
                        return e.token.text == "toString" ? ValueType.stringType : ValueType.intType;
                    }
                    if (target is null && extendsBuiltinException(owner) && ["string", "getMessage", "getStackTrace"].canFind(e.token.text)) {
                        checkArguments(e, []);
                        e.builtinCall = e.token.text == "getStackTrace" ? "z8_exception_object_stacktrace" : "z8_exception_object_message";
                        return ValueType.stringType;
                    }
                    if (target is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                    target = selectOverload(target, e);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    if (target.isStatic) {
                        e.staticInstanceCall = true;
                        e.targetClass = target.owner.emittedName;
                    } else e.instanceCall = true;
                    return checkCall(target, target.owner, e);
                } else if (receiver == ValueType.primaryType) {
                    checkArguments(e, []);
                    if (e.token.text == "toString") { e.builtinCall = "z8_primary_to_string"; return ValueType.stringType; }
                    if (e.token.text == "hashCode") { e.builtinCall = "z8_primary_hash"; return ValueType.intType; }
                } else if (receiver == ValueType.stringType) {
                    switch (e.token.text) {
                        case "setupMatcher":
                            checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_regex_setupMatcher"; return ValueType.voidType;
                        case "next":
                            checkArguments(e, []); e.builtinCall = "z8_regex_next"; return ValueType.boolType;
                        case "getGroup":
                            checkArguments(e, [ValueType.intType]); e.builtinCall = "z8_regex_getGroup"; return ValueType.nullableString;
                        case "matches":
                            checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_regex_matches"; return ValueType.boolType;
                        case "replaceFirst": case "replaceAll":
                            checkArguments(e, [ValueType.stringType, ValueType.stringType]);
                            e.builtinCall = "z8_regex_" ~ e.token.text; return ValueType.stringType;
                        case "split":
                            checkArguments(e, e.arguments.length == 1 ? [ValueType.stringType] : [ValueType.stringType, ValueType.intType]);
                            e.builtinCall = "z8_regex_split"; return ValueType.stringArray;
                        case "format":
                            checkArguments(e, [ValueType.primaryArray]); e.builtinCall = "z8_string_format"; return ValueType.stringType;
                        case "length": case "isEmpty": case "toString": case "trim": case "trimLeft": case "trimRight":
                        case "toLowerCase": case "toUpperCase": case "firstToLowerCase": case "firstToUpperCase":
                            checkArguments(e, []);
                            return e.token.text == "length" ? ValueType.intType : e.token.text == "isEmpty" ? ValueType.boolType : ValueType.stringType;
                        case "compare": case "compareNoCase": case "endsWith":
                            checkArguments(e, [ValueType.stringType]);
                            return e.token.text == "endsWith" ? ValueType.boolType : ValueType.intType;
                        case "indexOf": case "lastIndexOf": case "startsWith":
                            checkArguments(e, e.arguments.length == 1 ? [ValueType.stringType] : [ValueType.stringType, ValueType.intType]);
                            return e.token.text == "startsWith" ? ValueType.boolType : ValueType.intType;
                        case "substring":
                            checkArguments(e, e.arguments.length == 1 ? [ValueType.intType] : [ValueType.intType, ValueType.intType]);
                            return ValueType.stringType;
                        case "charAt": checkArguments(e, [ValueType.intType]); return ValueType.stringType;
                        case "left": case "right": checkArguments(e, [ValueType.intType]); return ValueType.stringType;
                        case "insert": checkArguments(e, [ValueType.intType, ValueType.stringType]); return ValueType.stringType;
                        case "replace": checkArguments(e, [ValueType.intType, ValueType.intType, ValueType.stringType]); return ValueType.stringType;
                        case "padLeft": case "padRight":
                            checkArguments(e, e.arguments.length == 1 ? [ValueType.intType] : [ValueType.intType, ValueType.stringType]);
                            return ValueType.stringType;
                        default: break;
                    }
                } else if (receiver == ValueType.intType) {
                    if (["sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "toRadians", "toDegrees", "exp", "ln", "log10", "sqrt", "cbrt"].canFind(e.token.text)) {
                        checkArguments(e, []); return ValueType.decimalType;
                    }
                    if (e.token.text == "power") { checkArguments(e, [ValueType.decimalType]); return ValueType.decimalType; }
                    switch (e.token.text) {
                        case "toString":
                            checkArguments(e, e.arguments.length ? [ValueType.intType] : []);
                            return ValueType.stringType;
                        case "toHexString": case "toBinaryString":
                            checkArguments(e, []); return ValueType.stringType;
                        case "abs": case "signum": case "not":
                            checkArguments(e, []); return ValueType.intType;
                        case "and": case "or": case "xor": case "leftShift": case "rightShift":
                            checkArguments(e, [ValueType.intType]); return ValueType.intType;
                        default: break;
                    }
                } else if (receiver == ValueType.boolType) {
                    checkArguments(e, []);
                    if (e.token.text == "toString") return ValueType.stringType;
                } else if (receiver == ValueType.exceptionType) {
                    if (e.arguments.length != 0) fail("incorrect argument count", e.token);
                    if (["string", "getMessage", "getStackTrace"].canFind(e.token.text)) return ValueType.stringType;
                } else if (receiver == ValueType.decimalType) {
                    if (e.token.text == "toString") { checkArguments(e, []); return ValueType.stringType; }
                    if (["abs", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "toRadians", "toDegrees", "exp", "ln", "log10", "sqrt", "cbrt"].canFind(e.token.text)) {
                        checkArguments(e, []); return ValueType.decimalType;
                    }
                    if (e.token.text == "power") { checkArguments(e, [ValueType.decimalType]); return ValueType.decimalType; }
                    if (["signum", "ceil", "floor"].canFind(e.token.text)) { checkArguments(e, []); return ValueType.intType; }
                    if (e.token.text == "round") {
                        if (e.arguments.length == 0) return ValueType.intType;
                        checkArguments(e, e.arguments.length == 1 ? [ValueType.intType] : [ValueType.intType, ValueType.intType]);
                        return ValueType.decimalType;
                    }
                } else if (isMap(receiver)) {
                    auto mapValue = mapValueType(receiver);
                    if (hasObjectClass(receiver)) e.objectClass = e.left.objectClass;
                    if (hasMapKeyClass(receiver)) e.keyObjectClasses = innerMapKeyClasses(receiver, e.left.keyObjectClasses);
                    switch (e.token.text) {
                        case "size": case "isEmpty": case "clear":
                            checkArguments(e, []);
                            return e.token.text == "size" ? ValueType.intType : e.token.text == "isEmpty" ? ValueType.boolType : ValueType.voidType;
                        case "containsKey": checkStoredArguments(e, [mapKeyType(receiver)], outerMapKeyClass(receiver, e.left.keyObjectClasses)); return ValueType.boolType;
                        case "containsValue":
                            if (e.arguments.length != 1 || !matchesStored(e.arguments[0], mapValue, e.left.objectClass, innerMapKeyClasses(receiver, e.left.keyObjectClasses))) fail("argument type mismatch", e.token);
                            return ValueType.boolType;
                        case "get":
                            checkStoredArguments(e, [mapKeyType(receiver)], outerMapKeyClass(receiver, e.left.keyObjectClasses)); return mapValueReadType(receiver);
                        case "remove":
                            checkStoredArguments(e, [mapKeyType(receiver)], outerMapKeyClass(receiver, e.left.keyObjectClasses)); return mapValueReadType(receiver);
                        case "add":
                            if (e.arguments.length == 1) {
                                if (!matches(e.arguments[0], receiver, e.left.objectClass, e.left.keyObjectClasses)) fail("argument type mismatch", e.token);
                                return ValueType.voidType;
                            }
                            if (e.arguments.length != 2 || !matchesStored(e.arguments[0], mapKeyType(receiver), outerMapKeyClass(receiver, e.left.keyObjectClasses)) || !matchesStored(e.arguments[1], mapValue, e.left.objectClass, innerMapKeyClasses(receiver, e.left.keyObjectClasses))) fail("argument type mismatch", e.token);
                            return mapValueReadType(receiver);
                        case "keys": checkArguments(e, []); e.objectClass = outerMapKeyClass(receiver, e.left.keyObjectClasses); return mapKeyArrayType(receiver);
                        case "values": checkArguments(e, []); return mapValueArrayType(receiver);
                        default: break;
                    }
                } else if (isArray(receiver)) {
                    if (isReferenceArray(receiver)) {
                        e.objectClass = e.left.objectClass;
                        e.keyObjectClasses = e.left.keyObjectClasses;
                        auto primaryJoin = e.token.text == "join" && [ValueType.guidArray, ValueType.binaryArray, ValueType.datespanArray,
                            ValueType.dateArray, ValueType.geometryArray, ValueType.fileArray, ValueType.primaryArray, ValueType.selfArray].canFind(receiver);
                        auto guidSort = receiver == ValueType.guidArray && e.token.text == "sort";
                        if (!primaryJoin && !guidSort && !["size", "isEmpty", "clear", "first", "last", "get", "add", "addAll", "removeAt", "set", "contains", "indexOf", "remove", "removeAll", "isSubsetOf", "reverse", "unique"].canFind(e.token.text))
                            fail("this method is not yet supported for object arrays", e.token);
                    }
                    switch (e.token.text) {
                        case "size": case "isEmpty": case "clear": case "reverse": case "sort": case "unique":
                            if (e.arguments.length != 0) fail("incorrect argument count", e.token);
                            return e.token.text == "size" ? ValueType.intType : e.token.text == "isEmpty" ? ValueType.boolType : e.token.text == "clear" ? ValueType.voidType : receiver;
                        case "join":
                            checkArguments(e, e.arguments.length ? [ValueType.stringType] : []);
                            return ValueType.stringType;
                        case "first": case "last":
                            checkArguments(e, []);
                            if (receiver == ValueType.stringArray) return ValueType.nullableString;
                            if (isReferenceArray(receiver)) return elementType(receiver);
                            return optionalForArray(receiver);
                        case "get":
                            if (e.arguments.length != 1 || !matches(e.arguments[0], ValueType.intType)) fail("get requires an int index", e.token);
                            return receiver == ValueType.stringArray ? ValueType.nullableString : storedValueType(elementType(receiver));
                        case "add":
                            if (e.arguments.length == 1) {
                                if (!matchesStored(e.arguments[0], elementType(receiver), e.left.objectClass, e.left.keyObjectClasses)) fail("add requires an element of the array type", e.token);
                            } else if (e.arguments.length == 2) {
                                if (!matches(e.arguments[0], ValueType.intType) || !matchesStored(e.arguments[1], elementType(receiver), e.left.objectClass, e.left.keyObjectClasses))
                                    fail("add requires an int index and an element of the array type", e.token);
                            } else fail("incorrect argument count", e.token);
                            return receiver;
                        case "addAll":
                            if (e.arguments.length == 1) {
                                if (!matches(e.arguments[0], receiver, e.left.objectClass, e.left.keyObjectClasses)) fail("addAll requires an array of the same type", e.token);
                            } else if (e.arguments.length == 2) {
                                if (!matches(e.arguments[0], ValueType.intType) || !matches(e.arguments[1], receiver, e.left.objectClass, e.left.keyObjectClasses)) fail("addAll requires an int index and an array of the same type", e.token);
                            } else fail("incorrect argument count", e.token);
                            return ValueType.voidType;
                        case "isSubsetOf":
                            if (e.arguments.length != 1 || !matches(e.arguments[0], receiver, e.left.objectClass, e.left.keyObjectClasses)) fail("isSubsetOf requires an array of the same type", e.token);
                            return ValueType.boolType;
                        case "removeAll":
                            if (e.arguments.length != 1) fail("incorrect argument count", e.token);
                            auto argType = typeOf(e.arguments[0]);
                            if (argType == receiver) {
                                if (!matches(e.arguments[0], receiver, e.left.objectClass, e.left.keyObjectClasses)) fail("removeAll requires an array of the same type", e.token);
                            } else if (!matchesStored(e.arguments[0], elementType(receiver), e.left.objectClass, e.left.keyObjectClasses)) fail("removeAll requires an element or array of the same type", e.token);
                            return receiver;
                        case "contains": case "indexOf": case "remove":
                            if (e.arguments.length != 1 || !matchesStored(e.arguments[0], elementType(receiver), e.left.objectClass, e.left.keyObjectClasses)) fail("method requires an element of the array type", e.token);
                            return e.token.text == "indexOf" ? ValueType.intType : ValueType.boolType;
                        case "removeAt":
                            if (e.arguments.length != 1 || !matches(e.arguments[0], ValueType.intType)) fail("removeAt requires an int index", e.token);
                            return receiver == ValueType.stringArray ? ValueType.nullableString : storedValueType(elementType(receiver));
                        case "set":
                            if (e.arguments.length != 2 || !matches(e.arguments[0], ValueType.intType) ||
                                !matchesStored(e.arguments[1], elementType(receiver), e.left.objectClass, e.left.keyObjectClasses)) fail("set requires an int index and an element of the array type", e.token);
                            return ValueType.voidType;
                        default: break;
                    }
                }
                fail("unsupported member method '" ~ e.token.text ~ "'", e.token); assert(0);
            case ExprKind.index:
                auto array = typeOf(e.left);
                if (isMap(array)) {
                    if (!matchesStored(e.right, mapKeyType(array), outerMapKeyClass(array, e.left.keyObjectClasses))) fail("map key type mismatch", e.token);
                    e.inferredType = array;
                    if (hasObjectClass(array)) e.objectClass = e.left.objectClass;
                    if (hasMapKeyClass(mapValueType(array))) e.keyObjectClasses = innerMapKeyClasses(array, e.left.keyObjectClasses);
                    return mapValueReadType(array);
                }
                if (!isArray(array)) fail("indexing requires an array", e.token);
                if (!matches(e.right, ValueType.intType)) fail("array index must be int", e.token);
                if (hasObjectClass(array)) e.objectClass = e.left.objectClass;
                if (hasMapKeyClass(array)) e.keyObjectClasses = e.left.keyObjectClasses;
                e.inferredType = array;
                return array == ValueType.stringArray ? ValueType.nullableString : storedValueType(elementType(array));
            case ExprKind.castExpr:
                if (typeOf(e.left) == ValueType.sqlPrimaryType && isSqlType(e.castType) && e.castType != ValueType.sqlPrimaryType) {
                    e.sqlPrimaryCast = true; return e.castType;
                }
                if (typeOf(e.left) == ValueType.primaryType && [ValueType.intType, ValueType.boolType, ValueType.decimalType,
                    ValueType.stringType, ValueType.guidType, ValueType.binaryType, ValueType.datespanType, ValueType.geometryType, ValueType.dateType, ValueType.fileType].canFind(e.castType)) {
                    e.primaryCast = true;
                    return e.castType == ValueType.stringType ? ValueType.nullableString : storedValueType(e.castType);
                }
                if (e.castType == ValueType.selfType) {
                    auto target = resolveClass(currentProgram, e.token.text, e.token);
                    if (target.isEnum) {
                        auto source = typeOf(e.left);
                        if (source == ValueType.selfType) {
                            auto conversion = findConversion(e.left.objectClass, ValueType.enumType, target);
                            if (conversion is null) fail("unsupported enum cast", e.token);
                            e.left.userConversion = conversion;
                        } else if (source != ValueType.nullType && (source != ValueType.enumType || e.left.objectClass !is target))
                            fail("unsupported enum cast", e.token);
                        e.castType = ValueType.enumType;
                        e.objectClass = target;
                        return ValueType.enumType;
                    }
                    if (typeOf(e.left) == ValueType.primaryType && extendsBuiltinPrimary(target)) {
                        e.primaryCast = true;
                        e.objectClass = target;
                        return ValueType.selfType;
                    }
                    if (typeOf(e.left) == ValueType.exceptionType && extendsBuiltinException(target)) {
                        e.exceptionObjectCast = true;
                        e.objectClass = target;
                        return ValueType.selfType;
                    }
                    if (typeOf(e.left) != ValueType.selfType) fail("unsupported object cast", e.token);
                    if (!isAssignable(e.left.objectClass, target)) {
                        auto conversion = findConversion(e.left.objectClass, ValueType.selfType, target);
                        if (conversion !is null) e.left.userConversion = conversion;
                        else if (!isAssignable(target, e.left.objectClass)) fail("unsupported object cast", e.token);
                    }
                    e.objectClass = target;
                    return ValueType.selfType;
                }
                if (e.castType == ValueType.intType || e.castType == ValueType.boolType || e.castType == ValueType.decimalType) {
                    if (!matchesStored(e.left, e.castType)) fail("unsupported type cast", e.token);
                    return storedValueType(e.castType);
                }
                if (!matches(e.left, e.castType)) fail("unsupported type cast", e.token);
                return e.castType;
            case ExprKind.instanceOf:
                auto sourceType = typeOf(e.left);
                ValueType targetType;
                switch (e.token.text) {
                    case "int": targetType = ValueType.intType; break;
                    case "bool": targetType = ValueType.boolType; break;
                    case "decimal": targetType = ValueType.decimalType; break;
                    case "string": targetType = ValueType.stringType; break;
                    case "guid": targetType = ValueType.guidType; break;
                    case "binary": targetType = ValueType.binaryType; break;
                    case "datespan": targetType = ValueType.datespanType; break;
                    case "geometry": targetType = ValueType.geometryType; break;
                    case "date": targetType = ValueType.dateType; break;
                    case "file": targetType = ValueType.fileType; break;
                    case "exception": targetType = ValueType.exceptionType; break;
                    case "encoding": targetType = ValueType.encodingType; break;
                    case "sql_bool": targetType = ValueType.sqlBoolType; break;
                    case "sql_int": targetType = ValueType.sqlIntType; break;
                    case "sql_decimal": targetType = ValueType.sqlDecimalType; break;
                    case "sql_string": targetType = ValueType.sqlStringType; break;
                    case "sql_guid": targetType = ValueType.sqlGuidType; break;
                    case "sql_date": targetType = ValueType.sqlDateType; break;
                    case "sql_datespan": targetType = ValueType.sqlDatespanType; break;
                    case "sql_binary": targetType = ValueType.sqlBinaryType; break;
                    case "sql_geometry": targetType = ValueType.sqlGeometryType; break;
                    case "sql_primary": targetType = ValueType.sqlPrimaryType; break;
                    case "primary": targetType = ValueType.primaryType; break;
                    default: targetType = ValueType.voidType; break;
                }
                if (targetType == ValueType.exceptionType && sourceType == ValueType.exceptionType) {
                    e.exceptionInstanceOf = true;
                    return ValueType.boolType;
                }
                if (targetType == ValueType.exceptionType && sourceType == ValueType.selfType && extendsBuiltinException(e.left.objectClass)) {
                    e.inferredType = sourceType;
                    e.scalarInstanceOf = true;
                    return ValueType.boolType;
                }
                if (isSqlType(sourceType) && isSqlType(targetType) && (sourceType == ValueType.sqlPrimaryType || targetType == ValueType.sqlPrimaryType)) {
                    e.sqlPrimaryInstanceOf = true; e.castType = targetType; return ValueType.boolType;
                }
                if (targetType != ValueType.voidType && targetType != ValueType.exceptionType && targetType != ValueType.encodingType && !isSqlType(targetType) && sourceType == ValueType.primaryType) {
                    e.castType = targetType; e.primaryInstanceOf = true;
                    return ValueType.boolType;
                }
                if (targetType == ValueType.primaryType && sourceType == ValueType.selfType && extendsBuiltinPrimary(e.left.objectClass)) {
                    e.inferredType = sourceType;
                    e.scalarInstanceOf = true;
                    return ValueType.boolType;
                }
                auto baseSource = isOptionalPrimitive(sourceType) ? optionalBaseType(sourceType) :
                    sourceType == ValueType.nullableString ? ValueType.stringType : sourceType;
                bool scalar = [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType,
                    ValueType.guidType, ValueType.binaryType, ValueType.datespanType, ValueType.geometryType,
                    ValueType.dateType, ValueType.fileType, ValueType.encodingType].canFind(baseSource) || isSqlType(baseSource);
                if (targetType != ValueType.voidType) {
                    if (sourceType == ValueType.voidType) fail("instanceof requires a value", e.token);
                    e.inferredType = sourceType;
                    e.falseInstanceOf = !scalar || (targetType == ValueType.primaryType && (baseSource == ValueType.encodingType || isSqlType(baseSource))) || (targetType != ValueType.primaryType && targetType != baseSource);
                    e.scalarInstanceOf = !e.falseInstanceOf;
                    return ValueType.boolType;
                }
                auto target = resolveClass(currentProgram, e.token.text, e.token);
                if (sourceType == ValueType.exceptionType && extendsBuiltinException(target)) {
                    e.objectClass = target;
                    e.exceptionObjectInstanceOf = true;
                    return ValueType.boolType;
                }
                if (sourceType == ValueType.primaryType && extendsBuiltinPrimary(target)) {
                    e.castType = ValueType.selfType;
                    e.objectClass = target;
                    e.primaryInstanceOf = true;
                    return ValueType.boolType;
                }
                if (scalar || sourceType == ValueType.primaryType || sourceType == ValueType.exceptionType || isArray(sourceType) || isMap(sourceType)) {
                    e.inferredType = sourceType;
                    e.falseInstanceOf = true;
                    return ValueType.boolType;
                }
                if (target.isEnum || sourceType == ValueType.enumType) {
                    if (![ValueType.selfType, ValueType.enumType, ValueType.nullType].canFind(sourceType))
                        fail("instanceof requires an object reference", e.token);
                    e.objectInstanceOf = true;
                    e.objectClass = target;
                    return ValueType.boolType;
                }
                if (sourceType != ValueType.selfType && sourceType != ValueType.nullType)
                    fail("instanceof requires an object reference", e.token);
                if (sourceType == ValueType.selfType && !isAssignable(e.left.objectClass, target) && !isAssignable(target, e.left.objectClass))
                    e.objectInstanceOf = true;
                e.objectClass = target;
                return ValueType.boolType;
            case ExprKind.unary:
                auto operand = typeOf(e.left);
                if (operand == ValueType.sqlBoolType && e.token.text == "!") { e.sqlBoolOperator = true; return ValueType.sqlBoolType; }
                if (operand == ValueType.sqlIntType && ["+", "-", "~"].canFind(e.token.text)) { e.sqlIntOperator = true; return ValueType.sqlIntType; }
                if (operand == ValueType.sqlDecimalType && ["+", "-"].canFind(e.token.text)) { e.sqlDecimalOperator = true; return ValueType.sqlDecimalType; }
                if (operand == ValueType.selfType && ["!", "~", "-"].canFind(e.token.text)) {
                    auto method = lookupUnaryOperator(e.left.objectClass, "operator" ~ e.token.text);
                    if (method is null) {
                        ValueType[] targets = e.token.text == "!" ? [ValueType.boolType, ValueType.sqlBoolType] :
                            e.token.text == "~" ? [ValueType.intType, ValueType.sqlIntType] :
                            [ValueType.intType, ValueType.decimalType, ValueType.sqlIntType, ValueType.sqlDecimalType];
                        Method conversion;
                        ValueType convertedType;
                        foreach (target; targets) {
                            auto candidate = findConversion(e.left.objectClass, target);
                            if (candidate is null) continue;
                            if (conversion !is null) fail("ambiguous unary operator", e.token);
                            conversion = candidate; convertedType = target;
                        }
                        if (conversion is null) fail("undefined unary operator", e.token);
                        e.left.userConversion = conversion;
                        if (convertedType == ValueType.sqlBoolType) e.sqlBoolOperator = true;
                        else if (convertedType == ValueType.sqlIntType) e.sqlIntOperator = true;
                        else if (convertedType == ValueType.sqlDecimalType) e.sqlDecimalOperator = true;
                        else e.left.optionalRequired = true;
                        return convertedType;
                    }
                    auto selected = selectOverload(method, e);
                    e.userUnaryOperator = true;
                    return checkCall(selected, selected.owner, e);
                }
                if (operand == ValueType.optionalInt && ["+", "-", "~"].canFind(e.token.text)) {
                    e.optionalIntUnary = true;
                    return ValueType.intType;
                }
                if (["+", "-"].canFind(e.token.text) && operand == ValueType.optionalDecimal) { e.optionalDecimalUnary = true; return ValueType.decimalType; }
                if (e.token.text == "!" && operand == ValueType.optionalBool) { e.optionalBoolUnary = true; return ValueType.boolType; }
                if (e.token.text == "!" && operand == ValueType.boolType) return operand;
                if (["+", "-", "~"].canFind(e.token.text) && operand == ValueType.intType) return operand;
                if (["+", "-"].canFind(e.token.text) && operand == ValueType.decimalType) return operand;
                fail("invalid unary operand", e.token); assert(0);
            case ExprKind.binary:
                auto left = typeOf(e.left), right = typeOf(e.right), op = e.token.text;
                if (left == ValueType.selfType && right != ValueType.nullType) {
                    auto method = lookupMethod(e.left.objectClass, "operator" ~ op);
                    if (method !is null) {
                        e.arguments = [e.right];
                        auto selected = selectOverload(method, e, true, true);
                        if (selected !is null) {
                            e.userBinaryOperator = true;
                            return checkCall(selected, selected.owner, e);
                        }
                    }
                    Method selectedConversion;
                    ValueType selectedRight;
                    foreach (target; [ValueType.sqlBoolType, ValueType.sqlIntType, ValueType.sqlDecimalType,
                                      ValueType.sqlStringType, ValueType.sqlGuidType, ValueType.sqlDateType,
                                      ValueType.sqlDatespanType, ValueType.sqlGeometryType]) {
                        auto conversion = findConversion(e.left.objectClass, target);
                        if (conversion is null) continue;
                        auto operand = sqlBinaryOperand(target, e.right, right, op);
                        if (operand == ValueType.voidType) continue;
                        if (selectedConversion !is null) fail("ambiguous binary operator", e.token);
                        selectedConversion = conversion; selectedRight = operand;
                    }
                    if (selectedConversion !is null) {
                        foreach (target; [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType,
                                         ValueType.guidType, ValueType.dateType, ValueType.datespanType, ValueType.fileType])
                            if (findConversion(e.left.objectClass, target) !is null &&
                                convertedBinaryOperand(target, e.right, right, op) != ValueType.voidType)
                                fail("ambiguous binary operator", e.token);
                        e.left.userConversion = selectedConversion;
                        left = selectedConversion.returnType;
                        if (right == ValueType.selfType) {
                            if (!matches(e.right, selectedRight)) fail("invalid SQL operands", e.token);
                            right = selectedRight;
                        }
                    }
                }
                if (right == ValueType.selfType &&
                    [ValueType.intType, ValueType.optionalInt, ValueType.boolType, ValueType.optionalBool,
                     ValueType.decimalType, ValueType.optionalDecimal, ValueType.stringType, ValueType.nullableString,
                     ValueType.guidType, ValueType.dateType, ValueType.datespanType, ValueType.fileType,
                     ValueType.geometryType].canFind(left)) {
                    auto plainLeft = isOptionalPrimitive(left) ? optionalBaseType(left) :
                        left == ValueType.nullableString ? ValueType.stringType : left;
                    auto operand = convertedBinaryOperand(plainLeft, e.right, right, op);
                    if (operand == ValueType.voidType) {
                        ValueType sqlLeft;
                        switch (plainLeft) {
                            case ValueType.boolType: sqlLeft = ValueType.sqlBoolType; break;
                            case ValueType.intType: sqlLeft = ValueType.sqlIntType; break;
                            case ValueType.decimalType: sqlLeft = ValueType.sqlDecimalType; break;
                            case ValueType.stringType: sqlLeft = ValueType.sqlStringType; break;
                            case ValueType.guidType: sqlLeft = ValueType.sqlGuidType; break;
                            case ValueType.dateType: sqlLeft = ValueType.sqlDateType; break;
                            case ValueType.datespanType: sqlLeft = ValueType.sqlDatespanType; break;
                            case ValueType.geometryType: sqlLeft = ValueType.sqlGeometryType; break;
                            default: break;
                        }
                        if (sqlLeft != ValueType.voidType) operand = sqlBinaryOperand(sqlLeft, e.right, right, op);
                    }
                    if (operand != ValueType.voidType) {
                        if (!matches(e.right, operand)) fail("invalid binary operands", e.token);
                        right = operand;
                    }
                }
                if ([ValueType.boolType, ValueType.optionalBool].canFind(left) && right == ValueType.sqlBoolType) {
                    matches(e.left, ValueType.sqlBoolType); left = ValueType.sqlBoolType;
                }
                if ([ValueType.intType, ValueType.optionalInt].canFind(left) && right == ValueType.sqlIntType) {
                    matches(e.left, ValueType.sqlIntType); left = ValueType.sqlIntType;
                }
                if ([ValueType.intType, ValueType.optionalInt].canFind(left) && right == ValueType.sqlDecimalType) {
                    matches(e.left, ValueType.sqlIntType); left = ValueType.sqlIntType;
                }
                if ([ValueType.decimalType, ValueType.optionalDecimal].canFind(left) && [ValueType.sqlIntType, ValueType.sqlDecimalType].canFind(right)) {
                    matches(e.left, ValueType.sqlDecimalType); left = ValueType.sqlDecimalType;
                }
                if ([ValueType.stringType, ValueType.nullableString].canFind(left) && right == ValueType.sqlStringType) {
                    matches(e.left, ValueType.sqlStringType); left = ValueType.sqlStringType;
                }
                if (left == ValueType.guidType && right == ValueType.sqlGuidType) {
                    matches(e.left, ValueType.sqlGuidType); left = ValueType.sqlGuidType;
                }
                if (left == ValueType.geometryType && right == ValueType.sqlGeometryType) {
                    matches(e.left, ValueType.sqlGeometryType); left = ValueType.sqlGeometryType;
                }
                if (left == ValueType.sqlGeometryType && right != ValueType.nullType) {
                    if (!["==", "!=", "&&"].canFind(op) || !matches(e.right, ValueType.sqlGeometryType)) fail("invalid SQL geometry operands", e.token);
                    e.sqlGeometryOperator = true; return ValueType.sqlBoolType;
                }
                if (left == ValueType.dateType && right == ValueType.sqlDateType) {
                    matches(e.left, ValueType.sqlDateType); left = ValueType.sqlDateType;
                }
                if (left == ValueType.datespanType && [ValueType.sqlDatespanType, ValueType.sqlDateType].canFind(right)) {
                    matches(e.left, ValueType.sqlDatespanType); left = ValueType.sqlDatespanType;
                }
                if (left == ValueType.dateType && right == ValueType.sqlDatespanType) {
                    matches(e.left, ValueType.sqlDateType); left = ValueType.sqlDateType;
                }
                if (left == ValueType.sqlDateType && (right == ValueType.sqlDatespanType || right == ValueType.datespanType)) {
                    if (!["+", "-"].canFind(op) || !matches(e.right, ValueType.sqlDatespanType)) fail("invalid SQL date arithmetic", e.token);
                    e.sqlDateArithmetic = true; return ValueType.sqlDateType;
                }
                if (left == ValueType.sqlDateType && [ValueType.sqlDateType, ValueType.dateType].canFind(right) && op == "-") {
                    if (!matches(e.right, ValueType.sqlDateType)) fail("invalid SQL date arithmetic", e.token);
                    e.sqlDateArithmetic = true; return ValueType.sqlDatespanType;
                }
                if (left == ValueType.sqlDatespanType && [ValueType.sqlDateType, ValueType.dateType].canFind(right)) {
                    if (op != "+" || !matches(e.right, ValueType.sqlDateType)) fail("invalid SQL date arithmetic", e.token);
                    e.sqlDateArithmetic = true; return ValueType.sqlDateType;
                }
                if (left == ValueType.sqlDatespanType && right != ValueType.nullType) {
                    if (!["+", "-", "==", "!=", "<", ">", "<=", ">="].canFind(op) || !matches(e.right, ValueType.sqlDatespanType)) fail("invalid SQL datespan operands", e.token);
                    e.sqlDatespanOperator = true; e.sqlDatespanComparison = op != "+" && op != "-";
                    return e.sqlDatespanComparison ? ValueType.sqlBoolType : ValueType.sqlDatespanType;
                }
                if (left == ValueType.sqlDateType && right != ValueType.nullType) {
                    if (!["==", "!=", "<", ">", "<=", ">="].canFind(op) || !matches(e.right, ValueType.sqlDateType)) fail("invalid SQL date operands", e.token);
                    e.sqlDateOperator = true; return ValueType.sqlBoolType;
                }
                if (left == ValueType.sqlGuidType && right != ValueType.nullType) {
                    if (!["==", "!="].canFind(op) || !matches(e.right, ValueType.sqlGuidType)) fail("invalid SQL guid operands", e.token);
                    e.sqlGuidOperator = true; return ValueType.sqlBoolType;
                }
                if (left == ValueType.sqlBoolType && right != ValueType.nullType) {
                    if (!["&&", "||", "==", "!="].canFind(op) || !matches(e.right, ValueType.sqlBoolType))
                        fail("invalid SQL boolean operands", e.token);
                    e.sqlBoolOperator = true; return ValueType.sqlBoolType;
                }
                if (left == ValueType.sqlStringType && right != ValueType.nullType) {
                    if (!["+", "==", "!=", "<", ">", "<=", ">="].canFind(op) || !matches(e.right, ValueType.sqlStringType))
                        fail("invalid SQL string operands", e.token);
                    e.sqlStringOperator = true;
                    e.sqlStringComparison = op != "+";
                    return e.sqlStringComparison ? ValueType.sqlBoolType : ValueType.sqlStringType;
                }
                if ((left == ValueType.sqlDecimalType && right != ValueType.nullType) ||
                    (left == ValueType.sqlIntType && [ValueType.sqlDecimalType, ValueType.decimalType, ValueType.optionalDecimal].canFind(right))) {
                    if (!["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="].canFind(op)) fail("invalid SQL decimal operands", e.token);
                    auto target = [ValueType.sqlIntType, ValueType.intType, ValueType.optionalInt].canFind(right) ? ValueType.sqlIntType : ValueType.sqlDecimalType;
                    if (!matches(e.right, target)) fail("invalid SQL decimal operands", e.token);
                    e.sqlDecimalOperator = true;
                    e.sqlDecimalComparison = ["==", "!=", "<", ">", "<=", ">="].canFind(op);
                    return e.sqlDecimalComparison ? ValueType.sqlBoolType : ValueType.sqlDecimalType;
                }
                if (left == ValueType.sqlIntType && right != ValueType.nullType) {
                    if (!["+", "-", "*", "/", "%", "&", "|", "^", "==", "!=", "<", ">", "<=", ">="].canFind(op) || !matches(e.right, ValueType.sqlIntType))
                        fail("invalid SQL integer operands", e.token);
                    e.sqlIntOperator = true;
                    e.sqlIntComparison = ["==", "!=", "<", ">", "<=", ">="].canFind(op);
                    return e.sqlIntComparison ? ValueType.sqlBoolType : ValueType.sqlIntType;
                }
                if (left == ValueType.selfType && right != ValueType.nullType) {
                    auto method = lookupMethod(e.left.objectClass, "operator" ~ op);
                    Method selected;
                    if (method !is null) {
                        e.arguments = [e.right];
                        selected = selectOverload(method, e, true, true);
                    }
                    if (selected !is null) {
                        e.userBinaryOperator = true;
                        return checkCall(selected, selected.owner, e);
                    }
                    Method conversion;
                    ValueType convertedRight;
                    foreach (target; [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType,
                                     ValueType.guidType, ValueType.dateType, ValueType.datespanType, ValueType.fileType]) {
                        auto candidate = findConversion(e.left.objectClass, target);
                        if (candidate is null) continue;
                        auto operand = convertedBinaryOperand(target, e.right, right, op);
                        if (operand == ValueType.voidType) continue;
                        if (conversion !is null) fail("ambiguous binary operator", e.token);
                        conversion = candidate; convertedRight = operand;
                    }
                    if (conversion is null) fail("undefined binary operator", e.token);
                    e.left.userConversion = conversion;
                    left = conversion.returnType == ValueType.stringType ? ValueType.nullableString : storedValueType(conversion.returnType);
                    if (right == ValueType.selfType) {
                        if (!matches(e.right, convertedRight)) fail("invalid binary operands", e.token);
                        right = convertedRight;
                    }
                }
                if (((left == ValueType.intType || left == ValueType.boolType || left == ValueType.decimalType) && right == ValueType.nullType) ||
                    ((right == ValueType.intType || right == ValueType.boolType || right == ValueType.decimalType) && left == ValueType.nullType)) {
                    if (right == ValueType.nullType) { e.left.optionalWrap = true; left = storedValueType(left); }
                    else { e.right.optionalWrap = true; right = storedValueType(right); }
                }
                if ((isOptionalPrimitive(left) && right == ValueType.nullType) ||
                    (isOptionalPrimitive(right) && left == ValueType.nullType)) {
                    if (!["==", "!="].canFind(op)) fail("null supports only equality comparisons", e.token);
                    e.optionalNullComparison = true;
                    e.optionalNullOnLeft = left == ValueType.nullType;
                    return ValueType.boolType;
                }
                if ((left == ValueType.optionalBool || left == ValueType.boolType) &&
                    (right == ValueType.optionalBool || right == ValueType.boolType) &&
                    (left == ValueType.optionalBool || right == ValueType.optionalBool) &&
                    ["==", "!=", "&&", "||"].canFind(op)) {
                    e.optionalBoolBinary = true; e.optionalBoolLeft = left == ValueType.optionalBool; e.optionalBoolRight = right == ValueType.optionalBool;
                    return ValueType.boolType;
                }
                if ((left == ValueType.optionalInt || left == ValueType.intType) &&
                    (right == ValueType.optionalInt || right == ValueType.intType) &&
                    (left == ValueType.optionalInt || right == ValueType.optionalInt) &&
                    ["==", "!=", "<", ">", "<=", ">=", "+", "-", "*", "/", "%", "&", "|", "^"].canFind(op)) {
                    e.optionalIntBinary = true;
                    e.optionalIntLeft = left == ValueType.optionalInt;
                    e.optionalIntRight = right == ValueType.optionalInt;
                    if (["==", "!=", "<", ">", "<=", ">="].canFind(op)) return ValueType.boolType;
                    return ValueType.intType;
                }
                if ((left == ValueType.optionalDecimal || left == ValueType.decimalType) &&
                    (right == ValueType.optionalDecimal || right == ValueType.decimalType) &&
                    (left == ValueType.optionalDecimal || right == ValueType.optionalDecimal)) {
                    if (!["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="].canFind(op)) fail("invalid binary operands", e.token);
                    e.optionalDecimalBinary = true; e.optionalDecimalLeft = left == ValueType.optionalDecimal; e.optionalDecimalRight = right == ValueType.optionalDecimal;
                    return ["==", "!=", "<", ">", "<=", ">="].canFind(op) ? ValueType.boolType : ValueType.decimalType;
                }
                if (((left == ValueType.optionalInt || left == ValueType.intType) && (right == ValueType.optionalDecimal || right == ValueType.decimalType)) ||
                    ((left == ValueType.optionalDecimal || left == ValueType.decimalType) && (right == ValueType.optionalInt || right == ValueType.intType))) {
                    if (!["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="].canFind(op)) fail("invalid binary operands", e.token);
                    e.optionalMixedIntDecimal = true; e.optionalMixedIntOnLeft = left == ValueType.optionalInt || left == ValueType.intType;
                    e.optionalIntLeft = left == ValueType.optionalInt; e.optionalIntRight = right == ValueType.optionalInt;
                    e.optionalDecimalLeft = left == ValueType.optionalDecimal; e.optionalDecimalRight = right == ValueType.optionalDecimal;
                    return ["==", "!=", "<", ">", "<=", ">="].canFind(op) ? ValueType.boolType : ValueType.decimalType;
                }
                if (left == ValueType.optionalDecimal && [ValueType.stringType, ValueType.nullableString].canFind(right)) { e.left.optionalRequired = true; left = ValueType.decimalType; }
                if (right == ValueType.optionalDecimal && [ValueType.stringType, ValueType.nullableString].canFind(left)) { e.right.optionalRequired = true; right = ValueType.decimalType; }
                if (left == ValueType.optionalBool && [ValueType.stringType, ValueType.nullableString].canFind(right)) { e.left.optionalRequired = true; left = ValueType.boolType; }
                if (right == ValueType.optionalBool && [ValueType.stringType, ValueType.nullableString].canFind(left)) { e.right.optionalRequired = true; right = ValueType.boolType; }
                if (left == ValueType.optionalInt && [ValueType.stringType, ValueType.nullableString].canFind(right)) {
                    e.left.optionalRequired = true; left = ValueType.intType;
                }
                if (right == ValueType.optionalInt && [ValueType.stringType, ValueType.nullableString].canFind(left)) {
                    e.right.optionalRequired = true; right = ValueType.intType;
                }
                if (isOptionalPrimitive(left) || isOptionalPrimitive(right))
                    fail("nullable primitive requires a null check or ?: first", e.token);
                if (left == ValueType.enumType && right == ValueType.enumType) {
                    if (e.left.objectClass !is e.right.objectClass || !["==", "!="].canFind(op))
                        fail("invalid enum operands", e.token);
                    e.emittedOperator = op == "==" ? "is" : "!is";
                    return ValueType.boolType;
                }
                if (left == ValueType.encodingType && right == ValueType.encodingType) {
                    if (!["==", "!="].canFind(op)) fail("invalid enum operands", e.token);
                    e.emittedOperator = op == "==" ? "is" : "!is"; return ValueType.boolType;
                }
                if (isMap(left) && left == right && op == "+") {
                    if (hasMapKeyClass(left) && e.left.keyObjectClasses != e.right.keyObjectClasses) fail("map key type mismatch", e.token);
                    e.keyObjectClasses = e.left.keyObjectClasses;
                    if (hasObjectClass(left) && e.left.objectClass !is e.right.objectClass)
                        fail("map value type mismatch", e.token);
                    e.objectClass = e.left.objectClass;
                    e.inferredType = left;
                    return left;
                }
                if (isArray(left) && left == right && op == "+") {
                    if (!matches(e.right, left, e.left.objectClass, e.left.keyObjectClasses))
                        fail("array element type mismatch", e.token);
                    e.keyObjectClasses = e.left.keyObjectClasses;
                    e.inferredType = left;
                    e.objectClass = e.left.objectClass;
                    return left;
                }
                if ((left == ValueType.nullType && (isNullableReference(right) || right == ValueType.nullType)) ||
                    (right == ValueType.nullType && isNullableReference(left))) {
                    if (!["==", "!="].canFind(op)) fail("null supports only equality comparisons", e.token);
                    e.inferredType = ValueType.nullType;
                    return ValueType.boolType;
                }
                if (left == ValueType.guidType && right == ValueType.guidType) {
                    if (!["==", "!="].canFind(op)) fail("invalid guid operands", e.token);
                    e.inferredType = ValueType.guidType; return ValueType.boolType;
                }
                if (left == ValueType.fileType && right == ValueType.fileType) {
                    if (!["==", "!="].canFind(op)) fail("invalid file operands", e.token);
                    e.fileBinary = true; return ValueType.boolType;
                }
                if (left == ValueType.datespanType && right == ValueType.datespanType) {
                    if (!["+", "-", "==", "!=", "<", ">", "<=", ">="].canFind(op)) fail("invalid datespan operands", e.token);
                    e.inferredType = ValueType.datespanType;
                    return op == "+" || op == "-" ? ValueType.datespanType : ValueType.boolType;
                }
                if ((left == ValueType.dateType && (right == ValueType.dateType || right == ValueType.datespanType)) ||
                    (left == ValueType.datespanType && right == ValueType.dateType)) {
                    if (left == ValueType.dateType && right == ValueType.dateType && ["==", "!=", "<", ">", "<=", ">="].canFind(op)) {
                        e.dateBinary = true; return ValueType.boolType;
                    }
                    if ((left == ValueType.dateType && right == ValueType.dateType && op == "-") ||
                        (left == ValueType.dateType && right == ValueType.datespanType && ["+", "-"].canFind(op)) ||
                        (left == ValueType.datespanType && right == ValueType.dateType && op == "+")) {
                        e.dateBinary = true;
                        return left == ValueType.dateType && right == ValueType.dateType ? ValueType.datespanType : ValueType.dateType;
                    }
                    fail("invalid date operands", e.token);
                }
                if (left == ValueType.nullableString) { e.nullableStringLeft = true; left = ValueType.stringType; }
                if (right == ValueType.nullableString) { e.right.nullableStringMode = NullableStringMode.nullAsEmpty; right = ValueType.stringType; }
                if (["+", "==", "!=", "<", ">", "<=", ">="].canFind(op) && left == ValueType.stringType && hasStringConversion(right)) {
                    e.right.convertToString = right; right = ValueType.stringType;
                }
                if (right == ValueType.stringType && hasStringConversion(left) &&
                    (op == "+" || (left == ValueType.guidType && ["==", "!=", "<", ">", "<=", ">="].canFind(op)))) {
                    e.left.convertToString = left; left = ValueType.stringType;
                    e.nullableStringLeft = true;
                }
                if (left == ValueType.decimalType && right == ValueType.intType) { e.right.promoteToDecimal = true; right = ValueType.decimalType; }
                if (left == ValueType.intType && right == ValueType.decimalType) {
                    e.left.promoteToDecimal = true; left = ValueType.decimalType;
                    // integer's mixed decimal comparisons in the original runtime use the inverse inclusive relation.
                    if (op == "<") e.emittedOperator = "<=";
                    else if (op == "<=") e.emittedOperator = "<";
                    else if (op == ">") e.emittedOperator = ">=";
                    else if (op == ">=") e.emittedOperator = ">";
                }
                if (left != right || left == ValueType.voidType || left == ValueType.exceptionType || left == ValueType.primaryType || left == ValueType.binaryType || left == ValueType.geometryType || left == ValueType.fileType || left == ValueType.selfType || isMap(left) || isArray(left)) fail("operand type mismatch", e.token);
                if (["==", "!="].canFind(op)) return ValueType.boolType;
                if ((left == ValueType.intType || left == ValueType.decimalType || left == ValueType.stringType) && ["<", ">", "<=", ">="].canFind(op)) return ValueType.boolType;
                if (left == ValueType.stringType && op == "+") { e.inferredType = ValueType.stringType; return ValueType.stringType; }
                if (left == ValueType.decimalType && ["+", "-", "*", "/", "%"].canFind(op)) { e.inferredType = ValueType.decimalType; return ValueType.decimalType; }
                if (left == ValueType.intType && ["+", "-", "*", "/", "%", "&", "|", "^"].canFind(op)) return ValueType.intType;
                if (left == ValueType.boolType && ["&&", "||"].canFind(op)) return ValueType.boolType;
                fail("invalid binary operands", e.token); assert(0);
            case ExprKind.conditional:
                if (!matches(e.left, ValueType.boolType)) fail("conditional expression requires a bool condition", e.token);
                auto left = typeOf(e.right), right = typeOf(e.third);
                if (left == ValueType.nullType && isNullableReference(right)) {
                    matches(e.right, right, e.third.objectClass, e.third.keyObjectClasses); left = right;
                }
                if (right == ValueType.nullType && isNullableReference(left)) {
                    matches(e.third, left, e.right.objectClass, e.right.keyObjectClasses); right = left;
                }
                if (right == ValueType.nullType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(left)) {
                    e.right.optionalWrap = true; left = storedValueType(left); e.third.inferredType = left; right = left;
                }
                if (left == ValueType.nullType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(right)) {
                    e.third.optionalWrap = true; right = storedValueType(right); e.right.inferredType = right; left = right;
                }
                if (isOptionalPrimitive(left) && right == ValueType.nullType) { e.third.inferredType = left; right = left; }
                if (isOptionalPrimitive(right) && left == ValueType.nullType) { e.right.inferredType = right; left = right; }
                if (isOptionalPrimitive(left) && right == optionalBaseType(left)) { e.third.optionalWrap = true; right = left; }
                if (isOptionalPrimitive(right) && left == optionalBaseType(right)) { e.right.optionalWrap = true; left = right; }
                if (left == ValueType.optionalDecimal && (right == ValueType.intType || right == ValueType.optionalInt)) { if (!matchesStored(e.third, ValueType.decimalType)) fail("conditional branch type mismatch", e.token); right = left; }
                if (right == ValueType.optionalDecimal && (left == ValueType.intType || left == ValueType.optionalInt)) { if (!matchesStored(e.right, ValueType.decimalType)) fail("conditional branch type mismatch", e.token); left = right; }
                if ([ValueType.stringType, ValueType.nullableString].canFind(left) && (isOptionalPrimitive(right) || [ValueType.intType, ValueType.boolType, ValueType.decimalType,
                    ValueType.guidType, ValueType.dateType, ValueType.datespanType, ValueType.geometryType].canFind(right))) {
                    if (!matches(e.third, ValueType.stringType)) fail("conditional branch type mismatch", e.token);
                    right = left;
                }
                if ([ValueType.stringType, ValueType.nullableString].canFind(right) && (isOptionalPrimitive(left) || [ValueType.intType, ValueType.boolType, ValueType.decimalType,
                    ValueType.guidType, ValueType.dateType, ValueType.datespanType, ValueType.geometryType].canFind(left))) {
                    if (!matches(e.right, ValueType.stringType)) fail("conditional branch type mismatch", e.token);
                    left = right;
                }
                if ([ValueType.stringType, ValueType.nullableString].canFind(left) && right == ValueType.selfType && matches(e.third, ValueType.stringType)) right = left;
                if ([ValueType.stringType, ValueType.nullableString].canFind(right) && left == ValueType.selfType && matches(e.right, ValueType.stringType)) left = right;
                if (left == ValueType.stringType && right == ValueType.nullableString) left = ValueType.nullableString;
                if (left == ValueType.nullableString && right == ValueType.stringType) right = ValueType.nullableString;
                if (left != right && isSqlType(right) && matches(e.right, right)) left = right;
                if (left != right && isSqlType(left) && matches(e.third, left)) right = left;
                if (left != ValueType.primaryType && right == ValueType.primaryType && matches(e.right, ValueType.primaryType))
                    left = ValueType.primaryType;
                if (right != ValueType.primaryType && left == ValueType.primaryType && matches(e.third, ValueType.primaryType))
                    right = ValueType.primaryType;
                if ([ValueType.stringArray, ValueType.guidArray, ValueType.intArray, ValueType.boolArray, ValueType.decimalArray, ValueType.fileArray].canFind(left) && right == ValueType.primaryArray && matches(e.right, ValueType.primaryArray)) left = right;
                if ([ValueType.stringArray, ValueType.guidArray, ValueType.intArray, ValueType.boolArray, ValueType.decimalArray, ValueType.fileArray].canFind(right) && left == ValueType.primaryArray && matches(e.third, ValueType.primaryArray)) right = left;
                if (left == ValueType.decimalType && right == ValueType.intType) { e.third.promoteToDecimal = true; right = ValueType.decimalType; }
                if (left == ValueType.intType && right == ValueType.decimalType) { e.right.promoteToDecimal = true; left = ValueType.decimalType; }
                if (left == ValueType.stringType && hasStringConversion(right)) {
                    e.third.convertToString = right; right = ValueType.stringType;
                }
                if (right == ValueType.stringType && hasStringConversion(left)) {
                    e.right.convertToString = left; left = ValueType.stringType;
                }
                if (left == ValueType.stringType && right == ValueType.stringType &&
                    (e.right.kind == ExprKind.nullLiteral || e.third.kind == ExprKind.nullLiteral)) left = right = ValueType.nullableString;
                bool selectedReferenceType;
                Program conditionalClass;
                Program[] conditionalKeys;
                if (left == right && (isArray(left) || isMap(left)) &&
                    (e.right.objectClass !is e.third.objectClass || e.right.keyObjectClasses != e.third.keyObjectClasses)) {
                    if (covariantCollectionMatches(left, e.right.objectClass, e.right.keyObjectClasses, e.third.objectClass, e.third.keyObjectClasses)) {
                        if (!matches(e.right, left, e.third.objectClass, e.third.keyObjectClasses)) fail("conditional branch type mismatch", e.token);
                        conditionalClass = e.third.objectClass; conditionalKeys = e.third.keyObjectClasses;
                    } else if (covariantCollectionMatches(left, e.third.objectClass, e.third.keyObjectClasses, e.right.objectClass, e.right.keyObjectClasses)) {
                        if (!matches(e.third, left, e.right.objectClass, e.right.keyObjectClasses)) fail("conditional branch type mismatch", e.token);
                        conditionalClass = e.right.objectClass; conditionalKeys = e.right.keyObjectClasses;
                    } else fail("conditional branch type mismatch", e.token);
                    selectedReferenceType = true;
                } else if (left == ValueType.selfType && right == left && e.right.objectClass !is e.third.objectClass) {
                    if (isAssignable(e.right.objectClass, e.third.objectClass)) conditionalClass = e.third.objectClass;
                    else if (isAssignable(e.third.objectClass, e.right.objectClass)) conditionalClass = e.right.objectClass;
                    else fail("conditional branch type mismatch", e.token);
                    selectedReferenceType = true;
                }
                if (left == ValueType.voidType || left != right || (!selectedReferenceType && hasObjectClass(left) && e.right.objectClass !is e.third.objectClass) || (!selectedReferenceType && hasMapKeyClass(left) && e.right.keyObjectClasses != e.third.keyObjectClasses))
                    fail("conditional branch type mismatch", e.token);
                if (hasObjectClass(left)) e.objectClass = selectedReferenceType ? conditionalClass : e.right.objectClass;
                if (hasMapKeyClass(left)) e.keyObjectClasses = selectedReferenceType ? conditionalKeys : e.right.keyObjectClasses;
                return left;
            case ExprKind.elvis:
                auto left = typeOf(e.left);
                if (isOptionalPrimitive(left)) {
                    auto right = typeOf(e.right);
                    if (right == left || right == ValueType.nullType) {
                        if (right == ValueType.nullType) e.right.inferredType = left;
                        e.optionalElvis = true; e.inferredType = left; return left;
                    }
                    if (!matches(e.right, optionalBaseType(left))) fail("elvis branch type mismatch", e.token);
                    e.inferredType = left;
                    return optionalBaseType(left);
                }
                if ([ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(left)) {
                    if (!matchesStored(e.right, left)) fail("elvis branch type mismatch", e.token);
                    e.inferredType = left;
                    return left;
                }
                if (!isNullableReference(left)) fail("elvis requires a supported reference type", e.token);
                auto expectedRight = left == ValueType.nullableString ? ValueType.stringType : left;
                if (!matches(e.right, expectedRight, e.left.objectClass, e.left.keyObjectClasses)) fail("elvis branch type mismatch", e.token);
                e.inferredType = left;
                e.objectClass = e.left.objectClass;
                e.keyObjectClasses = e.left.keyObjectClasses;
                return left;
        }
    }
    private bool useAssignmentOperator(Program target, Expression value, Token site, bool direct) {
        auto method = lookupMethod(target, "operator=");
        if (method is null) return false;
        auto call = new Expression(ExprKind.call, site);
        call.arguments = [value];
        int operatorWeight, operatorDistance;
        bool operatorAmbiguous;
        auto selected = selectOverload(method, call, true, true, &operatorWeight, &operatorDistance, &operatorAmbiguous);
        if (selected is null) return false;
        if (direct) {
            auto actual = typeOf(value);
            int directWeight, directDistance;
            if (actual == ValueType.selfType) {
                if (isAssignable(value.objectClass, target))
                    directDistance = inheritanceDistance(value.objectClass, target);
                else {
                    auto conversion = value.userConversion;
                    assert(conversion !is null && conversion.returnObjectClass !is null);
                    directWeight = 100;
                    directDistance = inheritanceDistance(conversion.returnObjectClass, target);
                }
            } else assert(actual == ValueType.nullType);
            if (directWeight < operatorWeight || (directWeight == operatorWeight && directDistance < operatorDistance))
                return false;
            if (directWeight == operatorWeight && directDistance == operatorDistance)
                fail("ambiguous assignment", site);
            // The direct candidate may have annotated the expression with a
            // conversion that does not belong to the selected operator.
            value.userConversion = null;
            value.optionalRequired = false;
            value.optionalWrap = false;
            value.boxPrimary = false;
        }
        if (operatorAmbiguous) fail("ambiguous assignment operator", site);
        checkCall(selected, selected.owner, call);
        return true;
    }
    private Expression copyQualifiedTarget(Expression expression) {
        assert(expression.kind == ExprKind.variable || expression.kind == ExprKind.field);
        auto copy = new Expression(expression.kind, expression.token);
        if (expression.left !is null) copy.left = copyQualifiedTarget(expression.left);
        return copy;
    }
    private bool checkStatement(Statement s) {
        final switch (s.kind) {
            case StmtKind.block:
                auto old = variables.dup; auto oldObjects = objectVariables.dup; auto oldKeyObjects = keyObjectVariables.dup; bool returns;
                foreach (child; s.children) { auto childReturns = checkStatement(child); returns = returns || childReturns; }
                variables = old; objectVariables = oldObjects; keyObjectVariables = oldKeyObjects; return returns;
            case StmtKind.variable:
                s.hasContainer = !staticContext;
                if (s.token.text in variables) fail("duplicate or shadowed variable", s.token);
                s.type = resolveDeclaredType(s.type, currentProgram, s.objectName, s.keyObjectNames, s.token);
                if (s.type == ValueType.voidType) fail("variable cannot be void", s.token);
                if (hasObjectClass(s.type)) s.objectClass = resolveClass(currentProgram, s.objectName, s.token);
                if (s.type == ValueType.selfType && isPrimaryClass(s.objectClass)) s.hasContainer = false;
                if (hasMapKeyClass(s.type)) s.keyObjectClasses = resolveKeyClasses(currentProgram, s.keyObjectNames, s.token);
                if (s.nestedClass !is null) {
                    s.nestedClass.enclosingStatic = staticContext;
                    auto names = variables.keys;
                    sort(names);
                    s.nestedClass.captures = null;
                    foreach (name; names)
                        s.nestedClass.captures ~= Capture(name, variables[name], name in objectVariables ? objectVariables[name] : null, name in keyObjectVariables ? keyObjectVariables[name] : null);
                }
                if (s.expression !is null) {
                    auto direct = matchesInitializer(s.expression, s.type, s.objectClass, s.keyObjectClasses);
                    if (s.type == ValueType.selfType)
                        s.userOperatorAssignment = useAssignmentOperator(s.objectClass, s.expression, s.token, direct);
                    if (!direct && !s.userOperatorAssignment) fail("initializer type mismatch", s.token);
                }
                variables[s.token.text] = s.type;
                if (hasObjectClass(s.type)) objectVariables[s.token.text] = s.objectClass;
                if (hasMapKeyClass(s.type)) keyObjectVariables[s.token.text] = s.keyObjectClasses;
                return false;
            case StmtKind.assignment:
                auto variableType = typeOf(s.target);
                if (variableType == ValueType.nullableString) variableType = ValueType.stringType;
                if (isOptionalPrimitive(variableType)) variableType = optionalBaseType(variableType);
                if (s.target.enumConstant) fail("enum constants cannot be assigned", s.token);
                if (variableType == ValueType.selfType && s.assignmentOperator != "=") {
                    auto token = s.token;
                    token.text = s.assignmentOperator[0 .. $ - 1];
                    auto binary = new Expression(ExprKind.binary, token);
                    binary.left = s.isMemberInitializer ? copyQualifiedTarget(s.target) : s.target;
                    binary.right = s.expression;
                    s.expression = binary;
                    s.assignmentOperator = "=";
                    s.userCompoundAssignment = true;
                    return checkStatement(s);
                }
                if (variableType == ValueType.selfType && s.assignmentOperator == "=" &&
                    lookupMethod(s.target.objectClass, "operator=") !is null && useAssignmentOperator(s.target.objectClass, s.expression, s.token,
                                          matchesStored(s.expression, variableType, s.target.objectClass))) {
                    s.userOperatorAssignment = true;
                    s.type = variableType;
                    return false;
                }
                if (variableType == ValueType.fileType && s.assignmentOperator == "=" &&
                    [ValueType.stringType, ValueType.nullableString].canFind(typeOf(s.expression))) {
                    s.filePathAssignment = true; s.type = variableType; return false;
                }
                if (variableType == ValueType.dateType && s.assignmentOperator == "=" &&
                    [ValueType.intType, ValueType.optionalInt].canFind(typeOf(s.expression))) {
                    if (!matches(s.expression, ValueType.intType)) fail("date ticks must be int", s.token);
                    s.dateTickAssignment = true; s.type = variableType; return false;
                }
                if (s.target.kind == ExprKind.index && isMap(s.target.inferredType))
                    variableType = mapValueType(s.target.inferredType);
                if ((s.target.kind != ExprKind.index || isMap(s.target.inferredType) || [ValueType.intArray, ValueType.boolArray, ValueType.decimalArray].canFind(s.target.inferredType)) && (s.assignmentOperator == "=" || variableType == ValueType.intType || variableType == ValueType.decimalType) ?
                    !matchesStored(s.expression, variableType, s.target.objectClass, s.target.keyObjectClasses) :
                    !matches(s.expression, variableType, s.target.objectClass, s.target.keyObjectClasses)) fail("assignment type mismatch", s.token);
                s.type = variableType;
                if (s.assignmentOperator != "=" && variableType != ValueType.intType &&
                    !(variableType == ValueType.stringType && s.assignmentOperator == "+=") &&
                    !(isMap(variableType) && s.assignmentOperator == "+=") &&
                    !(isArray(variableType) && s.assignmentOperator == "+=") &&
                    !(variableType == ValueType.decimalType && ["+=", "-=", "*=", "/=", "%="].canFind(s.assignmentOperator)))
                    fail("invalid compound assignment operands", s.token);
                return false;
            case StmtKind.expressionStmt:
                typeOf(s.expression);
                return false;
            case StmtKind.returnStmt:
                if (s.expression is null) { if (returnType != ValueType.voidType) fail("return value required", s.token); }
                else if (returnType == ValueType.voidType || !matchesStored(s.expression, returnType, returnObjectClass, returnKeyObjectClasses)) fail("return type mismatch", s.token);
                if (s.expression !is null && returnType == ValueType.selfType)
                    s.priorityMethod = lookupUnaryOperator(returnObjectClass, "operatorPriority");
                if (s.expression !is null && returnType == ValueType.sqlBoolType) s.sqlBoolReturnPriority = true;
                if (s.expression !is null && returnType == ValueType.sqlIntType) s.sqlIntReturnPriority = true;
                if (s.expression !is null && returnType == ValueType.sqlDecimalType) s.sqlDecimalReturnPriority = true;
                if (s.expression !is null && returnType == ValueType.sqlStringType) s.sqlStringReturnPriority = true;
                if (s.expression !is null && returnType == ValueType.sqlGuidType) s.sqlGuidReturnPriority = true;
                if (s.expression !is null && returnType == ValueType.sqlDateType) s.sqlDateReturnPriority = true;
                if (s.expression !is null && returnType == ValueType.sqlDatespanType) s.sqlDatespanReturnPriority = true;
                if (s.expression !is null && returnType == ValueType.sqlGeometryType) s.sqlGeometryReturnPriority = true;
                return true;
            case StmtKind.ifStmt:
                if (!matches(s.expression, ValueType.boolType)) fail("if condition must be bool", s.token);
                auto old = variables.dup; auto oldObjects = objectVariables.dup; auto oldKeyObjects = keyObjectVariables.dup;
                auto first = checkStatement(s.children[0]); variables = old.dup; objectVariables = oldObjects.dup; keyObjectVariables = oldKeyObjects.dup;
                bool second;
                if (s.children.length == 2) second = checkStatement(s.children[1]);
                variables = old; objectVariables = oldObjects; keyObjectVariables = oldKeyObjects; return first && second;
            case StmtKind.whileStmt:
            case StmtKind.doWhileStmt:
                if (!matches(s.expression, ValueType.boolType)) fail("loop condition must be bool", s.token);
                auto old = variables.dup; auto oldObjects = objectVariables.dup; auto oldKeyObjects = keyObjectVariables.dup;
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; keyObjectVariables = oldKeyObjects; return false;
            case StmtKind.forStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup; auto oldKeyObjects = keyObjectVariables.dup;
                if (s.initial !is null) checkStatement(s.initial);
                if (!matches(s.expression, ValueType.boolType)) fail("loop condition must be bool", s.token);
                checkStatement(s.step);
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; keyObjectVariables = oldKeyObjects; return false;
            case StmtKind.forEachStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup; auto oldKeyObjects = keyObjectVariables.dup;
                auto array = typeOf(s.expression);
                checkStatement(s.initial);
                if ([ValueType.stringArray, ValueType.guidArray, ValueType.intArray, ValueType.boolArray, ValueType.decimalArray, ValueType.fileArray].canFind(array) && s.initial.type == ValueType.primaryType && matches(s.expression, ValueType.primaryArray)) array = ValueType.primaryArray;
                if (!isArray(array) || elementType(array) != s.initial.type) fail("foreach element type mismatch", s.token);
                if (!matches(s.expression, array, s.initial.objectClass, s.initial.keyObjectClasses)) fail("foreach element type mismatch", s.token);
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; keyObjectVariables = oldKeyObjects; return false;
            case StmtKind.breakStmt:
            case StmtKind.continueStmt:
                if (loopDepth == 0) fail(s.token.text ~ " outside loop", s.token);
                return false;
            case StmtKind.throwStmt:
                s.type = typeOf(s.expression);
                if (s.type == ValueType.nullType) { matches(s.expression, ValueType.exceptionType); s.type = ValueType.exceptionType; }
                if (s.type == ValueType.selfType && matches(s.expression, ValueType.exceptionType)) s.type = ValueType.exceptionType;
                if (s.type == ValueType.nullableString) { s.type = ValueType.stringType; s.expression.nullableStringMode = NullableStringMode.required; }
                if (s.type != ValueType.exceptionType && s.type != ValueType.stringType) fail("throw requires exception or string", s.token);
                return true;
            case StmtKind.tryStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup; auto oldKeyObjects = keyObjectVariables.dup;
                auto tryReturns = checkStatement(s.children[0]);
                bool catchReturns = true, finallyReturns;
                if (s.hasCatch) {
                    variables = old.dup; objectVariables = oldObjects.dup; keyObjectVariables = oldKeyObjects.dup;
                    if (s.catchName.text in variables) fail("duplicate or shadowed variable", s.catchName);
                    variables[s.catchName.text] = ValueType.exceptionType;
                    catchReturns = checkStatement(s.children[1]);
                }
                variables = old.dup; objectVariables = oldObjects.dup; keyObjectVariables = oldKeyObjects.dup;
                if (s.hasFinally) {
                    finallyReturns = checkStatement(s.children[$-1]);
                }
                variables = old; objectVariables = oldObjects; keyObjectVariables = oldKeyObjects;
                return (tryReturns && catchReturns) || finallyReturns;
        }
    }
}

