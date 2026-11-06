"""Exercise host configuration through the original BL ServerConfig API."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/server_config_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "ConfigProbe.bl").write_text('''
import org.zenframework.z8.base.application.ServerConfig;
public class ConfigProbe {
    public static string get(string key) { return ServerConfig.get(key); }
    public static string getDefault(string key) { return ServerConfig.get(key, "fallback"); }
    public static bool getBool(string key, bool fallback) { return ServerConfig.get(key, fallback); }
    public static int getInt(string key, int fallback) { return ServerConfig.get(key, fallback); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_ConfigProbe;
void main() {
    alias P = Z8p_436F6E66696750726F6265;
    z8_string_set_resource("greeting"w, "hello"w);
    z8_server_config_replace(["plain"w:"value"w, "empty"w:""w, "resource"w:"$greeting$"w,
        "true"w:"TrUe"w, "false"w:"yes"w, "min"w:"-2147483648"w,
        "overflow"w:"2147483648"w, "space"w:" 9"w, "signed"w:"+17"w, "unicode"w:"١٢"w]);
    assert(P.m_get("plain"w) == "value"w && P.m_get("missing"w) is null);
    assert(P.m_getDefault("missing"w) is null && P.m_get("empty"w) !is null);
    assert(P.m_get("resource"w) == "hello"w);
    assert(z8_optional_require(P.m_getBool("true"w, false)));
    assert(!z8_optional_require(P.m_getBool("false"w, true)));
    assert(z8_optional_require(P.m_getBool("empty"w, true)));
    assert(z8_optional_require(P.m_getInt("min"w, 2)) == -2147483648L);
    assert(z8_optional_require(P.m_getInt("signed"w, 2)) == 17);
    assert(z8_optional_require(P.m_getInt("unicode"w, 2)) == 12);
    assert(z8_optional_require(P.m_getInt("overflow"w, 7)) == 7);
    assert(z8_optional_require(P.m_getInt("space"w, 8)) == 8);
    z8_server_config_replace(["plain"w:"updated"w]);
    assert(P.m_get("plain"w) == "updated"w && P.m_get("true"w) is null);
    z8_application_configure_from_server();
    auto defaults = z8_application_configuration();
    assert(defaults.authFailsLimit == 0 && defaults.authFailsBanSeconds == 0 && defaults.sessionTimeoutMinutes == 1440 && !defaults.oneSessionPerUser);
    assert(defaults.storagePathFormat == "yyyy.MM.dd"w);
    z8_server_config_replace(["auth.fails.limit"w:"3"w, "auth.fails.banSeconds"w:"90"w,
        "authority.center.session.timeout"w:"15"w, "authority.center.session.onePerUser"w:"true"w, "storage.path.format"w:"yyyy/MM"w]);
    z8_application_configure_from_server(); auto config = z8_application_configuration();
    assert(config.authFailsLimit == 3 && config.authFailsBanSeconds == 90 && config.sessionTimeoutMinutes == 15 && config.oneSessionPerUser && config.storagePathFormat == "yyyy/MM"w);
    config.sessionTimeoutMinutes = 0; assert(z8_application_configuration().sessionTimeoutMinutes == 15);
}
''', encoding="utf-8")
    executable = temp / ("config.exe" if os.name == "nt" else "config")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("ServerConfig host properties and BL overloads passed")
