module z8.nls;

import std.algorithm : canFind;
import std.conv : to;
import z8.compiler_model : SourceUnit, CompileException;
import z8.lexer : Lexer, LexException, Token, TokenKind, decodeStringLiteral;

// Share the XML-properties reader with the separately linked runtime.
mixin(import("z8_nls_parser.txt"));

struct MissingResource {
    string path;
    Token token;
    wstring key;
}

MissingResource[] checkResources(SourceUnit[] units, string directory, string language, out size_t bundleCount) {
    auto files = z8_nls_find_files(directory, language);
    bundleCount = files.length;
    if (!bundleCount) throw new Exception("no resource bundles for language '" ~ language ~ "' in " ~ directory);
    bool[wstring] keys;
    foreach (file; files) {
        try { foreach (key, value; z8_nls_read(file)) keys[key] = true; }
        catch (Exception error) { throw new Exception(file ~ ": " ~ error.msg); }
    }
    MissingResource[] missing;
    foreach (unit; units) {
        auto lexer = new Lexer(unit.source);
        Token previous, beforePrevious;
        while (true) {
            Token token;
            try { token = lexer.next(); }
            catch (LexException error) {
                auto wrapped = new CompileException(error.msg, error.position);
                wrapped.sourceName = unit.path;
                throw wrapped;
            }
            if (token.kind == TokenKind.endOfFile) break;
            bool nativeName = beforePrevious.text == "[" && (previous.text == "native" || previous.text == "primary");
            if (token.kind == TokenKind.stringLiteral && !nativeName) {
                auto value = decodeStringLiteral(token.text);
                if (value.length >= 2 && value[0] == '$' && value[$ - 1] == '$') {
                    auto key = value[1 .. $ - 1];
                    if (key !in keys) missing ~= MissingResource(unit.path, token, key);
                }
            }
            beforePrevious = previous; previous = token;
        }
    }
    return missing;
}
