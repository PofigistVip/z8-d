module z8.compiler_test;

import std.algorithm : canFind;
import std.string : indexOf;
import z8.compiler;

private void rejects(string source) {
    bool failed;
    try { compile(source); } catch (CompileException) { failed = true; }
    assert(failed, source);
}

unittest {
    compile(q{class A { bool operator !() { return true; } static bool f() { A a; return !a; } }});
    compile(q{class A { virtual int f() { return 1; } A child = class { int f() { return 2; } }; }});
    compile(q{class A { A child; child = class {}; }});
    compile(q{class A { int x; x = 1; int y = x + 1; }});
    rejects(q{class A { int x = 1; x = 2; }});
    rejects(q{class A { int x; x = 1; x = 2; }});
    compile(q{class A { A child; child.child = class {}; }});
    rejects(q{class A { A child; child.missing = class {}; }});
    rejects(q{class A { missing = class {}; }});
    rejects(q{class A { int child; child = class {}; }});
    rejects(q{class A { A child = class {}; child = class {}; }});
    rejects(q{class A { A child; child = class {}; child = class {}; }});
    rejects(q{class A { int f() { return container.x; } }});
    rejects(q{class A { A child = class { int f() { return container.container.x; } }; }});
    rejects(q{class A { static void f() { A child = class { int x = 1; }; } }});
    rejects(q{class A { int child = class {}; }});
    rejects(q{class A { A child = class { static int f() { return 1; } }; }});
    rejects(q{class A { static int f() { return +null; } }});
    compile(q{class A { operator int() { return 3; } static int f() { A a; return a; } }});
    rejects(q{class A { operator int(int value) { return value; } }});
    rejects(q{class A { operator int() { return 1; } operator decimal() { return 1.0; } static int f() { A a; return -a; } }});
    rejects(q{class A { operator int() { return 1; } operator decimal() { return 1.0; } static int f() { A a; return a + 1; } }});
    rejects(q{class A { operator int() { return 1; } operator string() { return "x"; } static int f(int x) { return 1; } static int f(string x) { return 2; } static int g() { A a; return f(a); } }});
    rejects(q{class A { static bool operator !() { return true; } }});
    compile(q{class A { int operator +(int x) { return x; } static int f() { A a; return a + 1; } }});
    compile(q{class A { A operator +(int x) { return this; } static void f() { A a; a += 1; } }});
    compile(q{class A { void operator =(int x) {} A child = 1; static void f() { A a = 2; a = 3; } }});
    rejects(q{class A { void operator =(int x) {} static void f() { A a = null; } }});
    rejects(q{class A { void operator =(A x) {} static void f() { A a; A b; a = b; } }});
    rejects(q{class A { int operator +(int x) { return x; } static int f() { A a; return a + true; } }});
    rejects(q{class A { bool operator !(int x, int y) { return true; } }});
    rejects(q{class A { static bool f() { A a; return !a; } }});
    compile(q{class A { static int f() {
        int[int] values = {(1, 2), (3, 4)};
        int missing = values.get(0);
        int absent = null;
        values.add(absent, 5);
        string[int] labels = {(1, "one")};
        labels.add(2, "two");
        primary[int] mixed = {(1, 42), (2, "text")};
        if ((int)mixed[1] != 42) return 1;
        int[string] scores = {("one", 1)};
        if (scores["one"] != 1) return 2;
        bool[int] flags = {(1, true)};
        decimal[string] prices = {("a", 1.0)};
        if (flags[1] && prices["a"] != null) return 3;
        string[guid] names = {(guid.create(1), "one")};
        if (names[guid.create(1)] != "one") return 4;
        guid[string] identifiers = {("a", guid.create(1))};
        if (identifiers["a"] != guid.create(1)) return 5;
        if (values.containsKey(absent) && labels[1] == "one") return values[3];
        return 0;
    } }});
    rejects(q{class A { static void f() { int[int] x = {("a", 1)}; } }});
    rejects(q{class A { static void f() { string[int] x; x.add("a", "b"); } }});
    rejects(q{class A { static void f() { decimal[int] x = {(1, 2)}; } }});
    rejects(q{class A { static void f() { string[guid] x = {(1, "wrong")}; } }});
}

unittest {
    auto repeated = compile("enum E { First,, Second,,, }");
    assert(repeated.canFind("e_First") && repeated.canFind("e_Second"));
    rejects("enum E { , First }");
    rejects("enum E { First,, First }");
}

