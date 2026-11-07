/// Direct, optional access to the OpenXLSX bridge. Indices are zero-based.
module z8.xlsx.openxlsx;

import std.string : fromStringz, toStringz;
import std.algorithm.searching : canFind;

private extern(C) {
    uint z8_xlsx_abi_version();
    const(char)* z8_xlsx_error();
    int z8_xlsx_open(const(char)*, void**);
    int z8_xlsx_open_memory(const(void)*, size_t, void**);
    void z8_xlsx_close(void*);
    int z8_xlsx_save_memory(void*, void*, size_t, size_t*);
    int z8_xlsx_sheet_count(void*, uint*);
    int z8_xlsx_sheet_name(void*, uint, char*, size_t, size_t*);
    int z8_xlsx_workbook_xml(void*, char*, size_t, size_t*);
    int z8_xlsx_shared_strings_xml(void*, char*, size_t, size_t*);
    int z8_xlsx_sheet_xml(void*, uint, char*, size_t, size_t*);
    int z8_xlsx_row_count(void*, uint, uint*);
    int z8_xlsx_row_exists(void*, uint, uint, int*);
    int z8_xlsx_row_cell_count(void*, uint, uint, uint*);
    int z8_xlsx_rename_sheet(void*, uint, const(char)*);
    int z8_xlsx_set_column_hidden(void*, uint, uint, int);
    int z8_xlsx_set_cell_text(void*, uint, uint, uint, const(char)*, size_t, int);
    int z8_xlsx_set_cell_number(void*, uint, uint, uint, double);
    int z8_xlsx_set_cell_boolean(void*, uint, uint, uint, int);
    int z8_xlsx_copy_cell(void*, uint, uint, uint, uint, uint, int);
    int z8_xlsx_cell_string(void*, uint, uint, uint, char*, size_t, size_t*);
    int z8_xlsx_cell_type(void*, uint, uint, uint, int*);
    int z8_xlsx_cell_number(void*, uint, uint, uint, double*);
    int z8_xlsx_cell_formula(void*, uint, uint, uint, char*, size_t, size_t*);
    int z8_xlsx_cell_has_formula(void*, uint, uint, uint, int*);
    int z8_xlsx_cell_xml(void*, uint, uint, uint, char*, size_t, size_t*);
}

enum CellType { missing = -1, blank = 0, boolean = 1, integer = 2, floating = 3, error = 4, text = 5 }

private void check(int result) {
    if (result != 0) throw new Exception(fromStringz(z8_xlsx_error()).idup);
}

private void checkAbi() {
    if (z8_xlsx_abi_version() != 3) throw new Exception("incompatible OpenXLSX bridge; rebuild xlsx");
}

class Workbook {
    private void* handle;

    this(string path) {
        checkAbi();
        if (path.canFind('\0')) throw new Exception("workbook path contains NUL");
        check(z8_xlsx_open(path.toStringz, &handle));
    }

    this(const(ubyte)[] bytes) {
        checkAbi();
        check(z8_xlsx_open_memory(bytes.ptr, bytes.length, &handle));
    }

    ~this() { close(); }

    void close() {
        if (handle !is null) { z8_xlsx_close(handle); handle = null; }
    }

    /// Serialize a workbook opened from bytes, without writing a temporary file.
    ubyte[] save() {
        size_t length;
        check(z8_xlsx_save_memory(handle, null, 0, &length));
        auto result = new ubyte[length];
        check(z8_xlsx_save_memory(handle, result.ptr, result.length, &length));
        return result;
    }

    uint sheetCount() {
        uint result;
        check(z8_xlsx_sheet_count(handle, &result));
        return result;
    }

