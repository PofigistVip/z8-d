module z8.runtime_source;

// The runtime fragments share one module and are compiled into the runtime library.
package enum string runtimeSource = import("z8_core_runtime.txt") ~
    import("z8_map_runtime.txt") ~ import("z8_array_runtime.txt") ~ "\n" ~
    import("z8_decimal_runtime.txt") ~ "\n" ~ import("z8_string_runtime.txt") ~ "\n";
