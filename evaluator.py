"""Safe AST evaluation against student records."""

from __future__ import annotations

from dataclasses import dataclass

from models import Student
from parser import AstNode, Comparison, Identifier, Literal, Logical, Negation


class EvaluationError(ValueError):
    """Raised for unknown attributes, incompatible values, or invalid ASTs."""


@dataclass(frozen=True)
class Evaluation:
    passed: bool
    failures: tuple[str, ...] = ()


def format_value(value: object) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


class Evaluator:
    def __init__(self, student: Student):
        self.student = student

    def evaluate(self, node: AstNode) -> Evaluation:
        if isinstance(node, Comparison):
            return self._compare(node)
        if isinstance(node, Logical):
            left = self.evaluate(node.left)  # type: ignore[arg-type]
            right = self.evaluate(node.right)  # type: ignore[arg-type]
            if node.operator == "AND":
                failures = left.failures + right.failures
                return Evaluation(left.passed and right.passed, failures)
            if node.operator == "OR":
                if left.passed or right.passed:
                    return Evaluation(True)
                return Evaluation(False, left.failures + right.failures)
            raise EvaluationError(f"Unsupported logical operator {node.operator!r}.")
        if isinstance(node, Negation):
            inner = self.evaluate(node.operand)  # type: ignore[arg-type]
            if inner.passed:
                return Evaluation(False, (f"NOT ({self._describe(node.operand)}) is false.",))
            return Evaluation(True)
        raise EvaluationError(f"Unsupported AST node {type(node).__name__}.")

    def _resolve(self, operand: Literal | Identifier) -> object:
        if isinstance(operand, Literal):
            return operand.value
        fields: dict[str, object] = {
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
    def _compatible(left: object, right: object) -> bool:
        if isinstance(left, bool) or isinstance(right, bool):
            return isinstance(left, bool) and isinstance(right, bool)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return True
        return type(left) is type(right)

    def _compare(self, node: Comparison) -> Evaluation:
        left = self._resolve(node.left)
        right = self._resolve(node.right)
        if not self._compatible(left, right):
            raise EvaluationError(
                f"Cannot compare {type(left).__name__} with {type(right).__name__}."
            )
        operations = {
            "==": lambda: left == right,
            "!=": lambda: left != right,
            ">": lambda: left > right,  # type: ignore[operator]
            ">=": lambda: left >= right,  # type: ignore[operator]
            "<": lambda: left < right,  # type: ignore[operator]
            "<=": lambda: left <= right,  # type: ignore[operator]
        }
        try:
            passed = bool(operations[node.operator]())
        except (TypeError, KeyError) as exc:
            raise EvaluationError(f"Cannot apply {node.operator!r} to these values.") from exc
        if passed:
            return Evaluation(True)
        return Evaluation(False, (self._failure_text(node, left, right),))

    def _failure_text(self, node: Comparison, actual: object, expected: object) -> str:
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
                f"{node.left.name} is {format_value(actual)}; condition requires "
                f"{node.left.name} {node.operator} {format_value(expected)}."
            )
        return (
            f"{format_value(actual)} {node.operator} {format_value(expected)} "
            "condition failed."
        )

    def _describe(self, node: object) -> str:
        if isinstance(node, Comparison):
            return (
                f"{self._describe_operand(node.left)} {node.operator} "
                f"{self._describe_operand(node.right)}"
            )
        if isinstance(node, Negation):
            return f"NOT ({self._describe(node.operand)})"
        if isinstance(node, Logical):
            return f"({self._describe(node.left)} {node.operator} {self._describe(node.right)})"
        return str(node)

    @staticmethod
    def _describe_operand(operand: Literal | Identifier) -> str:
        if isinstance(operand, Identifier):
            return operand.name
        return format_value(operand.value)
