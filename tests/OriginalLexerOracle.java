import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Base64;
import org.zenframework.z8.compiler.core.IPosition;
import org.zenframework.z8.compiler.core.IToken;
import org.zenframework.z8.compiler.parser.grammar.lexer.Lexer;
import org.zenframework.z8.compiler.parser.grammar.lexer.token.*;

/** Read-only adapter for the original, separately supplied Z8 compiler JAR. */
public class OriginalLexerOracle {
    public static void main(String[] args) throws Exception {
        String source = new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8);
        Lexer lexer = new Lexer(source.toCharArray());
        while (true) {
            Token token = lexer.nextToken();
            if (token.getId() == IToken.Eof) break;
            String kind;
            if (token instanceof StringToken) kind = "stringLiteral";
            else if (token instanceof IntegerToken) kind = "integerLiteral";
            else if (token instanceof DecimalToken) kind = "decimalLiteral";
            else if (token instanceof BooleanToken) kind = "booleanLiteral";
            else if (token instanceof DateToken) kind = "dateLiteral";
            else if (token instanceof DatespanToken) kind = "datespanLiteral";
            else if (token instanceof GuidToken) kind = "guidLiteral";
            else if (token instanceof BinaryToken) kind = "binaryLiteral";
            else if (token instanceof KeywordToken) kind = "keyword";
            else if (token instanceof OperatorToken) kind = "symbol";
            else kind = "identifier";
            IPosition p = token.getPosition();
            String raw = source.substring(p.getOffset(), p.getOffset() + p.getLength());
            String encoded = Base64.getEncoder().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
            System.out.printf("%s\t%d\t%d\t%d\t%d\t%s%n", kind, p.getOffset(), p.getLength(), p.getLine(), p.getColumn(), encoded);
        }
    }
}
