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
        if self._passes(node):
            return Evaluation(True)
        failures: list[str] = []
        self._collect_failures(node, failures)
        return Evaluation(False, tuple(failures))

    def is_eligible(self, node: AstNode) -> bool:
        return self._passes(node)

    def _passes(self, node: AstNode) -> bool:
        if isinstance(node, Comparison):
            return self._compare(node)
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
            if not self._compare_values(left, node.operator, right):
                failures.append(self._failure_text(node, left, right))
            return
        if isinstance(node, Logical):
            if node.operator == "AND":
                self._collect_failures(node.left, failures)  # type: ignore[arg-type]
                self._collect_failures(node.right, failures)  # type: ignore[arg-type]
            elif node.operator == "OR":
                if not self._passes(node.left) and not self._passes(node.right):  # type: ignore[arg-type]
                    left_failures: list[str] = []
                    self._collect_failures(node.left, left_failures)  # type: ignore[arg-type]
                    right_failures: list[str] = []
                    self._collect_failures(node.right, right_failures)  # type: ignore[arg-type]
                    failures.extend(left_failures)
                    failures.extend(right_failures)
            else:
                raise EvaluationError(f"Unsupported logical operator {node.operator!r}.")
            return
        if isinstance(node, Negation):
            if self._passes(node.operand):  # type: ignore[arg-type]
                failures.append(f"NOT ({self._describe(node.operand)}) is false.")
            return
        raise EvaluationError(f"Unsupported AST node {type(node).__name__}.")

    def _resolve(self, operand: Literal | Identifier) -> object:
        if isinstance(operand, Literal):
            return operand.value
        name = operand.name.casefold()
        if name == "cgpa":
            return self.student.cgpa
        if name == "arrears":
            return self.student.arrears
        if name == "department":
            return self.student.department
        if name == "student_id":
            return self.student.student_id
        raise EvaluationError(f"Unknown student field {operand.name!r}.")

    @staticmethod
    def _compatible(left: object, right: object) -> bool:
        if isinstance(left, bool) or isinstance(right, bool):
            return isinstance(left, bool) and isinstance(right, bool)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return True
        return type(left) is type(right)

    def _compare(self, node: Comparison) -> bool:
        return self._compare_values(
            self._resolve(node.left), node.operator, self._resolve(node.right)
        )

    @classmethod
    def _compare_values(cls, left: object, operator: str, right: object) -> bool:
        if not cls._compatible(left, right):
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
                f"{node.left.name} is {format_value(actual)}; condition requires "
                f"{node.left.name} {node.operator} {format_value(expected)}."
            )
        return (
            f"{format_value(actual)} {node.operator} {format_value(expected)} "
            "condition failed."
        )

    @staticmethod
    def _describe(node: object) -> str:
        if isinstance(node, Comparison):
            return (
                f"{Evaluator._describe_operand(node.left)} {node.operator} "
                f"{Evaluator._describe_operand(node.right)}"
            )
        if isinstance(node, Negation):
            return f"NOT ({Evaluator._describe(node.operand)})"
        if isinstance(node, Logical):
            return f"({Evaluator._describe(node.left)} {node.operator} {Evaluator._describe(node.right)})"
        return str(node)

    @staticmethod
    def _describe_operand(operand: Literal | Identifier) -> str:
        if isinstance(operand, Identifier):
            return operand.name
        return format_value(operand.value)
