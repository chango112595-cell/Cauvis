from dataclasses import dataclass


@dataclass(frozen=True)
class ActionRequest:
    """
    Deterministic classification of whether the user is asking
    Cauvis to perform an external action.

    This object does not authorize or execute the action.
    """

    requested: bool
    category: str | None = None
    action: str | None = None
    required_capability: str | None = None
    confidence: float = 0.0
    reason: str = ""


class ActionRequestDetector:
    """
    Conservative deterministic detector for direct external
    action requests.

    This classifier is intentionally separate from TaskAnalyzer.

    TaskAnalyzer answers:
        "What might this request require?"

    ActionRequestDetector answers:
        "Is the user directly asking Cauvis to perform an
        external action right now?"

    Informational or instructional questions must remain normal
    conversation even when they contain action verbs.
    """

    _CAPABILITY_STATUS_PHRASES = (
        "browse the web",
        "search the web",
        "use the web",
        "use the internet",
        "control my computer",
        "control the computer",
        "access my files",
        "access files",
        "use my files",
        "set reminders",
        "create reminders",
        "use tools",
        "run tools",
        "execute tools",
    )

    _CAPABILITY_STATUS_CONTEXT = (
        "in this running cauvis instance",
        "in this cauvis instance",
        "in this running instance",
        "currently available",
        "available right now",
        "capabilities are available",
        "capabilities do you have",
    )

    _INSTRUCTIONAL_PREFIXES = (
        "how do i ",
        "how can i ",
        "how would i ",
        "how should i ",
        "what command ",
        "which command ",
        "what commands ",
        "which commands ",
        "explain how ",
        "explain how to ",
        "show me how ",
        "show me how to ",
        "tell me how ",
        "tell me how to ",
        "can you tell me how ",
        "can you tell me how to ",
        "could you tell me how ",
        "could you tell me how to ",
        "would you tell me how ",
        "would you tell me how to ",
        "can you explain how ",
        "could you explain how ",
        "what is the best way to ",
        "what's the best way to ",
        "why does ",
        "why is ",
        "what happens if ",
        "is it possible to ",
    )

    _POLITE_PREFIXES = (
        "please ",
        "can you ",
        "could you ",
        "would you ",
        "will you ",
        "i want you to ",
        "i need you to ",
        "i'd like you to ",
        "i would like you to ",
    )

    _WEB_COMMANDS = (
        "search the web",
        "search online",
        "browse the web",
        "browse online",
        "look up",
    )

    _SYSTEM_VERBS = (
        "open",
        "close",
        "run",
        "launch",
        "start",
        "stop",
    )

    _FILESYSTEM_VERBS = (
        "delete",
        "move",
        "copy",
        "rename",
    )

    _GENERIC_EXTERNAL_VERBS = (
        "send",
        "click",
        "type",
        "install",
        "upload",
        "download",
    )

    _FILESYSTEM_OBJECT_HINTS = (
        "file",
        "folder",
        "directory",
        "document",
        "path",
    )

    def detect(
        self,
        text: str,
    ) -> ActionRequest:
        original = str(text)

        normalized = self._normalize(
            original
        )

        if not normalized:
            return self._not_requested(
                "Input is empty."
            )

        if self._is_capability_status_question(
            normalized
        ):
            return self._not_requested(
                "Request asks about capability availability "
                "rather than asking Cauvis to execute it."
            )

        if self._is_instructional(
            normalized
        ):
            return self._not_requested(
                "Request is instructional or informational."
            )

        command_text = self._strip_polite_prefix(
            normalized
        )

        # A polite prefix can reveal another instructional form,
        # for example:
        # "Can you explain how to open Notepad?"
        if self._is_instructional(
            command_text
        ):
            return self._not_requested(
                "Request is instructional or informational."
            )

        # -----------------------------------------------------
        # REMINDERS / SCHEDULED ACTIONS
        # -----------------------------------------------------

        reminder_action = self._detect_reminder(
            command_text
        )

        if reminder_action is not None:
            return ActionRequest(
                requested=True,
                category="reminder",
                action=reminder_action,
                required_capability="reminders",
                confidence=1.0,
                reason=(
                    "Direct reminder or scheduling request."
                ),
            )

        # -----------------------------------------------------
        # WEB ACTIONS
        # -----------------------------------------------------

        for command in self._WEB_COMMANDS:
            if self._starts_with_command(
                command_text,
                command,
            ):
                return ActionRequest(
                    requested=True,
                    category="web",
                    action=command,
                    required_capability="web_actions",
                    confidence=1.0,
                    reason=(
                        "Direct live web action request."
                    ),
                )

        # -----------------------------------------------------
        # FILESYSTEM ACTIONS
        # -----------------------------------------------------

        for verb in self._FILESYSTEM_VERBS:
            if self._starts_with_command(
                command_text,
                verb,
            ):
                return ActionRequest(
                    requested=True,
                    category="filesystem",
                    action=verb,
                    required_capability=(
                        "filesystem_actions"
                    ),
                    confidence=1.0,
                    reason=(
                        "Direct filesystem-changing request."
                    ),
                )

        filesystem_creation = (
            self._detect_filesystem_creation(
                command_text
            )
        )

        if filesystem_creation is not None:
            return ActionRequest(
                requested=True,
                category="filesystem",
                action=filesystem_creation,
                required_capability=(
                    "filesystem_actions"
                ),
                confidence=1.0,
                reason=(
                    "Direct filesystem-changing request."
                ),
            )

        # -----------------------------------------------------
        # SYSTEM / APPLICATION ACTIONS
        # -----------------------------------------------------

        for verb in self._SYSTEM_VERBS:
            if self._starts_with_command(
                command_text,
                verb,
            ):
                return ActionRequest(
                    requested=True,
                    category="system",
                    action=verb,
                    required_capability="system_actions",
                    confidence=1.0,
                    reason=(
                        "Direct operating-system or "
                        "application action request."
                    ),
                )

        # -----------------------------------------------------
        # OTHER EXTERNAL ACTIONS
        # -----------------------------------------------------

        for verb in self._GENERIC_EXTERNAL_VERBS:
            if self._starts_with_command(
                command_text,
                verb,
            ):
                return ActionRequest(
                    requested=True,
                    category="external",
                    action=verb,
                    required_capability=(
                        "execution_actions"
                    ),
                    confidence=1.0,
                    reason=(
                        "Direct external action request."
                    ),
                )

        return self._not_requested(
            "No deterministic direct external action "
            "pattern matched."
        )

    @classmethod
    def _is_capability_status_question(
        cls,
        text: str,
    ) -> bool:
        plain = text.rstrip(" ?.!")

        if any(
            plain.startswith(prefix)
            for prefix in (
                "which capabilities",
                "what capabilities",
                "what can you do",
                "what are you able to do",
            )
        ):
            return True

        capability_hits = tuple(
            phrase
            for phrase in cls._CAPABILITY_STATUS_PHRASES
            if phrase in plain
        )

        if not capability_hits:
            return False

        if any(
            context in plain
            for context in cls._CAPABILITY_STATUS_CONTEXT
        ):
            return True

        remainder = None

        for prefix in (
            "can you ",
            "could you ",
            "are you able to ",
        ):
            if plain.startswith(prefix):
                remainder = plain[len(prefix):].strip()
                break

        if remainder is None:
            return False

        if len(capability_hits) >= 2:
            return True

        allowed_suffixes = (
            "",
            " right now",
            " currently",
            " in this running cauvis instance",
            " in this cauvis instance",
            " in this running instance",
        )

        for phrase in cls._CAPABILITY_STATUS_PHRASES:
            for suffix in allowed_suffixes:
                if remainder == phrase + suffix:
                    return True

        return False

    @classmethod
    def _is_instructional(
        cls,
        text: str,
    ) -> bool:
        return any(
            text.startswith(prefix)
            for prefix in cls._INSTRUCTIONAL_PREFIXES
        )

    @classmethod
    def _strip_polite_prefix(
        cls,
        text: str,
    ) -> str:
        for prefix in cls._POLITE_PREFIXES:
            if text.startswith(prefix):
                return text[
                    len(prefix):
                ].strip()

        return text

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:
        return " ".join(
            text.lower().strip().split()
        )

    @staticmethod
    def _starts_with_command(
        text: str,
        command: str,
    ) -> bool:
        return (
            text == command
            or text.startswith(
                command + " "
            )
        )

    @classmethod
    def _detect_filesystem_creation(
        cls,
        text: str,
    ) -> str | None:
        for verb in (
            "create",
            "make",
            "save",
            "write",
        ):
            if not cls._starts_with_command(
                text,
                verb,
            ):
                continue

            if any(
                hint in text
                for hint in cls._FILESYSTEM_OBJECT_HINTS
            ):
                return verb

        return None

    @staticmethod
    def _detect_reminder(
        text: str,
    ) -> str | None:
        reminder_prefixes = (
            "remind me",
            "set a reminder",
            "create a reminder",
            "schedule a reminder",
        )

        for prefix in reminder_prefixes:
            if (
                text == prefix
                or text.startswith(
                    prefix + " "
                )
            ):
                return prefix

        return None

    @staticmethod
    def _not_requested(
        reason: str,
    ) -> ActionRequest:
        return ActionRequest(
            requested=False,
            confidence=0.0,
            reason=reason,
        )
