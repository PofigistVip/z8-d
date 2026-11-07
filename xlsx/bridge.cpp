#include <OpenXLSX.hpp>
#include <miniz.h>
#include <cstring>
#include <exception>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#ifdef _WIN32
#define Z8_EXPORT extern "C" __declspec(dllexport)
#else
#define Z8_EXPORT extern "C" __attribute__((visibility("default")))
#endif

namespace {
thread_local std::string error;

// OpenXLSX operates on an IZipArchive. Keep uploaded binaries in memory and
// implement the transient entries OpenXLSX adds when optional parts are absent.
struct MemoryArchiveState {
    std::vector<unsigned char> bytes;
    mz_zip_archive zip{};
    bool opened = false;
    std::unordered_map<std::string, std::string> changes;
    std::unordered_set<std::string> removed;
    std::vector<unsigned char> output;
    ~MemoryArchiveState() { if (opened) mz_zip_reader_end(&zip); }
};

class MemoryArchive {
    std::shared_ptr<MemoryArchiveState> state;
public:
    MemoryArchive(const void* data, size_t size) : state(std::make_shared<MemoryArchiveState>()) {
        if (!data || !size) throw std::invalid_argument("empty XLSX binary");
        auto first = static_cast<const unsigned char*>(data);
        state->bytes.assign(first, first + size);
    }
    bool isValid() const { return true; }
    bool isOpen() const { return state->opened; }
    void open(const std::string&) {
        if (state->opened) throw std::runtime_error("XLSX archive already open");
        if (!mz_zip_reader_init_mem(&state->zip, state->bytes.data(), state->bytes.size(), 0))
            throw std::runtime_error("invalid XLSX archive");
        state->opened = true;
    }
    void close() {
        if (state->opened) { mz_zip_reader_end(&state->zip); state->opened = false; }
    }
    void save(const std::string&) {
        if (!state->opened) throw std::runtime_error("XLSX archive is closed");
        mz_zip_archive writer{};
        if (!mz_zip_writer_init_heap(&writer, 0, 0)) throw std::runtime_error("cannot create XLSX archive");
        struct WriterGuard { mz_zip_archive* zip; ~WriterGuard() { mz_zip_writer_end(zip); } } guard{&writer};
        const auto count = mz_zip_reader_get_num_files(&state->zip);
        for (mz_uint i = 0; i < count; ++i) {
            auto length = mz_zip_reader_get_filename(&state->zip, i, nullptr, 0);
            if (!length) throw std::runtime_error("cannot read XLSX entry name");
            std::vector<char> name(length);
            if (mz_zip_reader_get_filename(&state->zip, i, name.data(), length) != length)
                throw std::runtime_error("cannot read XLSX entry name");
            std::string key(name.data(), length - 1);
            if (!state->removed.count(key) && !state->changes.count(key) &&
                !mz_zip_writer_add_from_zip_reader(&writer, &state->zip, i))
                throw std::runtime_error("cannot copy XLSX entry: " + key);
        }
        for (const auto& entry : state->changes) {
            if (!mz_zip_writer_add_mem(&writer, entry.first.c_str(), entry.second.data(), entry.second.size(), MZ_DEFAULT_COMPRESSION))
                throw std::runtime_error("cannot write XLSX entry: " + entry.first);
        }
        void* raw = nullptr;
        size_t size = 0;
        if (!mz_zip_writer_finalize_heap_archive(&writer, &raw, &size))
            throw std::runtime_error("cannot finalize XLSX archive");
        std::unique_ptr<void, decltype(&mz_free)> data(raw, &mz_free);
        auto first = static_cast<const unsigned char*>(data.get());
        state->output.assign(first, first + size);
    }
    void addEntry(const std::string& name, const std::string& data) {
        state->removed.erase(name);
        state->changes[name] = data;
    }
    void addEntryAndCommit(const std::string& name, const std::string& data) { addEntry(name, data); }
    void deleteEntry(const std::string& name) { state->changes.erase(name); state->removed.insert(name); }
    bool hasEntry(const std::string& name) const {
        if (state->removed.count(name)) return false;
        return state->changes.count(name) ||
            (state->opened && mz_zip_reader_locate_file(&state->zip, name.c_str(), nullptr, MZ_ZIP_FLAG_CASE_SENSITIVE) >= 0);
    }
    std::string getEntry(const std::string& name) {
        auto changed = state->changes.find(name);
        if (changed != state->changes.end()) return changed->second;
        if (!hasEntry(name)) throw std::runtime_error("missing XLSX entry: " + name);
        size_t size = 0;
        void* raw = mz_zip_reader_extract_file_to_heap(&state->zip, name.c_str(), &size, MZ_ZIP_FLAG_CASE_SENSITIVE);
        if (!raw) throw std::runtime_error("cannot read XLSX entry: " + name);
        std::unique_ptr<void, decltype(&mz_free)> value(raw, &mz_free);
        return std::string(static_cast<const char*>(value.get()), size);
    }
    std::shared_ptr<MemoryArchiveState> getState() const { return state; }
};

struct WorkbookHandle {
    std::shared_ptr<MemoryArchiveState> memory;
    std::unique_ptr<OpenXLSX::XLDocument> doc;
};

template<typename F> int protect(F&& function) noexcept {
    try { function(); error.clear(); return 0; }
    catch (const std::exception& e) { error = e.what(); }
    catch (...) { error = "unknown OpenXLSX error"; }
    return -1;
}

OpenXLSX::XLDocument& document(void* handle) {
    if (!handle) throw std::invalid_argument("workbook is closed");
    return *static_cast<WorkbookHandle*>(handle)->doc;
}

std::string sheetName(OpenXLSX::XLDocument& doc, unsigned index) {
    auto names = doc.workbook().sheetNames();
    if (index >= names.size()) throw std::out_of_range("sheet index out of bounds");
    return names[index];
}

OpenXLSX::XLCell findCell(void* handle, unsigned sheet, unsigned row, unsigned column) {
    if (row >= 1048576 || column >= 16384) throw std::out_of_range("cell index out of bounds");
    auto& doc = document(handle);
    return doc.workbook().worksheet(sheetName(doc, sheet)).findCell(row + 1, static_cast<uint16_t>(column + 1));
}

OpenXLSX::XLCell requireCell(void* handle, unsigned sheet, unsigned row, unsigned column) {
    auto cell = findCell(handle, sheet, row, column);
    if (cell.empty()) throw std::out_of_range("cell does not exist");
    return cell;
}

OpenXLSX::XLWorksheet worksheet(void* handle, unsigned sheet) {
    auto& doc = document(handle);
    return doc.workbook().worksheet(sheetName(doc, sheet));
}

OpenXLSX::XLRow findRow(OpenXLSX::XLWorksheet& sheet, unsigned row) {
    if (row >= 1048576) throw std::out_of_range("row index out of bounds");
    auto rows = sheet.rows(row + 1, row + 1);
    auto item = rows.begin();
    return item.rowExists() ? *item : OpenXLSX::XLRow{};
}

void copyString(const std::string& value, char* buffer, size_t capacity, size_t* length) {
    if (!length) throw std::invalid_argument("missing output length");
    *length = value.size();
    if (buffer) {
        if (capacity < value.size()) throw std::length_error("output buffer is too small");
        if (!value.empty()) std::memcpy(buffer, value.data(), value.size());
    }
}
}

