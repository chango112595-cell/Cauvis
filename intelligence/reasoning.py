from dataclasses import dataclass, field
from typing import Any

from intelligence.task import TaskAnalyzer, TaskRequirements, TaskComplexity


@dataclass
class ReasoningResult:
    """Represents Cauvis's understanding and execution plan."""

    goal: str
    steps: list[str] = field(default_factory=list)
    requires_tools: bool = False
    requires_verification: bool = True
    task_requirements: TaskRequirements | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ReasoningEngine:
    """
    Converts task requirements into a structured reasoning plan.

    The reasoning engine does not execute the task.
    It determines what needs to happen before execution begins.
    """

    def __init__(
        self,
        task_analyzer: TaskAnalyzer | None = None,
    ):
        self.task_analyzer = (
            task_analyzer or TaskAnalyzer()
        )

    def analyze(
        self,
        user_input: str,
        task: TaskRequirements | None = None,
    ) -> ReasoningResult:

        text = user_input.strip()

        if not text:
            return ReasoningResult(
                goal="empty_request",
                steps=[],
                requires_tools=False,
                requires_verification=False,
            )

        # Use an existing task analysis when the Brain has
        # already performed one. Otherwise analyze it here.
        requirements = task or self.task_analyzer.analyze(
            text
        )

        steps = self._build_steps(
            requirements
        )

        return ReasoningResult(
            goal=text,
            steps=steps,
            requires_tools=requirements.requires_tools,
            requires_verification=True,
            task_requirements=requirements,
            metadata={
                "complexity": requirements.complexity.value,
                "requires_internet": requirements.requires_internet,
                "requires_vision": requirements.requires_vision,
                "requires_code": requirements.requires_code,
                "privacy_sensitive": requirements.privacy_sensitive,
                "requires_long_context": requirements.requires_long_context,
            },
        )

    def _build_steps(
        self,
        requirements: TaskRequirements,
    ) -> list[str]:

        steps: list[str] = []

        # Every request begins with understanding the goal.
        steps.append(
            "Understand the user's requested outcome."
        )

        # Code-related work.
        if requirements.requires_code:
            steps.append(
                "Determine the required code, software, "
                "or implementation approach."
            )

        # Internet-related work.
        if requirements.requires_internet:
            steps.append(
                "Identify the information or resources "
                "that require internet access."
            )

        # Vision-related work.
        if requirements.requires_vision:
            steps.append(
                "Process the required visual information "
                "using an appropriate vision capability."
            )

        # Tool-related work.
        if requirements.requires_tools:
            steps.append(
                "Identify and prepare the tools required "
                "to accomplish the task."
            )

        # Long-context work.
        if requirements.requires_long_context:
            steps.append(
                "Gather and manage the required long-context "
                "information before execution."
            )

        # Privacy-sensitive work.
        if requirements.privacy_sensitive:
            steps.append(
                "Apply privacy-aware processing and keep "
                "sensitive information local when possible."
            )

        # Complexity-specific reasoning.
        if requirements.complexity == TaskComplexity.HIGH:
            steps.append(
                "Break the complex objective into smaller "
                "verifiable execution steps."
            )

        elif requirements.complexity == TaskComplexity.MEDIUM:
            steps.append(
                "Determine the most efficient sequence of "
                "actions needed to complete the objective."
            )

        # Execution preparation.
        steps.append(
            "Select the appropriate execution strategy "
            "and capabilities."
        )

        # Verification should be part of every real task.
        steps.append(
            "Verify that the requested outcome was actually achieved."
        )

        return steps