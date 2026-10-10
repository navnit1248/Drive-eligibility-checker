"""Tokenizer for the eligibility expression language."""

from __future__ import annotations

from dataclasses import dataclass


class LexerError(ValueError):
    """Raised when an expression contains an invalid token."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    position: int


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
                    escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "\"": "\"", "'": "'"}
                    escaped = source[index]
                    if escaped not in escapes:
                        raise LexerError(f"Unsupported escape sequence \\{escaped} at position {index - 1}.")
                    value.append(escapes[escaped])
                else:
                    value.append(source[index])
                index += 1
            if index >= len(source):
                raise LexerError(f"Unterminated string starting at position {start}.")
            index += 1
            tokens.append(Token("STRING", "".join(value), start))
            continue
        if char.isdigit() or (char == "." and index + 1 < len(source) and source[index + 1].isdigit()):
            start = index
            has_dot = False
            while index < len(source) and (source[index].isdigit() or (source[index] == "." and not has_dot)):
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
