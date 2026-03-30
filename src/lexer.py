"""
AXON Compiler - Lexer
Converts raw AXON source text into a token stream.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    # Structure keywords
    GRAPH       = auto()
    NODE        = auto()
    IN          = auto()
    OUT         = auto()
    RETURN      = auto()
    ROLLBACK    = auto()
    ON          = auto()
    FAULT       = auto()
    BUDGET      = auto()
    TYPES       = auto()

    # Node clause keywords
    OP          = auto()
    INVERSE     = auto()
    ASYNC       = auto()
    AFTER       = auto()

    # Operation keywords
    DB_READ     = auto()
    DB_WRITE    = auto()
    DB_DELETE   = auto()
    WHERE       = auto()
    ASSERT      = auto()
    SUM         = auto()
    AVG         = auto()
    COUNT       = auto()
    MAP         = auto()
    FILTER      = auto()
    EMAIL_SEND  = auto()
    HTTP_GET    = auto()
    HTTP_POST   = auto()
    HTTP_PUT    = auto()
    HTTP_DELETE = auto()
    MCP         = auto()

    # Fault actions
    HALT        = auto()
    RETRY       = auto()
    FALLBACK    = auto()

    # Literals
    IDENTIFIER  = auto()
    STRING      = auto()
    INTEGER     = auto()
    FLOAT       = auto()
    BOOLEAN     = auto()
    DURATION    = auto()

    # Operators & Punctuation
    ARROW       = auto()   # ->
    EQUALS      = auto()   # =
    EQEQ        = auto()   # ==
    NEQ         = auto()   # !=
    LT          = auto()   # <
    GT          = auto()   # >
    LTE         = auto()   # <=
    GTE         = auto()   # >=
    LBRACKET    = auto()   # [
    RBRACKET    = auto()   # ]
    LBRACE      = auto()   # {
    RBRACE      = auto()   # }
    LPAREN      = auto()   # (
    RPAREN      = auto()   # )
    COMMA       = auto()   # ,
    DOT         = auto()   # .
    COLON       = auto()   # :
    STAR        = auto()   # *
    PLUS        = auto()   # +
    MINUS       = auto()   # -
    SLASH       = auto()   # /

    # Special
    NULL        = auto()
    EOF         = auto()
    NEWLINE     = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.col})"


KEYWORDS = {
    "GRAPH":    TokenType.GRAPH,
    "NODE":     TokenType.NODE,
    "IN":       TokenType.IN,
    "OUT":      TokenType.OUT,
    "RETURN":   TokenType.RETURN,
    "ROLLBACK": TokenType.ROLLBACK,
    "ON":       TokenType.ON,
    "FAULT":    TokenType.FAULT,
    "BUDGET":   TokenType.BUDGET,
    "TYPES":    TokenType.TYPES,
    "OP":       TokenType.OP,
    "INVERSE":  TokenType.INVERSE,
    "ASYNC":    TokenType.ASYNC,
    "AFTER":    TokenType.AFTER,
    "WHERE":    TokenType.WHERE,
    "ASSERT":   TokenType.ASSERT,
    "SUM":      TokenType.SUM,
    "AVG":      TokenType.AVG,
    "COUNT":    TokenType.COUNT,
    "MAP":      TokenType.MAP,
    "FILTER":   TokenType.FILTER,
    "HALT":     TokenType.HALT,
    "RETRY":    TokenType.RETRY,
    "FALLBACK": TokenType.FALLBACK,
    "null":     TokenType.NULL,
    "true":     TokenType.BOOLEAN,
    "false":    TokenType.BOOLEAN,
}

COMPOUND_KEYWORDS = {
    "db.read":    TokenType.DB_READ,
    "db.write":   TokenType.DB_WRITE,
    "db.delete":  TokenType.DB_DELETE,
    "email.send": TokenType.EMAIL_SEND,
    "http.get":   TokenType.HTTP_GET,
    "http.post":  TokenType.HTTP_POST,
    "http.put":   TokenType.HTTP_PUT,
    "http.delete":TokenType.HTTP_DELETE,
}


class LexerError(Exception):
    def __init__(self, msg, line, col):
        super().__init__(f"LexerError at L{line}:C{col} — {msg}")
        self.line = line
        self.col = col


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def error(self, msg):
        raise LexerError(msg, self.line, self.col)

    def peek(self, offset=0) -> str:
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ""

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match(self, expected: str) -> bool:
        if self.source[self.pos:self.pos+len(expected)] == expected:
            for _ in expected:
                self.advance()
            return True
        return False

    def skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.peek()
            if ch in " \t\r":
                self.advance()
            elif ch == "#" or (ch == "-" and self.peek(1) == "-"):
                # Comment to end of line
                while self.pos < len(self.source) and self.peek() != "\n":
                    self.advance()
            else:
                break

    def read_string(self) -> Token:
        line, col = self.line, self.col
        self.advance()  # consume opening "
        buf = []
        while self.pos < len(self.source) and self.peek() != '"':
            buf.append(self.advance())
        if self.pos >= len(self.source):
            self.error("Unterminated string literal")
        self.advance()  # consume closing "
        return Token(TokenType.STRING, "".join(buf), line, col)

    def read_number(self) -> Token:
        line, col = self.line, self.col
        buf = []
        is_float = False
        while self.peek().isdigit():
            buf.append(self.advance())
        if self.peek() == "." and self.peek(1).isdigit():
            is_float = True
            buf.append(self.advance())
            while self.peek().isdigit():
                buf.append(self.advance())
        # Check for duration suffix
        duration_suffixes = ["ms", "s", "m"]
        for suffix in duration_suffixes:
            if self.source[self.pos:self.pos+len(suffix)] == suffix:
                for _ in suffix:
                    buf.append(self.advance())
                return Token(TokenType.DURATION, "".join(buf), line, col)
        tok_type = TokenType.FLOAT if is_float else TokenType.INTEGER
        return Token(tok_type, "".join(buf), line, col)

    def read_identifier_or_keyword(self) -> Token:
        line, col = self.line, self.col
        buf = []
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() in "_"):
            buf.append(self.advance())
        word = "".join(buf)

        # Check for compound keywords like db.read, email.send
        if self.peek() == ".":
            saved_pos = self.pos
            saved_line = self.line
            saved_col = self.col
            dot = self.advance()
            suffix_buf = []
            while self.peek().isalnum() or self.peek() == "_":
                suffix_buf.append(self.advance())
            compound = word + "." + "".join(suffix_buf)
            if compound in COMPOUND_KEYWORDS:
                return Token(COMPOUND_KEYWORDS[compound], compound, line, col)
            # Not a compound keyword — restore and emit just the word + dot separately
            self.pos = saved_pos
            self.line = saved_line
            self.col = saved_col

        if word in KEYWORDS:
            return Token(KEYWORDS[word], word, line, col)

        return Token(TokenType.IDENTIFIER, word, line, col)

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            ch = self.peek()
            line, col = self.line, self.col

            if ch == "\n":
                self.advance()
                self.tokens.append(Token(TokenType.NEWLINE, "\\n", line, col))

            elif ch == '"':
                self.tokens.append(self.read_string())

            elif ch.isdigit():
                self.tokens.append(self.read_number())

            elif ch.isalpha() or ch == "_":
                self.tokens.append(self.read_identifier_or_keyword())

            elif ch == "-" and self.peek(1) == ">":
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.ARROW, "->", line, col))

            elif ch == "=" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.EQEQ, "==", line, col))

            elif ch == "!" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.NEQ, "!=", line, col))

            elif ch == "<" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.LTE, "<=", line, col))

            elif ch == ">" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.GTE, ">=", line, col))

            elif ch == "=":
                self.advance()
                self.tokens.append(Token(TokenType.EQUALS, "=", line, col))

            elif ch == "<":
                self.advance()
                self.tokens.append(Token(TokenType.LT, "<", line, col))

            elif ch == ">":
                self.advance()
                self.tokens.append(Token(TokenType.GT, ">", line, col))

            elif ch == "[":
                self.advance()
                self.tokens.append(Token(TokenType.LBRACKET, "[", line, col))

            elif ch == "]":
                self.advance()
                self.tokens.append(Token(TokenType.RBRACKET, "]", line, col))

            elif ch == "{":
                self.advance()
                self.tokens.append(Token(TokenType.LBRACE, "{", line, col))

            elif ch == "}":
                self.advance()
                self.tokens.append(Token(TokenType.RBRACE, "}", line, col))

            elif ch == "(":
                self.advance()
                self.tokens.append(Token(TokenType.LPAREN, "(", line, col))

            elif ch == ")":
                self.advance()
                self.tokens.append(Token(TokenType.RPAREN, ")", line, col))

            elif ch == ",":
                self.advance()
                self.tokens.append(Token(TokenType.COMMA, ",", line, col))

            elif ch == ".":
                self.advance()
                self.tokens.append(Token(TokenType.DOT, ".", line, col))

            elif ch == ":":
                self.advance()
                self.tokens.append(Token(TokenType.COLON, ":", line, col))

            elif ch == "*":
                self.advance()
                self.tokens.append(Token(TokenType.STAR, "*", line, col))

            elif ch == "+":
                self.advance()
                self.tokens.append(Token(TokenType.PLUS, "+", line, col))

            elif ch == "/":
                self.advance()
                self.tokens.append(Token(TokenType.SLASH, "/", line, col))

            else:
                self.error(f"Unexpected character: {ch!r}")

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens
