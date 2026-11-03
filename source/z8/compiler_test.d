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
}