Z8_EXPORT const char* z8_xlsx_error() noexcept { return error.c_str(); }

Z8_EXPORT int z8_xlsx_open(const char* path, void** result) noexcept {
    return protect([&] {
        if (!path || !result) throw std::invalid_argument("missing workbook path or output");
        *result = nullptr;
        auto book = std::make_unique<WorkbookHandle>();
        book->doc = std::make_unique<OpenXLSX::XLDocument>();
        book->doc->open(path);
        *result = book.release();
    });
}

Z8_EXPORT int z8_xlsx_open_memory(const void* data, size_t size, void** result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing workbook output");
        *result = nullptr;
        MemoryArchive archive(data, size);
        auto book = std::make_unique<WorkbookHandle>();
        book->memory = archive.getState();
        book->doc = std::make_unique<OpenXLSX::XLDocument>(archive);
        book->doc->open("memory.xlsx");
        *result = book.release();
    });
}

Z8_EXPORT void z8_xlsx_close(void* handle) noexcept {
    delete static_cast<WorkbookHandle*>(handle);
}

Z8_EXPORT int z8_xlsx_save_memory(void* handle, void* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        if (!handle || !length) throw std::invalid_argument("missing workbook or output length");
        auto& book = *static_cast<WorkbookHandle*>(handle);
        if (!book.memory) throw std::runtime_error("workbook was not opened from memory");
        if (!buffer) book.doc->saveAs("memory.xlsx", OpenXLSX::XLForceOverwrite);
        auto& bytes = book.memory->output;
        *length = bytes.size();
        if (buffer) {
            if (capacity < bytes.size()) throw std::length_error("output buffer is too small");
            if (!bytes.empty()) std::memcpy(buffer, bytes.data(), bytes.size());
        }
    });
}

Z8_EXPORT int z8_xlsx_sheet_count(void* handle, unsigned* result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing output");
        *result = document(handle).workbook().sheetCount();
    });
}

Z8_EXPORT int z8_xlsx_sheet_name(void* handle, unsigned index, char* buffer,
                                  size_t capacity, size_t* length) noexcept {
    return protect([&] { copyString(sheetName(document(handle), index), buffer, capacity, length); });
}

Z8_EXPORT int z8_xlsx_workbook_xml(void* handle, char* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        std::ostringstream xml;
        document(handle).workbook().print(xml);
        copyString(xml.str(), buffer, capacity, length);
    });
}

