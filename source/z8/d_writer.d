module z8.d_writer;

import std.string : splitLines, stripLeft;

/// Indent generated D blocks without interpreting braces in literals or comments.
package string formatDSource(string source) {
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
    auto source = "class C {\nvoid f() {\nauto s = \"} {\\\"\"; // }\n/* {\n} */\nif (true) {\nwork();\n}\n}\n}\n";
    assert(formatDSource(source) ==
        "class C {\n    void f() {\n        auto s = \"} {\\\"\"; // }\n        /* {\n        } */\n        if (true) {\n            work();\n        }\n    }\n}\n", formatDSource(source));
}