    string sheetName(uint index) {
        size_t length;
        check(z8_xlsx_sheet_name(handle, index, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_sheet_name(handle, index, result.ptr, result.length, &length));
        return result.idup;
    }

    string workbookXml() {
        size_t length;
        check(z8_xlsx_workbook_xml(handle, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_workbook_xml(handle, result.ptr, result.length, &length));
        return result.idup;
    }

    string sharedStringsXml() {
        size_t length;
        check(z8_xlsx_shared_strings_xml(handle, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_shared_strings_xml(handle, result.ptr, result.length, &length));
        return result.idup;
    }

    string sheetXml(uint sheet) {
        size_t length;
        check(z8_xlsx_sheet_xml(handle, sheet, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_sheet_xml(handle, sheet, result.ptr, result.length, &length));
        return result.idup;
    }

    uint rowCount(uint sheet) {
        uint result;
        check(z8_xlsx_row_count(handle, sheet, &result));
        return result;
    }

    bool rowExists(uint sheet, uint row) {
        int result;
        check(z8_xlsx_row_exists(handle, sheet, row, &result));
        return result != 0;
    }

    uint cellCount(uint sheet, uint row) {
        uint result;
        check(z8_xlsx_row_cell_count(handle, sheet, row, &result));
        return result;
    }

    void renameSheet(uint sheet, string name) {
        if (name.canFind('\0')) throw new Exception("sheet name contains NUL");
        check(z8_xlsx_rename_sheet(handle, sheet, name.toStringz));
    }

    void setColumnHidden(uint sheet, uint column, bool hidden) {
        check(z8_xlsx_set_column_hidden(handle, sheet, column, hidden ? 1 : 0));
    }

    void setText(uint sheet, uint row, uint column, string value) {
        setTextInternal(sheet, row, column, value, true);
    }

    /// Preserve Apache POI's interpretation of literal OOXML escape sequences.
    void setPoiText(uint sheet, uint row, uint column, string value) {
        setTextInternal(sheet, row, column, value, false);
    }

    private void setTextInternal(uint sheet, uint row, uint column, string value, bool escapeLiterals) {
        import std.utf : validate;
        validate(value);
        check(z8_xlsx_set_cell_text(handle, sheet, row, column, value.ptr, value.length, escapeLiterals ? 1 : 0));
    }

    void setNumber(uint sheet, uint row, uint column, double value) {
        check(z8_xlsx_set_cell_number(handle, sheet, row, column, value));
    }

    void setBoolean(uint sheet, uint row, uint column, bool value) {
        check(z8_xlsx_set_cell_boolean(handle, sheet, row, column, value ? 1 : 0));
    }

    /// Copy an existing cell, retaining its XML attributes and children.
    /// Formula references are copied literally and are not adjusted.
    void copyCell(uint sheet, uint sourceRow, uint sourceColumn, uint targetRow, uint targetColumn, bool clearFormulaCache = false) {
        check(z8_xlsx_copy_cell(handle, sheet, sourceRow, sourceColumn, targetRow, targetColumn, clearFormulaCache ? 1 : 0));
    }

    /// Raw OpenXLSX conversion; rich inline text and OOXML escapes may need
    /// additional processing using cellXml() for compatibility with POI.
    string cellString(uint sheet, uint row, uint column) {
        size_t length;
        check(z8_xlsx_cell_string(handle, sheet, row, column, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_cell_string(handle, sheet, row, column, result.ptr, result.length, &length));
        return result.idup;
    }

    CellType cellType(uint sheet, uint row, uint column) {
        int result;
        check(z8_xlsx_cell_type(handle, sheet, row, column, &result));
        return cast(CellType) result;
    }

    double cellNumber(uint sheet, uint row, uint column) {
        double result;
        check(z8_xlsx_cell_number(handle, sheet, row, column, &result));
        return result;
    }

    /// Shared and array formulas may be rejected by OpenXLSX.
    string cellFormula(uint sheet, uint row, uint column) {
        size_t length;
        check(z8_xlsx_cell_formula(handle, sheet, row, column, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_cell_formula(handle, sheet, row, column, result.ptr, result.length, &length));
        return result.idup;
    }

    bool cellHasFormula(uint sheet, uint row, uint column) {
        int result;
        check(z8_xlsx_cell_has_formula(handle, sheet, row, column, &result));
        return result != 0;
    }

    /// OpenXLSX's XML representation, for formula and rich-text compatibility.
    string cellXml(uint sheet, uint row, uint column) {
        size_t length;
        check(z8_xlsx_cell_xml(handle, sheet, row, column, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_cell_xml(handle, sheet, row, column, result.ptr, result.length, &length));
        return result.idup;
    }
}
