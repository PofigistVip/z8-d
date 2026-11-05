module z8.runtime_source;

// The runtime fragments share one module and are compiled into the runtime library.
package enum string runtimeSource = import("z8_core_runtime.txt") ~
    import("z8_map_runtime.txt") ~ import("z8_array_runtime.txt") ~ import("z8_int_map_runtime.txt") ~ import("z8_string_value_map_runtime.txt") ~ import("z8_guid_map_runtime.txt") ~ "\n" ~
    import("z8_decimal_runtime.txt") ~ "\n" ~ import("z8_string_runtime.txt") ~ "\n" ~
    import("z8_nls_runtime.txt") ~ "\n" ~
    import("z8_regex_runtime.txt") ~ "\n" ~
    import("z8_math_runtime.txt") ~ "\n" ~
    import("z8_numeric_constants_runtime.txt") ~ "\n" ~
    import("z8_sql_runtime.txt") ~ "\n" ~
    import("z8_sql_integer_runtime.txt") ~ "\n" ~
    import("z8_sql_decimal_runtime.txt") ~ "\n" ~
    import("z8_sql_string_runtime.txt") ~ "\n" ~
    import("z8_sql_guid_runtime.txt") ~ "\n" ~
    import("z8_sql_date_runtime.txt") ~ "\n" ~
    import("z8_sql_datespan_runtime.txt") ~ "\n" ~
    import("z8_sql_binary_runtime.txt") ~ "\n" ~
    import("z8_sql_geometry_runtime.txt") ~ "\n" ~
    import("z8_guid_runtime.txt") ~ "\n" ~
    import("z8_binary_runtime.txt") ~ "\n" ~
    import("z8_encoding_tables_runtime.txt") ~ "\n" ~
    import("z8_encoding_runtime.txt") ~ "\n" ~
    import("z8_datespan_runtime.txt") ~ "\n" ~
    import("z8_moscow_timezone_runtime.txt") ~ "\n" ~
    import("z8_calendar_runtime.txt") ~ "\n" ~
    import("z8_date_runtime.txt") ~ "\n" ~
    import("z8_json_runtime.txt") ~ "\n" ~
    import("z8_geometry_runtime.txt") ~ "\n" ~
    import("z8_geometry_json_runtime.txt") ~ "\n" ~
    import("z8_file_runtime.txt") ~ "\n" ~
    import("z8_zip_runtime.txt") ~ "\n" ~
    import("z8_primary_runtime.txt") ~ "\n" ~ import("z8_primary_map_runtime.txt") ~ "\n" ~
    import("z8_messageformat_runtime.txt") ~ "\n";
