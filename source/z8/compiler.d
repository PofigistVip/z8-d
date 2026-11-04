module z8.compiler;

import std.algorithm : canFind;
import std.array : join;
import std.conv : to;
import std.format : format;
import std.string : replace, lastIndexOf, indexOf;
import std.math : isFinite, abs;
import z8.lexer;
public import z8.compiler_model;
public import z8.parser : Parser;

private enum coreRuntime = import("z8_core_runtime.txt");
private enum decimalRuntime = import("z8_decimal_runtime.txt");
private enum stringRuntime = import("z8_string_runtime.txt");

/// Checks the entire program before emitting code; unsupported constructs fail closed.
class Checker {
    private Method[string] methods;
    private Field[string] fields;
    private Program[string] visibleClasses;
    private Program[string] allClasses;
    private Program currentProgram;
    private bool staticContext;
    private ValueType[string] variables;
    private Program[string] objectVariables;
    private ValueType returnType;
    private Program returnObjectClass;
    private size_t loopDepth;
    private size_t finallyDepth;
    private void fail(string message, Token t) { throw new CompileException(message, t.position); }
    private static bool isConstantInitializer(Expression expression) {
        switch (expression.kind) {
            case ExprKind.integer: case ExprKind.decimalLiteral: case ExprKind.boolean: case ExprKind.stringLiteral: case ExprKind.nullLiteral: return true;
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
                else if (p.type == ValueType.stringType && [ValueType.intType, ValueType.boolType, ValueType.decimalType].canFind(actual)) weight += 100;
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
            if (field.isStatic && field.initializer !is null && !isConstantInitializer(field.initializer))
                fail("static field initializer must be a constant expression", field.name);
            if (field.initializer !is null && !matchesStored(field.initializer, field.type, field.objectClass))
                fail("field initializer type mismatch", field.name);
        }
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
                e.objectClass = resolveClass(currentProgram, e.token.text, e.token);
                if (e.objectClass.isEnum) fail("cannot instantiate an enum", e.token);
                return ValueType.selfType;
            case ExprKind.field:
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields)) {
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
                if (receiver == ValueType.selfType) {
                    auto owner = e.left.objectClass;
                    auto target = lookupMethod(owner, e.token.text);
                    if (target is null) fail("unknown method '" ~ e.token.text ~ "'", e.token);
                    if (target.isStatic) fail("static method call through an instance is not supported", e.token);
                    target = selectOverload(target, e);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    e.instanceCall = true;
                    return checkCall(target, target.owner, e);
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
                if (left != right || left == ValueType.voidType || left == ValueType.exceptionType || left == ValueType.selfType || left == ValueType.stringMap || isArray(left)) fail("operand type mismatch", e.token);
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
                if (s.token.text in variables) fail("duplicate or shadowed variable", s.token);
                s.type = resolveDeclaredType(s.type, currentProgram, s.objectName, s.token);
                if (s.type == ValueType.enumType && s.expression is null && !allowUninitializedEnum) fail("enum variables require an initializer", s.token);
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

private string dType(ValueType type, Program objectClass = null) {
    final switch (type) {
        case ValueType.intType: return "long"; case ValueType.boolType: return "bool";
        case ValueType.decimalType: return "Z8Decimal";
        case ValueType.voidType: return "void"; case ValueType.stringType: return "wstring";
        case ValueType.exceptionType: return "Throwable";
        case ValueType.selfType: assert(objectClass !is null); return objectClass.emittedName;
        case ValueType.selfArray: assert(objectClass !is null); return "Z8Array!(" ~ objectClass.emittedName ~ ")";
        case ValueType.stringMap: return "Z8StringMap";
        case ValueType.intArray: return "Z8Array!long";
        case ValueType.decimalArray: return "Z8Array!Z8Decimal";
        case ValueType.boolArray: return "Z8Array!bool";
        case ValueType.stringArray: return "Z8Array!wstring";
        case ValueType.nullType: assert(0, "null has no concrete D type");
        case ValueType.nullableString: return "wstring";
        case ValueType.enumType: assert(objectClass !is null); return objectClass.emittedName;
        case ValueType.enumArray: assert(objectClass !is null); return "Z8Array!(" ~ objectClass.emittedName ~ ")";
        case ValueType.optionalInt: return "Z8Optional!long";
        case ValueType.optionalBool: return "Z8Optional!bool";
        case ValueType.optionalDecimal: return "Z8Optional!Z8Decimal";
    }
}
/// The Java runtime stores strings as UTF-16; preserve its code-unit ordering.
private string emitStringLiteral(string text) {
    auto raw = text.to!wstring;
    wchar[] value;
    for (size_t i = 1; i + 1 < raw.length; ++i) {
        wchar c = raw[i];
        if (c == '\\') {
            c = raw[++i];
            switch (c) {
                case 'b': c = '\b'; break; case 'f': c = '\f'; break;
                case 'n': c = '\n'; break; case 'r': c = '\r'; break; case 't': c = '\t'; break;
                default: break; // lexer has validated quotes and backslash
            }
            value ~= c;
        } else if (c >= ' ' || c == '\t' || c == '\r' || c == '\n') value ~= c;
    }
    if (value.length == 0) return `""w`;
    string[] units;
    foreach (c; value) units ~= format("cast(wchar)0x%04X", cast(uint)c);
    return "[" ~ units.join(", ") ~ "].idup";
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
        foreach (i, argument; e.arguments) {
            savedOverrides ~= argument.emittedOverride;
            auto required = argument.optionalRequired, promote = argument.promoteToDecimal;
            auto convert = argument.convertToString;
            if (required) { argument.optionalRequired = false; argument.promoteToDecimal = false; argument.convertToString = ValueType.voidType; }
            auto name = "z8_arg_" ~ suffix ~ "_" ~ i.to!string;
            value ~= "auto " ~ name ~ " = " ~ emitExpr(argument) ~ "; ";
            argument.optionalRequired = required; argument.promoteToDecimal = promote; argument.convertToString = convert;
            argument.emittedOverride = name;
        }
        value ~= "return " ~ emitExprRaw(e) ~ "; })()";
        if (!e.builtinCall.length) e.left.emittedOverride = savedReceiver;
        foreach (i, argument; e.arguments) argument.emittedOverride = savedOverrides[i];
    } else value = emitExprRaw(e);
    if (e.nonNullStringResult) value = "z8_string_or_empty(" ~ value ~ ")";
    if (e.optionalRequired) value = "z8_optional_require(" ~ value ~ ")";
    if (e.nullableStringMode == NullableStringMode.required) value = "z8_string_required(" ~ value ~ ")";
    if (e.nullableStringMode == NullableStringMode.nullAsEmpty) value = "z8_string_or_empty(" ~ value ~ ")";
    if (e.kind == ExprKind.conditional && isNullableReference(e.inferredType))
        value = "cast(" ~ dType(e.inferredType, e.objectClass) ~ ")(" ~ value ~ ")";
    if (e.promoteToDecimal) value = "z8_decimal_from_int(" ~ value ~ ")";
    if (e.optionalWrap) value = "z8_optional_wrap(" ~ value ~ ")";
    if (e.convertToString == ValueType.intType) return "(" ~ value ~ ").to!string.to!wstring";
    if (e.convertToString == ValueType.boolType) return "(" ~ value ~ " ? \"true\"w : \"false\"w)";
    if (e.convertToString == ValueType.decimalType) return "(" ~ value ~ ").z8_string()";
    return value;
}
private string emitReceiver(Expression e) {
    if (e.kind == ExprKind.selfRef || e.kind == ExprKind.superRef) return "(" ~ emitExpr(e) ~ ")";
    return "z8_nonnull(" ~ emitExpr(e) ~ ")";
}
private string emitExprRaw(Expression e) {
    final switch (e.kind) {
        case ExprKind.integer:
            return "(cast(long)(" ~ e.token.text.replace(" ", "").replace("\t", "") ~ "))";
        case ExprKind.decimalLiteral:
            return "z8_decimal_literal(\"" ~ e.token.text.replace(" ", "").replace("\t", "") ~ "\")";
        case ExprKind.boolean: return e.token.text;
        case ExprKind.stringLiteral: return emitStringLiteral(e.token.text);
        case ExprKind.nullLiteral: return isOptionalPrimitive(e.inferredType) ? dType(e.inferredType) ~ ".init" : e.inferredType == ValueType.voidType ? "null" : "cast(" ~ dType(e.inferredType, e.objectClass) ~ ")null";
        case ExprKind.arrayLiteral:
            string[] elements; foreach (element; e.arguments)
                elements ~= (e.inferredType == ValueType.selfArray || e.inferredType == ValueType.enumArray) ? "cast(" ~ e.objectClass.emittedName ~ ")(" ~ emitExpr(element) ~ ")" : emitExpr(element);
            return "new " ~ dType(e.inferredType, e.objectClass) ~ "(" ~ (elements.length ? "[" ~ elements.join(", ") ~ "]" ~ ([ValueType.intArray, ValueType.boolArray, ValueType.decimalArray].canFind(e.inferredType) ? ", true" : "") : "") ~ ")";
        case ExprKind.variable: return e.isField ? (e.targetClass.length ? e.targetClass ~ ".f_" : "this.f_") ~ e.token.text : "v_" ~ e.token.text;
        case ExprKind.selfRef: return "this";
        case ExprKind.superRef: return "super";
        case ExprKind.newSelf: return "z8_new!(" ~ e.objectClass.emittedName ~ ")()";
        case ExprKind.field:
            if (e.enumConstant) return e.targetClass ~ ".e_" ~ e.token.text;
            return (e.targetClass.length ? e.targetClass : emitReceiver(e.left)) ~ ".f_" ~ e.token.text;
        case ExprKind.call:
            string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
            return "m_" ~ e.token.text ~ "(" ~ args.join(", ") ~ ")";
        case ExprKind.memberCall:
            if (e.builtinCall.length) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
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
            if (e.inferredType == ValueType.stringMap) {
                string[] args; foreach (a; e.arguments) args ~= emitExpr(a);
                return "z8_invoke!\"z8_" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ (args.length ? ", " ~ args.join(", ") : "") ~ ")";
            }
            if (e.inferredType == ValueType.exceptionType) return "z8_message(z8_nonnull(" ~ emitExpr(e.left) ~ "))";
            if (e.inferredType == ValueType.decimalType) {
                auto receiver = "(" ~ emitExpr(e.left) ~ ")";
                if (e.token.text == "toString") return receiver ~ ".z8_string()";
                if (["signum", "ceil", "floor"].canFind(e.token.text)) return receiver ~ ".z8_" ~ e.token.text ~ "()";
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
            if (e.inferredType == ValueType.stringMap) return "z8_invoke!\"z8_get\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            return "z8_array_at(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
        case ExprKind.castExpr:
            return e.castType == ValueType.selfType ? "z8_cast!(" ~ e.objectClass.emittedName ~ ")(" ~ emitExpr(e.left) ~ ")" : emitExpr(e.left);
        case ExprKind.instanceOf:
            return "(cast(" ~ e.objectClass.emittedName ~ ")(" ~ emitExpr(e.left) ~ ") !is null)";
        case ExprKind.unary:
            if (e.optionalDecimalUnary) return "(" ~ e.token.text ~ "z8_optional_require(" ~ emitExpr(e.left) ~ "))";
            if (e.optionalBoolUnary) return "(!z8_optional_require(" ~ emitExpr(e.left) ~ "))";
            if (e.optionalIntUnary) return "z8_optional_int_unary!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ")";
            return "(" ~ e.token.text ~ emitExpr(e.left) ~ ")";
        case ExprKind.binary:
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
            if (e.inferredType == ValueType.stringMap)
                return "z8_map_union(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (isArray(e.inferredType))
                return "z8_array_union(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
            if (e.nullableStringLeft)
                return "z8_nullable_string_binary!\"" ~ e.token.text ~ "\"(" ~ emitExpr(e.left) ~ ", " ~ emitExpr(e.right) ~ ")";
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
private string emitStatement(Statement s) {
    final switch (s.kind) {
        case StmtKind.block:
            string result = "{\n"; foreach (child; s.children) result ~= emitStatement(child); return result ~ "}\n";
        case StmtKind.variable:
        case StmtKind.assignment:
        case StmtKind.expressionStmt: return emitSimple(s) ~ ";\n";
        case StmtKind.returnStmt: return "return" ~ (s.expression is null ? "" : " " ~ emitExpr(s.expression)) ~ ";\n";
        case StmtKind.ifStmt:
            auto result = "if (" ~ emitExpr(s.expression) ~ ") {\n" ~ emitStatement(s.children[0]) ~ "}\n";
            if (s.children.length == 2) result ~= "else {\n" ~ emitStatement(s.children[1]) ~ "}\n";
            return result;
        case StmtKind.whileStmt:
            return "while (" ~ emitExpr(s.expression) ~ ") {\n" ~ emitStatement(s.children[0]) ~ "}\n";
        case StmtKind.doWhileStmt:
            return "do {\n" ~ emitStatement(s.children[0]) ~ "} while (" ~ emitExpr(s.expression) ~ ");\n";
        case StmtKind.forStmt:
            return "for (" ~ (s.initial is null ? "" : emitSimple(s.initial)) ~ "; " ~ emitExpr(s.expression) ~ "; " ~ emitSimple(s.step) ~ ") {\n" ~ emitStatement(s.children[0]) ~ "}\n";
        case StmtKind.forEachStmt:
            auto suffix = s.token.position.offset.to!string;
            auto iter = "z8_iter_" ~ suffix, versionName = "z8_version_" ~ suffix, indexName = "z8_index_" ~ suffix;
            return "{\nauto " ~ iter ~ " = " ~ emitReceiver(s.expression) ~ ";\nauto " ~ versionName ~ " = " ~ iter ~ ".z8_version;\n" ~
                "for (long " ~ indexName ~ " = 0; " ~ indexName ~ " != " ~ iter ~ ".z8_size(); ++" ~ indexName ~ ") {\n" ~
                "if (" ~ versionName ~ " != " ~ iter ~ ".z8_version) throw new Exception(\"array modified during iteration\");\n" ~
                dStorageType(s.initial.type, s.initial.objectClass) ~ " v_" ~ s.initial.token.text ~ " = " ~ iter ~ ".z8_get(" ~ indexName ~ ");\n" ~
                emitStatement(s.children[0]) ~ "}\n}\n";
        case StmtKind.breakStmt: return "break;\n";
        case StmtKind.continueStmt: return "continue;\n";
        case StmtKind.throwStmt:
            return "throw " ~ (s.type == ValueType.stringType ? "new Exception(z8_to_utf8(" ~ emitExpr(s.expression) ~ "))" : "z8_nonnull(" ~ emitExpr(s.expression) ~ ")") ~ ";\n";
        case StmtKind.tryStmt:
            auto result = "try " ~ emitStatement(s.children[0]);
            if (s.hasCatch) result ~= "catch (Throwable v_" ~ s.catchName.text ~ ") " ~ emitStatement(s.children[1]);
            if (s.hasFinally) result ~= "finally " ~ emitStatement(s.children[$-1]);
            return result;
    }
}
private string emitSimple(Statement s) {
    if (s.kind == StmtKind.variable)
        return dStorageType(s.type, s.objectClass) ~ " v_" ~ s.token.text ~ " = " ~
            (s.expression !is null ? emitExpr(s.expression) : s.type == ValueType.intType ? "z8_optional_wrap(0L)" : s.type == ValueType.boolType ? "z8_optional_wrap(false)" : s.type == ValueType.decimalType ? "z8_optional_wrap(z8_decimal_from_int(0))" : defaultValue(s.type, s.objectClass));
    if (s.kind == StmtKind.expressionStmt) return emitExpr(s.expression);
    assert(s.kind == StmtKind.assignment);
    if (s.target.kind == ExprKind.index && s.target.inferredType == ValueType.stringMap)
        return "z8_invoke!\"z8_add\"(" ~ emitExpr(s.target.left) ~ ", " ~ emitExpr(s.target.right) ~ ", " ~ emitExpr(s.expression) ~ ")";
    auto name = emitExpr(s.target);
    if (s.type == ValueType.stringMap && s.assignmentOperator == "+=")
        return "z8_map_add_assign(" ~ name ~ ", " ~ emitExpr(s.expression) ~ ")";
    if (isArray(s.type) && s.assignmentOperator == "+=")
        return "z8_array_add_assign(" ~ name ~ ", " ~ emitExpr(s.expression) ~ ")";
    if (s.type == ValueType.intType && s.assignmentOperator != "=")
        return "z8_optional_int_assign!\"" ~ s.assignmentOperator[0 .. $-1] ~ "\"(" ~ name ~ ", " ~ emitExpr(s.expression) ~ ")";
    if (s.type == ValueType.decimalType && s.assignmentOperator != "=")
        return "z8_optional_decimal_assign!\"" ~ s.assignmentOperator[0 .. $-1] ~ "\"(" ~ name ~ ", " ~ emitExpr(s.expression) ~ ")";
    if (s.type == ValueType.stringType && s.assignmentOperator == "+=")
        return "z8_string_add_assign(" ~ name ~ ", " ~ emitExpr(s.expression) ~ ")";
    return name ~ " " ~ s.assignmentOperator ~ " " ~ emitExpr(s.expression);
}
private string defaultValue(ValueType type, Program objectClass = null) {
    if (type == ValueType.exceptionType) return "new Exception(null)";
    if (type == ValueType.decimalType) return "z8_decimal_from_int(0)";
    if (type == ValueType.selfType) return "z8_new!(" ~ dType(type, objectClass) ~ ")()";
    if (type == ValueType.stringMap) return "new Z8StringMap()";
    if (isArray(type)) return "new " ~ dType(type, objectClass) ~ "()";
    if (type == ValueType.intType) return "0";
    if (type == ValueType.stringType) return `""w`;
    assert(type == ValueType.boolType); return "false";
}
string compile(string source) {
    auto program = (new Parser(source)).parse();
    program.qualifiedName = program.name.text;
    program.emittedName = "Z8_" ~ program.name.text;
    Program[string] programs;
    programs[program.qualifiedName] = program;
    prepareInheritance([program], programs);
    (new Checker).prepareDeclarations(program, programs);
    (new Checker).check(program, programs);
    checkDefaultConstruction([program]);
    return emitPrograms([program]);
}

private void prepareInheritance(Program[] ordered, Program[string] programs) {
    foreach (program; ordered) {
        try { (new Checker).bindBase(program, programs); }
        catch (CompileException e) { e.sourceName = program.sourceName; throw e; }
    }
    bool[string] active, finished;
    void visit(Program program) {
        if (program.qualifiedName in finished) return;
        if (program.qualifiedName in active) {
            auto error = new CompileException("cyclic inheritance", program.baseToken.position);
            error.sourceName = program.sourceName; throw error;
        }
        active[program.qualifiedName] = true;
        if (program.baseClass !is null) visit(program.baseClass);
        active.remove(program.qualifiedName);
        finished[program.qualifiedName] = true;
    }
    foreach (program; ordered) visit(program);
}

/// Prevent unbounded recursive allocation of automatically created object fields.
private void checkDefaultConstruction(Program[] programs) {
    bool[string] active, finished;
    void visit(Program program) {
        if (program.qualifiedName in finished) return;
        active[program.qualifiedName] = true;
        if (program.baseClass !is null) {
            if (program.baseClass.qualifiedName in active) {
                auto error = new CompileException("recursive automatic object construction", program.baseToken.position);
                error.sourceName = program.sourceName; throw error;
            }
            visit(program.baseClass);
        }
        foreach (field; program.fields) {
            if (field.isStatic) continue;
            if (field.type != ValueType.selfType) continue;
            Program target;
            if (field.initializer is null) target = field.objectClass;
            else if (field.initializer.kind == ExprKind.newSelf) target = field.initializer.objectClass;
            if (target is null) continue;
            if (target.qualifiedName in active) {
                auto error = new CompileException("recursive automatic object construction", field.name.position);
                error.sourceName = program.sourceName; throw error;
            }
            visit(target);
        }
        active.remove(program.qualifiedName);
        finished[program.qualifiedName] = true;
    }
    foreach (program; programs) visit(program);
}

/// Each unit name is the dotted path of the .bl file relative to the source root.
string compileSources(SourceUnit[] units, string entry = "") {
    if (!units.length) throw new CompileException("no .bl source files found", Position.init);
    Program[] ordered;
    Program[string] programs;
    foreach (unit; units) {
        Program program;
        try { program = (new Parser(unit.source)).parse(); }
        catch (LexException e) {
            auto wrapped = new CompileException(e.msg, e.position); wrapped.sourceName = unit.path; throw wrapped;
        } catch (CompileException e) { e.sourceName = unit.path; throw e; }
        auto dot = unit.name.lastIndexOf('.');
        auto simpleName = dot < 0 ? unit.name : unit.name[dot + 1 .. $];
        if (program.name.text != simpleName) {
            auto error = new CompileException("class name must match its file name", program.name.position);
            error.sourceName = unit.path; throw error;
        }
        if (unit.name in programs) {
            auto error = new CompileException("duplicate source '" ~ unit.name ~ "'", program.name.position);
            error.sourceName = unit.path; throw error;
        }
        program.sourceName = unit.path;
        program.qualifiedName = unit.name;
        program.emittedName = "Z8p_";
        foreach (i; 0 .. unit.name.length) program.emittedName ~= format("%02X", cast(ubyte)unit.name[i]);
        programs[unit.name] = program;
        ordered ~= program;
    }
    prepareInheritance(ordered, programs);
    foreach (program; ordered) {
        try { (new Checker).prepareDeclarations(program, programs); }
        catch (CompileException e) { e.sourceName = program.sourceName; throw e; }
    }
    bool[string] checked;
    void checkInOrder(Program program) {
        if (program.qualifiedName in checked) return;
        if (program.baseClass !is null) checkInOrder(program.baseClass);
        try { (new Checker).check(program, programs); }
        catch (CompileException e) { e.sourceName = program.sourceName; throw e; }
        checked[program.qualifiedName] = true;
    }
    foreach (program; ordered) checkInOrder(program);
    checkDefaultConstruction(ordered);
    auto output = emitPrograms(ordered);
    if (entry.length) {
        auto dot = entry.lastIndexOf('.');
        if (dot <= 0 || dot + 1 == entry.length)
            throw new CompileException("entry must be a qualified class and method name", Position.init);
        auto ownerName = entry[0 .. dot];
        auto methodName = entry[dot + 1 .. $];
        auto owner = ownerName in programs;
        if (owner is null) throw new CompileException("entry class not found: " ~ ownerName, Position.init);
        Method target;
        Method named;
        foreach (candidate; (*owner).methods) if (candidate.name.text == methodName) {
            named = candidate;
            if (candidate.parameters.length == 0) { target = candidate; break; }
        }
        if (target is null && named !is null) {
            auto error = new CompileException("entry must be a public static method with no parameters returning void or int", named.name.position);
            error.sourceName = (*owner).sourceName; throw error;
        }
        if (target is null) throw new CompileException("entry method not found: " ~ entry, Position.init);
        if (!target.isPublic || !target.isStatic || target.parameters.length != 0 ||
            (target.returnType != ValueType.voidType && target.returnType != ValueType.intType)) {
            auto error = new CompileException("entry must be a public static method with no parameters returning void or int", target.name.position);
            error.sourceName = (*owner).sourceName; throw error;
        }
        auto call = (*owner).emittedName ~ ".m_" ~ target.name.text ~ "()";
        output ~= target.returnType == ValueType.voidType ? "\nvoid main() { " ~ call ~ "; }\n" :
            "\nint main() { return cast(int)(" ~ call ~ "); }\n";
    }
    return output;
}

private string emitPrograms(Program[] programs) {
    string result = coreRuntime;
    result ~= "\n" ~ decimalRuntime ~ "\n" ~ stringRuntime ~ "\n";
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
        result ~= "class " ~ program.emittedName ~ (program.baseClass is null ? "" : " : " ~ program.baseClass.emittedName) ~ " {\n";
        result ~= "alias Z8Self = " ~ program.emittedName ~ ";\n";
        bool invalidObjectField;
        foreach (field; program.fields)
            if (!field.isStatic && field.type == ValueType.selfType && field.initializer !is null && field.initializer.kind == ExprKind.nullLiteral) {
                invalidObjectField = true; break;
            }
        if (invalidObjectField) result ~= "enum bool z8_invalid_object_field = true;\n";
        result ~= (program.baseClass is null ? "" : "override ") ~ "void z8_validate_object() { ";
        if (program.baseClass !is null) result ~= "super.z8_validate_object(); ";
        if (invalidObjectField) result ~= "throw new Exception(\"null object field initializer\"); ";
        result ~= "}\n";
        bool hasInstanceFields, hasStaticFields;
        foreach (field; program.fields) {
            result ~= (field.isStatic ? "__gshared " : "") ~ dStorageType(field.type, field.objectClass) ~ " f_" ~ field.name.text ~ ";\n";
            if (field.isStatic) hasStaticFields = true; else hasInstanceFields = true;
        }
        if (hasInstanceFields) {
            result ~= "this() {\n";
            foreach (field; program.fields)
                if (!field.isStatic && field.initializer is null) result ~= "this.f_" ~ field.name.text ~ " = " ~ (field.type == ValueType.intType ? "z8_optional_wrap(0L)" : field.type == ValueType.boolType ? "z8_optional_wrap(false)" : field.type == ValueType.decimalType ? "z8_optional_wrap(z8_decimal_from_int(0))" : defaultValue(field.type, field.objectClass)) ~ ";\n";
            foreach (field; program.fields)
                if (!field.isStatic && field.initializer !is null) result ~= "this.f_" ~ field.name.text ~ " = " ~ emitExpr(field.initializer) ~ ";\n";
            result ~= "}\n";
        }
        if (hasStaticFields) {
            result ~= "shared static this() {\n";
            foreach (field; program.fields) if (field.isStatic)
                result ~= "f_" ~ field.name.text ~ " = " ~ (field.initializer is null ? field.type == ValueType.intType ? "z8_optional_wrap(0L)" : field.type == ValueType.boolType ? "z8_optional_wrap(false)" : field.type == ValueType.decimalType ? "z8_optional_wrap(z8_decimal_from_int(0))" : defaultValue(field.type, field.objectClass) : emitExpr(field.initializer)) ~ ";\n";
            result ~= "}\n";
        }
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
                    result ~= "alias m_" ~ m.name.text ~ " = " ~ program.baseClass.emittedName ~ ".m_" ~ m.name.text ~ ";\n";
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
                result ~= (m.isStatic ? "static " : "final ") ~ dStorageType(m.returnType, m.returnObjectClass) ~ " m_" ~ m.name.text ~ "(" ~ nativeParams.join(", ") ~ ") { " ~
                    (m.returnType == ValueType.voidType ? "" : "return ") ~ "m_" ~ m.name.text ~ "(" ~ nativeArgs.join(", ") ~ "); }\n";
            }
            auto modifiers = m.isStatic ? "static " : m.overrides ? "override " : m.isVirtual ? "" : "final ";
            result ~= modifiers ~ dStorageType(m.returnType, m.returnObjectClass) ~ " m_" ~ m.name.text ~ "(" ~ params.join(", ") ~ ")\n" ~ emitStatement(m.body);
        }
        result ~= "}\n";
    }
    return result;
}
