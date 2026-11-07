/// Direct, optional access to the OpenXLSX bridge. Indices are zero-based.
module z8.xlsx.openxlsx;

import std.string : fromStringz, toStringz;
import std.algorithm.searching : canFind;

private extern(C) {
    const(char)* z8_xlsx_error();
    int z8_xlsx_open(const(char)*, void**);
    int z8_xlsx_open_memory(const(void)*, size_t, void**);
    void z8_xlsx_close(void*);
    int z8_xlsx_sheet_count(void*, uint*);
    int z8_xlsx_sheet_name(void*, uint, char*, size_t, size_t*);
    int z8_xlsx_row_count(void*, uint, uint*);
    int z8_xlsx_row_exists(void*, uint, uint, int*);
    int z8_xlsx_row_cell_count(void*, uint, uint, uint*);
    int z8_xlsx_cell_string(void*, uint, uint, uint, char*, size_t, size_t*);
    int z8_xlsx_cell_type(void*, uint, uint, uint, int*);
    int z8_xlsx_cell_number(void*, uint, uint, uint, double*);
    int z8_xlsx_cell_formula(void*, uint, uint, uint, char*, size_t, size_t*);
}

enum CellType { missing = -1, blank = 0, boolean = 1, integer = 2, floating = 3, error = 4, text = 5 }

private void check(int result) {
    if (result != 0) throw new Exception(fromStringz(z8_xlsx_error()).idup);
}

class Workbook {
    private void* handle;

    this(string path) {
        if (path.canFind('\0')) throw new Exception("workbook path contains NUL");
        check(z8_xlsx_open(path.toStringz, &handle));
    }

    this(const(ubyte)[] bytes) {
        check(z8_xlsx_open_memory(bytes.ptr, bytes.length, &handle));
    }

    ~this() { close(); }

    void close() {
        if (handle !is null) { z8_xlsx_close(handle); handle = null; }
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
}
