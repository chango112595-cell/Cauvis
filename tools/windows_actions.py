import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable
import webbrowser


Launcher = Callable[[list[str]], Any]
BrowserOpener = Callable[[str], bool]


class WindowsActionRuntime:
    """Bounded Windows handlers: known app launch + URL open only."""

    _ALIASES = {
        "notepad": "notepad.exe",
        "notepad.exe": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "calc.exe": "calc.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "file explorer": "explorer.exe",
        "explorer": "explorer.exe",
        "windows explorer": "explorer.exe",
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
    }

    def __init__(
        self,
        *,
        launcher: Launcher | None = None,
        browser_opener: BrowserOpener | None = None,
        environment: dict[str, str] | None = None,
    ):
        self._launcher = launcher or self._default_launcher
        self._browser_opener = browser_opener or webbrowser.open
        self.environment = (
            environment
            if environment is not None
            else dict(os.environ)
        )

    def resolve_application(self, application: str) -> str:
        value = " ".join(
            str(application).lower().strip().split()
        )
        command = self._ALIASES.get(value, value)

        direct = shutil.which(command)
        if direct:
            return direct

        if command in {
            "notepad.exe",
            "calc.exe",
            "mspaint.exe",
            "explorer.exe",
        }:
            return command

        if command == "chrome.exe":
            candidates = (
                Path(self.environment.get("PROGRAMFILES", ""))
                / "Google/Chrome/Application/chrome.exe",
                Path(self.environment.get("PROGRAMFILES(X86)", ""))
                / "Google/Chrome/Application/chrome.exe",
                Path(self.environment.get("LOCALAPPDATA", ""))
                / "Google/Chrome/Application/chrome.exe",
            )
            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)

        if command == "msedge.exe":
            candidates = (
                Path(self.environment.get("PROGRAMFILES(X86)", ""))
                / "Microsoft/Edge/Application/msedge.exe",
                Path(self.environment.get("PROGRAMFILES", ""))
                / "Microsoft/Edge/Application/msedge.exe",
            )
            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)

        raise RuntimeError(
            "Application is not currently resolvable: "
            + str(application)
        )

    def launch_application(
        self,
        application: str,
        url: str | None = None,
    ) -> dict[str, Any]:
        executable = self.resolve_application(application)
        command = [executable]

        if url:
            command.append(str(url))

        process = self._launcher(command)

        pid = getattr(process, "pid", None)
        running = None

        poll = getattr(process, "poll", None)
        if callable(poll):
            try:
                running = poll() is None
            except Exception:
                running = None

        return {
            "application": application,
            "executable": executable,
            "command": list(command),
            "pid": pid,
            "launch_request_completed": True,
            "process_running_observed": running,
            "url": url,
        }

    def open_url(self, url: str) -> dict[str, Any]:
        normalized = self._normalize_url(url)
        accepted = bool(self._browser_opener(normalized))

        if not accepted:
            raise RuntimeError(
                "The default browser did not accept the URL request."
            )

        return {
            "url": normalized,
            "browser_request_accepted": True,
            "visual_page_open_verified": False,
        }

    @staticmethod
    def _normalize_url(url: str) -> str:
        value = str(url).strip()

        if not value:
            raise ValueError("URL cannot be empty.")

        if not value.lower().startswith(("http://", "https://")):
            value = "https://" + value

        return value

    @staticmethod
    def _default_launcher(command: list[str]):
        if os.name != "nt":
            raise RuntimeError(
                "Windows application launching is available only on Windows."
            )

        return subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
