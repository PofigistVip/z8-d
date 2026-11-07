module z8.lexer;

import std.algorithm : canFind;
import std.conv : to;
import std.format : format;
import std.regex : matchFirst, regex;
import std.string : strip, replace;
import std.uni : unicode;

enum TokenKind { identifier, keyword, booleanLiteral, integerLiteral, decimalLiteral,
                 stringLiteral, dateLiteral, datespanLiteral, guidLiteral, binaryLiteral,
                 symbol, endOfFile }

/// Offsets and columns count UTF-16 code units, as in the original Java compiler.
/// Lines and columns are zero-based; a tab advances the column by four.
struct Position { size_t offset, line, column, length; }
struct Token { TokenKind kind; string text; Position position; }

class LexException : Exception {
    Position position;
    this(string message, Position position) { super(message); this.position = position; }
}

// Decode a validated BL string token into Java-compatible UTF-16 code units.
package wstring decodeStringLiteral(string text) {
    auto raw = text.to!wstring;
    wchar[] value;
    for (size_t i = 1; i + 1 < raw.length; ++i) {
        wchar c = raw[i];
        if (c == '\\') {
            c = raw[++i];
            switch (c) {
                case 'b': c = '\b'; break; case 'f': c = '\f'; break;
                case 'n': c = '\n'; break; case 'r': c = '\r'; break; case 't': c = '\t'; break;
                default: break;
            }
            value ~= c;
        } else if (c >= ' ' || c == '\t' || c == '\r' || c == '\n') value ~= c;
    }
    return value.idup;
}

private enum keywords = ["operator", "do", "for", "while", "if", "else", "break",
    "continue", "return", "this", "super", "container", "null", "import", "class",
    "public", "protected", "private", "extends", "enum", "records", "auto", "new",
    "static", "try", "catch", "finally", "throw", "virtual", "final", "instanceof"];
private enum reserved = ["boolean", "byte", "case", "char", "const", "default", "double",
    "float", "goto", "implements", "interface", "long", "package", "short", "strictfp",
    "switch", "synchronized", "throws", "transient", "volatile"];

