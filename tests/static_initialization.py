"""Exercise concurrent first access to generated BL static fields."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "bl" / "demo" / "cases"
    source.mkdir(parents=True)
    for name in ("StaticInitTracker", "StaticInitTarget", "StaticInitUnused", "StaticInitFailure"):
        shutil.copy2(root / "examples" / "project" / "demo" / "cases" / (name + ".bl"), source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(temp / "bl"), str(generated)], check=True)
    runner = temp / "main.d"
    runner.write_text('''
import core.thread;
import z8.runtime;
import z8gen.demo.cases.StaticInitTracker;
import z8gen.demo.cases.StaticInitTarget;
import z8gen.demo.cases.StaticInitFailure;
alias Tracker = Z8p_64656D6F2E63617365732E537461746963496E6974547261636B6572;
alias Target = Z8p_64656D6F2E63617365732E537461746963496E6974546172676574;
alias Failure = Z8p_64656D6F2E63617365732E537461746963496E69744661696C757265;
void main() {
    assert(z8_optional_require(Tracker.f_calls) == 0);
    Thread[] workers;
    foreach (_; 0 .. 16) workers ~= new Thread({
        foreach (i; 0 .. 50) {
            assert(z8_optional_require(Target.f_first) == 1);
            assert(z8_optional_require(Target.f_second) == 7);
        }
    });
    foreach (worker; workers) worker.start();
    foreach (worker; workers) worker.join();
    assert(z8_optional_require(Tracker.f_calls) == 2);
    assert(z8_optional_require(Tracker.f_trace) == 17);
    foreach (i; 0 .. 2) {
        bool caught;
        try { auto ignored = Failure.f_value; }
        catch (Throwable failure) { caught = true; }
        assert(caught);
    }
    assert(z8_optional_require(Tracker.f_calls) == 3);
    assert(z8_optional_require(Tracker.f_trace) == 175);
}
''', encoding="utf-8")
    executable = temp / ("static-init.exe" if os.name == "nt" else "static-init")
    subprocess.run(["dmd", str(runner), *map(str, generated.rglob("*.d")), "-I" + str(generated),
                    *import_args(), str(runtime), "-oq", "-od=" + str(temp), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True, timeout=30)
print("Concurrent static initialization verified")
