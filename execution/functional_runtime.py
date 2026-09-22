from dataclasses import dataclass
from pathlib import Path

from capabilities.registry import Capability, CapabilityRegistry
from execution.action_bridge import ActionExecutionBridge
from execution.engine import ExecutionEngine
from security.permissions import PermissionManager
from tools.filesystem_actions import FilesystemActionRuntime
from tools.registry import Tool, ToolRegistry
from tools.windows_actions import WindowsActionRuntime
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


def build_functional_execution_runtime(
    *,
    project_root: str | Path,
    windows_runtime: WindowsActionRuntime | None = None,
    filesystem_runtime: FilesystemActionRuntime | None = None,
) -> FunctionalExecutionRuntime:
    root = Path(project_root).resolve()

    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    permissions = PermissionManager()
    verifier = VerificationEngine()

    windows = windows_runtime or WindowsActionRuntime()
    filesystem = filesystem_runtime or FilesystemActionRuntime(
        project_root=root
    )

    for name, description, category in (
        (
            "execution_actions",
            "Bound external action execution.",
            "execution",
        ),
        (
            "system_actions",
            "Known application launching and bounded system actions.",
            "system",
        ),
        (
            "filesystem_actions",
            "Bounded file read/create/write actions.",
            "filesystem",
        ),
        (
            "web_actions",
            "Open a URL through a bound browser handler.",
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
                "functional_core": True,
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
                "functional_core": True,
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
                "functional_core": True,
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
                "functional_core": True,
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
    )