private bool digit(wchar c) { return c >= '0' && c <= '9'; }
private bool hexDigit(wchar c) { return digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'); }
private bool space(wchar c) { return c == ' ' || c == '\t'; }
private bool newline(wchar c) { return c == '\r' || c == '\n'; }
// Java accepts currency and format characters as identifier parts as well;
// the D emitter encodes names containing these characters.
private bool identifierChar(wchar c) {
    return c != '$' && (c == '_' || (c in unicode.L) || (c in unicode.Nl) || (c in unicode.Nd) ||
        (c in unicode.Mn) || (c in unicode.Mc) || (c in unicode.Pc) ||
        (c in unicode.Sc) || (c in unicode.Cf) || (c >= 0x7F && c <= 0x9F));
}

class Lexer {
    private wstring input;
    private size_t offset, line, column;
    private TokenKind previous = TokenKind.endOfFile;

    this(string source) { input = source.to!wstring; }
    private wchar peek(size_t n = 0) { return offset + n < input.length ? input[offset + n] : '\0'; }
    private Position here() { return Position(offset, line, column, 0); }
    private void advance() {
        if (offset >= input.length) return;
        auto c = input[offset++];
        if (c == '\r') { if (peek() == '\n') ++offset; ++line; column = 0; }
        else if (c == '\n') { ++line; column = 0; }
        else column += c == '\t' ? 4 : 1;
    }
    private Token finish(TokenKind kind, Position start) {
        start.length = offset - start.offset;
        auto result = Token(kind, input[start.offset .. offset].to!string, start);
        previous = kind;
        return result;
    }
    private void fail(string message, Position start) {
        start.length = offset - start.offset;
        throw new LexException(message, start);
    }
    private void trivia() {
        while (true) {
            while (space(peek()) || newline(peek())) advance();
            if (peek() != '/') return;
            if (peek(1) == '/') {
                advance(); advance();
                while (peek() != '\0' && !newline(peek())) advance();
            } else if (peek(1) == '*') {
                auto start = here(); advance(); advance(); size_t depth = 1;
                while (depth && peek() != '\0') {
                    if (peek() == '/' && peek(1) == '*') { advance(); advance(); ++depth; }
                    else if (peek() == '*' && peek(1) == '/') { advance(); advance(); --depth; }
                    else advance();
                }
                if (depth) fail("end of comment not found", start);
            } else return;
        }
    }
    private bool signedNumber() {
        if ((peek() != '+' && peek() != '-') ||
            (previous != TokenKind.endOfFile && previous != TokenKind.keyword)) return false;
        size_t n = 1;
        while (space(peek(n))) ++n;
        return digit(peek(n)) || peek(n) == '.';
    }
    private Token number(Position start) {
        if (peek() == '+' || peek() == '-') { advance(); while (space(peek())) advance(); }
        if (peek() == '0' && (peek(1) == 'x' || peek(1) == 'X')) {
            advance(); advance();
            if (!hexDigit(peek())) fail("expected hexadecimal digit", start);
            while (hexDigit(peek())) advance();
            auto spelling = input[start.offset .. offset].to!string.replace(" ", "").replace("\t", "");
            auto prefix = spelling[0] == '+' || spelling[0] == '-' ? 1 : 0;
            try {
                auto magnitude = spelling[prefix + 2 .. $].to!ulong(16);
                auto limit = cast(ulong)long.max + (spelling[0] == '-' ? 1UL : 0UL);
                if (magnitude > limit) fail("integer out of range", start);
            }
            catch (Exception) { fail("integer out of range", start); }
            return finish(TokenKind.integerLiteral, start);
        }
        bool hasIntegerDigits = digit(peek());
        while (digit(peek())) advance();
        if (peek() != '.') {
            try { auto ignored = input[start.offset .. offset].to!string.replace(" ", "").replace("\t", "").to!long; }
            catch (Exception) { fail("integer out of range", start); }
            return finish(TokenKind.integerLiteral, start);
        }
        advance();
        if (!hasIntegerDigits && !digit(peek()))
            fail("expected decimal digit", start);
        while (digit(peek())) advance();
        if (peek() == 'e' || peek() == 'E') {
            advance();
            if (peek() != '+' && peek() != '-') fail("expected exponent sign ('+' or '-')", start);
            advance();
            if (!digit(peek())) fail("expected decimal digit", start);
            while (digit(peek())) advance();
        }
        return finish(TokenKind.decimalLiteral, start);
    }
    private Token special(Position start) {
        advance();
        while (peek() != '\0' && peek() != '\'') advance();
        if (peek() == '\0') fail("end of special constant not found", start);
        advance();
        auto value = input[start.offset + 1 .. offset - 1].to!string;
        if (matchFirst(value, regex(`^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$`)))
            return finish(TokenKind.guidLiteral, start);
        auto date = matchFirst(value, regex(`^\s*([0-9]{1,2})/([0-9]{1,2})/([0-9]{1,4})(?:\s+([0-9]{1,2}):([0-9]{1,2}):([0-9]{1,2}))?\s*$`));
        if (!date.empty) {
            auto day = date[1].to!int, month = date[2].to!int, year = date[3].to!int;
            int[] days = [0,31,28,31,30,31,30,31,31,30,31,30,31];
            if (year % 4 == 0 && (year <= 1582 || year % 100 != 0 || year % 400 == 0)) days[2] = 29;
            if (year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month] &&
                (date[4].length == 0 || (date[4].to!int < 24 && date[5].to!int < 60 && date[6].to!int < 60)))
                return finish(TokenKind.dateLiteral, start);
        }
        auto span = matchFirst(value, regex(`^\s*([0-9]+)\s+([0-9]{1,2}):([0-9]{1,2}):([0-9]{1,2})\s*$`));
        if (!span.empty && span[2].to!int < 24 && span[3].to!int < 60 && span[4].to!int < 60) {
            try { auto days = span[1].to!int; }
            catch (Exception) { fail("datespan days out of range", start); }
            return finish(TokenKind.datespanLiteral, start);
        }
        auto time = matchFirst(value, regex(`^\s*([0-9]{1,2}):([0-9]{1,2}):([0-9]{1,2})\s*$`));
        if (!time.empty && time[1].to!int < 24 && time[2].to!int < 60 && time[3].to!int < 60)
            return finish(TokenKind.dateLiteral, start);
        if (matchFirst(value, regex(`^\s*(?:0[xX][0-9a-fA-F]+|[0-9]+)(?:\s*,\s*(?:0[xX][0-9a-fA-F]+|[0-9]+))*\s*$`))) {
            import std.string : split;
            bool valid = true;
            foreach (part; value.split(',')) {
                auto v = part.strip;
                try { if ((v.length > 2 && (v[0..2] == "0x" || v[0..2] == "0X") ? v[2..$].to!uint(16) : v.to!uint) > 255) valid = false; }
                catch (Exception) { valid = false; }
            }
            if (valid) return finish(TokenKind.binaryLiteral, start);
        }
        fail("bad special constant format", start);
        assert(0);
    }
    Token next() {
        trivia();
        auto start = here(); auto c = peek();
        if (offset == input.length) return finish(TokenKind.endOfFile, start);
        if (c == '\0') { advance(); fail("not allowed character found", start); }
        if (digit(c) || (c == '.' && digit(peek(1))) || signedNumber()) return number(start);
        if (identifierChar(c) && !digit(c)) {
            do advance(); while (identifierChar(peek()));
            auto word = input[start.offset .. offset].to!string;
            if (reserved.canFind(word)) fail("token '" ~ word ~ "' is reserved and cannot be used", start);
            return finish(word == "true" || word == "false" ? TokenKind.booleanLiteral :
                keywords.canFind(word) ? TokenKind.keyword : TokenKind.identifier, start);
        }
        if (c == '"') {
            advance();
            while (peek() != '\0' && peek() != '"') {
                if (peek() == '\\') {
                    advance();
                    if (!"bfnrt\"\\'".canFind(cast(char)peek())) fail("bad escape sequence", start);
                }
                advance();
            }
            if (peek() == '\0') fail("end of string not found", start);
            advance(); return finish(TokenKind.stringLiteral, start);
        }
        if (c == '\'') return special(start);
        if ("~&|^()%*/+-,.;?[]{}!=<>:".canFind(cast(char)c) && c < 128) {
            auto pair = input[offset .. offset + (peek(1) == '\0' ? 1 : 2)].to!string;
            advance();
            if (["!=", "==", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "&&", "||", "?:"].canFind(pair)) advance();
            return finish(TokenKind.symbol, start);
        }
        advance(); fail("not allowed character found", start); assert(0);
    }
}
