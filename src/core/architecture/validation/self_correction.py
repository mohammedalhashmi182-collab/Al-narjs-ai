"""Real-time LLM output validation and a bounded self-correction loop.

The validator checks model output against optional structural constraints
(JSON shape / Pydantic response model / minimum length). The self-correction
loop re-invokes the dynamic router with the collected validation errors as
feedback, up to a hard limit, and always returns the best available result —
the orchestrator layer never blocks or raises on imperfect model output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationLevel(str, Enum):
    LENIENT = "lenient"
    STRICT = "strict"


@dataclass
class ValidationOutcome:
    """Result of validating one model response."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    parsed: Any = None


class OutputValidator:
    """Pure, dependency-free response validator."""

    def __init__(
        self,
        min_length: int = 1,
        require_json: bool = False,
    ) -> None:
        self.min_length = min_length
        self.require_json = require_json

    def validate(
        self,
        content: str,
        response_model: Optional[Any] = None,
    ) -> ValidationOutcome:
        """Validate ``content``; optional Pydantic model enforces the schema."""
        errors: List[str] = []
        warnings: List[str] = []
        parsed: Any = None

        text = str(content or "")
        if len(text.strip()) < self.min_length:
            errors.append(
                f"output shorter than min_length={self.min_length}"
            )
            return ValidationOutcome(valid=False, errors=errors, warnings=warnings)

        if response_model is not None:
            parsed, schema_errors = self._parse_against_model(text, response_model)
            if schema_errors:
                errors.extend(schema_errors)
        elif self.require_json:
            import json

            try:
                parsed = json.loads(text)
            except ValueError as e:
                errors.append(f"invalid_json: {e}")

        return ValidationOutcome(
            valid=not errors, errors=errors, warnings=warnings, parsed=parsed
        )

    def _parse_against_model(
        self, text: str, response_model: Any
    ) -> Tuple[Any, List[str]]:
        """Try the strictest parse first, then a plain ``json.loads``."""
        try:
            return response_model.model_validate_json(text), []
        except Exception:
            pass
        import json

        try:
            return response_model.model_validate(json.loads(text)), []
        except Exception as e2:
            return None, [f"schema_parse_failed: {e2}"]

    def feedback_prompt(self, original_task: str, outcome: ValidationOutcome) -> str:
        """Append validation feedback so the next attempt can self-correct."""
        if not outcome.errors:
            return original_task
        return (
            f"{original_task}\n\n"
            "Your previous answer was rejected for the following reasons:\n"
            + "\n".join(f"- {e}" for e in outcome.errors)
            + "\nRe-answer the ORIGINAL task now. Keep the same meaning and "
              "facts, but make sure the output passes every check above "
              "(strict valid JSON matching the requested schema when one was "
              "given). Output only the final result, no commentary."
        )


@dataclass
class CorrectionStats:
    """Rolling counters for the self-correction loop."""

    total_attempts: int = 0
    corrections: int = 0
    last_corrected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_attempts": self.total_attempts,
            "corrections": self.corrections,
            "last_corrected": self.last_corrected,
        }


class SelfCorrectionLoop:
    """Bounded retry-with-feedback loop around a dynamic router."""

    def __init__(
        self,
        router: Any,
        validator: Optional[OutputValidator] = None,
        max_corrections: int = 2,
    ) -> None:
        self.router = router
        self.validator = validator or OutputValidator()
        self.max_corrections = max_corrections
        self._stats = CorrectionStats()

    async def run(
        self,
        task: str,
        *,
        agent_slug: Optional[str] = None,
        system_prompt: Optional[str] = None,
        response_model: Optional[Any] = None,
        temperature: float = 0.6,
        max_tokens: int = 1500,
        lang: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Tuple[Any, ValidationOutcome]:
        """Run the task, validating and correcting up to ``max_corrections``.

        Returns ``(best_result, last_outcome)``. The result is the last
        invocation of the router; validity is reported through ``last_outcome``.
        """
        current_task = task
        result: Any = None
        outcome = ValidationOutcome(valid=False, errors=["no attempt performed"])

        for attempt in range(self.max_corrections + 1):
            result = await self.router.execute(
                current_task,
                agent_slug=agent_slug,
                system_prompt=system_prompt,
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
                lang=lang,
                category=category,
            )
            self._stats.total_attempts += 1

            outcome = self.validator.validate(
                result.content, response_model=response_model
            )

            # Defensive: the loop accepts both the structured RouterResult and
            # a bare ModelResponse (treat missing ``success`` as success).
            success = bool(getattr(result, "success", True))

            if success and outcome.valid:
                self._stats.last_corrected = attempt > 0
                return result, outcome

            if attempt < self.max_corrections:
                self._stats.corrections += 1
                current_task = self.validator.feedback_prompt(
                    current_task, outcome
                )

        logger.warning(
            "self_correction exhausted",
            attempts=self._stats.total_attempts,
            corrections=self._stats.corrections,
            errors=outcome.errors,
        )
        return result, outcome

    def stats(self) -> CorrectionStats:
        return self._stats
