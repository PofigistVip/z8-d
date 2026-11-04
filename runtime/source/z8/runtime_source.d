module z8.runtime_source;

// The runtime fragments share one module and are compiled into the runtime library.
package enum string runtimeSource = import("z8_core_runtime.txt") ~
    import("z8_map_runtime.txt") ~ import("z8_array_runtime.txt") ~ "\n" ~
    import("z8_decimal_runtime.txt") ~ "\n" ~ import("z8_string_runtime.txt") ~ "\n" ~
    import("z8_math_runtime.txt") ~ "\n" ~
    import("z8_numeric_constants_runtime.txt") ~ "\n" ~
    import("z8_guid_runtime.txt") ~ "\n" ~
    import("z8_binary_runtime.txt") ~ "\n" ~
    import("z8_datespan_runtime.txt") ~ "\n" ~
    import("z8_date_runtime.txt") ~ "\n" ~
    import("z8_geometry_runtime.txt") ~ "\n" ~
    import("z8_geometry_json_runtime.txt") ~ "\n" ~
    import("z8_file_runtime.txt") ~ "\n" ~
    import("z8_primary_runtime.txt") ~ "\n" ~ import("z8_primary_map_runtime.txt") ~ "\n";
