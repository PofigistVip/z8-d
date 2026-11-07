#include <OpenXLSX.hpp>
#include <cstring>
#include <exception>
#include <memory>
#include <stdexcept>
#include <string>

#ifdef _WIN32
#define Z8_EXPORT extern "C" __declspec(dllexport)
#else
#define Z8_EXPORT extern "C" __attribute__((visibility("default")))
#endif

namespace {
thread_local std::string error;

template<typename F> int protect(F&& function) noexcept {
    try { function(); error.clear(); return 0; }
    catch (const std::exception& e) { error = e.what(); }
    catch (...) { error = "unknown OpenXLSX error"; }
    return -1;
}

OpenXLSX::XLDocument& document(void* handle) {
    if (!handle) throw std::invalid_argument("workbook is closed");
    return *static_cast<OpenXLSX::XLDocument*>(handle);
}

std::string sheetName(OpenXLSX::XLDocument& doc, unsigned index) {
    auto names = doc.workbook().sheetNames();
    if (index >= names.size()) throw std::out_of_range("sheet index out of bounds");
    return names[index];
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
        auto doc = std::make_unique<OpenXLSX::XLDocument>();
        doc->open(path);
        *result = doc.release();
    });
}

Z8_EXPORT void z8_xlsx_close(void* handle) noexcept {
    delete static_cast<OpenXLSX::XLDocument*>(handle);
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

Z8_EXPORT int z8_xlsx_cell_string(void* handle, unsigned sheet, unsigned row, unsigned column,
                                   char* buffer, size_t capacity, size_t* length) noexcept {
    return protect([&] {
        if (row >= 1048576 || column >= 16384) throw std::out_of_range("cell index out of bounds");
        auto& doc = document(handle);
        auto cell = doc.workbook().worksheet(sheetName(doc, sheet)).cell(row + 1, static_cast<uint16_t>(column + 1));
        copyString(cell.value().getString(), buffer, capacity, length);
    });
}
