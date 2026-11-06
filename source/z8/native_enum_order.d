module z8.native_enum_order;

import std.algorithm : canFind;
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
