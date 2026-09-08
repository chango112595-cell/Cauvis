from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskComplexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class TaskRequirements:
    complexity: TaskComplexity = TaskComplexity.LOW
    requires_tools: bool = False
    requires_internet: bool = False
    privacy_sensitive: bool = False
    requires_vision: bool = False
    requires_code: bool = False
    requires_long_context: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskAnalyzer:
    """Determines the capabilities a user request may require."""

    def analyze(self, user_input: str) -> TaskRequirements:
        text = user_input.lower().strip()

        if not text:
            return TaskRequirements()

        requires_internet = any(
            keyword in text
            for keyword in (
                "search",
                "search the web",
                "search online",
                "look online",
                "look up",
                "browse",
                "internet",
                "online",
                "latest",
                "current",
                "news",
                "website",
                "web page",
                "webpage",
            )
        )

        requires_vision = any(
            keyword in text
            for keyword in (
                "look at",
                "see this",
                "analyze this image",
                "analyze the image",
                "camera",
                "screenshot",
                "photo",
                "picture",
                "visual",
                "screen",
            )
        )

        requires_code = any(
            keyword in text
            for keyword in (
                "code",
                "program",
                "python",
                "script",
                "debug",
                "programming",
                "software",
                "function",
                "class",
                "api",
                "application",
                "app",
            )
        )

        requires_tools = any(
            keyword in text
            for keyword in (
                "open",
                "close",
                "run",
                "launch",
                "create",
                "delete",
                "move",
                "copy",
                "install",
                "send",
                "search",
                "browse",
                "execute",
                "access",
                "use",
                "read",
                "write",
                "click",
                "type",
                "download",
                "upload",
                "start",
                "stop",
            )
        )

        privacy_sensitive = any(
            keyword in text
            for keyword in (
                "private",
                "personal",
                "confidential",
                "password",
                "secret",
                "my files",
                "private files",
                "personal files",
                "sensitive",
            )
        )

        requires_long_context = any(
            keyword in text
            for keyword in (
                "entire project",
                "whole project",
                "large document",
                "codebase",
                "entire codebase",
                "long document",
                "large file",
                "all of these files",
            )
        )

        high_complexity_keywords = (
            "build",
            "develop",
            "design",
            "architect",
            "complex",
            "research",
            "analyze",
            "solve",
            "debug",
            "implement",
            "develop",
            "engineer",
            "create an application",
            "create a system",
        )

        medium_complexity_keywords = (
            "explain",
            "compare",
            "summarize",
            "plan",
            "calculate",
            "describe",
            "review",
            "evaluate",
        )

        if any(keyword in text for keyword in high_complexity_keywords):
            complexity = TaskComplexity.HIGH
        elif any(keyword in text for keyword in medium_complexity_keywords):
            complexity = TaskComplexity.MEDIUM
        else:
            complexity = TaskComplexity.LOW

        return TaskRequirements(
            complexity=complexity,
            requires_tools=requires_tools,
            requires_internet=requires_internet,
            privacy_sensitive=privacy_sensitive,
            requires_vision=requires_vision,
            requires_code=requires_code,
            requires_long_context=requires_long_context,
        )