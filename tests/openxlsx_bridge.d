import z8.xlsx.openxlsx : Workbook;
import std.exception : assertThrown;

void main(string[] args) {
    assertThrown!Exception(new Workbook(args[1] ~ ".missing"));
    auto book = new Workbook(args[1]);
    assert(book.sheetCount() == 2);
    assert(book.sheetName(0) == "Данные 😀");
    assert(book.sheetName(1) == "Second");
    assert(book.cellString(0, 0, 0) == "Привет 😀 & text");
    assert(book.cellString(0, 0, 1) == "42");
    assert(book.cellString(1, 1, 2) == "other");
    assertThrown!Exception(book.sheetName(2));
    assertThrown!Exception(book.cellString(0, 1048576, 0));
    book.close();
    book.close();
    assertThrown!Exception(book.sheetCount());
}
