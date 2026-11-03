module z8.compiler_test;

import std.algorithm : canFind;
import z8.compiler;

private void rejects(string source) {
    bool failed;
    try { compile(source); } catch (CompileException) { failed = true; }
    assert(failed, source);
}

unittest {
    auto output = compile(q{
        public class Math {
            public static int add(int a, int b) { return a + b; }
            static bool positive(int x) { if (x > 0) return true; else return false; }
            static int calculate(int a) { int b = add(a, 2); if (positive(b)) b = b * 3; return b; }
        }
    });
    assert(output.canFind("class Z8_Math"));
    assert(output.canFind("static long m_add(long v_a, long v_b)"));
    assert(output.canFind("m_add(v_a, (cast(long)(2)))"));
}

private void rejectsSources(SourceUnit[] sources, string expectedFile) {
    bool failed;
    try { compileSources(sources); } catch (CompileException e) { failed = true; assert(e.sourceName == expectedFile); }
    assert(failed);
}

unittest {
    auto a = SourceUnit("pkg.A", "A.bl", "import other.B; class A { public static int f() { return B.g(2); } }");
    auto b = SourceUnit("other.B", "B.bl", "class B { public static int g(int x) { return x; } }");
    auto output = compileSources([a, b]);
    assert(output.canFind("Z8p_6F746865722E42.m_g"));
    assert(compileSources([a, b], "pkg.A.f").canFind("int main()"));
    bool badEntry;
    try { compileSources([a, b], "other.B.g"); } catch (CompileException e) { badEntry = true; assert(e.sourceName == "B.bl"); }
    assert(badEntry);
    rejectsSources([a], "A.bl");
    auto privateB = SourceUnit("other.B", "B.bl", "class B { static int g(int x) { return x; } }");
    rejectsSources([a, privateB], "A.bl");
    auto invalidB = SourceUnit("other.B", "B.bl", "class B { public static int g() { return true; } }");
    rejectsSources([a, invalidB], "A.bl"); // the call has the wrong arity
    auto wrongName = SourceUnit("other.NotB", "B.bl", "class B { }");
    rejectsSources([wrongName], "B.bl");
    auto badImport = SourceUnit("pkg.A", "A.bl", "import other.B; import third.B; class A { }");
    auto third = SourceUnit("third.B", "third.bl", "class B { }");
    rejectsSources([badImport, b, third], "A.bl");
    auto syntax = SourceUnit("pkg.C", "C.bl", "class C { $");
    rejectsSources([syntax], "C.bl");
}

unittest {
    rejects("class A { static int f() { return true; } }");
    rejects("class A { static int f() { if (true) return 1; } }");
    rejects("class A { static int f() { return missing; } }");
    rejects("class A { static int f(int x) { return x + true; } }");
    rejects("class A { static int f() { return f(1); } }");
    rejects("class A { int f() { return 1; } }");
    rejects("class A { static int f() { while (true) return 1; } }");
    rejects("class A { static int f() { if (true) { int x = 1; } return x; } }");
    rejects("class A { static int f(int x) { int x = 1; return x; } }");
    rejects("class A { static int f() { return 1; } static int f() { return 2; } }");
    rejects("class A { static int f(void x) { return 1; } }");
    rejects("class A { static void f() { break; } }");
    rejects("class A { static void f() { continue; } }");
    rejects("class A { static void f() { while (1) { break; } } }");
    rejects("class A { static void f() { for (int i = 0; i < 1; i += 1) {} i = 2; } }");
    rejects("class A { static void f() { bool x = true; x += true; } }");
    rejects("class A { static void f() {} static bool g() { return f() == f(); } }");
    rejects("class A { static void f() {} static int g() { return f(); } }");
    rejects("class A { static void f() { for (; true; int x = 1) {} } }");
    rejects("class A { static string f() { return 1; } }");
    rejects("class A { static string f() { return \"a\" - \"b\"; } }");
    rejects("class A { static void f() { string x = \"x\"; x -= \"y\"; } }");
    rejects("class A { static int f() { return 1.length(); } }");
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
    rejects("class A { static void f() { string[] x = {\"ok\", false}; } }");
    rejects("class A { static int[] f() { return {1, false}; } }");
    rejects("class A { static void f() { int[] x; x.clear(1); } }");
    rejects("class A { static void f() { int[] x; x.add(1, 2); } }");
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
}