unittest {
    compile(`class A { records {
        public First = '00000000-0000-0000-0000-000000000001';
        private Second = '00000000-0000-0000-0000-000000000002';
    } static guid f() { First = '00000000-0000-0000-0000-000000000003'; return Second; } }`);
    rejects(q{class A { records { First = 1; } }});
    rejects(`class A { records { [name "value"] First = '00000000-0000-0000-0000-000000000001'; } }`);
    rejects(`class A { guid First; records { First = '00000000-0000-0000-0000-000000000001'; } }`);
    rejects(`class A { records {
        First = 'abcdef00-0000-0000-0000-000000000001';
        Second = 'ABCDEF00-0000-0000-0000-000000000001';
    } }`);
}

unittest {
    auto source = "class A { static void f() { return; int x = 1; } }";
    bool reported;
    try { compile(source); } catch (CompileException e) {
        reported = true;
        assert(e.msg == "unreachable code");
        assert(e.position.offset == source.indexOf("x = 1"));
    }
    assert(reported);
    rejects(q{class A { static void f() { return; int x = 1; } }});
    rejects(q{class A { static void f() { throw "x"; int x = 1; } }});
    rejects(q{class A { static void f() { while (true) { break; int x = 1; } } }});
    rejects(q{class A { static void f() { while (true) { continue; int x = 1; } } }});
    rejects(q{class A { static int f(bool c) { if (c) return 1; else return 2; int x = 1; } }});
    compile(q{class A { static void f() { while (true) { { break; } int x = 1; } } }});
    compile(q{class A { static int f(bool c) { if (c) {} else { return 1; int x = 0; } return 2; } }});
}

unittest {
    compile(q{class A {
        static int choose(int[] x) { return 1; }
        static int choose(string[] x) { return 2; }
        static int f() { return choose(int[] {1, 2}); }
        static string g(string[string] x) { return x["a"]; }
        static string h() { return g(string[string] {("a", "b")}); }
        static void clearLiteral() { int[] {1, 2}.clear(); }
    }});
    rejects(q{class A { static int f(int[] x) { return 1; } static int g() { return f({1}); } }});
    rejects(q{class A { static int f(int[] x) { return 1; } static int g() { return f(string[] {"x"}); } }});
    rejects(q{class A { static int f() { return int[] {"x"}.size(); } }});
}

unittest {
    compile(q{class A { static void f() {
        string[string] values = {("a", "b"), ("c", "d"),};
        primary[string] mixed = {("number", 42), ("text", "value")};
        decimal[][] matrix = {{1.0}, {2.0, 3.0}};
        int[] ordinary = {(1 + 2), (3)};
    } }});
    rejects(q{class A { static void f() { int[] values = {(1, 2)}; } }});
    rejects(q{class A { static void f() { string[string] values = {"a"}; } }});
    rejects(q{class A { static void f() { string[string] values = {(null, "x")}; } }});
    rejects(q{class A { static void f() { primary[string] values = {("x", null)}; } }});
    rejects(q{class A { static void f() { string[string] values = {(1, "x")}; } }});
    rejects(q{class A { static void f() { string[string] values = {("x", 1)}; } }});
    rejects(q{class A { static void f() { int[] key; string[string] values = {(key, "x")}; } }});
}

unittest {
    rejects("class A { auto int[] items; }");
    rejects("class A { auto A item; }");
    rejects("class A { auto static A[] items; }");
    rejects("class A { auto auto A[] items; }");
    rejects("class A { auto void f() {} }");
    auto automatic = (new Parser("class A { auto A[] items; A item; }")).parse();
    assert(automatic.fields[0].isAuto && !automatic.fields[1].isAuto);
    compile("class A { auto A[] items; A item; }");
}

unittest {
    auto parsed = (new Parser(q{
        class FinalDeclarations {
            final int field;
            int f(final int value, int[] values) {
                final int local = 1;
                for (final int item : values) {}
                try {} catch (final exception error) {}
                return value;
            }
        }
    })).parse();
    assert(parsed.fields[0].declaredFinal);
    assert(parsed.methods[0].parameters[0].declaredFinal);
    assert(parsed.methods[0].body.children[0].declaredFinal);
    assert(parsed.methods[0].body.children[1].initial.declaredFinal);
    assert(parsed.methods[0].body.children[2].catchDeclaredFinal);
    rejects("class A { final int f() { return 1; } }");
    rejects("class A { void f() { final x = 1; } }");
    rejects("class A { void f() { final final int x = 1; } }");
    compile(q{class A { static int f() {
        decimal[][] matrix;
        for (final decimal[] row : matrix) { if (row.size() == 0) return 1; }
        return 0;
    } }});
}

