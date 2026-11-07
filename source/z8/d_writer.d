module z8.d_writer;

import std.string : splitLines, stripLeft;
import std.conv : to;
import std.format : format;
import std.uni : unicode;

// Prefixes on generated symbols keep this escape namespace separate from BL
// names that happen to resemble an encoded identifier.
package string dIdentifier(string name) {
    foreach (dchar c; name) if ((c >= 0x7F && c <= 0x9F) ||
        (c >= 128 && ((c in unicode.Sc) || (c in unicode.Cf)))) {
        string encoded = "_z8id_";
        foreach (ubyte byteValue; name) encoded ~= format("%02X", byteValue);
        return encoded;
    }
    return name;
}

// Rewrite generated identifiers only; names in string literals are metadata
// and must retain the original BL spelling.
private string encodeDIdentifiers(string source) {
    bool needsEncoding;
    foreach (dchar c; source) if ((c >= 0x7F && c <= 0x9F) ||
        (c >= 128 && ((c in unicode.Sc) || (c in unicode.Cf)))) { needsEncoding = true; break; }
    if (!needsEncoding) return source;
    auto input = source.to!dstring;
    dchar[] output;
    bool blockComment, lineComment, escaped;
    dchar quote = 0;
    bool word(dchar c) {
        return c == '_' || (c >= '0' && c <= '9') || (c in unicode.L) || (c in unicode.Nl) ||
            (c in unicode.Nd) || (c in unicode.Mn) || (c in unicode.Mc) || (c in unicode.Pc) ||
            (c in unicode.Sc) || (c in unicode.Cf) || (c >= 0x7F && c <= 0x9F);
    }
    for (size_t i; i < input.length;) {
        auto c = input[i];
        auto next = i + 1 < input.length ? input[i + 1] : '\0';
        if (lineComment) {
            output ~= c; ++i;
            if (c == '\n') lineComment = false;
        } else if (blockComment) {
            output ~= c; ++i;
            if (c == '*' && next == '/') { output ~= next; ++i; blockComment = false; }
        } else if (quote) {
            output ~= c; ++i;
            if (escaped) escaped = false;
            else if (c == '\\' && quote != '`') escaped = true;
            else if (c == quote) quote = 0;
        } else if (c == '/' && (next == '/' || next == '*')) {
            output ~= c; output ~= next; i += 2;
            lineComment = next == '/'; blockComment = next == '*';
        } else if (c == '"' || c == '\'' || c == '`') {
            quote = c; output ~= c; ++i;
        } else if (word(c)) {
            auto start = i++;
            while (i < input.length && word(input[i])) ++i;
            output ~= dIdentifier(input[start .. i].to!string).to!dstring;
        } else { output ~= c; ++i; }
    }
    return output.to!string;
}

/// Indent generated D blocks without interpreting braces in literals or comments.
package string formatDSource(string source) {
    source = encodeDIdentifiers(source);
    string output;
    size_t depth;
    bool blockComment;
    foreach (original; source.splitLines()) {
        auto line = original.stripLeft();
        size_t leadingCloses;
        if (!blockComment) {
            foreach (c; line) {
                if (c == '}') ++leadingCloses;
                else if (c != ' ' && c != '\t') break;
            }
        }
        auto indent = leadingCloses < depth ? depth - leadingCloses : 0;
        if (line.length) foreach (_; 0 .. indent) output ~= "    ";
        output ~= line ~ "\n";

        char quote = 0;
        bool escaped;
        for (size_t i = 0; i < line.length; ++i) {
            auto c = line[i];
            if (blockComment) {
                if (c == '*' && i + 1 < line.length && line[i + 1] == '/') {
                    blockComment = false;
                    ++i;
                }
            } else if (quote) {
                if (escaped) escaped = false;
                else if (c == '\\' && quote != '`') escaped = true;
                else if (c == quote) quote = 0;
            } else if (c == '/' && i + 1 < line.length && line[i + 1] == '/') break;
            else if (c == '/' && i + 1 < line.length && line[i + 1] == '*') {
                blockComment = true;
                ++i;
            } else if (c == '"' || c == '\'' || c == '`') quote = c;
            else if (c == '{') ++depth;
            else if (c == '}' && depth) --depth;
        }
    }
    return output;
}

unittest {
    assert(dIdentifier("m_€value") == "_z8id_6D5FE282AC76616C7565");
    auto encodedTest = formatDSource("// comment\nstring s = \"€value\"; int m_€value;\n");
    assert(encodedTest == "// comment\nstring s = \"€value\"; int _z8id_6D5FE282AC76616C7565;\n", encodedTest);
    assert(formatDSource("auto x = values[$ - 1]; int m_€value;\n") ==
        "auto x = values[$ - 1]; int _z8id_6D5FE282AC76616C7565;\n");
    auto source = "class C {\nvoid f() {\nauto s = \"} {\\\"\"; // }\n/* {\n} */\nif (true) {\nwork();\n}\n}\n}\n";
    assert(formatDSource(source) ==
        "class C {\n    void f() {\n        auto s = \"} {\\\"\"; // }\n        /* {\n        } */\n        if (true) {\n            work();\n        }\n    }\n}\n", formatDSource(source));
}
