"""Recursive-descent parser and AST definitions."""

from __future__ import annotations

from dataclasses import dataclass

from lexer import LexerError, Token, tokenize


class ParseError(ValueError):
    """Raised when an eligibility expression does not match the grammar."""


@dataclass(frozen=True)
class Literal:
    value: object


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class Comparison:
    left: Literal | Identifier
    operator: str
    right: Literal | Identifier


@dataclass(frozen=True)
class Logical:
    operator: str
    left: object
    right: object


@dataclass(frozen=True)
class Negation:
    operand: object


AstNode = Comparison | Logical | Negation


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        if token.kind != "EOF":
            self.index += 1
        return token

    def expect(self, kind: str, expectation: str) -> Token:
        if self.current.kind != kind:
            raise ParseError(
                f"Expected {expectation} at position {self.current.position}; "
                f"found {self.current.value!r}."
            )
        return self.advance()

    def parse(self) -> AstNode:
        expression = self.parse_or()
        if self.current.kind != "EOF":
            raise ParseError(
                f"Unexpected token {self.current.value!r} at position {self.current.position}."
            )
        return expression

    def parse_or(self) -> AstNode:
        node = self.parse_and()
        while self.current.kind == "OR":
            self.advance()
            node = Logical("OR", node, self.parse_and())
        return node

    def parse_and(self) -> AstNode:
        node = self.parse_not()
        while self.current.kind == "AND":
            self.advance()
            node = Logical("AND", node, self.parse_not())
        return node

    def parse_not(self) -> AstNode:
        if self.current.kind == "NOT":
            self.advance()
            return Negation(self.parse_not())
        if self.current.kind == "(":
            self.advance()
            node = self.parse_or()
            self.expect(")", "')'")
            return node
        return self.parse_comparison()

    def parse_comparison(self) -> Comparison:
        left = self.parse_operand()
        operator = self.expect("OP", "a comparison operator")
        right = self.parse_operand()
        return Comparison(left, str(operator.value), right)

    def parse_operand(self) -> Literal | Identifier:
        token = self.current
        if token.kind == "IDENTIFIER":
            self.advance()
            return Identifier(str(token.value))
        if token.kind in {"NUMBER", "STRING", "BOOLEAN"}:
            self.advance()
            return Literal(token.value)
        raise ParseError(
            f"Expected an identifier or literal at position {token.position}; "
            f"found {token.value!r}."
        )


def parse(source: str) -> AstNode:
    try:
        return Parser(tokenize(source)).parse()
    except LexerError as exc:
        raise ParseError(str(exc)) from exc
