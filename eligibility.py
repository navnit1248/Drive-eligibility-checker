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

    def _ast(self, company: Company) -> AstNode:
        ast = self._asts.get(company.eligibility_rule)
        if ast is None:
            ast = parse(company.eligibility_rule)
            self._asts[company.eligibility_rule] = ast
        return ast
