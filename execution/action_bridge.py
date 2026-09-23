from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from core.action_request import ActionRequest
from core.command_normalizer import CommandNormalizer
from execution.engine import ExecutionEngine
from execution.pending_actions import (
    PendingAction,
    PendingActionManager,
)
from security.permissions import PermissionLevel, PermissionManager
from tools.windows_known_folders import WindowsKnownFolderResolver


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


class ActionExecutionBridge:
    """
    Functional action bridge with clarification and pending-action resume.

    Missing parameters do not fall through to the language model. Cauvis
    asks a focused question, stores the unfinished action by session, and
    resumes it from the user's next answer.
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
        known_folders: WindowsKnownFolderResolver | None = None,
        pending_actions: PendingActionManager | None = None,
    ):
        self.execution_engine = execution_engine
        self.permission_manager = permission_manager
        self.project_root = Path(project_root).resolve()
        self.home = Path(
            home if home is not None else Path.home()
        ).resolve()

        self.known_folders = (
            known_folders
            or WindowsKnownFolderResolver(
                home=self.home
            )
        )

        self.pending_actions = (
            pending_actions
            or PendingActionManager()
        )

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
                "diagnose",
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
        session_id: str = "local-session",
    ) -> ActionExecutionResult:
        routing_text = CommandNormalizer.routing_text(
            user_input
        )

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

        if (
            action_request.category == "system"
            and action_request.action == "diagnose"
        ):
            return self._execute_diagnostic(
                explicit_user_request=explicit_user_request,
            )

        if action_request.category == "system":
            return self._execute_system(
                routing_text,
                explicit_user_request=explicit_user_request,
            )

        return self._execute_filesystem(
            routing_text,
            action_request,
            explicit_user_request=explicit_user_request,
            session_id=session_id,
        )

    def resume_pending(
        self,
        session_id: str,
        user_input: str,
    ) -> ActionExecutionResult | None:
        pending = self.pending_actions.get(
            session_id
        )

        if pending is None:
            return None

        reply = CommandNormalizer.routing_text(
            user_input
        )

        if reply.lower().strip(" .!?") in {
            "cancel",
            "never mind",
            "nevermind",
            "stop",
        }:
            self.pending_actions.clear(
                session_id
            )

            return ActionExecutionResult(
                handled=True,
                success=True,
                status="success",
                message="Okay, I canceled the pending action.",
                metadata={
                    "pending_action_canceled": True,
                },
            )

        if pending.category != "filesystem":
            self.pending_actions.clear(
                session_id
            )
            return None

        data = dict(
            pending.data
        )

        missing = list(
            pending.missing_fields
        )

        if "filename" in missing:
            filename = self._extract_filename(
                reply
            )

            if filename:
                data["filename"] = filename
                missing.remove("filename")

        if "location" in missing:
            location = self._extract_location(
                reply
            )

            if location is not None:
                data["location"] = str(location)
                missing.remove("location")

        if "content" in missing:
            content = self._content_from_clarification(
                reply
            )

            if content is not None:
                data["content"] = content
                missing.remove("content")

        if "overwrite" in missing:
            answer = reply.lower().strip(" .!?")

            if answer in {
                "yes",
                "yes overwrite",
                "overwrite",
                "replace",
                "replace it",
                "overwrite it",
            }:
                data["overwrite"] = True
                missing.remove("overwrite")

            elif answer in {
                "no",
                "no cancel",
                "cancel",
                "do not overwrite",
                "don't overwrite",
            }:
                self.pending_actions.clear(
                    session_id
                )

                return ActionExecutionResult(
                    handled=True,
                    success=True,
                    status="success",
                    message=(
                        "Okay, I did not overwrite the existing file."
                    ),
                    metadata={
                        "pending_action_canceled": True,
                    },
                )

        if missing:
            updated = PendingAction(
                original_input=pending.original_input,
                category=pending.category,
                action=pending.action,
                missing_fields=tuple(missing),
                data=data,
            )

            self.pending_actions.set(
                session_id,
                updated,
            )

            return self._clarification_result(
                updated
            )

        result = self._execute_completed_file_request(
            data,
            explicit_user_request=True,
            session_id=session_id,
            original_input=pending.original_input,
        )

        if result.status != "clarification_required":
            self.pending_actions.clear(
                session_id
            )

        return result

    def _execute_system(
        self,
        user_input: str,
        *,
        explicit_user_request: bool,
    ) -> ActionExecutionResult:
        urls = self._extract_urls(
            user_input
        )

        apps = self._extract_applications(
            user_input
        )

        results = []

        for app in apps:
            app_url = (
                urls[0]
                if len(apps) == 1 and len(urls) == 1
                else None
            )

            result = self._run_tool(
                tool_name="application.launch",
                permission_action="application.launch",
                explicit_user_request=explicit_user_request,
                kwargs={
                    "application": app,
                    "url": app_url,
                },
                success_message=(
                    "Launched " + app + "."
                ),
                verification_kind="process_launch",
            )

            results.append(
                result
            )

            if not result.success:
                return result

        urls_to_open = urls

        if (
            len(apps) == 1
            and len(urls) == 1
        ):
            urls_to_open = []

        for url in urls_to_open:
            result = self._run_tool(
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

            results.append(
                result
            )

            if not result.success:
                return result

        if len(results) == 1:
            return results[0]

        if results:
            messages = [
                item.message
                for item in results
                if item.message
            ]

            return ActionExecutionResult(
                handled=True,
                success=True,
                status="success",
                message=" ".join(messages),
                action_performed=True,
                execution_attempted=True,
                verification_status="verified",
                verification_success=True,
                output=[
                    item.output
                    for item in results
                ],
                metadata={
                    "batch_action_count": len(results),
                    "multi_action": len(results) > 1,
                },
            )

        target = self._extract_application_target(
            user_input
        )

        if not target:
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="clarification_required",
                message=(
                    "Which application or website would you like me to open?"
                ),
                error="system_target_not_parsed",
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
                "Launched " + target + "."
            ),
            verification_kind="process_launch",
        )

    def _execute_diagnostic(
        self,
        *,
        explicit_user_request: bool,
    ) -> ActionExecutionResult:
        result = self._run_tool(
            tool_name="system.performance_snapshot",
            permission_action="system.info",
            explicit_user_request=explicit_user_request,
            kwargs={},
            success_message=None,
            verification_kind="diagnostic_snapshot",
        )

        if not result.success:
            return result

        payload = (
            result.output
            if isinstance(result.output, dict)
            else {}
        )

        snapshot = payload.get(
            "snapshot",
            {}
        )

        findings = payload.get(
            "findings",
            [],
        )

        lines = [
            "I checked the PC's current performance snapshot.",
            "",
            (
                "CPU: "
                + str(snapshot.get("cpu_percent", "?"))
                + "%"
            ),
            (
                "Memory: "
                + str(snapshot.get("memory_percent", "?"))
                + "% used"
            ),
        ]

        disks = snapshot.get(
            "disks",
            [],
        ) or []

        for disk in disks[:4]:
            lines.append(
                (
                    "Disk "
                    + str(disk.get("drive", "?"))
                    + ": "
                    + str(disk.get("free_gb", "?"))
                    + " GB free ("
                    + str(disk.get("free_percent", "?"))
                    + "%)"
                )
            )

        if findings:
            lines.append("")
            lines.append("What stands out:")

            for item in findings:
                lines.append(
                    "- " + str(item)
                )

        result.message = "\n".join(
            lines
        )

        return result

    def _execute_filesystem(
        self,
        user_input: str,
        action_request: ActionRequest,
        *,
        explicit_user_request: bool,
        session_id: str,
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
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="blocked",
                message=(
                    "That filesystem operation remains protected "
                    "and was not performed."
                ),
                action_performed=False,
                execution_attempted=False,
                error="protected_filesystem_operation",
            )

        if action == "read":
            path = self._extract_read_path(
                user_input
            )

            if path is None:
                pending = PendingAction(
                    original_input=user_input,
                    category="filesystem",
                    action="read",
                    missing_fields=("filename", "location"),
                    data={
                        "mode": "read",
                    },
                )

                self.pending_actions.set(
                    session_id,
                    pending,
                )

                return self._clarification_result(
                    pending
                )

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

        data, missing = self._parse_file_create_request(
            user_input
        )

        if missing:
            pending = PendingAction(
                original_input=user_input,
                category="filesystem",
                action="write",
                missing_fields=tuple(missing),
                data=data,
            )

            self.pending_actions.set(
                session_id,
                pending,
            )

            return self._clarification_result(
                pending
            )

        return self._execute_completed_file_request(
            data,
            explicit_user_request=explicit_user_request,
            session_id=session_id,
            original_input=user_input,
        )

    def _execute_completed_file_request(
        self,
        data: dict[str, Any],
        *,
        explicit_user_request: bool,
        session_id: str,
        original_input: str,
    ) -> ActionExecutionResult:
        mode = str(
            data.get("mode", "write")
        )

        filename = str(
            data.get("filename", "")
        ).strip()

        location_value = str(
            data.get("location", "")
        ).strip()

        if not filename:
            pending = PendingAction(
                original_input=original_input,
                category="filesystem",
                action=mode,
                missing_fields=("filename",),
                data=data,
            )
            self.pending_actions.set(session_id, pending)
            return self._clarification_result(pending)

        location = Path(
            location_value
        ).expanduser().resolve(strict=False)

        path = (
            location / Path(filename).name
        ).resolve(strict=False)

        if mode == "read":
            return self._run_tool(
                tool_name="filesystem.read",
                permission_action="filesystem.read",
                explicit_user_request=explicit_user_request,
                kwargs={"path": str(path)},
                success_message=None,
                verification_kind="file_read",
            )

        content = data.get(
            "content"
        )

        if content is None:
            pending = PendingAction(
                original_input=original_input,
                category="filesystem",
                action="write",
                missing_fields=("content",),
                data=data,
            )
            self.pending_actions.set(session_id, pending)
            return self._clarification_result(pending)

        overwrite = bool(
            data.get(
                "overwrite",
                False,
            )
        )

        if path.exists() and not overwrite:
            pending = PendingAction(
                original_input=original_input,
                category="filesystem",
                action="write",
                missing_fields=("overwrite",),
                data=data,
            )
            self.pending_actions.set(session_id, pending)
            return self._clarification_result(pending)

        return self._run_tool(
            tool_name="filesystem.write",
            permission_action="filesystem.write",
            explicit_user_request=explicit_user_request,
            kwargs={
                "path": str(path),
                "content": str(content),
                "overwrite": overwrite,
            },
            success_message=(
                "Created and verified file: "
                + str(path)
            ),
            verification_kind="file_write",
        )

    def _parse_file_create_request(
        self,
        user_input: str,
    ) -> tuple[dict[str, Any], list[str]]:
        filename = self._extract_filename(
            user_input
        )

        location = self._extract_location(
            user_input
        )

        content = self._extract_content(
            user_input
        )

        data = {
            "mode": "write",
            "filename": filename,
            "location": (
                str(location)
                if location is not None
                else None
            ),
            "content": content,
            "overwrite": bool(
                re.search(
                    r"\b(?:overwrite|replace)\b",
                    user_input,
                    flags=re.IGNORECASE,
                )
            ),
        }

        missing = []

        if not filename:
            missing.append("filename")

        if location is None:
            missing.append("location")

        if content is None:
            missing.append("content")

        return data, missing

    def _clarification_result(
        self,
        pending: PendingAction,
    ) -> ActionExecutionResult:
        missing = set(
            pending.missing_fields
        )

        if missing == {"overwrite"}:
            path = self._pending_path(
                pending
            )
            message = (
                str(path)
                + " already exists. Do you want me to overwrite it "
                "or cancel?"
            )

        else:
            questions = []

            if "filename" in missing:
                questions.append(
                    "what should the file be called"
                )

            if "location" in missing:
                questions.append(
                    "where should I save it (Desktop, Documents, "
                    "Downloads, or another path)"
                )

            if "content" in missing:
                questions.append(
                    "what should it contain"
                )

            message = (
                "I need one more detail before I do that: "
                + "; ".join(questions)
                + "."
            )

        return ActionExecutionResult(
            handled=True,
            success=False,
            status="clarification_required",
            message=message,
            action_performed=False,
            execution_attempted=False,
            error="missing_action_parameters",
            metadata={
                "pending_action": True,
                "missing_fields": list(
                    pending.missing_fields
                ),
            },
        )

    def _pending_path(
        self,
        pending: PendingAction,
    ) -> Path:
        location = Path(
            str(
                pending.data.get(
                    "location",
                    self.project_root,
                )
            )
        )

        filename = str(
            pending.data.get(
                "filename",
                "file",
            )
        )

        return (
            location / Path(filename).name
        ).resolve(strict=False)

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
                permission_action=permission_action,
                permission_level=decision.level.value,
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
                execution_attempted=True,
                tool_name=tool_name,
                permission_action=permission_action,
                permission_level=decision.level.value,
                approval_from_current_request=approved_from_request,
                verification_status="failed",
                error=tool_result.error,
                metadata={
                    "tool_execution_time": tool_result.execution_time,
                },
            )

        output = tool_result.output

        verified = self._verify_output(
            verification_kind,
            output,
        )

        if not verified:
            return ActionExecutionResult(
                handled=True,
                success=False,
                status="error",
                message=(
                    "The tool returned success, but Cauvis could not "
                    "verify the expected outcome."
                ),
                action_performed=True,
                execution_attempted=True,
                tool_name=tool_name,
                permission_action=permission_action,
                permission_level=decision.level.value,
                approval_from_current_request=approved_from_request,
                verification_status="failed",
                output=output,
                error="outcome_verification_failed",
            )

        message = success_message

        if verification_kind == "file_read":
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
            verification_status="verified",
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

        if verification_kind == "diagnostic_snapshot":
            return bool(
                output.get(
                    "verified_runtime_observation"
                )
            )

        return False

    @classmethod
    def _extract_urls(
        cls,
        user_input: str,
    ) -> list[str]:
        values = []

        for match in cls._URL_PATTERN.finditer(
            str(user_input)
        ):
            value = match.group("url").rstrip(
                ".,;:)"
            )

            if not value.lower().startswith(
                (
                    "http://",
                    "https://",
                )
            ):
                value = "https://" + value

            if value not in values:
                values.append(value)

        return values

    @classmethod
    def _extract_applications(
        cls,
        user_input: str,
    ) -> list[str]:
        lower = str(user_input).lower()
        apps = []

        # Longest aliases are listed first to avoid duplicate chrome/edge.
        for alias in cls._APP_ALIASES:
            if alias in lower:
                if alias == "chrome" and "google chrome" in lower:
                    continue
                if alias == "edge" and "microsoft edge" in lower:
                    continue
                if alias == "explorer" and "file explorer" in lower:
                    continue
                if alias not in apps:
                    apps.append(alias)

        return apps

    def _extract_location(
        self,
        text: str,
    ) -> Path | None:
        value = str(text)
        lower = value.lower()

        for name in (
            "desktop",
            "documents",
            "downloads",
        ):
            if name in lower:
                resolved = self.known_folders.resolve(
                    name
                )

                if resolved is not None:
                    return resolved

                return None

        absolute_dir = re.search(
            r"\b([A-Za-z]:[\\/][^\"\r\n]+?)(?=[.!?,;:]?$)",
            value,
        )

        if absolute_dir:
            candidate = Path(
                absolute_dir.group(1).strip()
            ).expanduser()

            if candidate.suffix:
                candidate = candidate.parent

            return candidate.resolve(strict=False)

        return None

    @staticmethod
    def _extract_filename(
        text: str,
    ) -> str | None:
        value = str(text)

        quoted = re.search(
            r'["\']([^"\']+\.[A-Za-z0-9]{1,10})["\']',
            value,
        )

        if quoted:
            return Path(
                quoted.group(1).strip()
            ).name

        called = re.search(
            r"\b(?:called|named)\s+"
            r'["\']?([^"\'\r\n]+?\.[A-Za-z0-9]{1,10})'
            r'["\']?(?=\s+(?:on|in|with|containing)\b|[.!?,;:]?$)',
            value,
            flags=re.IGNORECASE,
        )

        if called:
            return Path(
                called.group(1).strip()
            ).name

        simple = re.search(
            r"\b([A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,10})\b",
            value,
        )

        if simple:
            return Path(
                simple.group(1).strip()
            ).name

        return None

    def _extract_read_path(
        self,
        text: str,
    ) -> Path | None:
        filename = self._extract_filename(
            text
        )

        if filename is None:
            return None

        quoted_absolute = re.search(
            r'["\']([A-Za-z]:[\\/][^"\']+\.[A-Za-z0-9]{1,10})["\']',
            str(text),
        )

        if quoted_absolute:
            return Path(
                quoted_absolute.group(1)
            ).resolve(strict=False)

        location = self._extract_location(
            text
        )

        if location is None:
            return None

        return (
            location / filename
        ).resolve(strict=False)

    @staticmethod
    def _extract_content(
        user_input: str,
    ) -> str | None:
        value = str(user_input)

        if re.search(
            r"\bempty\s+file\b",
            value,
            flags=re.IGNORECASE,
        ):
            return ""

        match = re.search(
            r"\b(?:with\s+(?:the\s+)?(?:text|content)|containing)\s+(.+)$",
            value,
            flags=re.IGNORECASE,
        )

        if match is None:
            return None

        content = match.group(1).strip()

        content = re.sub(
            r"\s+inside[.!]?$",
            "",
            content,
            flags=re.IGNORECASE,
        )

        return content.strip().strip('"').strip("'").rstrip(".")

    @staticmethod
    def _content_from_clarification(
        reply: str,
    ) -> str | None:
        value = str(reply).strip()

        if not value:
            return None

        if value.lower() in {
            "empty",
            "leave it empty",
            "empty file",
        }:
            return ""

        value = re.sub(
            r"^(?:with\s+)?(?:text|content)\s+",
            "",
            value,
            count=1,
            flags=re.IGNORECASE,
        )

        return value.strip().strip('"').strip("'")

    @staticmethod
    def _extract_application_target(
        text: str,
    ) -> str:
        value = str(text).lower().strip().rstrip(" .!?")

        for prefix in (
            "open ",
            "launch ",
            "start ",
            "run ",
        ):
            if value.startswith(prefix):
                value = value[len(prefix):].strip()
                break

        if " and " in value:
            value = value.split(" and ", 1)[0].strip()

        return value
