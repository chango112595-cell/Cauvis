from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class VerificationStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class VerificationResult:
    """Result of checking whether an expected outcome occurred."""

    success: bool
    status: VerificationStatus
    description: str
    expected: Any = None
    actual: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class VerificationCheck:
    """
    A reusable verification check.

    The check function should return True when the
    expected outcome has actually occurred.
    """

    name: str
    description: str
    check: Callable[[], bool]
    expected: Any = None


class VerificationEngine:
    """
    Verifies whether requested outcomes actually occurred.

    Verification is intentionally separate from execution.
    A tool saying "success" is not treated as proof that
    the requested outcome actually happened.
    """

    def __init__(self):
        self._checks: dict[str, VerificationCheck] = {}

    # ---------------------------------------------------------
    # REGISTRATION
    # ---------------------------------------------------------

    def register(
        self,
        verification: VerificationCheck,
    ) -> None:
        """Register a reusable verification check."""

        if not verification.name.strip():
            raise ValueError(
                "Verification name cannot be empty."
            )

        self._checks[
            verification.name
        ] = verification

    def unregister(
        self,
        name: str,
    ) -> None:
        """Remove a verification check."""

        self._checks.pop(name, None)

    # ---------------------------------------------------------
    # DISCOVERY
    # ---------------------------------------------------------

    def get(
        self,
        name: str,
    ) -> VerificationCheck | None:
        """Return a verification check by name."""

        return self._checks.get(name)

    def has(
        self,
        name: str,
    ) -> bool:
        """Determine whether a verification check exists."""

        return name in self._checks

    def list_all(
        self,
    ) -> list[VerificationCheck]:
        """Return all registered verification checks."""

        return list(
            self._checks.values()
        )

    # ---------------------------------------------------------
    # GENERIC VERIFICATION
    # ---------------------------------------------------------

    def verify(
        self,
        name: str,
    ) -> VerificationResult:
        """Run a registered verification check."""

        verification = self.get(name)

        if verification is None:
            return VerificationResult(
                success=False,
                status=VerificationStatus.FAILED,
                description=(
                    f"Unknown verification check: {name}"
                ),
                error=(
                    "Verification check is not registered."
                ),
            )

        try:
            result = verification.check()

            if result:
                return VerificationResult(
                    success=True,
                    status=VerificationStatus.VERIFIED,
                    description=verification.description,
                    expected=verification.expected,
                    actual=True,
                )

            return VerificationResult(
                success=False,
                status=VerificationStatus.FAILED,
                description=verification.description,
                expected=verification.expected,
                actual=False,
                error=(
                    "The verification condition "
                    "was not satisfied."
                ),
            )

        except Exception as exc:
            return VerificationResult(
                success=False,
                status=VerificationStatus.FAILED,
                description=verification.description,
                expected=verification.expected,
                error=str(exc),
            )

    def verify_condition(
        self,
        description: str,
        condition: Callable[[], bool],
        expected: Any = None,
    ) -> VerificationResult:
        """
        Directly verify a condition without registering it.
        """

        try:
            result = condition()

            if result:
                return VerificationResult(
                    success=True,
                    status=VerificationStatus.VERIFIED,
                    description=description,
                    expected=expected,
                    actual=True,
                )

            return VerificationResult(
                success=False,
                status=VerificationStatus.FAILED,
                description=description,
                expected=expected,
                actual=False,
                error=(
                    "The verification condition "
                    "was not satisfied."
                ),
            )

        except Exception as exc:
            return VerificationResult(
                success=False,
                status=VerificationStatus.FAILED,
                description=description,
                expected=expected,
                error=str(exc),
            )

    # ---------------------------------------------------------
    # FILESYSTEM VERIFICATION
    # ---------------------------------------------------------

    def verify_file_exists(
        self,
        path: str | Path,
    ) -> VerificationResult:
        """
        Verify that a file actually exists.

        This does not create, modify, or delete anything.
        """

        target = Path(path)

        return self.verify_condition(
            description=(
                f"Verify that file exists: {target}"
            ),
            condition=target.is_file,
            expected=True,
        )

    def verify_directory_exists(
        self,
        path: str | Path,
    ) -> VerificationResult:
        """
        Verify that a directory actually exists.

        This does not create, modify, or delete anything.
        """

        target = Path(path)

        return self.verify_condition(
            description=(
                f"Verify that directory exists: {target}"
            ),
            condition=target.is_dir,
            expected=True,
        )

    def verify_path_not_exists(
        self,
        path: str | Path,
    ) -> VerificationResult:
        """
        Verify that a file or directory does not exist.
        """

        target = Path(path)

        return self.verify_condition(
            description=(
                f"Verify that path does not exist: {target}"
            ),
            condition=lambda: not target.exists(),
            expected=False,
        )

    # ---------------------------------------------------------
    # INFORMATION
    # ---------------------------------------------------------

    def count(self) -> int:
        """Return the number of registered checks."""

        return len(self._checks)