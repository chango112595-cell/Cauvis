from pathlib import Path
from typing import Any


class FilesystemActionRuntime:
    """
    Functional-v1 filesystem handlers.

    Writes are limited to the current user's home directory or Cauvis
    project root. Delete operations are intentionally absent.
    """

    def __init__(
        self,
        *,
        project_root: str | Path,
        home: str | Path | None = None,
        max_read_bytes: int = 262_144,
    ):
        self.project_root = Path(project_root).resolve()
        self.home = Path(
            home if home is not None else Path.home()
        ).resolve()
        self.max_read_bytes = int(max_read_bytes)

        if self.max_read_bytes <= 0:
            raise ValueError(
                "max_read_bytes must be greater than zero."
            )

    def allowed_roots(self) -> tuple[Path, ...]:
        roots = []
        for root in (self.home, self.project_root):
            if root not in roots:
                roots.append(root)
        return tuple(roots)

    def is_allowed_path(self, path: str | Path) -> bool:
        target = Path(path).expanduser()

        try:
            resolved = target.resolve(strict=False)
        except Exception:
            return False

        for root in self.allowed_roots():
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue

        return False

    def read_text(self, path: str | Path) -> dict[str, Any]:
        target = self._require_allowed(path)

        if not target.is_file():
            raise FileNotFoundError(
                "File does not exist: " + str(target)
            )

        size = target.stat().st_size

        if size > self.max_read_bytes:
            raise RuntimeError(
                "File is larger than the functional-v1 read limit of "
                + str(self.max_read_bytes)
                + " bytes."
            )

        content = target.read_text(
            encoding="utf-8",
            errors="replace",
        )

        return {
            "path": str(target),
            "content": content,
            "bytes": size,
            "verified_exists": target.is_file(),
        }

    def write_text(
        self,
        path: str | Path,
        content: str = "",
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        target = self._require_allowed(path)

        if not target.parent.is_dir():
            raise FileNotFoundError(
                "Parent directory does not exist: "
                + str(target.parent)
            )

        if target.exists() and not overwrite:
            raise FileExistsError(
                "File already exists. Say overwrite or replace to "
                "explicitly replace it: "
                + str(target)
            )

        text = str(content)

        target.write_text(
            text,
            encoding="utf-8",
        )

        verified = (
            target.is_file()
            and target.read_text(
                encoding="utf-8",
                errors="replace",
            )
            == text
        )

        if not verified:
            raise RuntimeError(
                "File write completed but verification failed."
            )

        return {
            "path": str(target),
            "bytes": target.stat().st_size,
            "created": True,
            "overwrite": bool(overwrite),
            "verified_exists": True,
            "verified_content": True,
        }

    def _require_allowed(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser().resolve(strict=False)

        if not self.is_allowed_path(resolved):
            raise PermissionError(
                "Functional-v1 filesystem access is limited to the "
                "current user's home directory and Cauvis project directory."
            )

        return resolved
