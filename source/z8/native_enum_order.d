module z8.native_enum_order;

import std.algorithm : canFind;
import std.string : toLower;
import z8.compiler_model : Program;

// Explicit orders of the Java-backed platform enums. BL declaration order is
// not authoritative for native enums; in particular Aggregation and FieldType
// differ. Keep these in sync with the native implementations.
package string[] nativeEnumOrder(wstring name) {
    switch (name) {
        case "org.zenframework.z8.server.base.form.action.ActionType"w:
            return ["Default", "Danger", "Primary", "Success"];
        case "org.zenframework.z8.server.base.query.ReadLock"w:
            return ["None", "Update", "Share", "UpdateNoWait", "ShareNoWait"];
        case "org.zenframework.z8.server.db.sql.SortDirection"w:
            return ["Asc", "Desc"];
        case "org.zenframework.z8.server.base.table.value.Aggregation"w:
            return ["None", "Sum", "Min", "Max", "Average", "Count", "Array", "Distinct", "Concat", "BitwiseOr", "BitwiseAnd"];
        case "org.zenframework.z8.server.db.FieldType"w:
            return ["None", "Null", "Attachments", "Binary", "Boolean", "Date", "Datetime", "Datespan", "Decimal", "File", "Geometry", "Guid", "Integer", "String", "Text"];
        case "org.zenframework.z8.server.base.table.value.JoinType"w:
            return ["Inner", "Left", "Right", "Full"];
        case "org.zenframework.z8.server.ie.ImportPolicy"w:
            return ["Keep", "Override", "Merge"];
        default: return null;
    }
}

// Reject unknown or stale declarations rather than inventing an order.
package bool enumSortOrder(Program program, out string[] values) {
    if (program is null || !program.isEnum) return false;
    if (!program.isNative) {
        foreach (value; program.enumValues) values ~= value.text;
        return true;
    }
    auto known = nativeEnumOrder(program.nativeName);
    if (!known.length) return false;
    foreach (value; program.enumValues) if (!known.canFind(value.text)) return false;
    foreach (name; known) foreach (value; program.enumValues) if (value.text == name) values ~= name;
    return true;
}

// Native Java enums can override toString independently of their identifiers.
package bool enumJoinNames(Program program, out string[] values, out string[] names) {
    if (!enumSortOrder(program, values)) return false;
    foreach (value; values) {
        if (!program.isNative || program.nativeName == "org.zenframework.z8.server.ie.ImportPolicy"w) {
            names ~= value;
        } else if (program.nativeName == "org.zenframework.z8.server.base.query.ReadLock"w) {
            switch (value) {
                case "None": names ~= ""; break;
                case "Update": names ~= "for update"; break;
                case "Share": names ~= "for share"; break;
                case "UpdateNoWait": names ~= "for update nowait"; break;
                case "ShareNoWait": names ~= "for share nowait"; break;
                default: return false;
            }
        } else if (program.nativeName == "org.zenframework.z8.server.db.FieldType"w && value == "Decimal") {
            names ~= "float";
        } else if (program.nativeName == "org.zenframework.z8.server.db.FieldType"w && value == "Integer") {
            names ~= "int";
        } else if (program.nativeName == "org.zenframework.z8.server.base.table.value.Aggregation"w && value == "BitwiseOr") {
            names ~= "bitwise_or";
        } else if (program.nativeName == "org.zenframework.z8.server.base.table.value.Aggregation"w && value == "BitwiseAnd") {
            names ~= "bitwise_and";
        } else {
            names ~= value.toLower();
        }
    }
    return true;
}
