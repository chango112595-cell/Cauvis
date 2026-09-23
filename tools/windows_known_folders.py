import os
from pathlib import Path
from typing import Mapping


class WindowsKnownFolderResolver:
    """
    Resolve user folders from Windows' User Shell Folders registry.

    Falls back to existing profile/OneDrive paths when registry access
    is unavailable. No hard-coded username paths are used.
    """

    _REGISTRY_NAMES = {
        "desktop": "Desktop",
        "documents": "Personal",
        "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    }

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        overrides: Mapping[str, str | Path] | None = None,
    ):
        self.home = Path(
            home if home is not None else Path.home()
        ).resolve()
        self.overrides = {
            str(k).lower(): Path(v).expanduser().resolve(strict=False)
            for k, v in dict(overrides or {}).items()
        }

    def resolve(self, name: str) -> Path | None:
        key = str(name).strip().lower()

        if key in self.overrides:
            return self.overrides[key]

        registered = self._registry_path(key)

        if registered is not None and registered.is_dir():
            return registered

        for candidate in self._fallback_candidates(key):
            if candidate.is_dir():
                return candidate.resolve(strict=False)

        return None

    def _registry_path(self, key: str) -> Path | None:
        value_name = self._REGISTRY_NAMES.get(key)

        if value_name is None or os.name != "nt":
            return None

        try:
            import winreg

            registry_path = (
                r"Software\Microsoft\Windows\CurrentVersion"
                r"\Explorer\User Shell Folders"
            )

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                registry_path,
            ) as handle:
                value, _ = winreg.QueryValueEx(
                    handle,
                    value_name,
                )

            expanded = os.path.expandvars(
                str(value)
            )

            return Path(expanded).expanduser().resolve(strict=False)

        except Exception:
            return None

    def _fallback_candidates(self, key: str) -> tuple[Path, ...]:
        folder_name = {
            "desktop": "Desktop",
            "documents": "Documents",
            "downloads": "Downloads",
        }.get(key)

        if folder_name is None:
            return ()

        return (
            self.home / folder_name,
            self.home / "OneDrive" / folder_name,
        )
