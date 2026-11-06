"""Exercise native declarations with callbacks in a separately linked D runtime."""
from pathlib import Path
import os, shutil, subprocess, tempfile
from runtime_support import import_args, runtime_library
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "bl"
    shutil.copytree(root / "examples" / "native", source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    # The adapter is compiled separately and has no dependency on generated modules.
    adapter = temp / "adapter.d"
    adapter.write_text('''module adapter;
import z8.runtime;
__gshared int constructed, cleared;
__gshared Z8Object partnerValue, currentValue;
Z8Object* partner(Z8Object self) { assert(self !is null); return &partnerValue; }
Z8Object* current() { return &currentValue; }
void onNew(Z8Object self) { assert(self !is null); ++constructed; }
Z8Optional!long get(Z8Object self) { return z8_optional_wrap(21L); }
Z8Object echo(Z8Object self, Z8Object value) { return value; }
Z8Object invalid(Z8Object self) { return new Z8Object(); }
Z8Optional!long inspect(Z8Object value) { return z8_optional_wrap(value is null ? 0L : 7L); }
Z8Object make() { return z8_native_new("example.GenericNative"w); }
Z8Object makeInvalid() { return new Z8Object(); }
Z8ObjectArray!Z8Object extend(Z8Object self, Z8ObjectArray!Z8Object values) {
    assert(self !is null);
    if (values is null) return null;
    values.z8_add(self);
    return values;
}
Z8ObjectArray!Z8Object invalidArray() {
    return new Z8ObjectArray!Z8Object([new Z8Object()]);
}
void clearArray(Z8ObjectArray!Z8Object values) { z8_nonnull(values).z8_clear(); }
void clear(Z8Object self) { ++cleared; }
bool valueEquals(Z8Object self, Z8Object other) { return other !is null && self.classinfo is other.classinfo; }
void bindGeneric() {
    z8_native_bind_field("example.GenericNative.f_partner"w, &partner);
    z8_native_bind_field("example.GenericNative.f_current"w, &current);
    z8_native_bind("example.GenericNative.m_new"w, &onNew);
    z8_native_bind("example.GenericNative.m_get"w, &get);
    z8_native_bind("example.GenericNative.m_echo"w, &echo);
    z8_native_bind("example.GenericNative.m_invalid"w, &invalid);
    z8_native_bind("example.GenericNative.m_inspect"w, &inspect);
    z8_native_bind("example.GenericNative.m_make"w, &make);
    z8_native_bind("example.GenericNative.m_makeInvalid"w, &makeInvalid);
    z8_native_bind("example.GenericNative.m_extend"w, &extend);
    z8_native_bind("example.GenericNative.m_invalidArray"w, &invalidArray);
    z8_native_bind("example.GenericNative.m_clearArray"w, &clearArray);
    z8_native_bind("example.GenericNative.m_clear"w, &clear);
    z8_native_bind("example.NativeNumber.m_equals"w, &valueEquals);
}
''', encoding="utf-8")
    adapter_object = temp / ("adapter.obj" if os.name == "nt" else "adapter.o")
    subprocess.run(["dmd", "-c", *import_args(), str(adapter), "-of=" + str(adapter_object)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.NativeMath;
import z8gen.NativeNumber;
import z8gen.NativeConsumer;
import z8gen.EagerUser;
import z8gen.EagerHolder;
import z8gen.GenericNative;
import adapter;
alias Math = Z8p_4E61746976654D617468;
alias Number = Z8p_4E61746976654E756D626572;
alias Consumer = Z8p_4E6174697665436F6E73756D6572;
alias Generic = Z8p_47656E657269634E6174697665;
Z8Optional!long add(Z8Optional!long a, Z8Optional!long b) { return z8_optional_wrap(z8_optional_require(a) + z8_optional_require(b)); }
wstring addText(wstring a, wstring b) { return a ~ b; }
Z8Optional!long scale(Math self, Z8Optional!long value) { return z8_optional_wrap(z8_optional_require(value) * 3); }
Z8Optional!long read(Number self) { return z8_optional_wrap(9L); }
Z8Optional!long convertNumber(Number self) { return z8_optional_wrap(2L); }
wstring numberText(Number self) { return "native:9"w; }
Z8Optional!long numberHash(Number self) { return z8_optional_wrap(37L); }
Z8Optional!long ignored(Math self) { return z8_optional_wrap(10L); }
__gshared Z8Optional!long nativeFactor, nativeTotal;
__gshared int numberConstructs, mathConstructs;
void constructNumber(Number self) { assert(self !is null); ++numberConstructs; }
void constructMath(Math self) { assert(self !is null); ++mathConstructs; }
Z8Optional!long* factor(Math self) { assert(self !is null); return &nativeFactor; }
Z8Optional!long* total() { return &nativeTotal; }
Z8Optional!long* badField() { return null; }
void reset() {}
Z8Optional!long exactGet(Generic self) { return z8_optional_wrap(22L); }
__gshared Generic exactPartnerValue;
Generic* exactPartner(Generic self) { return &exactPartnerValue; }
Z8ObjectArray!Generic exactExtend(Generic self, Z8ObjectArray!Generic values) { return values; }
Z8Object anyFactory() { return new Z8Object(); }
void main() {
    bool missing;
    try { Consumer.m_run(); } catch (Exception e) { missing = e.msg.indexOf("native binding not found") >= 0; }
    assert(missing);
    z8_native_bind_field("example.bad.f_field"w, &badField);
    bool badPointer;
    try { z8_native_field!(Z8Optional!long)("example.bad.f_field"w) = z8_optional_wrap(1L); }
    catch (Exception e) { badPointer = e.msg.indexOf("native field binding returned null") >= 0; }
    assert(badPointer);
    bindGeneric();
    nativeFactor = z8_optional_wrap(3L);
    nativeTotal = z8_optional_wrap(7L);
    z8_native_bind("example.NativeMath.m_add"w, &add);
    z8_native_bind("example.NativeMath.m_add"w, &addText);
    z8_native_bind("example.NativeMath.m_scale"w, &scale);
    z8_native_bind("example.NativeMath.m_reset"w, &reset);
    z8_native_bind("example.NativeNumber.m_read"w, &read);
    z8_native_bind("example.NativeNumber.z8cast_int"w, &convertNumber);
    z8_native_bind("example.NativeNumber.m_toString"w, &numberText);
    z8_native_bind("example.NativeNumber.m_hashCode"w, &numberHash);
    z8_native_bind("example.NativeNumber.m_new"w, &constructNumber);
    z8_native_bind("example.NativeMath.m_new"w, &constructMath);
    z8_native_bind("example.NativeMath.m_ignored"w, &ignored);
    bool missingField;
    try { Consumer.m_run(); } catch (Exception e) { missingField = e.msg.indexOf("example.NativeMath.f_factor") >= 0; }
    assert(missingField);
    z8_native_bind_field("example.NativeMath.f_factor"w, &factor);
    bool missingStaticField;
    try { Consumer.m_run(); } catch (Exception e) { missingStaticField = e.msg.indexOf("example.NativeMath.f_total") >= 0; }
    assert(missingStaticField);
    z8_native_bind_field("example.NativeMath.f_total"w, &total);
    numberConstructs = mathConstructs = 0;
    assert(z8_optional_require(Consumer.m_run()) == 54);
    assert(z8_optional_require(nativeFactor) == 4 && z8_optional_require(nativeTotal) == 12);
    assert(numberConstructs == 3 && mathConstructs == 1);
    auto nativeNumber = cast(Number)z8_native_new("example.NativeNumber"w);
    assert(nativeNumber !is null && numberConstructs == 4);
    auto nativeMath = cast(Math)z8_native_new("example.NativeMath"w);
    assert(nativeMath !is null && mathConstructs == 1);
    z8_nonnull(nativeMath);
    assert(mathConstructs == 2);
    bool missingType;
    try { z8_native_new("example.Missing"w); } catch (Exception e) { missingType = e.msg.indexOf("native type not registered") >= 0; }
    assert(missingType);
    z8_native_register_factory("example.Ambiguous"w, typeid(Number), &anyFactory);
    z8_native_register_factory("example.Ambiguous"w, typeid(Math), &anyFactory);
    bool ambiguousType;
    try { z8_native_new("example.Ambiguous"w); } catch (Exception e) { ambiguousType = e.msg.indexOf("native type is ambiguous") >= 0; }
    assert(ambiguousType);
    z8_native_register_factory("example.InvalidFactory"w, typeid(Number), &anyFactory);
    bool invalidRegisteredFactory;
    try { z8_native_new("example.InvalidFactory"w); } catch (Exception e) { invalidRegisteredFactory = e.msg.indexOf("invalid native type factory result") >= 0; }
    assert(invalidRegisteredFactory);
    assert(z8_optional_require(Z8p_456167657255736572.m_run()) == 43);
    alias Holder = Z8p_4561676572486F6C646572;
    auto holder = z8_new!Holder();
    auto fieldPrimary = z8_nonnull(holder).f_first;
    auto constructedPrimary = z8_nonnull(holder).m_create();
    foreach (value; [fieldPrimary, constructedPrimary]) {
        bool hasNoContainer;
        try { z8_get_container!Holder(value); } catch (Exception) { hasNoContainer = true; }
        assert(hasNoContainer);
    }
    auto generic = z8_new!Generic();
    assert(z8_optional_require(z8_nonnull(generic).m_get()) == 21 && constructed == 1);
    assert(z8_optional_require(Consumer.m_fieldRoundTrip(generic)));
    assert(partnerValue is generic && z8_nonnull(generic).f_partner is generic);
    Generic.f_current = nativeNumber;
    assert(currentValue is nativeNumber && Generic.f_current is nativeNumber);
    partnerValue = new Z8Object();
    bool invalidField;
    try { auto value = z8_nonnull(generic).f_partner; } catch (Exception e) { invalidField = e.msg.indexOf("invalid native return type") >= 0; }
    assert(invalidField);
    partnerValue = null;
    z8_nonnull(generic).f_partner = null;
    Generic.f_current = null;
    assert(partnerValue is null && currentValue is null);
    z8_native_bind_field("example.GenericNative.f_partner"w, &exactPartner);
    z8_nonnull(generic).f_partner = generic;
    assert(exactPartnerValue is generic && partnerValue is null);
    assert(z8_nonnull(generic).m_echo(generic) is generic);
    assert(z8_nonnull(generic).m_echo(null) is null);
    assert(z8_optional_require(Generic.m_inspect(generic)) == 7);
    assert(z8_optional_require(Generic.m_inspect(null)) == 0);
    auto created = Generic.m_make();
    assert(created !is null && created !is generic && constructed == 1);
    assert(z8_optional_require(z8_nonnull(created).m_get()) == 21 && constructed == 2);
    bool invalidFactoryResult;
    try { Generic.m_makeInvalid(); } catch (Exception e) { invalidFactoryResult = e.msg.indexOf("invalid native return type") >= 0; }
    assert(invalidFactoryResult);
    z8_nonnull(generic).m_clear();
    assert(cleared == 1);
    bool invalidReturn;
    try { z8_nonnull(generic).m_invalid(); } catch (Exception e) { invalidReturn = e.msg.indexOf("invalid native return type") >= 0; }
    assert(invalidReturn);
    assert(z8_optional_require(Consumer.m_nativeArray(generic)) == 2);
    assert(z8_nonnull(generic).m_extend(null) is null);
    auto objects = new Z8ObjectArray!Generic([generic]);
    auto returnedObjects = z8_nonnull(generic).m_extend(objects);
    assert(objects.z8_size() == 2 && returnedObjects.z8_size() == 2);
    assert(returnedObjects.z8_get(1) is generic);
    returnedObjects.z8_set(0, created);
    assert(objects.z8_get(0) is created);
    bool badArrayElement;
    try { Generic.m_invalidArray().z8_get(0); } catch (Exception e) { badArrayElement = e.msg.indexOf("invalid object array element cast") >= 0; }
    assert(badArrayElement);
    Generic.m_clearArray(returnedObjects);
    assert(objects.z8_isEmpty());
    z8_native_bind("example.GenericNative.m_extend"w, &exactExtend);
    assert(z8_nonnull(generic).m_extend(objects) is objects && objects.z8_isEmpty());
    z8_native_bind("example.GenericNative.m_get"w, &exactGet);
    assert(z8_optional_require(z8_nonnull(generic).m_get()) == 22);
    z8_native_clear_bindings();
    assert(cast(Generic)z8_native_new("example.GenericNative"w) !is null);
}
'''.replace('import z8.runtime;', 'import z8.runtime;\nimport std.string : indexOf;'), encoding="utf-8")
    executable = temp / ("native.exe" if os.name == "nt" else "native")
    modules = [str(p) for p in generated.rglob("*.d")]
    subprocess.run(["dmd", "-I" + str(generated), "-I" + str(temp), *import_args(), *modules, str(harness), str(adapter_object), str(runtime), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    (source / "Bad.bl").write_text("class Bad { public void f(); }", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad")], capture_output=True, text=True)
    if result.returncode == 0 or "requires a native type" not in result.stderr:
        raise SystemExit("A bodyless method was accepted on an ordinary class")
    (source / "Bad.bl").write_text("class Bad extends primary {}", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad-primary")], capture_output=True, text=True)
    if result.returncode == 0 or "must implement assignment from itself" not in result.stderr:
        raise SystemExit("A non-native primary subclass without assignment was accepted")
    (source / "Bad.bl").write_text('''class Bad extends primary {
        public void operator = (Bad value) {}
    }''', encoding="utf-8")
    (source / "GoodUser.bl").write_text('''class GoodUser { public static int run() {
        Bad value;
        primary boxed = value;
        if (value.toString() != boxed.toString()) return 1;
        if (value.hashCode() != boxed.hashCode()) return 2;
        return 31;
    }}''', encoding="utf-8")
    good = temp / "good-primary"
    subprocess.run([str(compiler), "project", str(source), str(good)], check=True)
    good_harness = temp / "good.d"
    good_harness.write_text('''import z8.runtime; import z8gen.GoodUser;
void main() { assert(z8_optional_require(Z8p_476F6F6455736572.m_run()) == 31); }
''', encoding="utf-8")
    good_executable = temp / ("good.exe" if os.name == "nt" else "good")
    subprocess.run(["dmd", "-I" + str(good), *import_args(), *map(str, good.rglob("*.d")),
                    str(good_harness), str(runtime), "-of=" + str(good_executable)], check=True)
    subprocess.run([str(good_executable)], check=True)
    (source / "Bad.bl").write_text('''class Bad extends primary {
        public void operator = (Bad value) {}
        public string toString() { return "invalid"; }
    }''', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad-override")], capture_output=True, text=True)
    if result.returncode == 0 or "only virtual instance methods" not in result.stderr:
        raise SystemExit("A primary subclass was allowed to override non-virtual toString")
    for declaration in (
        "NativeNumber[NativeMath] value;",
        "int[NativeNumber][NativeMath] value;",
        "NativeMath[NativeNumber] value;",
    ):
        (source / "Bad.bl").write_text("class Bad { public static " + declaration + " }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad-static")], capture_output=True, text=True)
        if result.returncode == 0 or "static reference fields" not in result.stderr:
            raise SystemExit("A static collection containing reference objects was accepted: " + declaration)
    (source / "Bad.bl").write_text('class Bad { [name "number"] NativeNumber value; }', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad-attribute")], capture_output=True, text=True)
    if result.returncode == 0 or "attributes require an object reference field" not in result.stderr:
        raise SystemExit("Attributes were accepted on a primary field")
    (source / "Bad.bl").write_text("class Bad extends NativeMarker {}", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad-marker-child")], capture_output=True, text=True)
    if result.returncode == 0 or "must implement assignment from itself" not in result.stderr:
        raise SystemExit("A non-native subclass of a primary-attributed type lacked an assignment operator")
print("Native and primary declarations bound through the separate runtime")
