import z8.xlsx.openxlsx : Workbook, CellType;
import std.exception : assertThrown;
import std.file : read;

void main(string[] args) {
    assertThrown!Exception(new Workbook(args[1] ~ ".missing"));
    auto book = new Workbook(args[1]);
    assert(book.sheetCount() == 3);
    assert(book.sheetName(0) == "Данные 😀");
    assert(book.sheetName(1) == "Second");
    assert(book.rowCount(0) == 2 && book.rowCount(1) == 2);
    assert(book.rowCount(2) == 0 && !book.rowExists(2, 0));
    assert(!book.rowExists(1, 0) && book.rowExists(1, 1));
    assert(!book.rowExists(1, 2) && book.rowExists(1, 3));
    assert(book.cellCount(0, 0) == 8 && book.cellCount(0, 1) == 1);
    assert(book.cellCount(1, 1) == 1 && book.cellCount(1, 3) == 0);
    assertThrown!Exception(book.cellCount(1, 0));
    assertThrown!Exception(book.rowExists(0, 1048576));
    assert(book.rowCount(1) == 2);
    assert(book.cellString(0, 0, 0) == "Привет 😀 & text");
    assert(book.cellString(0, 0, 1) == "42");
    assert(book.cellType(0, 0, 0) == CellType.text);
    assert(book.cellType(0, 0, 1) == CellType.integer);
    assert(book.cellType(0, 0, 2) == CellType.missing);
    assert(book.cellType(0, 0, 3) == CellType.blank);
    assert(book.cellType(0, 0, 4) == CellType.boolean);
    assert(book.cellType(0, 0, 5) == CellType.floating);
    assert(book.cellNumber(0, 0, 1) == 42);
    assert(book.cellNumber(0, 0, 5) == 42.25);
    assert(book.cellNumber(0, 0, 6) == 84);
    assert(book.cellFormula(0, 0, 6) == "B1*2");
    assert(book.cellFormula(0, 0, 1) == "");
    assert(book.cellNumber(0, 0, 7) == 43);
    assert(book.cellNumber(0, 1, 7) == 45);
    assert(book.cellNumber(0, 0, 8) == 44);
    assertThrown!Exception(book.cellFormula(0, 0, 7));
    assertThrown!Exception(book.cellFormula(0, 1, 7));
    assertThrown!Exception(book.cellFormula(0, 0, 8));
    assertThrown!Exception(book.cellNumber(0, 0, 4));
    assertThrown!Exception(book.cellString(0, 0, 2));
    assert(book.cellType(0, 0, 2) == CellType.missing);
    assert(book.cellString(1, 1, 2) == "other");
    assertThrown!Exception(book.sheetName(3));
    assertThrown!Exception(book.cellString(0, 1048576, 0));
    book.close();
    book.close();
    assertThrown!Exception(book.sheetCount());

    auto bytes = cast(ubyte[])read(args[1]);
    auto memoryBook = new Workbook(bytes);
    bytes[] = 0; // The bridge retains its own archive data.
    assert(memoryBook.sheetCount() == 3);
    assert(memoryBook.cellString(0, 0, 0) == "Привет 😀 & text");
    memoryBook.close();
    assertThrown!Exception(new Workbook(cast(ubyte[])[]));
    assertThrown!Exception(new Workbook(cast(ubyte[])[1, 2, 3]));
}
