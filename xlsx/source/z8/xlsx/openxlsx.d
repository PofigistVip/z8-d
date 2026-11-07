/// Direct, optional access to the OpenXLSX bridge. Indices are zero-based.
module z8.xlsx.openxlsx;

import std.string : fromStringz, toStringz;
import std.algorithm.searching : canFind;

private extern(C) {
    const(char)* z8_xlsx_error();
    int z8_xlsx_open(const(char)*, void**);
    void z8_xlsx_close(void*);
    int z8_xlsx_sheet_count(void*, uint*);
    int z8_xlsx_sheet_name(void*, uint, char*, size_t, size_t*);
    int z8_xlsx_cell_string(void*, uint, uint, uint, char*, size_t, size_t*);
}

private void check(int result) {
    if (result != 0) throw new Exception(fromStringz(z8_xlsx_error()).idup);
}

class Workbook {
    private void* handle;

    this(string path) {
        if (path.canFind('\0')) throw new Exception("workbook path contains NUL");
        check(z8_xlsx_open(path.toStringz, &handle));
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

    string cellString(uint sheet, uint row, uint column) {
        size_t length;
        check(z8_xlsx_cell_string(handle, sheet, row, column, null, 0, &length));
        auto result = new char[length];
        check(z8_xlsx_cell_string(handle, sheet, row, column, result.ptr, result.length, &length));
        return result.idup;
    }
}
