"""Lexer, recursive-descent parser, AST evaluator, and eligibility service."""

from __future__ import annotations

from dataclasses import dataclass

from models import Company, Student


class ParseError(ValueError):
    """Invalid token or expression syntax."""


class LexerError(ParseError):
    """Invalid token in an expression."""


class EvaluationError(ValueError):
    """Unknown student fields or incompatible comparison values."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    position: int


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


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if char in "()":
            tokens.append(Token(char, char, index))
            index += 1
            continue
        if char in "<>!=":
            start = index
            index += 1
            if index < len(source) and source[index] == "=":
                index += 1
            operator = source[start:index]
            if operator not in {">", ">=", "<", "<=", "==", "!="}:
                raise LexerError(f"Unexpected operator {operator!r} at position {start}.")
            tokens.append(Token("OP", operator, start))
            continue
        if char in "\"'":
            quote = char
            start = index
            index += 1
            value: list[str] = []
            while index < len(source) and source[index] != quote:
                if source[index] == "\\":
                    index += 1
                    if index >= len(source):
                        raise LexerError(f"Unterminated escape sequence at position {start}.")
                    escapes = {
                        "n": "\n",
                        "r": "\r",
                        "t": "\t",
                        "\\": "\\",
                        "\"": "\"",
                        "'": "'",
                    }
                    escaped = source[index]
                    if escaped not in escapes:
                        raise LexerError(
                            f"Unsupported escape sequence \\{escaped} at position {index - 1}."
                        )
                    value.append(escapes[escaped])
                else:
                    value.append(source[index])
                index += 1
            if index >= len(source):
                raise LexerError(f"Unterminated string starting at position {start}.")
            index += 1
            tokens.append(Token("STRING", "".join(value), start))
            continue
        if char.isdigit() or (
            char == "." and index + 1 < len(source) and source[index + 1].isdigit()
        ):
            start = index
            has_dot = False
            while index < len(source) and (
                source[index].isdigit() or (source[index] == "." and not has_dot)
            ):
                if source[index] == ".":
                    has_dot = True
                index += 1
            raw = source[start:index]
            try:
                value = float(raw) if has_dot else int(raw)
            except ValueError as exc:
                raise LexerError(f"Invalid number {raw!r} at position {start}.") from exc
            tokens.append(Token("NUMBER", value, start))
            continue
        if char.isalpha() or char == "_":
            start = index
            index += 1
            while index < len(source) and (source[index].isalnum() or source[index] == "_"):
                index += 1
            word = source[start:index]
            upper = word.upper()
            if upper in {"AND", "OR", "NOT"}:
                tokens.append(Token(upper, upper, start))
            elif upper in {"TRUE", "FALSE"}:
                tokens.append(Token("BOOLEAN", upper == "TRUE", start))
            else:
                tokens.append(Token("IDENTIFIER", word, start))
            continue
        raise LexerError(f"Unexpected character {char!r} at position {index}.")
    tokens.append(Token("EOF", None, len(source)))
    return tokens


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
        node = self.parse_or()
        if self.current.kind != "EOF":
            raise ParseError(
                f"Unexpected token {self.current.value!r} at position {self.current.position}."
            )
        return node

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
        return Comparison(left, str(operator.value), self.parse_operand())

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
    return Parser(tokenize(source)).parse()


@dataclass(frozen=True)
class Evaluation:
    passed: bool
    failures: tuple[str, ...] = ()


def _format_value(value: object) -> str:
    return f'"{value}"' if isinstance(value, str) else str(value)


class Evaluator:
    def __init__(self, student: Student):
        self.student = student

    def evaluate(self, node: AstNode) -> Evaluation:
        if self._passes(node):
            return Evaluation(True)
        failures: list[str] = []
        self._collect_failures(node, failures)
        return Evaluation(False, tuple(failures))

    def is_eligible(self, node: AstNode) -> bool:
        return self._passes(node)

    def _passes(self, node: AstNode) -> bool:
        if isinstance(node, Comparison):
            return self._compare(self._resolve(node.left), node.operator, self._resolve(node.right))
        if isinstance(node, Logical):
            if node.operator == "AND":
                return self._passes(node.left) and self._passes(node.right)  # type: ignore[arg-type]
            if node.operator == "OR":
                return self._passes(node.left) or self._passes(node.right)  # type: ignore[arg-type]
            raise EvaluationError(f"Unsupported logical operator {node.operator!r}.")
        if isinstance(node, Negation):
            return not self._passes(node.operand)  # type: ignore[arg-type]
        raise EvaluationError(f"Unsupported AST node {type(node).__name__}.")

    def _collect_failures(self, node: AstNode, failures: list[str]) -> None:
        if isinstance(node, Comparison):
            left = self._resolve(node.left)
            right = self._resolve(node.right)
            if not self._compare(left, node.operator, right):
                failures.append(self._failure_text(node, left, right))
        elif isinstance(node, Logical):
            if node.operator == "AND":
                self._collect_failures(node.left, failures)  # type: ignore[arg-type]
                self._collect_failures(node.right, failures)  # type: ignore[arg-type]
            elif node.operator == "OR" and not (
                self._passes(node.left) or self._passes(node.right)  # type: ignore[arg-type]
            ):
                self._collect_failures(node.left, failures)  # type: ignore[arg-type]
                self._collect_failures(node.right, failures)  # type: ignore[arg-type]
            elif node.operator != "OR":
                raise EvaluationError(f"Unsupported logical operator {node.operator!r}.")
        elif isinstance(node, Negation) and self._passes(node.operand):  # type: ignore[arg-type]
            failures.append(f"NOT ({self._describe(node.operand)}) is false.")

    def _resolve(self, operand: Literal | Identifier) -> object:
        if isinstance(operand, Literal):
            return operand.value
        fields = {
            "cgpa": self.student.cgpa,
            "arrears": self.student.arrears,
            "department": self.student.department,
            "student_id": self.student.student_id,
        }
        try:
            return fields[operand.name.casefold()]
        except KeyError as exc:
            raise EvaluationError(f"Unknown student field {operand.name!r}.") from exc

    @staticmethod
    def _compare(left: object, operator: str, right: object) -> bool:
        if isinstance(left, bool) or isinstance(right, bool):
            compatible = isinstance(left, bool) and isinstance(right, bool)
        elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
            compatible = True
        else:
            compatible = type(left) is type(right)
        if not compatible:
            raise EvaluationError(
                f"Cannot compare {type(left).__name__} with {type(right).__name__}."
            )
        try:
            if operator == "==":
                return left == right
            if operator == "!=":
                return left != right
            if operator == ">":
                return left > right  # type: ignore[operator]
            if operator == ">=":
                return left >= right  # type: ignore[operator]
            if operator == "<":
                return left < right  # type: ignore[operator]
            if operator == "<=":
                return left <= right  # type: ignore[operator]
        except TypeError as exc:
            raise EvaluationError(f"Cannot apply {operator!r} to these values.") from exc
        raise EvaluationError(f"Unsupported comparison operator {operator!r}.")

    @staticmethod
    def _failure_text(node: Comparison, actual: object, expected: object) -> str:
        if isinstance(node.left, Identifier):
            field_name = node.left.name.casefold()
            if field_name == "cgpa" and node.operator in {">", ">="}:
                return f"CGPA is {actual}; minimum required is {expected}."
            if field_name == "arrears" and node.operator in {"<", "<="}:
                return f"Arrears are {actual}; maximum permitted is {expected}."
            if field_name == "arrears" and node.operator == "==":
                return f"Arrears are {actual}; required value is {expected}."
            if field_name == "department" and node.operator == "==":
                return f"Department is {actual}; required department is {expected}."
            return (
                f"{node.left.name} is {_format_value(actual)}; condition requires "
                f"{node.left.name} {node.operator} {_format_value(expected)}."
            )
        return f"{_format_value(actual)} {node.operator} {_format_value(expected)} condition failed."

    @staticmethod
    def _describe(node: object) -> str:
        if isinstance(node, Comparison):
            left = node.left.name if isinstance(node.left, Identifier) else _format_value(node.left.value)
            right = node.right.name if isinstance(node.right, Identifier) else _format_value(node.right.value)
            return f"{left} {node.operator} {right}"
        if isinstance(node, Negation):
            return f"NOT ({Evaluator._describe(node.operand)})"
        if isinstance(node, Logical):
            return f"({Evaluator._describe(node.left)} {node.operator} {Evaluator._describe(node.right)})"
        return str(node)


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: tuple[str, ...] = ()


class EligibilityService:
    def __init__(self) -> None:
        self._asts: dict[str, AstNode] = {}

    def _ast(self, company: Company) -> AstNode:
        if company.eligibility_rule not in self._asts:
            self._asts[company.eligibility_rule] = parse(company.eligibility_rule)
        return self._asts[company.eligibility_rule]

    def evaluate(self, student: Student, company: Company) -> EligibilityResult:
        try:
            result = Evaluator(student).evaluate(self._ast(company))
        except EvaluationError as exc:
            raise EvaluationError(f"Cannot evaluate rule for {company.name}: {exc}") from exc
        return EligibilityResult(result.passed, result.failures)

    def is_eligible(self, student: Student, company: Company) -> bool:
        try:
            return Evaluator(student).is_eligible(self._ast(company))
        except EvaluationError as exc:
            raise EvaluationError(f"Cannot evaluate rule for {company.name}: {exc}") from exc
