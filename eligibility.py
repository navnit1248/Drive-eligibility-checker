"""Eligibility rules and condition-level explanations."""

from __future__ import annotations

from dataclasses import dataclass

from evaluator import EvaluationError, Evaluator
from models import Company, Student
from parser import AstNode, parse


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: tuple[str, ...] = ()


class EligibilityService:
    def __init__(self) -> None:
        self._asts: dict[str, AstNode] = {}

    def evaluate(self, student: Student, company: Company) -> EligibilityResult:
        ast = self._asts.get(company.eligibility_rule)
        if ast is None:
            ast = parse(company.eligibility_rule)
            self._asts[company.eligibility_rule] = ast
        try:
            result = Evaluator(student).evaluate(ast)
        except EvaluationError as exc:
            raise EvaluationError(
                f"Cannot evaluate rule for {company.name}: {exc}"
            ) from exc
        return EligibilityResult(result.passed, result.failures)