unittest {
    compile("class A { static primary f() { return 1; } }");
    rejects("class A { static void f() { primary value; } }");
    rejects("class A { static int f(primary x) { return 1; } static int f(int x) { return 2; } static int g() { return f(1); } }");
    // The facade continues to expose the parser, checker and model types.
    auto parsed = (new Parser("class PublicApi {} ")).parse();
    auto checker = new Checker;
    assert(parsed.name.text == "PublicApi" && checker !is null);
    auto output = compile(q{
        public class Math {
            public static int add(int a, int b) { return a + b; }
            static bool positive(int x) { if (x > 0) return true; else return false; }
            static int calculate(int a) { int b = add(a, 2); if (positive(b)) b = b * 3; return b; }
        }
    });
    assert(output.canFind("class Z8_Math"));
    assert(output.canFind("static Z8Optional!long m_add(long v_a, long v_b)"));
    assert(output.canFind("m_add(v_a, z8_optional_wrap((cast(long)(2))))"));
    auto decimalArrays = compile("class A { static void f() { decimal[] values = {1, 2.5}; values.add(3); values.set(0, 4); } }");
    assert(decimalArrays.canFind("Z8Array!Z8Decimal"));
    compile("import org.zenframework.z8.lang.Math; class A { static decimal f() { return Math.max(1, 2.5) + Math.PI; } }");
    rejects("import org.zenframework.z8.lang.Math; class A { static decimal f() { return Math.max(true, 1); } }");
    rejects("import org.zenframework.z8.lang.Math; class A { static decimal f() { return Math.sin(); } }");
}

private void rejectsSources(SourceUnit[] sources, string expectedFile) {
    bool failed;
    try { compileSources(sources); } catch (CompileException e) { failed = true; assert(e.sourceName == expectedFile); }
    assert(failed);
}

unittest {
    auto base = SourceUnit("pkg.Base", "Base.bl", "class Base { public int value = 7; }");
    auto child = SourceUnit("pkg.Child", "Child.bl", "class Child extends pkg.Base { }");
    auto user = SourceUnit("other.User", "User.bl", q{class User {
        static int run() {
            pkg.Child child;
            pkg.Base base = child;
            pkg.Child recovered = (pkg.Child)base;
            pkg.Base[] values = pkg.Base[] {base, child};
            for (pkg.Base value : values) { if (!(value instanceof pkg.Base)) return 1; }
            return 0;
        }
    }});
    compileSources([user, child, base]);
    auto bad = SourceUnit("other.Bad", "Bad.bl", "class Bad { missing.Base value; }");
    rejectsSources([bad, base], "Bad.bl");
    auto staticType = SourceUnit("pkg.Static", "Static.bl", "class Static { public static int value; public static int f(int x) { return x; } }");
    auto staticField = SourceUnit("other.User", "User.bl", "class User { static int run() { return pkg.Static.value; } }");
    auto staticCall = SourceUnit("other.User", "User.bl", "class User { static int run() { return pkg.Static.f(3); } }");
    rejectsSources([staticField, staticType], "User.bl");
    rejectsSources([staticCall, staticType], "User.bl");
    auto records = SourceUnit("pkg.Records", "Records.bl", `class Records { records {
        public Open = '00000000-0000-0000-0000-000000000001';
        private Hidden = '00000000-0000-0000-0000-000000000002';
        Default = '00000000-0000-0000-0000-000000000003';
    } }`);
    auto recordUser = SourceUnit("other.User", "User.bl", "import pkg.Records; class User { static guid f() { return Records.Open; } static guid g() { return Records.Default; } }");
    auto hiddenUser = SourceUnit("other.User", "User.bl", "import pkg.Records; class User { static guid f() { return Records.Hidden; } }");
    compileSources([recordUser, records]);
    rejectsSources([hiddenUser, records], "User.bl");
    auto duplicateRecord = SourceUnit("pkg.Child", "Child.bl", `class Child extends Records { records { Other = '00000000-0000-0000-0000-000000000001'; } }`);
    rejectsSources([duplicateRecord, records], "Child.bl");
}

