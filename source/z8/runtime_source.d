module z8.runtime_source;

// These fragments form one self-contained D module in every generated program.
package enum string runtimeSource = import("z8_core_runtime.txt") ~
    import("z8_map_runtime.txt") ~ import("z8_array_runtime.txt") ~ "\n" ~
    import("z8_decimal_runtime.txt") ~ "\n" ~ import("z8_string_runtime.txt") ~ "\n";
