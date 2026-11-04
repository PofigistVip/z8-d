module z8.semantic;

import std.algorithm : canFind;
import std.conv : to;
import std.string : lastIndexOf, indexOf, icmp;
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
    private bool importedMath;
    private ValueType[string] variables;
    private Program[string] objectVariables;
    private ValueType returnType;
    private Program returnObjectClass;
    private size_t loopDepth;
    private size_t finallyDepth;
    private void fail(string message, Token t) { throw new CompileException(message, t.position); }
    private static bool isConstantInitializer(Expression expression) {
        switch (expression.kind) {
            case ExprKind.integer: case ExprKind.decimalLiteral: case ExprKind.boolean: case ExprKind.stringLiteral: case ExprKind.guidLiteral: case ExprKind.binaryLiteral: case ExprKind.datespanLiteral: case ExprKind.dateLiteral: case ExprKind.nullLiteral: return true;
            case ExprKind.arrayLiteral:
                foreach (item; expression.arguments) if (!isConstantInitializer(item)) return false;
                return true;
            case ExprKind.mapEntry: return isConstantInitializer(expression.left) && isConstantInitializer(expression.right);
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
    private bool accessible(Program owner, bool isPublic, bool isProtected) {
        return owner is currentProgram || isPublic || (isProtected && isAssignable(currentProgram, owner));
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
            if (field.isAuto && (field.isStatic || field.type != ValueType.selfArray))
                fail("auto requires an instance array of object references", field.name);
            if (field.isStatic && (field.type == ValueType.selfType || field.type == ValueType.enumType))
                fail("static object and enum fields are not supported", field.name);
            if (field.type == ValueType.enumType && field.initializer is null)
                fail("enum fields require an initializer", field.name);
            if (field.type == ValueType.primaryType && field.initializer is null)
                fail("primary fields require an initializer", field.name);
        }
        foreach (method; program.methods) {
            method.returnType = resolveDeclaredType(method.returnType, program, method.returnObjectName, method.name);
            if (method.isCastOperator && method.returnType == ValueType.enumType)
                fail("conversion operators to enums are not supported", method.name);
            if (method.isCastOperator && method.returnType == ValueType.selfType) {
                method.returnObjectClass = resolveClass(program, method.returnObjectName, method.name);
                method.name.text = "operatorCast:" ~ method.returnObjectClass.qualifiedName;
            }
            foreach (ref parameter; method.parameters)
                parameter.type = resolveDeclaredType(parameter.type, program, parameter.objectName, parameter.name);
        }
    }
    private Method findConversion(Program owner, ValueType target, Program targetClass = null) {
        Method best;
        size_t bestDistance = size_t.max;
        for (auto current = owner; current !is null; current = current.baseClass)
            foreach (method; current.methods) {
                if (!method.isCastOperator || method.returnType != target ||
                    !accessible(method.owner, method.isPublic, method.isProtected)) continue;
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
    private bool matches(Expression e, ValueType expected, Program expectedClass = null) {
        if (e.kind == ExprKind.arrayLiteral && (expected == ValueType.selfArray || expected == ValueType.enumArray)) e.objectClass = expectedClass;
        auto actual = typeOf(e, expected);
        if (actual == ValueType.selfType) {
            if (expected == ValueType.selfType && isAssignable(e.objectClass, expectedClass)) return true;
            auto conversion = findConversion(e.objectClass, expected, expectedClass);
            if (conversion !is null) {
                e.userConversion = conversion;
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
            e.inferredType = expected; e.objectClass = expectedClass; return true;
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
            (expected != ValueType.selfArray && expected != ValueType.enumType && expected != ValueType.enumArray) || e.objectClass is expectedClass);
    }
    private bool matchesStored(Expression e, ValueType expected, Program expectedClass = null) {
        if (expected != ValueType.intType && expected != ValueType.boolType && expected != ValueType.decimalType) return matches(e, expected, expectedClass);
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
    private bool matchesInitializer(Expression e, ValueType expected, Program expectedClass = null) {
        if (expected == ValueType.fileType && [ValueType.stringType, ValueType.nullableString].canFind(typeOf(e))) {
            e.makeFile = true; return true;
        }
        return matchesStored(e, expected, expectedClass);
    }
    private ValueType checkCall(Method method, Program owner, Expression e) {
        if (e.arguments.length != method.parameters.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) {
            auto p = method.parameters[i];
            if (arg.kind == ExprKind.arrayLiteral && !arg.typedInitializer) fail("array initializer requires a known target", arg.token);
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
    private Method selectOverload(Method first, Expression e, bool allowNoMatch = false, bool binaryOperator = false) {
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
                    if (actual == ValueType.selfArray && e.arguments[i].objectClass !is resolveClass(candidate.owner, p.objectName, p.name)) applicable = false;
                    if (actual == ValueType.enumType && e.arguments[i].objectClass !is resolveClass(candidate.owner, p.objectName, p.name)) applicable = false;
                    if (actual == ValueType.enumArray && e.arguments[i].objectClass !is resolveClass(candidate.owner, p.objectName, p.name)) applicable = false;
                } else if (actual == ValueType.selfType && findConversion(e.arguments[i].objectClass, p.type) !is null) weight += 100;
                else if (actual == ValueType.intType && p.type == ValueType.decimalType) weight += 100;
                else if (actual == ValueType.intType && p.type == ValueType.dateType) weight += 100;
                else if (p.type == ValueType.binaryType && [ValueType.stringType, ValueType.nullableString, ValueType.fileType].canFind(actual)) weight += 100;
                else if ([ValueType.fileType, ValueType.exceptionType].canFind(p.type) && [ValueType.stringType, ValueType.nullableString].canFind(actual)) weight += 100;
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
        if (ambiguous) fail("ambiguous method overload", e.token);
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
        return false;
    }
    private void checkArguments(Expression e, ValueType[] types) {
        if (e.arguments.length != types.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) if (!matches(arg, types[i])) fail("argument type mismatch", arg.token);
    }
    private void checkStoredArguments(Expression e, ValueType[] types) {
        if (e.arguments.length != types.length) fail("incorrect argument count", e.token);
        foreach (i, arg; e.arguments) if (!matchesStored(arg, types[i])) fail("argument type mismatch", arg.token);
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
            if (targetPackage == packageName) visibleClasses[target.name.text] = target;
        }
        Program[string] imported;
        foreach (item; program.imports) {
            if (item.name == "org.zenframework.z8.lang.encoding") continue;
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
                foreach (i, p; m.parameters) {
                    auto baseParam = baseMethod.parameters[i];
                    if (p.type != baseParam.type || (hasObjectClass(p.type) &&
                        resolveClass(program, p.objectName, p.name) !is resolveClass(baseMethod.owner, baseParam.objectName, baseParam.name)))
                        fail("override parameter type mismatch", p.name);
                }
                if (baseMethod.isPublic && !m.isPublic) fail("override cannot reduce public access", m.name);
                if (baseMethod.isProtected && !m.isPublic && !m.isProtected) fail("override cannot reduce protected access", m.name);
                if (!m.isStatic) { m.isVirtual = true; m.overrides = true; }
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
            if (field.initializer !is null && !matchesInitializer(field.initializer, field.type, field.objectClass))
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
            checkStatement(m.body);
            auto returns = analyzeControlFlow(m.body);
            if (returnType != ValueType.voidType && !returns) fail("method may finish without returning a value", m.name);
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
                    expected = resolveDeclaredType(e.initializerType, currentProgram, e.initializerObjectName, e.token);
                    if (hasObjectClass(expected)) e.objectClass = resolveClass(currentProgram, e.initializerObjectName, e.token);
                }
                if (isMap(expected)) {
                    auto keyType = mapKeyType(expected);
                    auto valueType = mapValueType(expected);
                    foreach (entry; e.arguments) {
                        if (entry.kind != ExprKind.mapEntry) fail("map initializer requires key-value pairs", entry.token);
                        if (entry.left.kind == ExprKind.nullLiteral || entry.right.kind == ExprKind.nullLiteral)
                            fail("null literal is not supported in a map initializer pair", entry.token);
                        if (keyType == ValueType.stringType) {
                            if (![ValueType.stringType, ValueType.nullableString].canFind(typeOf(entry.left)))
                                fail("map key type mismatch", entry.left.token);
                        } else if (!matchesStored(entry.left, keyType)) fail("map key type mismatch", entry.left.token);
                        if (valueType == ValueType.stringType) {
                            if (![ValueType.stringType, ValueType.nullableString].canFind(typeOf(entry.right)))
                                fail("map value type mismatch", entry.right.token);
                        } else {
                            // Array/map type casts in the original use inheritance,
                            // not scalar conversion operators such as int -> decimal.
                            if (valueType == ValueType.decimalType &&
                                ![ValueType.decimalType, ValueType.optionalDecimal].canFind(typeOf(entry.right)))
                                fail("map value type mismatch", entry.right.token);
                            if (!matchesStored(entry.right, valueType)) fail("map value type mismatch", entry.right.token);
                        }
                    }
                    e.inferredType = expected; return expected;
                }
                if (!isArray(expected)) fail("array initializer requires an array type", e.token);
                foreach (element; e.arguments)
                    if (!matchesStored(element, elementType(expected), e.objectClass)) fail("array element type mismatch", element.token);
                e.inferredType = expected; return expected;
            case ExprKind.mapEntry: fail("key-value pair requires a map initializer", e.token); assert(0);
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
                    return staticField.type == ValueType.stringType ? ValueType.nullableString : storedValueType(staticField.type);
                }
                auto receiverType = typeOf(e.left);
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
                        case "details": return ValueType.stringMap;
                        default: fail("unknown file field", e.token);
                    }
                }
                if (receiverType != ValueType.selfType) fail("field access requires an object", e.token);
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
                auto selected = selectOverload(*method, e);
                if (staticContext && !selected.isStatic) fail("instance method in static context", e.token);
                if (!accessible(selected.owner, selected.isPublic, selected.isProtected)) fail("method is not accessible", e.token);
                if (selected.isStatic) e.targetClass = selected.owner.emittedName;
                return checkCall(selected, selected.owner, e);
            case ExprKind.memberCall:
                if (e.left.kind == ExprKind.variable && e.left.token.text == "Math" && importedMath &&
                    !(e.left.token.text in variables) && !(e.left.token.text in fields)) {
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
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) && e.left.token.text == "string") {
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
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) && e.left.token.text == "file") {
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
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) && e.left.token.text == "binary") {
                    if (e.token.text != "zip" || e.arguments.length != 1) fail("unsupported static binary method", e.token);
                    auto source = typeOf(e.arguments[0]);
                    auto expectedSource = source == ValueType.fileType ? ValueType.fileType : ValueType.binaryArray;
                    checkArguments(e, [expectedSource]); e.builtinCall = "z8_binary_zip"; return ValueType.binaryType;
                }
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) && e.left.token.text == "geometry") {
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
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) && e.left.token.text == "date") {
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
                if (e.left.kind == ExprKind.variable && !(e.left.token.text in variables) && !(e.left.token.text in fields) && e.left.token.text == "datespan") {
                    if (e.token.text != "parse") fail("unsupported static datespan method", e.token);
                    checkArguments(e, [ValueType.stringType]); e.builtinCall = "z8_datespan_parse"; return ValueType.datespanType;
                }
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
                    target = selectOverload(target, e);
                    if (!target.isStatic) fail("instance method cannot be called on a class", e.token);
                    if (!accessible(target.owner, target.isPublic, target.isProtected)) fail("method is not accessible", e.token);
                    e.targetClass = target.owner.emittedName;
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
                    if (e.token.text == "getMessage" || e.token.text == "getStackTrace") return ValueType.stringType;
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
                    switch (e.token.text) {
                        case "size": case "isEmpty": case "clear":
                            checkArguments(e, []);
                            return e.token.text == "size" ? ValueType.intType : e.token.text == "isEmpty" ? ValueType.boolType : ValueType.voidType;
                        case "containsKey": checkStoredArguments(e, [mapKeyType(receiver)]); return ValueType.boolType;
                        case "containsValue": checkStoredArguments(e, [mapValue]); return ValueType.boolType;
                        case "get":
                            checkStoredArguments(e, [mapKeyType(receiver)]); return mapValueReadType(receiver);
                        case "remove":
                            checkStoredArguments(e, [mapKeyType(receiver)]); return mapValueReadType(receiver);
                        case "add":
                            if (e.arguments.length == 1) { checkArguments(e, [receiver]); return ValueType.voidType; }
                            checkStoredArguments(e, [mapKeyType(receiver), mapValue]); return mapValueReadType(receiver);
                        case "keys": checkArguments(e, []); return mapKeyArrayType(receiver);
                        case "values": checkArguments(e, []); return mapValueArrayType(receiver);
                        default: break;
                    }
                } else if (isArray(receiver)) {
                    if (isReferenceArray(receiver)) {
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
                            if (isReferenceArray(receiver)) return elementType(receiver);
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
                if (isMap(array)) {
                    if (!matchesStored(e.right, mapKeyType(array))) fail("map key type mismatch", e.token);
                    e.inferredType = array;
                    return mapValueReadType(array);
                }
                if (!isArray(array)) fail("indexing requires an array", e.token);
                if (!matches(e.right, ValueType.intType)) fail("array index must be int", e.token);
                if (array == ValueType.selfArray || array == ValueType.enumArray) e.objectClass = e.left.objectClass;
                e.inferredType = array;
                return array == ValueType.stringArray ? ValueType.nullableString : storedValueType(elementType(array));
            case ExprKind.castExpr:
                if (typeOf(e.left) == ValueType.primaryType && [ValueType.intType, ValueType.boolType, ValueType.decimalType,
                    ValueType.stringType, ValueType.guidType, ValueType.binaryType, ValueType.datespanType, ValueType.geometryType, ValueType.dateType, ValueType.fileType].canFind(e.castType)) {
                    e.primaryCast = true;
                    return e.castType == ValueType.stringType ? ValueType.nullableString : storedValueType(e.castType);
                }
                if (e.castType == ValueType.selfType) {
                    auto target = resolveClass(currentProgram, e.token.text, e.token);
                    if (target.isEnum) fail("enum casts are not supported", e.token);
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
                auto primarySource = typeOf(e.left);
                if (primarySource == ValueType.primaryType) {
                    switch (e.token.text) {
                        case "int": e.castType = ValueType.intType; break;
                        case "bool": e.castType = ValueType.boolType; break;
                        case "decimal": e.castType = ValueType.decimalType; break;
                        case "string": e.castType = ValueType.stringType; break;
                        case "guid": e.castType = ValueType.guidType; break;
                        case "binary": e.castType = ValueType.binaryType; break;
                        case "datespan": e.castType = ValueType.datespanType; break;
                        case "geometry": e.castType = ValueType.geometryType; break;
                        case "date": e.castType = ValueType.dateType; break;
                        case "file": e.castType = ValueType.fileType; break;
                        case "primary": e.castType = ValueType.primaryType; break;
                        default: fail("unsupported primary instanceof target", e.token);
                    }
                    e.primaryInstanceOf = true;
                    return ValueType.boolType;
                }
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
                if (operand == ValueType.selfType && ["!", "~", "-"].canFind(e.token.text)) {
                    auto method = lookupUnaryOperator(e.left.objectClass, "operator" ~ e.token.text);
                    if (method is null) {
                        ValueType[] targets = e.token.text == "!" ? [ValueType.boolType] :
                            e.token.text == "~" ? [ValueType.intType] : [ValueType.intType, ValueType.decimalType];
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
                        e.left.optionalRequired = true;
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
                    foreach (target; [ValueType.intType, ValueType.boolType, ValueType.decimalType, ValueType.stringType]) {
                        if (!supportsConvertedBinary(target, right, op)) continue;
                        auto candidate = findConversion(e.left.objectClass, target);
                        if (candidate is null) continue;
                        if (conversion !is null) fail("ambiguous binary operator", e.token);
                        conversion = candidate;
                    }
                    if (conversion is null) fail("undefined binary operator", e.token);
                    e.left.userConversion = conversion;
                    left = conversion.returnType == ValueType.stringType ? ValueType.nullableString : storedValueType(conversion.returnType);
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
                    e.inferredType = left;
                    return left;
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
                if (op == "+" && right == ValueType.stringType && hasStringConversion(left)) {
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
                if (left == ValueType.stringType && hasStringConversion(right)) {
                    e.third.convertToString = right; right = ValueType.stringType;
                }
                if (right == ValueType.stringType && hasStringConversion(left)) {
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
                if (s.type == ValueType.primaryType && s.expression is null && !allowUninitializedEnum) fail("primary variables require an initializer", s.token);
                if (s.type == ValueType.voidType) fail("variable cannot be void", s.token);
                if (hasObjectClass(s.type)) s.objectClass = resolveClass(currentProgram, s.objectName, s.token);
                if (s.expression !is null && !matchesInitializer(s.expression, s.type, s.objectClass)) fail("initializer type mismatch", s.token);
                variables[s.token.text] = s.type;
                if (hasObjectClass(s.type)) objectVariables[s.token.text] = s.objectClass;
                return false;
            case StmtKind.assignment:
                auto variableType = typeOf(s.target);
                if (variableType == ValueType.nullableString) variableType = ValueType.stringType;
                if (isOptionalPrimitive(variableType)) variableType = optionalBaseType(variableType);
                if (s.target.enumConstant) fail("enum constants cannot be assigned", s.token);
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
                    !matchesStored(s.expression, variableType, s.target.objectClass) :
                    !matches(s.expression, variableType, s.target.objectClass)) fail("assignment type mismatch", s.token);
                if (s.target.kind == ExprKind.index && isMap(s.target.inferredType) && s.assignmentOperator != "=") fail("compound assignment to a map entry is not supported", s.token);
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
                if (s.expression.kind == ExprKind.memberCall && s.expression.inferredType == ValueType.stringType && s.expression.builtinCall != "z8_regex_setupMatcher")
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

