module z8.lexer_test;

import z8.lexer;

version (unittest) void main() {}

private Token[] scan(string source) {
    auto lexer = new Lexer(source);
    Token[] result;
    while (true) {
        auto t = lexer.next();
        result ~= t;
        if (t.kind == TokenKind.endOfFile) return result;
    }
}

private void rejects(string source) {
    bool failed;
    try { scan(source); } catch (LexException) { failed = true; }
    assert(failed, source);
}

unittest {
    auto tokens = scan("import org.test;\r\n\tclass Пример { /* a /* b */ c */ bool x = true; }");
    assert(tokens[0].kind == TokenKind.keyword && tokens[0].text == "import");
    assert(tokens[5].text == "class" && tokens[5].position.line == 1 && tokens[5].position.column == 4);
    assert(tokens[6].kind == TokenKind.identifier && tokens[6].text == "Пример");
    assert(tokens[11].kind == TokenKind.booleanLiteral);
}

unittest {
    auto tokens = scan("return - 0x7f; x-2; .5 2.0e-3 12.");
    assert(tokens[1].kind == TokenKind.integerLiteral && tokens[1].text == "- 0x7f");
    assert(tokens[4].text == "-" && tokens[5].text == "2");
    assert(tokens[7].kind == TokenKind.decimalLiteral && tokens[8].text == "2.0e-3");
    rejects("0x"); rejects("1.2e3"); rejects("9223372036854775808");
}

unittest {
    auto tokens = scan("\"a\\n\\\"b\" '29/02/2024' '2 03:04:05' '00112233-4455-6677-8899-aabbccddeeff' '0, 0xFF'");
    assert(tokens[0].kind == TokenKind.stringLiteral);
    assert(tokens[1].kind == TokenKind.dateLiteral);
    assert(tokens[2].kind == TokenKind.datespanLiteral);
    assert(tokens[3].kind == TokenKind.guidLiteral);
    assert(tokens[4].kind == TokenKind.binaryLiteral);
    rejects("'29/02/2023'"); rejects("'256'"); rejects("'2147483648 00:00:00'"); rejects("\"bad\\q\"");
    rejects("/* unclosed"); rejects("class\0x"); rejects("switch");
}