unittest {
    auto a = SourceUnit("pkg.A", "A.bl", "import other.B; class A { public static int f() { return B.g(2); } }");
    auto b = SourceUnit("other.B", "B.bl", "class B { public static int g(int x) { return x; } }");
    auto output = compileSources([a, b]);
    assert(output.length == 2 && output[0].source.canFind("Z8p_6F746865722E42.m_g"));
    assert(output[0].source.canFind("import z8gen.p_other.p_B;"));
    auto withEntry = compileSources([a, b], "pkg.A.f");
    assert(withEntry.length == 3 && withEntry[$-1].source.canFind("int main()"));
    bool badEntry;
    try { compileSources([a, b], "other.B.g"); } catch (CompileException e) { badEntry = true; assert(e.sourceName == "B.bl"); }
    assert(badEntry);
    rejectsSources([a], "A.bl");
    auto privateB = SourceUnit("other.B", "B.bl", "class B { private static int g(int x) { return x; } }");
    rejectsSources([a, privateB], "A.bl");
    auto defaultPublic = SourceUnit("other.B", "B.bl", "class B { static int g(int x) { return x; } }");
    compileSources([a, defaultPublic]);
    auto invalidB = SourceUnit("other.B", "B.bl", "class B { public static int g() { return true; } }");
    rejectsSources([a, invalidB], "A.bl"); // the call has the wrong arity
    auto wrongName = SourceUnit("other.NotB", "B.bl", "class B { }");
    rejectsSources([wrongName], "B.bl");
    auto badImport = SourceUnit("pkg.A", "A.bl", "import other.B; import third.B; class A { }");
    auto third = SourceUnit("third.B", "third.bl", "class B { }");
    rejectsSources([badImport, b, third], "A.bl");
    auto syntax = SourceUnit("pkg.C", "C.bl", "class C { $");
    rejectsSources([syntax], "C.bl");
    auto usesObject = SourceUnit("pkg.A", "A.bl", "import other.B; class A { static void f() { B.make(); } }");
    auto createsObject = SourceUnit("other.B", "B.bl", "class B { public static B make() { return new B; } }");
    compileSources([usesObject, createsObject]);
    auto wrongArgument = SourceUnit("pkg.A", "A.bl", "import other.B; class A { static void f() { B.take(new A); } }");
    auto takesB = SourceUnit("other.B", "B.bl", "class B { public static void take(B value) {} }");
    rejectsSources([wrongArgument, takesB], "A.bl");
    auto hiddenField = SourceUnit("other.B", "B.bl", "class B { private int secret; }");
    auto readsField = SourceUnit("pkg.A", "A.bl", "import other.B; class A { static int f() { B b; return b.secret; } }");
    rejectsSources([readsField, hiddenField], "A.bl");
    auto protectedField = SourceUnit("other.B", "B.bl", "class B { protected int secret; }");
    rejectsSources([readsField, protectedField], "A.bl");
    auto cycleA = SourceUnit("pkg.A", "A.bl", "class A { B next; }");
    auto cycleB = SourceUnit("pkg.B", "B.bl", "class B { A next; }");
    compileSources([cycleA, cycleB]);
    auto base = SourceUnit("pkg.Base", "Base.bl", "class Base { public int f() { return 1; } }");
    auto derived = SourceUnit("pkg.Derived", "Derived.bl", "class Derived extends Base { public int f() { return 2; } }");
    rejectsSources([derived, base], "Derived.bl");
    auto virtualBase = SourceUnit("pkg.Base", "Base.bl", "class Base { virtual public int f() { return 1; } }");
    compileSources([derived, virtualBase]);
    auto badOverride = SourceUnit("pkg.Derived", "Derived.bl", "class Derived extends Base { public bool f() { return true; } }");
    rejectsSources([badOverride, virtualBase], "Derived.bl");
    auto overloadedBase = SourceUnit("pkg.Base", "Base.bl", "class Base { virtual public int f(int x) { return x; } public int f(string x) { return 1; } }");
    auto overloadedDerived = SourceUnit("pkg.Derived", "Derived.bl", "class Derived extends Base { public int f(bool x) { return 1; } public int f(int x) { return 2; } public int g() { return f(1) + f(\"x\") + f(true); } }");
    compileSources([overloadedDerived, overloadedBase]);
    auto badInheritedSignature = SourceUnit("pkg.Derived", "Derived.bl", "class Derived extends Base { public int f(bool x) { return 1; } public bool f(int x) { return true; } }");
    rejectsSources([badInheritedSignature, overloadedBase], "Derived.bl");
    auto wrongDerivedVisibility = SourceUnit("pkg.Derived", "Derived.bl", "class Derived extends Base { private int f(int x) { return x; } }");
    rejectsSources([wrongDerivedVisibility, overloadedBase], "Derived.bl");
    auto finalBase = SourceUnit("pkg.Base", "Base.bl", "final class Base { }");
    rejectsSources([derived, finalBase], "Derived.bl");
    auto inheritanceA = SourceUnit("pkg.A", "A.bl", "class A extends B { }");
    auto inheritanceB = SourceUnit("pkg.B", "B.bl", "class B extends A { }");
    rejectsSources([inheritanceA, inheritanceB], "A.bl");
    auto objectArray = SourceUnit("pkg.A", "A.bl", "class A { B[] values; B[] f(B[] x) { values.add(new B); return x; } }");
    auto arrayItem = SourceUnit("pkg.B", "B.bl", "class B { }");
    compileSources([objectArray, arrayItem]);
    auto wrongArray = SourceUnit("pkg.A", "A.bl", "class A { B[] f(A[] x) { return x; } }");
    rejectsSources([wrongArray, arrayItem], "A.bl");
    auto wrongArrayElement = SourceUnit("pkg.A", "A.bl", "class A { void f() { B[] x; x.add(new A); } }");
    rejectsSources([wrongArrayElement, arrayItem], "A.bl");
    auto wrongArrayMethod = SourceUnit("pkg.A", "A.bl", "class A { void f() { B[] x; x.contains(new A); } }");
    rejectsSources([wrongArrayMethod, arrayItem], "A.bl");
    auto wrongArrayRemoval = SourceUnit("pkg.A", "A.bl", "class A { void f() { B[] x; A[] y; x.removeAll(y); } }");
    rejectsSources([wrongArrayRemoval, arrayItem], "A.bl");
    auto enumType = SourceUnit("pkg.Mode", "Mode.bl", "[native \"demo.Mode\"] public enum Mode { One, Two, }");
    auto enumUse = SourceUnit("pkg.A", "A.bl", "class A { static Mode f() { return Mode.One; } }");
    compileSources([enumUse, enumType]);
    auto enumDefault = SourceUnit("pkg.A", "A.bl", "class A { void f() { Mode value; } }");
    rejectsSources([enumDefault, enumType], "A.bl");
    auto enumWrite = SourceUnit("pkg.A", "A.bl", "class A { void f() { Mode.One = Mode.Two; } }");
    rejectsSources([enumWrite, enumType], "A.bl");
    auto enumArray = SourceUnit("pkg.A", "A.bl", "class A { void f() { Mode[] values; } }");
    compileSources([enumArray, enumType]);
    auto enumChild = SourceUnit("pkg.A", "A.bl", "class A extends Mode { }");
    rejectsSources([enumChild, enumType], "A.bl");
    auto otherEnum = SourceUnit("pkg.Other", "Other.bl", "enum Other { One }");
    auto enumCompare = SourceUnit("pkg.A", "A.bl", "class A { bool f() { return Mode.One == Other.One; } }");
    rejectsSources([enumCompare, enumType, otherEnum], "A.bl");
    auto enumArrayMismatch = SourceUnit("pkg.A", "A.bl", "class A { void f() { Mode[] x; Other[] y; x.addAll(y); } }");
    rejectsSources([enumArrayMismatch, enumType, otherEnum], "A.bl");
    auto enumForeachMismatch = SourceUnit("pkg.A", "A.bl", "class A { void f() { Mode[] x; for (Other item : x) {} } }");
    rejectsSources([enumForeachMismatch, enumType, otherEnum], "A.bl");
    auto wrongForeach = SourceUnit("pkg.A", "A.bl", "class A { void f() { B[] x; for (A item : x) {} } }");
    rejectsSources([wrongForeach, arrayItem], "A.bl");
    auto invalidCast = SourceUnit("pkg.A", "A.bl", "class A { static B f() { A a; return (B)a; } }");
    rejectsSources([invalidCast, arrayItem], "A.bl");
    auto badInstanceOf = SourceUnit("pkg.A", "A.bl", "class A { static bool f() { A a; return a instanceof B; } }");
    rejectsSources([badInstanceOf, arrayItem], "A.bl");
    rejects("class A { static bool f() { return 1 instanceof A; } }");
    rejects("class A { static bool f(A x) { return x instanceof A == true; } }");
    auto badCastValue = SourceUnit("pkg.A", "A.bl", "class A { static B f() { return (B)1; } }");
    rejectsSources([badCastValue, arrayItem], "A.bl");
    compile("class A { static int f(int x) { return (x) + 2; } }");
}

