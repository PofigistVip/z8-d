/// Optional OpenXLSX document provider for the Z8 native POI facade.
module z8.xlsx.poi;

import z8.runtime : IZ8PoiDocument, IZ8PoiProvider, z8_poi_set_provider;
import z8.xlsx.openxlsx : Workbook;

private class OpenXlsxDocument : IZ8PoiDocument {
    private Workbook book;
    this(const(ubyte)[] bytes) { book = new Workbook(bytes); }
    string workbookXml() { return book.workbookXml(); }
    string sharedStringsXml() { return book.sharedStringsXml(); }
    uint sheetCount() { return book.sheetCount(); }
    string sheetXml(uint index) { return book.sheetXml(index); }
    void close() { book.close(); }
}

private class OpenXlsxProvider : IZ8PoiProvider {
    IZ8PoiDocument open(const(ubyte)[] bytes) { return new OpenXlsxDocument(bytes); }
}

/// Install at host startup. The previous provider can be restored with z8_poi_set_provider.
IZ8PoiProvider z8_openxlsx_configure() { return z8_poi_set_provider(new OpenXlsxProvider()); }
