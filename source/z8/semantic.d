module z8.semantic;

import std.algorithm : canFind;
import std.string : lastIndexOf;
import z8.compiler_model;
import z8.lexer : Token;

/// Checks the entire program before emitting code; unsupported constructs fail closed.
class Checker {
    private Method[string] methods;
    private Field[string] fields;
    private Program[string] visibleClasses;
    private Program[string] allClasses;
    private Program currentProgram;
    private bool staticContext, fieldInitialization;
    private ValueType[string] variables;
    private Program[string] objectVariables;
    private ValueType returnType;
    private Program returnObjectClass;
    private size_t loopDepth;
    private size_t finallyDepth;
    private void fail(string message, Token t) { throw new CompileException(message, t.position); }
    private static bool isConstantInitializer(Expression expression) {
        switch (expression.kind) {
            case ExprKind.integer: case ExprKind.decimalLiteral: case ExprKind.boolean: case ExprKind.stringLiteral: case ExprKind.guidLiteral: case ExprKind.nullLiteral: return true;
            case ExprKind.arrayLiteral:
                foreach (item; expression.arguments) if (!isConstantInitializer(item)) return false;
                return true;
            case ExprKind.castExpr: case ExprKind.unary: return isConstantInitializer(expression.left);
            case ExprKind.binary: return isConstantInitializer(expression.left) && isConstantInitializer(expression.right);
            case ExprKind.conditional: return isConstantInitializer(expression.left) && isConstantInitializer(expression.right) && isConstantInitializer(expression.third);
            default: return false;
        }
    }
    void bindBase(Program program, Program[string] programs) {
        currentProgram = program; allClasses = programs;
        if (program.baseName.length) {
            program.baseClass = resolveClass(program, program.baseName, program.baseToken);
            if (program.baseClass.isEnum) fail("cannot extend an enum", program.baseToken);
            if (program.baseClass.isFinal) fail("cannot extend a final class", program.baseToken);
        }
    }
    private static Method lookupMethod(Program owner, string name) {
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (candidate; current.methods) if (candidate.name.text == name) return candidate;
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
    private bool accessible(Program owner, bool isPublic, bool isProtected) {
        return owner is currentProgram || isPublic || (isProtected && isAssignable(currentProgram, owner));
    }
    private Program resolveClass(Program owner, string name, Token site) {
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
    private ValueType resolveDeclaredType(ValueType type, Program owner, string objectName, Token site) {
        if (type != ValueType.selfType && type != ValueType.selfArray) return type;
        auto target = resolveClass(owner, objectName, site);
        if (!target.isEnum) return type;
        return type == ValueType.selfArray ? ValueType.enumArray : ValueType.enumType;
    }
    void prepareDeclarations(Program program, Program[string] programs) {
        currentProgram = program; allClasses = programs;
        foreach (field; program.fields) {
            field.type = resolveDeclaredType(field.type, program, field.objectName, field.name);
            if (field.isStatic && (field.type == ValueType.selfType || field.type == ValueType.enumType))
                fail("static object and enum fields are not supported", field.name);
            if (field.type == ValueType.enumType && field.initializer is null)
                fail("enum fields require an initializer", field.name);
            if (field.type == ValueType.primaryType && field.initializer is null)
                fail("primary fields require an initializer", field.name);
        }
        foreach (method; program.methods) {
            method.returnType = resolveDeclaredType(method.returnType, program, method.returnObjectName, method.name);
            foreach (ref parameter; method.parameters)
                parameter.type = resolveDeclaredType(parameter.type, program, parameter.objectName, parameter.name);
        }
    }
    private bool matches(Expression e, ValueType expected, Program expectedClass = null) {
        if (e.kind == ExprKind.arrayLiteral && (expected == ValueType.selfArray || expected == ValueType.enumArray)) e.objectClass = expectedClass;
        auto actual = typeOf(e, expected);
        if (expected == ValueType.primaryType && [ValueType.intType, ValueType.boolType, ValueType.decimalType,
            ValueType.optionalInt, ValueType.optionalBool, ValueType.optionalDecimal, ValueType.stringType, ValueType.nullableString, ValueType.guidType].canFind(actual)) {
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
            if (expected == ValueType.stringType) {
                e.optionalRequired = true; e.convertToString = base; return true;
            }
        }
        if (actual == ValueType.nullableString && expected == ValueType.stringType) {
            return true;
        }
        if (actual == ValueType.nullType && isNullableReference(expected)) {
            e.inferredType = expected; e.objectClass = expectedClass; return true;
        }
        if (actual == ValueType.intType && expected == ValueType.decimalType) { e.promoteToDecimal = true; return true; }
        if (expected == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(actual)) {
            e.convertToString = actual; return true;
        }
        if (expected == ValueType.stringType && actual == ValueType.guidType) { e.convertToString = actual; return true; }
        return actual == expected && (expected == ValueType.selfType ? isAssignable(e.objectClass, expectedClass) :
            (expected != ValueType.selfArray && expected != ValueType.enumType && expected != ValueType.enumArray) || e.objectClass is expectedClass);
    }
    private bool matchesStored(Expression e, ValueType expected, Program expectedClass = null) {
        if (expected != ValueType.intType && expected != ValueType.boolType && expected != ValueType.decimalType) return matches(e, expected, expectedClass);
        auto optional = storedValueType(expected);
        auto actual = typeOf(e, expected);
        if (actual == ValueType.nullType) { e.inferredType = optional; return true; }
        if (actual == optional) return true;
        if (actual == expected) { e.optionalWrap = true; return true; }
        if (expected == ValueType.decimalType && matches(e, expected, expectedClass)) { e.optionalWrap = true; return true; }
        return false;
    }
    private ValueType checkCall(Method method, Program owner, Expression e) {
        if (e.arguments.length != method.parameters.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) {
            auto p = method.parameters[i];
            if (arg.kind == ExprKind.arrayLiteral) fail("array initializer requires a known target", arg.token);
            auto objectClass = hasObjectClass(p.type) ? resolveClass(owner, p.objectName, p.name) : null;
            if (!matchesStored(arg, p.type, objectClass)) fail("argument type mismatch", arg.token);
        }
        if (hasObjectClass(method.returnType))
            e.objectClass = resolveClass(owner, method.returnObjectName, method.name);
        return method.returnType == ValueType.stringType ? ValueType.nullableString : storedValueType(method.returnType);
    }
    private bool sameParameters(Method left, Method right) {
        if (left.parameters.length != right.parameters.length) return false;
        foreach (i, p; left.parameters) {
            auto q = right.parameters[i];
            if (p.type != q.type) return false;
            if (hasObjectClass(p.type) && resolveClass(left.owner, p.objectName, p.name) !is resolveClass(right.owner, q.objectName, q.name)) return false;
        }
        return true;
    }
    // Z8 ranks direct casts ahead of conversions defined by an operator.
    private Method selectOverload(Method first, Expression e) {
        ValueType[] actualTypes;
        foreach (arg; e.arguments) {
            if (arg.kind == ExprKind.arrayLiteral) fail("array initializer requires a known target", arg.token);
            actualTypes ~= typeOf(arg);
        }
        Method best;
        int bestWeight = int.max;
        bool ambiguous;
        Method[] seen;
        for (auto owner = first.owner; owner !is null; owner = owner.baseClass) foreach (candidate; owner.methods) {
            if (candidate.name.text != first.name.text || candidate.isStatic != first.isStatic) continue;
            bool hidden;
            foreach (previous; seen) if (sameParameters(previous, candidate)) { hidden = true; break; }
            if (hidden) continue;
            seen ~= candidate;
            if (candidate.parameters.length != e.arguments.length) continue;
            if (!accessible(candidate.owner, candidate.isPublic, candidate.isProtected)) continue;
            int weight; bool applicable = true;
            foreach (i, p; candidate.parameters) {
                auto actual = actualTypes[i];
                if (isOptionalPrimitive(actual)) actual = optionalBaseType(actual);
                if ((actual == ValueType.nullType && (isNullableReference(p.type) || p.type == ValueType.intType || p.type == ValueType.boolType || p.type == ValueType.decimalType)) ||
                    (actual == ValueType.nullableString && p.type == ValueType.stringType)) {
                    // Null is equally applicable to each supported reference type.
                } else if (actual == p.type) {
                    if (actual == ValueType.selfType && !isAssignable(e.arguments[i].objectClass, resolveClass(candidate.owner, p.objectName, p.name))) applicable = false;
                    if (actual == ValueType.selfArray && e.arguments[i].objectClass !is resolveClass(candidate.owner, p.objectName, p.name)) applicable = false;
                    if (actual == ValueType.enumType && e.arguments[i].objectClass !is resolveClass(candidate.owner, p.objectName, p.name)) applicable = false;
                    if (actual == ValueType.enumArray && e.arguments[i].objectClass !is resolveClass(candidate.owner, p.objectName, p.name)) applicable = false;
                } else if (actual == ValueType.intType && p.type == ValueType.decimalType) weight += 100;
                else if (p.type == ValueType.primaryType && [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType, ValueType.nullableString, ValueType.guidType].canFind(actual)) { }
                else if (p.type == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(actual)) weight += 100;
                else if (p.type == ValueType.stringType && actual == ValueType.guidType) weight += 100;
                else applicable = false;
                if (!applicable) break;
            }
            if (!applicable) continue;
            if (weight < bestWeight) { best = candidate; bestWeight = weight; ambiguous = false; }
            else if (weight == bestWeight) ambiguous = true;
        }
        if (best is null) fail("no matching method overload", e.token);
        if (ambiguous) fail("ambiguous method overload", e.token);
        return best;
    }
    private void checkArguments(Expression e, ValueType[] types) {
        if (e.arguments.length != types.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) if (!matches(arg, types[i])) fail("argument type mismatch", arg.token);
    }
    void check(Program program, Program[string] allPrograms = null) {
        currentProgram = program;
        allClasses = allPrograms;
        visibleClasses = null;
        visibleClasses[program.name.text] = program;
        auto dot = program.qualifiedName.lastIndexOf('.');
        auto packageName = dot < 0 ? "" : program.qualifiedName[0 .. dot + 1];
        foreach (qualified, target; allPrograms) {
            auto targetDot = qualified.lastIndexOf('.');
            auto targetPackage = targetDot < 0 ? "" : qualified[0 .. targetDot + 1];
            if (targetPackage == packageName) visibleClasses[target.name.text] = target;
        }
        Program[string] imported;
        foreach (item; program.imports) {
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
        Method[][string] ownOverloads;
        foreach (m; program.methods) {
            auto inherited = m.name.text in methods;
            auto previousOverloads = m.name.text in ownOverloads;
            if (previousOverloads !is null) foreach (previous; *previousOverloads) {
                if (m.isStatic != previous.isStatic) fail("mixing static and instance overloads is not supported", m.name);
                if (sameParameters(previous, m)) fail("duplicate method signature", m.name);
            }
            Method baseMethod;
            for (auto base = program.baseClass; base !is null && baseMethod is null; base = base.baseClass)
                foreach (candidate; base.methods)
                    if (candidate.name.text == m.name.text && sameParameters(candidate, m)) { baseMethod = candidate; break; }
            if (inherited !is null && (*inherited).owner !is program && (m.isStatic || (*inherited).isStatic))
                fail("inherited static method overloads are not supported", m.name);
            if (baseMethod !is null) {
                if (m.isStatic || baseMethod.isStatic || !baseMethod.isVirtual) fail("only virtual instance methods may be overridden", m.name);
                if (m.returnType != baseMethod.returnType || m.parameters.length != baseMethod.parameters.length)
                    fail("override signature mismatch", m.name);
                if (hasObjectClass(m.returnType) && resolveClass(program, m.returnObjectName, m.name) !is resolveClass(baseMethod.owner, baseMethod.returnObjectName, baseMethod.name))
                    fail("override return type mismatch", m.name);
                foreach (i, p; m.parameters) {
                    auto baseParam = baseMethod.parameters[i];
                    if (p.type != baseParam.type || (hasObjectClass(p.type) &&
                        resolveClass(program, p.objectName, p.name) !is resolveClass(baseMethod.owner, baseParam.objectName, baseParam.name)))
                        fail("override parameter type mismatch", p.name);
                }
                if (baseMethod.isPublic && !m.isPublic) fail("override cannot reduce public access", m.name);
                if (baseMethod.isProtected && !m.isPublic && !m.isProtected) fail("override cannot reduce protected access", m.name);
                m.isVirtual = true; m.overrides = true;
            }
            methods[m.name.text] = m;
            ownOverloads[m.name.text] ~= m;
        }
        variables = null; objectVariables = null; staticContext = false;
        foreach (field; program.fields)
            if (hasObjectClass(field.type)) field.objectClass = resolveClass(program, field.objectName, field.name);
        foreach (field; program.fields) {
            staticContext = field.isStatic;
            fieldInitialization = !field.isStatic;
            if (field.isStatic && field.initializer !is null && !isConstantInitializer(field.initializer))
                fail("static field initializer must be a constant expression", field.name);
            if (field.initializer !is null && !matchesStored(field.initializer, field.type, field.objectClass))
                fail("field initializer type mismatch", field.name);
        }
        fieldInitialization = false;
        foreach (m; program.methods) {
            variables = null; objectVariables = null; returnType = m.returnType; loopDepth = 0; finallyDepth = 0; staticContext = m.isStatic;
            m.returnObjectClass = hasObjectClass(m.returnType) ? resolveClass(program, m.returnObjectName, m.name) : null;
            returnObjectClass = m.returnObjectClass;
            foreach (ref p; m.parameters) {
                if (p.type == ValueType.voidType) fail("parameter cannot be void", p.name);
                if (p.name.text in variables) fail("duplicate parameter", p.name);
                variables[p.name.text] = p.type;
                if (hasObjectClass(p.type)) {
                    p.objectClass = resolveClass(program, p.objectName, p.name);
                    objectVariables[p.name.text] = p.objectClass;
                }
            }
            auto returns = checkStatement(m.body);
            if (returnType != ValueType.voidType && !returns) fail("method may finish without returning a value", m.name);
        }
    }
    private ValueType typeOf(Expression e, ValueType expected = ValueType.voidType) {
        e.fieldInitialization = fieldInitialization;
        auto result = typeOfRaw(e, expected);
        if (result == ValueType.stringType && (e.kind == ExprKind.memberCall || e.kind == ExprKind.binary))
            e.nonNullStringResult = true;
        return result;
    }
    private ValueType typeOfRaw(Expression e, ValueType expected = ValueType.voidType) {
        final switch (e.kind) {
            case ExprKind.integer: return ValueType.intType;
            case ExprKind.decimalLiteral:
                if (!safeDecimalLiteral(e.token.text)) fail("decimal literal cannot yet be converted reliably; use decimal.parse with a string", e.token);
                return ValueType.decimalType;
            case ExprKind.boolean: return ValueType.boolType;
            case ExprKind.stringLiteral: return ValueType.stringType;
            case ExprKind.guidLiteral: return ValueType.guidType;
            case ExprKind.nullLiteral: return ValueType.nullType;
            case ExprKind.arrayLiteral:
                if (!isArray(expected)) fail("array initializer requires an array type", e.token);
                foreach (element; e.arguments)
                    if (!matchesStored(element, elementType(expected), e.objectClass)) fail("array element type mismatch", element.token);
                e.inferredType = expected; return expected;
            case ExprKind.variable:
                auto variable = e.token.text in variables;
                if (variable is null) {
                    auto field = e.token.text in fields;
                    if (field is null) fail("unknown variable '" ~ e.token.text ~ "'", e.token);
                    if (!accessible((*field).owner, (*field).isPublic, (*field).isProtected)) fail("field is not accessible", e.token);
                    if (staticContext && !(*field).isStatic) fail("instance field in static context", e.token);
                    e.isField = true;
                    if ((*field).isStatic) e.targetClass = (*field).owner.emittedName;
                    if (hasObjectClass((*field).type)) e.objectClass = (*field).objectClass;
                    return (*field).type == ValueType.stringType ? ValueType.nullableString : storedValueType((*field).type);
                }
                if (hasObjectClass(*variable)) e.objectClass = objectVariables[e.token.text];
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
            case ExprKind.newSelf:
                e.newHasContainer = !staticContext;
                e.objectClass = resolveClass(currentProgram, e.token.text, e.token);
                if (e.objectClass.isEnum) fail("cannot instantiate an enum", e.token);
                return ValueType.selfType;
            case ExprKind.field:
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields)) {
                    if (e.left.token.text == "guid" && e.token.text == "Null") {
                        e.emittedOverride = "z8_guid_zero()"; return ValueType.guidType;
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
                    return staticField.type == ValueType.stringType ? ValueType.nullableString : storedValueType(staticField.type);
                }
                if (typeOf(e.left) != ValueType.selfType) fail("field access requires an object", e.token);
                auto field = lookupField(e.left.objectClass, e.token.text);
                if (field is null) fail("unknown field '" ~ e.token.text ~ "'", e.token);
                if (field.isStatic) fail("static field access through an instance is not supported", e.token);
                if (!accessible(field.owner, field.isPublic, field.isProtected)) fail("field is not accessible", e.token);
                if (hasObjectClass(field.type))
                    e.objectClass = field.objectClass !is null ? field.objectClass : resolveClass(field.owner, field.objectName, field.name);
                return field.type == ValueType.stringType ? ValueType.nullableString : storedValueType(field.type);
            case ExprKind.call:
                auto method = e.token.text in methods;
                if (method is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                if (staticContext && !(*method).isStatic) fail("instance method in static context", e.token);
                auto selected = selectOverload(*method, e);
                if (!accessible(selected.owner, selected.isPublic, selected.isProtected)) fail("method is not accessible", e.token);
                return checkCall(selected, selected.owner, e);
            case ExprKind.memberCall:
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) && e.left.token.text == "guid") {
                    if (e.token.text == "parse") {
                        checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_guid_parse"; return ValueType.guidType;
                    }
                    if (e.token.text == "create") {
                        if (!e.arguments.length) e.builtinCall = "z8_guid_create_random";
                        else if (e.arguments.length == 1 && [ValueType.stringType, ValueType.nullableString].canFind(typeOf(e.arguments[0]))) {
                            checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_guid_create_name";
                        } else {
                            checkArguments(e, e.arguments.length == 1 ? [ValueType.intType] : [ValueType.intType, ValueType.intType]);
                            e.builtinCall = "z8_guid_create";
                        }
                        return ValueType.guidType;
                    }
                    fail("unsupported static guid method", e.token);
                }
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) &&
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
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields)) {
                    auto owner = e.left.token.text in visibleClasses;
                    if (owner is null) fail("unknown class or variable '" ~ e.left.token.text ~ "'", e.left.token);
                    auto target = lookupMethod(*owner, e.token.text);
                    if (target is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                    if (!target.isStatic) fail("instance method cannot be called on a class", e.token);
                    target = selectOverload(target, e);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    e.targetClass = (*owner).emittedName;
                    return checkCall(target, target.owner, e);
                }
                auto receiver = typeOf(e.left);
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
                    if (target is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                    if (target.isStatic) fail("static method call through an instance is not supported", e.token);
                    target = selectOverload(target, e);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    e.instanceCall = true;
                    return checkCall(target, target.owner, e);
                } else if (receiver == ValueType.primaryType) {
                    checkArguments(e, []);
                    if (e.token.text == "toString") { e.builtinCall = "z8_primary_to_string"; return ValueType.stringType; }
                    if (e.token.text == "hashCode") { e.builtinCall = "z8_primary_hash"; return ValueType.intType; }
                } else if (receiver == ValueType.stringType) {
                    switch (e.token.text) {
                        case "length": case "isEmpty": case "toString": case "trim": case "trimLeft": case "trimRight":
                            checkArguments(e, []);
                            return e.token.text == "length" ? ValueType.intType : e.token.text == "isEmpty" ? ValueType.boolType : ValueType.stringType;
                        case "compare": case "endsWith":
                            checkArguments(e, [ValueType.stringType]);
                            return e.token.text == "compare" ? ValueType.intType : ValueType.boolType;
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
                    if (e.token.text == "getMessage") return ValueType.stringType;
                } else if (receiver == ValueType.decimalType) {
                    if (e.token.text == "toString") { checkArguments(e, []); return ValueType.stringType; }
                    if (["signum", "ceil", "floor"].canFind(e.token.text)) { checkArguments(e, []); return ValueType.intType; }
                    if (e.token.text == "round") {
                        if (e.arguments.length == 0) return ValueType.intType;
                        checkArguments(e, e.arguments.length == 1 ? [ValueType.intType] : [ValueType.intType, ValueType.intType]);
                        return ValueType.decimalType;
                    }
                } else if (receiver == ValueType.stringMap) {
                    switch (e.token.text) {
                        case "size": case "isEmpty": case "clear":
                            checkArguments(e, []);
                            return e.token.text == "size" ? ValueType.intType : e.token.text == "isEmpty" ? ValueType.boolType : ValueType.voidType;
                        case "containsKey": case "containsValue":
                            checkArguments(e, [ValueType.stringType]); return ValueType.boolType;
                        case "get":
                            checkArguments(e, [ValueType.stringType]); return ValueType.nullableString;
                        case "remove":
                            checkArguments(e, [ValueType.stringType]); return ValueType.nullableString;
                        case "add":
                            if (e.arguments.length == 1) { checkArguments(e, [ValueType.stringMap]); return ValueType.voidType; }
                            checkArguments(e, [ValueType.stringType, ValueType.stringType]); return ValueType.nullableString;
                        case "keys": case "values":
                            checkArguments(e, []); return ValueType.stringArray;
                        default: break;
                    }
                } else if (isArray(receiver)) {
                    if (receiver == ValueType.selfArray || receiver == ValueType.enumArray) {
                        e.objectClass = e.left.objectClass;
                        if (!["size", "isEmpty", "clear", "first", "last", "get", "add", "addAll", "removeAt", "set", "contains", "indexOf", "remove", "removeAll", "isSubsetOf", "reverse", "unique"].canFind(e.token.text))
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
                            if (receiver == ValueType.selfArray || receiver == ValueType.enumArray) return elementType(receiver);
                            return optionalForArray(receiver);
                        case "get":
                            if (e.arguments.length != 1 || !matches(e.arguments[0], ValueType.intType)) fail("get requires an int index", e.token);
                            return receiver == ValueType.stringArray ? ValueType.nullableString : storedValueType(elementType(receiver));
                        case "add":
                            if (e.arguments.length == 1) {
                                if (!matchesStored(e.arguments[0], elementType(receiver), e.left.objectClass)) fail("add requires an element of the array type", e.token);
                            } else if (e.arguments.length == 2) {
                                if (!matches(e.arguments[0], ValueType.intType) || !matchesStored(e.arguments[1], elementType(receiver), e.left.objectClass))
                                    fail("add requires an int index and an element of the array type", e.token);
                            } else fail("incorrect argument count", e.token);
                            return receiver;
                        case "addAll":
                            if (e.arguments.length == 1) {
                                if (!matches(e.arguments[0], receiver, e.left.objectClass)) fail("addAll requires an array of the same type", e.token);
                            } else if (e.arguments.length == 2) {
                                if (!matches(e.arguments[0], ValueType.intType) || !matches(e.arguments[1], receiver, e.left.objectClass)) fail("addAll requires an int index and an array of the same type", e.token);
                            } else fail("incorrect argument count", e.token);
                            return ValueType.voidType;
                        case "isSubsetOf":
                            if (e.arguments.length != 1 || !matches(e.arguments[0], receiver, e.left.objectClass)) fail("isSubsetOf requires an array of the same type", e.token);
                            return ValueType.boolType;
                        case "removeAll":
                            if (e.arguments.length != 1) fail("incorrect argument count", e.token);
                            auto argType = typeOf(e.arguments[0]);
                            if (argType == receiver) {
                                if (!matches(e.arguments[0], receiver, e.left.objectClass)) fail("removeAll requires an array of the same type", e.token);
                            } else if (!matchesStored(e.arguments[0], elementType(receiver), e.left.objectClass)) fail("removeAll requires an element or array of the same type", e.token);
                            return receiver;
                        case "contains": case "indexOf": case "remove":
                            if (e.arguments.length != 1 || !matchesStored(e.arguments[0], elementType(receiver), e.left.objectClass)) fail("method requires an element of the array type", e.token);
                            return e.token.text == "indexOf" ? ValueType.intType : ValueType.boolType;
                        case "removeAt":
                            if (e.arguments.length != 1 || !matches(e.arguments[0], ValueType.intType)) fail("removeAt requires an int index", e.token);
                            return receiver == ValueType.stringArray ? ValueType.nullableString : storedValueType(elementType(receiver));
                        case "set":
                            if (e.arguments.length != 2 || !matches(e.arguments[0], ValueType.intType) ||
                                !matchesStored(e.arguments[1], elementType(receiver), e.left.objectClass)) fail("set requires an int index and an element of the array type", e.token);
                            return ValueType.voidType;
                        default: break;
                    }
                }
                fail("unsupported member method '" ~ e.token.text ~ "'", e.token); assert(0);
            case ExprKind.index:
                auto array = typeOf(e.left);
                if (array == ValueType.stringMap) {
                    if (!matches(e.right, ValueType.stringType)) fail("map key must be string", e.token);
                    e.inferredType = ValueType.stringMap;
                    return ValueType.nullableString;
                }
                if (!isArray(array)) fail("indexing requires an array", e.token);
                if (!matches(e.right, ValueType.intType)) fail("array index must be int", e.token);
                if (array == ValueType.selfArray || array == ValueType.enumArray) e.objectClass = e.left.objectClass;
                e.inferredType = array;
                return array == ValueType.stringArray ? ValueType.nullableString : storedValueType(elementType(array));
            case ExprKind.castExpr:
                if (e.castType == ValueType.selfType) {
                    auto target = resolveClass(currentProgram, e.token.text, e.token);
                    if (target.isEnum) fail("enum casts are not supported", e.token);
                    if (typeOf(e.left) != ValueType.selfType ||
                        (!isAssignable(e.left.objectClass, target) && !isAssignable(target, e.left.objectClass)))
                        fail("unsupported object cast", e.token);
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
                auto target = resolveClass(currentProgram, e.token.text, e.token);
                if (target.isEnum) fail("instanceof for enums is not supported", e.token);
                auto sourceType = typeOf(e.left);
                if (sourceType != ValueType.selfType && sourceType != ValueType.nullType)
                    fail("instanceof requires an object reference", e.token);
                if (sourceType == ValueType.selfType && !isAssignable(e.left.objectClass, target) && !isAssignable(target, e.left.objectClass))
                    fail("unrelated classes in instanceof", e.token);
                e.objectClass = target;
                return ValueType.boolType;
            case ExprKind.unary:
                auto operand = typeOf(e.left);
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
                if (left == ValueType.stringMap && right == ValueType.stringMap && op == "+") {
                    e.inferredType = ValueType.stringMap;
                    return ValueType.stringMap;
                }
                if (isArray(left) && left == right && op == "+") {
                    if ((left == ValueType.selfArray || left == ValueType.enumArray) && e.left.objectClass !is e.right.objectClass)
                        fail("array element type mismatch", e.token);
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
                if (left == ValueType.nullableString) { e.nullableStringLeft = true; left = ValueType.stringType; }
                if (right == ValueType.nullableString) { e.right.nullableStringMode = NullableStringMode.nullAsEmpty; right = ValueType.stringType; }
                if (op == "+" && left == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(right)) {
                    e.right.convertToString = right; right = ValueType.stringType;
                }
                if (op == "+" && right == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(left)) {
                    e.left.convertToString = left; left = ValueType.stringType;
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
                if (left != right || left == ValueType.voidType || left == ValueType.exceptionType || left == ValueType.primaryType || left == ValueType.selfType || left == ValueType.stringMap || isArray(left)) fail("operand type mismatch", e.token);
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
                    matches(e.right, right, e.third.objectClass); left = right;
                }
                if (right == ValueType.nullType && isNullableReference(left)) {
                    matches(e.third, left, e.right.objectClass); right = left;
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
                if (left == ValueType.nullableString && (isOptionalPrimitive(right) || [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(right))) {
                    if (!matches(e.third, ValueType.stringType)) fail("conditional branch type mismatch", e.token);
                    right = left;
                }
                if (right == ValueType.nullableString && (isOptionalPrimitive(left) || [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(left))) {
                    if (!matches(e.right, ValueType.stringType)) fail("conditional branch type mismatch", e.token);
                    left = right;
                }
                if (left == ValueType.stringType && right == ValueType.nullableString) left = ValueType.nullableString;
                if (left == ValueType.nullableString && right == ValueType.stringType) right = ValueType.nullableString;
                if (left == ValueType.decimalType && right == ValueType.intType) { e.third.promoteToDecimal = true; right = ValueType.decimalType; }
                if (left == ValueType.intType && right == ValueType.decimalType) { e.right.promoteToDecimal = true; left = ValueType.decimalType; }
                if (left == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(right)) {
                    e.third.convertToString = right; right = ValueType.stringType;
                }
                if (right == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(left)) {
                    e.right.convertToString = left; left = ValueType.stringType;
                }
                if (left == ValueType.stringType && right == ValueType.stringType &&
                    (e.right.kind == ExprKind.nullLiteral || e.third.kind == ExprKind.nullLiteral)) left = right = ValueType.nullableString;
                if (left == ValueType.voidType || left != right || (hasObjectClass(left) && e.right.objectClass !is e.third.objectClass))
                    fail("conditional branch type mismatch", e.token);
                if (hasObjectClass(left)) e.objectClass = e.right.objectClass;
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
                if (!isNullableReference(left)) fail("elvis requires a supported reference type", e.token);
                auto expectedRight = left == ValueType.nullableString ? ValueType.stringType : left;
                if (!matches(e.right, expectedRight, e.left.objectClass)) fail("elvis branch type mismatch", e.token);
                e.inferredType = left;
                e.objectClass = e.left.objectClass;
                return left;
        }
    }
    private bool checkStatement(Statement s, bool allowUninitializedEnum = false) {
        final switch (s.kind) {
            case StmtKind.block:
                auto old = variables.dup; auto oldObjects = objectVariables.dup; bool returns;
                foreach (child; s.children) { auto childReturns = checkStatement(child); returns = returns || childReturns; }
                variables = old; objectVariables = oldObjects; return returns;
            case StmtKind.variable:
                s.hasContainer = !staticContext;
                if (s.token.text in variables) fail("duplicate or shadowed variable", s.token);
                s.type = resolveDeclaredType(s.type, currentProgram, s.objectName, s.token);
                if (s.type == ValueType.enumType && s.expression is null && !allowUninitializedEnum) fail("enum variables require an initializer", s.token);
                if (s.type == ValueType.primaryType && s.expression is null) fail("primary variables require an initializer", s.token);
                if (s.type == ValueType.voidType) fail("variable cannot be void", s.token);
                if (hasObjectClass(s.type)) s.objectClass = resolveClass(currentProgram, s.objectName, s.token);
                if (s.expression !is null && !matchesStored(s.expression, s.type, s.objectClass)) fail("initializer type mismatch", s.token);
                variables[s.token.text] = s.type;
                if (hasObjectClass(s.type)) objectVariables[s.token.text] = s.objectClass;
                return false;
            case StmtKind.assignment:
                auto variableType = typeOf(s.target);
                if (variableType == ValueType.nullableString) variableType = ValueType.stringType;
                if (isOptionalPrimitive(variableType)) variableType = optionalBaseType(variableType);
                if (s.target.enumConstant) fail("enum constants cannot be assigned", s.token);
                if (s.target.kind == ExprKind.index && s.target.inferredType == ValueType.stringMap)
                    variableType = ValueType.stringType;
                if ((s.target.kind != ExprKind.index || [ValueType.intArray, ValueType.boolArray, ValueType.decimalArray].canFind(s.target.inferredType)) && (s.assignmentOperator == "=" || variableType == ValueType.intType || variableType == ValueType.decimalType) ?
                    !matchesStored(s.expression, variableType, s.target.objectClass) :
                    !matches(s.expression, variableType, s.target.objectClass)) fail("assignment type mismatch", s.token);
                if (s.target.kind == ExprKind.index && s.target.inferredType == ValueType.stringMap && s.assignmentOperator != "=") fail("compound assignment to a map entry is not supported", s.token);
                s.type = variableType;
                if (s.assignmentOperator != "=" && variableType != ValueType.intType &&
                    !(variableType == ValueType.stringType && s.assignmentOperator == "+=") &&
                    !(variableType == ValueType.stringMap && s.assignmentOperator == "+=") &&
                    !(isArray(variableType) && s.assignmentOperator == "+=") &&
                    !(variableType == ValueType.decimalType && ["+=", "-=", "*=", "/=", "%="].canFind(s.assignmentOperator)))
                    fail("invalid compound assignment operands", s.token);
                return false;
            case StmtKind.expressionStmt:
                typeOf(s.expression);
                if (s.expression.kind == ExprKind.memberCall && s.expression.inferredType == ValueType.stringType)
                    fail("string query cannot be used as a statement", s.token);
                return false;
            case StmtKind.returnStmt:
                if (finallyDepth) fail("return inside finally is not supported", s.token);
                if (s.expression is null) { if (returnType != ValueType.voidType) fail("return value required", s.token); }
                else if (returnType == ValueType.voidType || !matchesStored(s.expression, returnType, returnObjectClass)) fail("return type mismatch", s.token);
                return true;
            case StmtKind.ifStmt:
                if (!matches(s.expression, ValueType.boolType)) fail("if condition must be bool", s.token);
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                auto first = checkStatement(s.children[0]); variables = old.dup; objectVariables = oldObjects.dup;
                bool second;
                if (s.children.length == 2) second = checkStatement(s.children[1]);
                variables = old; objectVariables = oldObjects; return first && second;
            case StmtKind.whileStmt:
            case StmtKind.doWhileStmt:
                if (!matches(s.expression, ValueType.boolType)) fail("loop condition must be bool", s.token);
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; return false;
            case StmtKind.forStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                if (s.initial !is null) checkStatement(s.initial);
                if (!matches(s.expression, ValueType.boolType)) fail("loop condition must be bool", s.token);
                checkStatement(s.step);
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; return false;
            case StmtKind.forEachStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                auto array = typeOf(s.expression);
                checkStatement(s.initial, true);
                if (!isArray(array) || elementType(array) != s.initial.type) fail("foreach element type mismatch", s.token);
                if (array == ValueType.selfArray && !isAssignable(s.expression.objectClass, s.initial.objectClass)) fail("foreach element type mismatch", s.token);
                if (array == ValueType.enumArray && s.expression.objectClass !is s.initial.objectClass) fail("foreach element type mismatch", s.token);
                ++loopDepth; checkStatement(s.children[0]); --loopDepth;
                variables = old; objectVariables = oldObjects; return false;
            case StmtKind.breakStmt:
            case StmtKind.continueStmt:
                if (loopDepth == 0) fail(s.token.text ~ " outside loop", s.token);
                if (finallyDepth) fail(s.token.text ~ " inside finally is not supported", s.token);
                return false;
            case StmtKind.throwStmt:
                s.type = typeOf(s.expression);
                if (s.type == ValueType.nullType) { matches(s.expression, ValueType.exceptionType); s.type = ValueType.exceptionType; }
                if (s.type == ValueType.nullableString) { s.type = ValueType.stringType; s.expression.nullableStringMode = NullableStringMode.required; }
                if (s.type != ValueType.exceptionType && s.type != ValueType.stringType) fail("throw requires exception or string", s.token);
                return true;
            case StmtKind.tryStmt:
                auto old = variables.dup; auto oldObjects = objectVariables.dup;
                auto tryReturns = checkStatement(s.children[0]);
                bool catchReturns = true, finallyReturns;
                if (s.hasCatch) {
                    variables = old.dup; objectVariables = oldObjects.dup;
                    if (s.catchName.text in variables) fail("duplicate or shadowed variable", s.catchName);
                    variables[s.catchName.text] = ValueType.exceptionType;
                    catchReturns = checkStatement(s.children[1]);
                }
                variables = old.dup; objectVariables = oldObjects.dup;
                if (s.hasFinally) {
                    ++finallyDepth; finallyReturns = checkStatement(s.children[$-1]); --finallyDepth;
                }
                variables = old; objectVariables = oldObjects;
                return (tryReturns && catchReturns) || finallyReturns;
        }
    }
}

