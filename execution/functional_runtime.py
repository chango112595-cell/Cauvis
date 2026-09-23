from dataclasses import dataclass
from pathlib import Path

from capabilities.registry import Capability, CapabilityRegistry
from execution.action_bridge import ActionExecutionBridge
from execution.engine import ExecutionEngine
from execution.pending_actions import PendingActionManager
from security.permissions import PermissionManager
from tools.filesystem_actions import FilesystemActionRuntime
from tools.registry import Tool, ToolRegistry
from tools.system_diagnostics import SystemDiagnosticsRuntime
from tools.windows_actions import WindowsActionRuntime
from tools.windows_known_folders import WindowsKnownFolderResolver
from verification.verifier import VerificationEngine


@dataclass
class FunctionalExecutionRuntime:
    capability_registry: CapabilityRegistry
    tool_registry: ToolRegistry
    permission_manager: PermissionManager
    verification_engine: VerificationEngine
    execution_engine: ExecutionEngine
    action_bridge: ActionExecutionBridge
    windows_runtime: WindowsActionRuntime
    filesystem_runtime: FilesystemActionRuntime
    known_folders: WindowsKnownFolderResolver
    diagnostics_runtime: SystemDiagnosticsRuntime
    pending_actions: PendingActionManager


def build_functional_execution_runtime(
    *,
    project_root: str | Path,
    windows_runtime: WindowsActionRuntime | None = None,
    filesystem_runtime: FilesystemActionRuntime | None = None,
    known_folders: WindowsKnownFolderResolver | None = None,
    diagnostics_runtime: SystemDiagnosticsRuntime | None = None,
    pending_actions: PendingActionManager | None = None,
) -> FunctionalExecutionRuntime:
    root = Path(project_root).resolve()

    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    permissions = PermissionManager()
    verifier = VerificationEngine()

    windows = windows_runtime or WindowsActionRuntime()

    filesystem = (
        filesystem_runtime
        or FilesystemActionRuntime(
            project_root=root
        )
    )

    if known_folders is not None:
        folders = known_folders

    elif filesystem.home != Path.home().resolve():
        sandbox_home = filesystem.home

        def sandbox_known_folder(name: str) -> Path:
            direct = (
                sandbox_home / name
            ).resolve(strict=False)

            onedrive = (
                sandbox_home / "OneDrive" / name
            ).resolve(strict=False)

            if direct.is_dir():
                return direct

            if onedrive.is_dir():
                return onedrive

            return direct

        folders = WindowsKnownFolderResolver(
            home=sandbox_home,
            overrides={
                "desktop": sandbox_known_folder(
                    "Desktop"
                ),
                "documents": sandbox_known_folder(
                    "Documents"
                ),
                "downloads": sandbox_known_folder(
                    "Downloads"
                ),
            },
        )

    else:
        folders = WindowsKnownFolderResolver(
            home=filesystem.home
        )

    diagnostics = (
        diagnostics_runtime
        or SystemDiagnosticsRuntime()
    )

    pending = (
        pending_actions
        or PendingActionManager()
    )

    for name, description, category in (
        (
            "execution_actions",
            "Bound external action execution.",
            "execution",
        ),
        (
            "system_actions",
            "Known application launching and read-only system diagnostics.",
            "system",
        ),
        (
            "filesystem_actions",
            "Bounded file read/create/write actions.",
            "filesystem",
        ),
        (
            "web_actions",
            "Open one or more URLs through a bound browser handler.",
            "web",
        ),
    ):
        capabilities.register(
            Capability(
                name=name,
                description=description,
                category=category,
            )
        )

    tools.register(
        Tool(
            name="application.launch",
            description="Launch a known Windows application.",
            capabilities={
                "execution_actions",
                "system_actions",
            },
            handler=windows.launch_application,
            metadata={
                "permission_action": "application.launch",
                "phase": "3B",
            },
        )
    )

    tools.register(
        Tool(
            name="web.open_url",
            description="Send an HTTP(S) URL to the default browser.",
            capabilities={
                "execution_actions",
                "system_actions",
                "web_actions",
            },
            handler=windows.open_url,
            metadata={
                "permission_action": "web.open_url",
                "phase": "3B",
            },
        )
    )

    tools.register(
        Tool(
            name="filesystem.read",
            description="Read a bounded text file.",
            capabilities={
                "execution_actions",
                "filesystem_actions",
            },
            handler=filesystem.read_text,
            metadata={
                "permission_action": "filesystem.read",
                "phase": "3B",
            },
        )
    )

    tools.register(
        Tool(
            name="filesystem.write",
            description="Create or explicitly overwrite a bounded text file.",
            capabilities={
                "execution_actions",
                "filesystem_actions",
            },
            handler=filesystem.write_text,
            metadata={
                "permission_action": "filesystem.write",
                "phase": "3B",
            },
        )
    )

    tools.register(
        Tool(
            name="system.performance_snapshot",
            description=(
                "Collect a read-only Windows CPU, memory, disk, uptime, "
                "and process snapshot."
            ),
            capabilities={
                "execution_actions",
                "system_actions",
            },
            handler=diagnostics.performance_snapshot,
            metadata={
                "permission_action": "system.info",
                "phase": "3B",
                "read_only": True,
            },
        )
    )

    engine = ExecutionEngine(
        capability_registry=capabilities,
        tool_registry=tools,
        permission_manager=permissions,
        verification_engine=verifier,
    )

    bridge = ActionExecutionBridge(
        execution_engine=engine,
        permission_manager=permissions,
        project_root=root,
        home=filesystem.home,
        known_folders=folders,
        pending_actions=pending,
    )

    return FunctionalExecutionRuntime(
        capability_registry=capabilities,
        tool_registry=tools,
        permission_manager=permissions,
        verification_engine=verifier,
        execution_engine=engine,
        action_bridge=bridge,
        windows_runtime=windows,
        filesystem_runtime=filesystem,
        known_folders=folders,
        diagnostics_runtime=diagnostics,
        pending_actions=pending,
    )
