/// Optional OpenXLSX document provider for the Z8 native POI facade.
module z8.xlsx.poi;

import z8.runtime : IZ8PoiDocument, IZ8PoiProvider, IZ8PoiReportWriter, Z8PoiHiddenColumn, Z8PoiUnsupportedWorkbook, z8_poi_set_provider;
import z8.xlsx.openxlsx : Workbook;
import std.conv : to;

private class OpenXlsxDocument : IZ8PoiDocument {
    private Workbook book;
    this(const(ubyte)[] bytes) {
        try book = new Workbook(bytes);
        catch (Exception error) throw new Z8PoiUnsupportedWorkbook(error.msg);
    }
    string workbookXml() {
        try return book.workbookXml();
        catch (Exception error) throw new Z8PoiUnsupportedWorkbook(error.msg);
    }
    string sharedStringsXml() {
        try return book.sharedStringsXml();
        catch (Exception error) throw new Z8PoiUnsupportedWorkbook(error.msg);
    }
    uint sheetCount() {
        try return book.sheetCount();
        catch (Exception error) throw new Z8PoiUnsupportedWorkbook(error.msg);
    }
    string sheetXml(uint index) {
        try return book.sheetXml(index);
        catch (Exception error) throw new Z8PoiUnsupportedWorkbook(error.msg);
    }
    void close() { book.close(); }
}

private class OpenXlsxProvider : IZ8PoiProvider, IZ8PoiReportWriter {
    IZ8PoiDocument open(const(ubyte)[] bytes) { return new OpenXlsxDocument(bytes); }
    ubyte[] renameReportSheet(const(ubyte)[] input, uint index, wstring name) {
        try {
            auto book = new Workbook(input);
            scope(exit) book.close();
            book.renameSheet(index, name.to!string);
            return book.save();
        } catch (Exception error) throw new Z8PoiUnsupportedWorkbook(error.msg);
    }
    ubyte[] hideReportColumns(const(ubyte)[] input, const(Z8PoiHiddenColumn)[] columns) {
        try {
            auto book = new Workbook(input);
            scope(exit) book.close();
            foreach (column; columns) book.setColumnHidden(column.sheet, column.column, true);
            return book.save();
        } catch (Exception error) throw new Z8PoiUnsupportedWorkbook(error.msg);
    }
}

/// Install at host startup. The previous provider can be restored with z8_poi_set_provider.
IZ8PoiProvider z8_openxlsx_configure() { return z8_poi_set_provider(new OpenXlsxProvider()); }