unittest {
    rejects("class A { static int f() { return true; } }");
    rejects("class A { static int f() { if (true) return 1; } }");
    rejects("class A { static int f() { return missing; } }");
    rejects("class A { static int f(int x) { return x + true; } }");
    rejects("class A { static int f() { return f(1); } }");
    rejects("class A { int x; static int f() { return x; } }");
    rejects("class A { static A x; }");
    compile("class A { A value = null; }");
    compile("class A { static int f() { int value = null; return value; } }");
    compile("class A { static bool f() { return 1 == null; } }");
    rejects("class A { static bool f() { int[] x = null; return x < null; } }");
    rejects("class A { static int f() { return 1 ?: 2; } }");
    rejects("class A { static void f() { int[] x; bool[] y; x = x ?: y; } }");
    compile("class A { static string f() { string[string] x; return x.get(\"a\") ?: x.get(\"b\"); } }");
    rejects("class A { static A[] x; }");
    rejects("class A { static string[string] x; }");
    rejects("class A { static void f() { geometry[string] x; } }");
    rejects("class A { static void f() { string[string] x; x[\"a\"] += \"b\"; } }");
    rejects("class A { static void f() { string[string] x; int[] key; x.add(key, \"b\"); } }");
    rejects("class A { static void f() { string[string] x; int[] key; x.remove(key); } }");
    rejects("class A { static void f() { string[string] x; int[] value; x.add(value); } }");
    rejects("class A { static void f() { string[string] x; x.keys(1); } }");
    rejects("class A { static void f() { string[string] x; x -= x; } }");
    rejects("class A { static void f() { string[string] x; int[] y; x = x + y; } }");
    rejects("class A { static void f() { A[] x = {true}; } }");
    rejects("class A { static int f() { return 1; } static int x = f(); }");
    rejects("class A { int x; static int f() { return A.x; } }");
    rejects("class A { int f() { return 1; } static int g() { return f(); } }");
    rejects("class A { static int f() { return this.f(); } }");
    rejects("class A { static A f() { return new Other; } }");
    rejects("class A { int f() { return 1; } static int g() { return A.f(); } }");
    rejects("class A { void item; }");
    rejects("class A { static void constructor() {} }");
    rejects("class A { int constructor() { return 1; } }");
    rejects("class A { void constructor(int value) {} }");
    compile("class A { A next; }");
    rejects("class A { static int f() { while (true) return 1; } }");
    rejects("class A { static int f() { if (true) { int x = 1; } return x; } }");
    rejects("class A { static int f(int x) { int x = 1; return x; } }");
    rejects("class A { static int f() { return 1; } static int f() { return 2; } }");
    rejects("class A { static int f(int x) { return x; } static bool f(int x) { return true; } }");
    compile("class A { static int f(int x) { return x; } int f(bool x) { return 1; } }");
    rejects("class A { static int f(int x) { return x; } int f(bool x) { return 1; } static int g() { return f(true); } }");
    rejects("class A { static int f(int x) { return x; } int f(bool x) { return 1; } static int g() { return A.f(true); } }");
    rejects("class A { static int f(decimal x) { return 1; } static int f(string x) { return 2; } static int g() { return f(1); } }");
    rejects("class A { static int f(void x) { return 1; } }");
    rejects("class A { static void f() { break; } }");
    rejects("class A { static void f() { continue; } }");
    rejects("class A { static void f() { while (1) { break; } } }");
    rejects("class A { static void f() { for (int i = 0; i < 1; i += 1) {} i = 2; } }");
    rejects("class A { static void f() { bool x = true; x += true; } }");
    rejects("class A { static void f() {} static bool g() { return f() == f(); } }");
    rejects("class A { static void f() {} static int g() { return f(); } }");
    rejects("class A { static void f() { for (; true; int x = 1) {} } }");
    rejects("class A { static string f() { int[] value; return value; } }");
    rejects("class A { static string f() { return \"a\" - \"b\"; } }");
    rejects("class A { static void f() { string x = \"x\"; x -= \"y\"; } }");
    rejects("class A { static int f() { return 1.length(); } }");
    rejects("class A { static int f() { return 1.and(true); } }");
    rejects("class A { static int f() { return 1.leftShift(); } }");
    rejects("class A { static string f() { return 1.toString(true); } }");
    rejects("class A { static int f() { return \"x\".length(1); } }");
    rejects("class A { static int f() { return \"x\".missing(); } }");
    rejects("class A { static void f() { int[] x = {true}; } }");
    rejects("class A { static void f() { int[] x = {1}; int y = x[true]; } }");
    rejects("class A { static void f() { bool[] x = {true}; x.add(1); } }");
    rejects("class A { static void f() { int[] x; x.set(0, true); } }");
    rejects("class A { static int f() { return {}; } }");
    rejects("class A { static void f() { int x = 1; x[0] = 2; } }");
    rejects("class A { static void f() { int[] x; bool y = x == x; } }");
    rejects("class A { static void f() { int[][] x; } }");
    rejects("class A { static void f() { int[] bad; string[] x = {\"ok\", bad}; } }");
    rejects("class A { static int[] f() { return {1, false}; } }");
    rejects("class A { static int f(int[] x) { return 1; } static int g() { return f({1}); } }");
    rejects("class A { static void f() { int[] x; x.clear(1); } }");
    compile("class A { static decimal f() { decimal[] x; return x.first() + 1.0; } }");
    rejects("class A { static int f() { int[] x; return x.first() ?: true; } }");
    rejects("class A { static void f() { int[] x; x.add(true, 2); } }");
    rejects("class A { static void f() { int[] x; x.contains(true); } }");
    rejects("class A { static void f() { int[] x; bool[] y; x.addAll(y); } }");
    rejects("class A { static void f() { int[] x; bool[] y; x = x + y; } }");
    rejects("class A { static void f() { int[] x; x -= x; } }");
    rejects("class A { static void f() { int[] x; x.addAll(true, x); } }");
    rejects("class A { static void f() { int[] x; x.isSubsetOf(true); } }");
    rejects("class A { static void f() { int[] x; x.removeAll(false); } }");
    rejects("class A { static string f() { int[] x; return x.join(x); } }");
    rejects("class A { static void f() { int[] x; for (bool y : x) {} } }");
    rejects("class A { static void f() { int x = 1; for (int y : x) {} } }");
    rejects("class A { static int f() { return 1 ? 2 : 3; } }");
    rejects("class A { static int f() { return true ? 2 : false; } }");
    rejects("class A { static int f() { int[] x; for (int y : x) {} return y; } }");
    rejects("class A { static void f() { throw 1; } }");
    rejects("class A { static void f() { try {} } }");
    rejects("class A { static void f() { try {} catch (int e) {} } }");
    rejects("class A { static void f() { try {} finally { return; } } }");
    rejects("class A { static int f() { try { return 1; } catch (exception e) {} } }");
    rejects("class A { static void f() { try {} catch (exception e) {} e.getMessage(); } }");
    rejects("class A { static int f() { return 1.0; } }");
    rejects("class A { static decimal f() { return 1.0 + true; } }");
    rejects("class A { static decimal f() { return 1.0.round(true); } }");
    rejects("class A { static int f() { return 1.0.floor(1); } }");
    rejects("class A { static int f() { return 1.0.ceil(true); } }");
    rejects("class A { static bool f() { int[] x; return \"a\".startsWith(x); } }");
    rejects("class A { static string f() { return \"a\".substring(true); } }");
    rejects("class A { static int f() { int[] x; return int.parse(x); } }");
    rejects("class A { static decimal f() { int[] x; return decimal.parse(x); } }");
    rejects("class A { static bool f() { int[] x; return bool.parse(x); } }");
    rejects("class A { static int f() { return (int)1.5; } }");
    rejects("class A { static bool f() { return (bool)\"true\"; } }");
    rejects("class A { static decimal f() { return 8966366107597250171.7934341923; } }");
    rejects("class A { static void f() { decimal[] x = {1.0, false}; } }");
}
