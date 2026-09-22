from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from core.action_request import ActionRequest
from core.routing_language import RoutingLanguageNormalizer
from execution.engine import ExecutionEngine
from security.permissions import PermissionLevel, PermissionManager


@dataclass
class ActionExecutionResult:
    handled: bool
    success: bool
    status: str
    message: str
    action_performed: bool = False
    execution_attempted: bool = False
    tool_name: str | None = None
    permission_action: str | None = None
    permission_level: str | None = None
    approval_from_current_request: bool = False
    verification_status: str = "not_checked"
    verification_success: bool = False
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "handled": self.handled,
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "action_performed": self.action_performed,
            "execution_attempted": self.execution_attempted,
            "tool_name": self.tool_name,
            "permission_action": self.permission_action,
            "permission_level": self.permission_level,
            "approval_from_current_request": (
                self.approval_from_current_request
            ),
            "verification_status": self.verification_status,
            "verification_success": self.verification_success,
            "output": self.output,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


class ActionExecutionBridge:
    """
    Connect direct user action requests to bound tools.

    An explicit current-turn user command counts as approval only for
    APPROVAL_REQUIRED low-risk actions. HIGH_RISK actions remain blocked.
    """

    _URL_PATTERN = re.compile(
        r"(?P<url>"
        r"https?://[^\s\"']+"
        r"|www\.[^\s\"']+"
        r"|(?:[A-Za-z0-9-]+\.)+(?:com|org|net|io|dev|ai|gov|edu)"
        r"(?:/[^\s\"']*)?"
        r")",
        re.IGNORECASE,
    )

    _APP_ALIASES = (
        "google chrome",
        "microsoft edge",
        "file explorer",
        "notepad",
        "calculator",
        "chrome",
        "edge",
        "paint",
        "explorer",
    )

    def __init__(
        self,
        *,
        execution_engine: ExecutionEngine,
        permission_manager: PermissionManager,
        project_root: str | Path,
        home: str | Path | None = None,
    ):
        self.execution_engine = execution_engine
        self.permission_manager = permission_manager
        self.project_root = Path(project_root).resolve()
        self.home = Path(
            home if home is not None else Path.home()
        ).resolve()

    def can_handle(
        self,
        action_request: ActionRequest,
    ) -> bool:
        if not action_request.requested:
            return False

        if action_request.category == "system":
            return action_request.action in {
                "open",
                "run",
                "launch",
                "start",
            }

        if action_request.category == "filesystem":
            return action_request.action in {
                "read",
                "create",
                "make",
                "save",
                "write",
                "delete",
                "move",
                "copy",
                "rename",
            }

        return False

    def execute(
        self,
        user_input: str,
        action_request: ActionRequest,
        *,
        explicit_user_request: bool,
    ) -> ActionExecutionResult:
        if not self.can_handle(action_request):
            return ActionExecutionResult(
                handled=False,
                success=False,
                status="blocked",
                message=(
                    "This action is not yet connected to a functional "
                    "Cauvis execution handler."
                ),
            )

        if action_request.category == "system":
            return self._execute_system(
                user_input,
                explicit_user_request=explicit_user_request,
            )

        return self._execute_filesystem(
            user_input,
            action_request,
            explicit_user_request=explicit_user_request,
        )

    def _execute_system(
        self,
        user_input: str,
        *,
        explicit_user_request: bool,
    ) -> ActionExecutionResult:
        normalized = RoutingLanguageNormalizer.normalize(
            user_input
        )

        url = self._extract_url(
            user_input
        )

        app = None

        for alias in self._APP_ALIASES:
            if alias in normalized:
                app = alias
                break

        if app is not None:
            return self._run_tool(
                tool_name="application.launch",
                permission_action="application.launch",
                explicit_user_request=explicit_user_request,
                kwargs={
                    "application": app,
                    "url": url,
                },
                success_message=(
                    "Launched "
                    + app
                    + (
                        " and sent it "
                        + url
                        if url
                        else ""
                    )
                    + "."
                ),
                verification_kind="process_launch",
            )

        if url:
            return self._run_tool(
                tool_name="web.open_url",
                permission_action="web.open_url",
                explicit_user_request=explicit_user_request,
                kwargs={
                    "url": url,
                },
                success_message=(
                    "Sent "
                    + url
                    + " to the default browser."
                ),
                verification_kind="browser_acceptance",
            )

        target = self._extract_application_target(
            normalized
        )

        if not target:
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="blocked",
                message=(
                    "I recognized the launch request but could not "
                    "determine which application to open."
                ),
                execution_attempted=False,
                error="application_target_not_parsed",
            )

        return self._run_tool(
            tool_name="application.launch",
            permission_action="application.launch",
            explicit_user_request=explicit_user_request,
            kwargs={
                "application": target,
                "url": None,
            },
            success_message=(
                "Launched "
                + target
                + "."
            ),
            verification_kind="process_launch",
        )

    def _execute_filesystem(
        self,
        user_input: str,
        action_request: ActionRequest,
        *,
        explicit_user_request: bool,
    ) -> ActionExecutionResult:
        action = str(
            action_request.action
            or ""
        ).lower()

        if action in {
            "delete",
            "move",
            "copy",
            "rename",
        }:
            permission_action = {
                "delete": "filesystem.delete",
                "move": "filesystem.move",
                "copy": "filesystem.copy",
                "rename": "filesystem.move",
            }[action]

            decision = self.permission_manager.evaluate(
                permission_action
            )

            return ActionExecutionResult(
                handled=True,
                success=False,
                status="blocked",
                message=(
                    "That filesystem operation remains protected "
                    "in the functional core and was not performed."
                ),
                action_performed=False,
                execution_attempted=False,
                permission_action=permission_action,
                permission_level=decision.level.value,
                verification_status="not_checked",
                error="protected_filesystem_operation",
            )

        path = self._extract_file_path(
            user_input
        )

        if path is None:
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="blocked",
                message=(
                    "I recognized the file request but could not "
                    "determine the file path."
                ),
                execution_attempted=False,
                error="file_path_not_parsed",
            )

        if action == "read":
            return self._run_tool(
                tool_name="filesystem.read",
                permission_action="filesystem.read",
                explicit_user_request=explicit_user_request,
                kwargs={
                    "path": str(path),
                },
                success_message=None,
                verification_kind="file_read",
            )

        content = self._extract_content(
            user_input
        )

        overwrite = bool(
            re.search(
                r"\b(?:overwrite|replace)\b",
                user_input,
                flags=re.IGNORECASE,
            )
        )

        return self._run_tool(
            tool_name="filesystem.write",
            permission_action="filesystem.write",
            explicit_user_request=explicit_user_request,
            kwargs={
                "path": str(path),
                "content": content,
                "overwrite": overwrite,
            },
            success_message=(
                "Created and verified file: "
                + str(path)
            ),
            verification_kind="file_write",
        )

    def _run_tool(
        self,
        *,
        tool_name: str,
        permission_action: str,
        explicit_user_request: bool,
        kwargs: dict[str, Any],
        success_message: str | None,
        verification_kind: str,
    ) -> ActionExecutionResult:
        decision = self.permission_manager.evaluate(
            permission_action
        )

        approved_from_request = False

        if decision.allowed:
            allowed = True

        elif (
            decision.level
            == PermissionLevel.APPROVAL_REQUIRED
            and explicit_user_request
        ):
            # The user just issued this exact low-risk action command.
            allowed = True
            approved_from_request = True

        else:
            allowed = False

        if not allowed:
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="blocked",
                message=(
                    "This action requires a higher level of permission "
                    "and was not performed."
                ),
                action_performed=False,
                execution_attempted=False,
                tool_name=tool_name,
                permission_action=permission_action,
                permission_level=decision.level.value,
                approval_from_current_request=False,
                error=decision.reason,
            )

        tool_result = self.execution_engine.execute_tool(
            tool_name,
            **kwargs,
        )

        if not tool_result.success:
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="error",
                message=(
                    "Cauvis attempted the action but the bound tool failed: "
                    + str(tool_result.error or "unknown tool failure")
                ),
                action_performed=False,
                execution_attempted=True,
                tool_name=tool_name,
                permission_action=permission_action,
                permission_level=decision.level.value,
                approval_from_current_request=approved_from_request,
                verification_status="failed",
                verification_success=False,
                error=tool_result.error,
                metadata={
                    "tool_execution_time": tool_result.execution_time,
                },
            )

        output = tool_result.output

        verification_success = self._verify_output(
            verification_kind,
            output,
        )

        if not verification_success:
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="error",
                message=(
                    "The tool returned success, but Cauvis could not "
                    "verify the expected execution outcome."
                ),
                action_performed=True,
                execution_attempted=True,
                tool_name=tool_name,
                permission_action=permission_action,
                permission_level=decision.level.value,
                approval_from_current_request=approved_from_request,
                verification_status="failed",
                verification_success=False,
                output=output,
                error="outcome_verification_failed",
            )

        message = success_message

        if verification_kind == "file_read":
            content = ""
            path = ""

            if isinstance(output, dict):
                content = str(
                    output.get(
                        "content",
                        "",
                    )
                )
                path = str(
                    output.get(
                        "path",
                        "",
                    )
                )

            if len(content) > 12000:
                content = (
                    content[:12000]
                    + "\n...[output truncated by Cauvis]"
                )

            message = (
                "Contents of "
                + path
                + ":\n"
                + content
            )

        verification_status = (
            "accepted_not_visually_verified"
            if verification_kind == "browser_acceptance"
            else "verified"
        )

        return ActionExecutionResult(
            handled=True,
            success=True,
            status="success",
            message=message or "Action completed.",
            action_performed=True,
            execution_attempted=True,
            tool_name=tool_name,
            permission_action=permission_action,
            permission_level=decision.level.value,
            approval_from_current_request=approved_from_request,
            verification_status=verification_status,
            verification_success=True,
            output=output,
            metadata={
                "tool_execution_time": tool_result.execution_time,
            },
        )

    @staticmethod
    def _verify_output(
        verification_kind: str,
        output: Any,
    ) -> bool:
        if not isinstance(output, dict):
            return False

        if verification_kind == "process_launch":
            return bool(
                output.get(
                    "launch_request_completed"
                )
            )

        if verification_kind == "browser_acceptance":
            return bool(
                output.get(
                    "browser_request_accepted"
                )
            )

        if verification_kind == "file_read":
            return bool(
                output.get(
                    "verified_exists"
                )
            )

        if verification_kind == "file_write":
            return bool(
                output.get(
                    "verified_exists"
                )
                and output.get(
                    "verified_content"
                )
            )

        return False

    def _extract_file_path(
        self,
        user_input: str,
    ) -> Path | None:
        text = str(user_input)

        # Quoted absolute/relative path gets highest priority.
        quoted = re.search(
            r'["\']([^"\']+\.[A-Za-z0-9]{1,10})["\']',
            text,
        )

        filename = (
            quoted.group(1).strip()
            if quoted
            else None
        )

        if filename is None:
            called = re.search(
                r"\b(?:called|named)\s+"
                r'["\']?([^"\'\r\n]+?\.[A-Za-z0-9]{1,10})'
                r'["\']?(?=\s+(?:on|in|with|containing)\b|[.!?,;:]?$)',
                text,
                flags=re.IGNORECASE,
            )

            if called:
                filename = called.group(1).strip()

        if filename is None:
            absolute = re.search(
                r"\b([A-Za-z]:[\\/][^\"\r\n]+?\.[A-Za-z0-9]{1,10})"
                r"(?=\s+(?:with|containing|overwrite|replace)\b|[.!?,;:]?$)",
                text,
            )

            if absolute:
                filename = absolute.group(1).strip()

        if filename is None:
            simple = re.search(
                r"\b([A-Za-z0-9_. -]+\.[A-Za-z0-9]{1,10})\b",
                text,
            )

            if simple:
                filename = simple.group(1).strip()

        if not filename:
            return None

        candidate = Path(filename).expanduser()

        if candidate.is_absolute():
            return candidate.resolve(strict=False)

        lower = text.lower()

        if "desktop" in lower:
            base = self._desktop_path()

        elif "documents" in lower:
            base = self.home / "Documents"

        elif "downloads" in lower:
            base = self.home / "Downloads"

        else:
            base = self.project_root

        return (
            base
            / candidate.name
        ).resolve(strict=False)

    def _desktop_path(self) -> Path:
        direct = self.home / "Desktop"

        if direct.is_dir():
            return direct

        onedrive = self.home / "OneDrive" / "Desktop"

        if onedrive.is_dir():
            return onedrive

        return direct

    @staticmethod
    def _extract_content(
        user_input: str,
    ) -> str:
        match = re.search(
            r"\b(?:with\s+(?:the\s+)?(?:text|content)|containing)\s+(.+)$",
            str(user_input),
            flags=re.IGNORECASE,
        )

        if match is None:
            return ""

        return match.group(1).strip().strip('"').strip("'").rstrip(".")

    @classmethod
    def _extract_url(
        cls,
        user_input: str,
    ) -> str | None:
        match = cls._URL_PATTERN.search(
            str(user_input)
        )

        if match is None:
            return None

        value = match.group("url").rstrip(".,;:)")

        if not value.lower().startswith(
            (
                "http://",
                "https://",
            )
        ):
            value = "https://" + value

        return value

    @staticmethod
    def _extract_application_target(
        normalized: str,
    ) -> str:
        text = normalized.strip().rstrip(" .!?")

        for prefix in (
            "open ",
            "launch ",
            "start ",
            "run ",
        ):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        if " and " in text:
            text = text.split(" and ", 1)[0].strip()

        return text