Z8_EXPORT int z8_xlsx_shared_strings_xml(void* handle, char* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        std::ostringstream xml;
        document(handle).sharedStrings().print(xml);
        copyString(xml.str(), buffer, capacity, length);
    });
}

Z8_EXPORT int z8_xlsx_sheet_xml(void* handle, unsigned sheet, char* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        auto& doc = document(handle);
        auto name = sheetName(doc, sheet);
        (void)doc.workbook().worksheet(name); // The native POI facade expects worksheets.
        std::ostringstream xml;
        doc.workbook().sheet(name).print(xml);
        copyString(xml.str(), buffer, capacity, length);
    });
}

Z8_EXPORT int z8_xlsx_row_count(void* handle, unsigned sheet, unsigned* result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing output");
        auto page = worksheet(handle, sheet);
        auto rows = page.rows();
        unsigned count = 0;
        for (auto it = rows.begin(); it != rows.end(); ++it) if (it.rowExists()) ++count;
        *result = count;
    });
}

Z8_EXPORT int z8_xlsx_row_exists(void* handle, unsigned sheet, unsigned row, int* result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing output");
        auto page = worksheet(handle, sheet);
        *result = !findRow(page, row).empty();
    });
}

Z8_EXPORT int z8_xlsx_row_cell_count(void* handle, unsigned sheet, unsigned row, unsigned* result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing output");
        auto page = worksheet(handle, sheet);
        auto record = findRow(page, row);
        if (record.empty()) throw std::out_of_range("row does not exist");
        unsigned count = 0;
        auto last = record.cellCount();
        if (last) {
            auto range = page.range(OpenXLSX::XLCellReference(row + 1, 1), OpenXLSX::XLCellReference(row + 1, last));
            for (auto it = range.begin(); it != range.end(); ++it) if (it.cellExists()) ++count;
        }
        *result = count;
    });
}

Z8_EXPORT int z8_xlsx_rename_sheet(void* handle, unsigned sheet, const char* name) noexcept {
    return protect([&] {
        if (!name) throw std::invalid_argument("missing sheet name");
        auto& doc = document(handle);
        doc.workbook().worksheet(sheetName(doc, sheet)).setName(name);
    });
}

Z8_EXPORT int z8_xlsx_set_column_hidden(void* handle, unsigned sheet, unsigned column, int hidden) noexcept {
    return protect([&] {
        if (column >= 16384) throw std::out_of_range("column index out of bounds");
        auto page = worksheet(handle, sheet);
        page.column(static_cast<uint16_t>(column + 1)).setHidden(hidden != 0);
    });
}

Z8_EXPORT int z8_xlsx_cell_string(void* handle, unsigned sheet, unsigned row, unsigned column,
                                   char* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        auto cell = requireCell(handle, sheet, row, column);
        copyString(cell.value().getString(), buffer, capacity, length);
    });
}

Z8_EXPORT int z8_xlsx_cell_type(void* handle, unsigned sheet, unsigned row, unsigned column, int* result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing output");
        auto cell = findCell(handle, sheet, row, column);
        if (cell.empty()) { *result = -1; return; }
        switch (cell.value().type()) {
            case OpenXLSX::XLValueType::Empty:   *result = 0; break;
            case OpenXLSX::XLValueType::Boolean: *result = 1; break;
            case OpenXLSX::XLValueType::Integer: *result = 2; break;
            case OpenXLSX::XLValueType::Float:   *result = 3; break;
            case OpenXLSX::XLValueType::Error:   *result = 4; break;
            case OpenXLSX::XLValueType::String:  *result = 5; break;
            default: throw std::runtime_error("unknown XLSX cell type");
        }
    });
}

Z8_EXPORT int z8_xlsx_cell_number(void* handle, unsigned sheet, unsigned row, unsigned column, double* result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing output");
        auto cell = requireCell(handle, sheet, row, column);
        auto type = cell.value().type();
        if (type != OpenXLSX::XLValueType::Integer && type != OpenXLSX::XLValueType::Float)
            throw std::runtime_error("XLSX cell is not numeric");
        *result = cell.value().get<double>();
    });
}

Z8_EXPORT int z8_xlsx_cell_formula(void* handle, unsigned sheet, unsigned row, unsigned column,
                                    char* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        auto cell = requireCell(handle, sheet, row, column);
        copyString(cell.formula().get(), buffer, capacity, length);
    });
}

Z8_EXPORT int z8_xlsx_cell_has_formula(void* handle, unsigned sheet, unsigned row, unsigned column, int* result) noexcept {
    return protect([&] {
        if (!result) throw std::invalid_argument("missing output");
        *result = requireCell(handle, sheet, row, column).hasFormula();
    });
}

Z8_EXPORT int z8_xlsx_cell_xml(void* handle, unsigned sheet, unsigned row, unsigned column,
                                char* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        auto cell = requireCell(handle, sheet, row, column);
        std::ostringstream xml;
        cell.print(xml);
        copyString(xml.str(), buffer, capacity, length);
    });
}
