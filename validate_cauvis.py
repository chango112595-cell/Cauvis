from pathlib import Path
import subprocess
import sys
import time
import traceback

from core.config import CauvisConfig
from core.orchestrator import CauvisOrchestrator

from intelligence.task import (
    TaskAnalyzer,
    TaskComplexity,
    TaskRequirements,
)
from intelligence.device import DeviceProfiler
from intelligence.policy import AdaptivePolicyEngine
from intelligence.capabilities import CapabilityMapper
from intelligence.reasoning import (
    ReasoningEngine,
    ReasoningResult,
)
from intelligence.models import ModelRequest, ModelResponse
from intelligence.router import ModelProvider
from intelligence.router import AIModelRouter
from intelligence.brain import CauvisBrain

from capabilities.registry import Capability, CapabilityRegistry

from security.permissions import PermissionLevel, PermissionManager

from tools.registry import Tool, ToolRegistry

from verification.verifier import VerificationEngine

from execution.workers import (
    Worker,
    WorkerRegistry,
    WorkerPool,
    WorkerTask,
    WorkerTaskType,
)

from execution.scheduler import (
    WorkerScheduler,
    SchedulingStrategy,
)

from execution.aem import (
    AEMRegistry,
    AEMStrategy,
    AEMTask,
    SequentialAEM,
    DependencyGraphAEM,
)

from execution.engine import ExecutionEngine
from execution.planner import AdaptiveExecutionPlan, AdaptiveTaskPlanner
from execution.worker_catalog import WorkerCatalog


PASSED = 0
FAILED = 0
START_TIME = time.perf_counter()


def test(number, name, function):
    global PASSED, FAILED

    print(f"\n[{number:02d}] {name}")
    print("-" * 60)

    try:
        result = function()

        if result is False:
            raise AssertionError("Test returned False.")

        PASSED += 1
        print("PASS")
        return True

    except Exception as exc:
        FAILED += 1
        print(f"FAIL: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

class FakeProvider(ModelProvider):
    def __init__(self, name="fake-cloud", provider_type="cloud"):
        self._name = name
        self._provider_type = provider_type

    @property
    def name(self):
        return self._name

    @property
    def provider_type(self):
        return self._provider_type

    def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text=f"FAKE RESPONSE: {request.prompt}",
            model="fake-model",
            provider=self.name,
            success=True,
        )


def build_router():
    router = AIModelRouter()

    router.register_provider(
        FakeProvider("fake-cloud", "cloud")
    )

    router.register_provider(
        FakeProvider("fake-local", "local")
    )

    return router


def build_worker_registry():
    registry = WorkerRegistry()

    registry.register(
        Worker(
            name="general_worker",
            description="General worker",
            capabilities={"chat", "general"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: f"GENERAL: {task.payload}",
        )
    )

    registry.register(
        Worker(
            name="research_worker",
            description="Research worker",
            capabilities={"web", "research"},
            task_types={WorkerTaskType.RESEARCH},
            handler=lambda task: f"RESEARCH: {task.payload}",
        )
    )

    registry.register(
        Worker(
            name="code_worker",
            description="Code worker",
            capabilities={"code"},
            task_types={WorkerTaskType.CODE},
            handler=lambda task: f"CODE: {task.payload}",
        )
    )

    registry.register(
        Worker(
            name="verification_worker",
            description="Verification worker",
            capabilities={"verification"},
            task_types={WorkerTaskType.VERIFICATION},
            handler=lambda task: f"VERIFIED: {task.payload}",
        )
    )

    return registry


def build_aem_registry():
    registry = build_worker_registry()

    scheduler = WorkerScheduler(
        registry,
        SchedulingStrategy.ROUND_ROBIN,
    )

    return AEMRegistry(scheduler)


# ------------------------------------------------------------
# 01 Compilation
# ------------------------------------------------------------

def test_compilation():
    root = Path(__file__).resolve().parent

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            str(root),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)

    return True


# ------------------------------------------------------------
# 02 Core
# ------------------------------------------------------------

def test_core():
    config = CauvisConfig()
    cauvis = CauvisOrchestrator(config)

    response = cauvis.handle("hello")

    assert config.name == "Cauvis"
    assert response.status == "success"
    assert response.intent == "greeting"

    return True


# ------------------------------------------------------------
# 03 Intent
# ------------------------------------------------------------

def test_intent():
    from core.intent import IntentDetector

    detector = IntentDetector()

    assert detector.detect("hello").name == "greeting"
    assert detector.detect("what is this").name == "question"
    assert detector.detect("shutdown").name == "shutdown"

    return True


# ------------------------------------------------------------
# 04 Task Analyzer
# ------------------------------------------------------------

def test_task_analyzer():
    analyzer = TaskAnalyzer()

    task = analyzer.analyze(
        "Build a Python program that searches the web and analyzes a screenshot."
    )

    assert task.complexity.value == "high"
    assert task.requires_tools
    assert task.requires_internet
    assert task.requires_vision
    assert task.requires_code

    return True


# ------------------------------------------------------------
# 05 Device
# ------------------------------------------------------------

def test_device():
    profiler = DeviceProfiler()
    profile = profiler.profile()

    assert profile.operating_system
    assert profile.operating_system_version
    assert profile.architecture
    assert profile.processor
    assert profile.cpu_threads > 0
    assert profile.memory_gb > 0
    assert isinstance(profile.gpu_names, list)
    assert isinstance(profile.gpu_memory_gb, list)

    print(f"OS: {profile.operating_system}")
    print(f"CPU: {profile.processor}")
    print(f"RAM: {profile.memory_gb:.2f} GB")
    print(f"GPU: {profile.gpu_names}")

    return True


# ------------------------------------------------------------
# 06 Policy
# ------------------------------------------------------------

def test_policy():
    analyzer = TaskAnalyzer()
    profiler = DeviceProfiler()
    policy = AdaptivePolicyEngine()

    task = analyzer.analyze(
        "Build a Python program that searches the web and analyzes a screenshot."
    )

    profile = profiler.profile()

    result = policy.evaluate(profile, task)

    assert result is not None

    print(f"POLICY: {result}")

    return True


# ------------------------------------------------------------
# 07 Capability Mapping
# ------------------------------------------------------------

def test_capability_mapping():
    analyzer = TaskAnalyzer()
    mapper = CapabilityMapper()

    task = analyzer.analyze(
        "Build a Python program that searches the web and analyzes a screenshot."
    )

    capabilities = mapper.map(task)

    required = {
        "chat",
        "code",
        "vision",
        "web",
        "tools",
        "reasoning",
        "complexity:high",
    }

    assert required.issubset(capabilities.capabilities)

    print("CAPABILITIES:", sorted(capabilities.capabilities))

    return True


# ------------------------------------------------------------
# 08 Reasoning
# ------------------------------------------------------------

def test_reasoning():
    reasoning = ReasoningEngine()
    analyzer = TaskAnalyzer()

    task = analyzer.analyze(
        "Build a Python program that searches the web and analyzes a screenshot."
    )

    result = reasoning.analyze(
        user_input="Build a Python program that searches the web and analyzes a screenshot.",
        task=task,
    )

    assert result is not None
    assert len(result.steps) > 0
    assert result.task_requirements is not None

    print(f"STEPS: {len(result.steps)}")
    print(f"GOAL: {result.goal}")

    return True


# ------------------------------------------------------------
# 09 Brain
# ------------------------------------------------------------

def test_brain():
    brain = CauvisBrain(build_router())

    analysis = brain.analyze(
        "Build a Python program that searches the web and analyzes a screenshot."
    )

    assert analysis is not None
    assert analysis.task is not None
    assert analysis.reasoning is not None

    response = brain.think("What is Cauvis?")

    assert response.success
    assert response.text

    print("ANALYSIS READY")
    print("MODEL RESPONSE:", response.text)

    return True


# ------------------------------------------------------------
# 10 Capability Registry
# ------------------------------------------------------------

def test_capability_registry():
    registry = CapabilityRegistry()

    registry.register(
        Capability(
            name="web",
            description="Web access",
            category="internet",
        )
    )

    registry.register(
        Capability(
            name="vision",
            description="Vision",
            category="ai",
        )
    )

    registry.register(
        Capability(
            name="code",
            description="Code",
            category="ai",
        )
    )

    assert registry.has("web")
    assert registry.has("vision")
    assert registry.enabled_count() == 3
    assert "filesystem" in registry.missing({"web", "filesystem"})

    return True


# ------------------------------------------------------------
# 11 Security
# ------------------------------------------------------------

def test_security():
    manager = PermissionManager()

    safe = manager.evaluate("web.search")
    approval = manager.evaluate("filesystem.write")
    dangerous = manager.evaluate("terminal.execute")
    unknown = manager.evaluate("unknown.action")

    assert safe.level == PermissionLevel.SAFE
    assert approval.level == PermissionLevel.APPROVAL_REQUIRED
    assert dangerous.level == PermissionLevel.HIGH_RISK
    assert unknown.level == PermissionLevel.DENIED

    print("web.search:", safe.level)
    print("filesystem.write:", approval.level)
    print("terminal.execute:", dangerous.level)
    print("unknown.action:", unknown.level)

    return True


# ------------------------------------------------------------
# 12 Tools
# ------------------------------------------------------------

def test_tools():
    registry = ToolRegistry()

    registry.register(
        Tool(
            name="browser_search",
            description="Search the web",
            capabilities={"web"},
            handler=lambda query: f"SEARCHED: {query}",
        )
    )

    result = registry.execute(
        "browser_search",
        "Cauvis architecture",
    )

    assert result.success
    assert "Cauvis architecture" in result.output

    return True


# ------------------------------------------------------------
# 13 Verification
# ------------------------------------------------------------

def test_verification():
    verifier = VerificationEngine()

    result = verifier.verify_file_exists(".\\cauvis.py")

    assert result.success
    assert result.status.value == "verified"

    failed = verifier.verify_file_exists(
        ".\\this_file_should_not_exist_123456.py"
    )

    assert not failed.success

    return True


# ------------------------------------------------------------
# 14 Worker
# ------------------------------------------------------------

def test_worker():
    worker = Worker(
        name="test_worker",
        description="Test worker",
        capabilities={"general"},
        task_types={WorkerTaskType.GENERAL},
        handler=lambda task: f"DONE: {task.payload}",
    )

    task = WorkerTask(
        name="test_task",
        payload="hello",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"general"},
    )

    result = worker.execute(task)

    assert result.success
    assert result.output == "DONE: hello"
    assert worker.metrics.tasks_completed == 1

    return True


# ------------------------------------------------------------
# 15 Worker Pool
# ------------------------------------------------------------

def test_worker_pool():
    registry = build_worker_registry()
    pool = WorkerPool(registry, max_workers=4)

    assert pool.active
    assert pool.worker_count() == 4

    task = WorkerTask(
        name="research",
        payload="test",
        task_type=WorkerTaskType.RESEARCH,
        required_capabilities={"web", "research"},
    )

    candidates = pool.submit(task)

    assert len(candidates) == 1
    assert candidates[0].name == "research_worker"

    result = candidates[0].execute(task)
    pool.record_result(result)

    assert result.success
    assert pool.stats()["completed"] == 1

    return True


# ------------------------------------------------------------
# 16 Scheduler
# ------------------------------------------------------------

def test_scheduler():
    registry = build_worker_registry()

    scheduler = WorkerScheduler(
        registry,
        SchedulingStrategy.ROUND_ROBIN,
    )

    task = WorkerTask(
        name="research_task",
        payload="Cauvis",
        task_type=WorkerTaskType.RESEARCH,
        required_capabilities={"web", "research"},
    )

    worker = scheduler.select_worker(task)

    assert worker is not None
    assert worker.name == "research_worker"

    result = scheduler.dispatch(task)

    assert result.worker_name == "research_worker"
    assert result.worker_result is not None
    assert result.worker_result.success

    print("WORKER:", result.worker_name)
    print("OUTPUT:", result.worker_result.output)

    return True


# ------------------------------------------------------------
# AEM helper
# ------------------------------------------------------------

def run_aem(strategy, tasks):
    registry = build_aem_registry()

    aem = registry.get(strategy)

    assert aem is not None, f"AEM not registered: {strategy}"

    result = aem.execute(tasks)

    assert result.strategy == strategy

    return result


# ------------------------------------------------------------
# 17 Sequential AEM
# ------------------------------------------------------------

def test_sequential_aem():
    tasks = [
        AEMTask(
            name="one",
            payload="A",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="two",
            payload="B",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
    ]

    result = run_aem(AEMStrategy.SEQUENTIAL, tasks)

    assert result.success
    assert result.completed_tasks == 2
    assert result.total_tasks == 2
    assert len(result.results) == 2

    return True


# ------------------------------------------------------------
# 18 Parallel AEM
# ------------------------------------------------------------

def test_parallel_aem():
    tasks = [
        AEMTask(
            name="one",
            payload="A",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="two",
            payload="B",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="three",
            payload="C",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
    ]

    result = run_aem(AEMStrategy.PARALLEL, tasks)

    assert result.success
    assert result.completed_tasks == 3
    assert result.total_tasks == 3

    return True


# ------------------------------------------------------------
# 19 Priority AEM
# ------------------------------------------------------------

def test_priority_aem():
    tasks = [
        AEMTask(
            name="low",
            payload="LOW",
            priority=100,
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="high",
            payload="HIGH",
            priority=1,
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
    ]

    result = run_aem(AEMStrategy.PRIORITY, tasks)

    assert result.success
    assert result.completed_tasks == 2

    return True


# ------------------------------------------------------------
# 20 Retry AEM
# ------------------------------------------------------------

def test_retry_aem():
    attempts = {"count": 0}

    registry = build_worker_registry()

    worker = registry.get("general_worker")

    original_handler = worker.handler

    def retry_handler(task):
        attempts["count"] += 1

        if attempts["count"] == 1:
            raise RuntimeError("intentional first failure")

        return original_handler(task)

    worker.handler = retry_handler

    scheduler = WorkerScheduler(registry)

    aem_registry = AEMRegistry(scheduler)
    aem = aem_registry.get(AEMStrategy.RETRY)

    assert aem is not None

    task = AEMTask(
        name="retry_test",
        payload="retry",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"general"},
    )

    result = aem.execute([task])

    assert result.success
    assert attempts["count"] >= 2

    return True


# ------------------------------------------------------------
# 21 Fallback AEM
# ------------------------------------------------------------

def test_fallback_aem():
    registry = WorkerRegistry()

    registry.register(
        Worker(
            name="worker_A",
            description="Fails",
            capabilities={"general"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: (_ for _ in ()).throw(
                RuntimeError("worker A failed")
            ),
        )
    )

    registry.register(
        Worker(
            name="worker_B",
            description="Succeeds",
            capabilities={"general"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: "SUCCESS FROM WORKER B",
        )
    )

    scheduler = WorkerScheduler(registry)

    aem_registry = AEMRegistry(scheduler)
    aem = aem_registry.get(AEMStrategy.FALLBACK)

    assert aem is not None

    task = AEMTask(
        name="fallback_test",
        payload="fallback",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"general"},
    )

    result = aem.execute([task])

    assert result.success
    assert result.completed_tasks == 1

    return True


# ------------------------------------------------------------
# 22 Pipeline AEM
# ------------------------------------------------------------

def test_pipeline_aem():
    registry = WorkerRegistry()

    registry.register(
        Worker(
            name="pipeline_worker",
            description="Pipeline worker",
            capabilities={"general"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: (
                "START"
                if task.name == "step_A"
                else f"{task.payload} -> PROCESSED"
                if task.name == "step_B"
                else f"{task.payload} -> FINAL"
            ),
        )
    )

    scheduler = WorkerScheduler(registry)

    aem_registry = AEMRegistry(scheduler)
    aem = aem_registry.get(AEMStrategy.PIPELINE)

    assert aem is not None

    tasks = [
        AEMTask(
            name="step_A",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="step_B",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="step_C",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
    ]

    result = aem.execute(tasks)

    assert result.success
    assert result.completed_tasks == 3
    assert result.total_tasks == 3

    final_output = result.results[-1].output

    assert final_output == "START -> PROCESSED -> FINAL"

    print("FINAL:", final_output)

    return True


# ------------------------------------------------------------
# 23 Dependency Graph AEM
# ------------------------------------------------------------

def test_dependency_graph_aem():
    registry = WorkerRegistry()

    registry.register(
        Worker(
            name="dependency_worker",
            description="Dependency graph test worker",
            capabilities={"general"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: f"DONE: {task.payload}",
        )
    )

    scheduler = WorkerScheduler(
        registry,
        SchedulingStrategy.ROUND_ROBIN,
    )

    aem = DependencyGraphAEM(
        scheduler,
        max_workers=3,
    )

    tasks = [
        AEMTask(
            name="research",
            payload="research",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="image",
            payload="image",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="plan",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
            dependencies={"research", "image"},
        ),
        AEMTask(
            name="execute",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
            dependencies={"plan"},
        ),
    ]

    result = aem.execute(tasks)

    assert result.success
    assert result.completed_tasks == 4
    assert result.total_tasks == 4

    waves = result.metadata.get("waves")

    assert waves == [
        ["image", "research"],
        ["plan"],
        ["execute"],
    ]

    outputs = result.metadata.get("outputs")

    assert outputs is not None

    assert outputs["research"] == "DONE: research"
    assert outputs["image"] == "DONE: image"

    assert "DONE: research" in outputs["plan"]
    assert "DONE: image" in outputs["plan"]

    assert "DONE:" in outputs["execute"]

    print("WAVES:", waves)
    print("OUTPUTS:", outputs)

    return True


# ------------------------------------------------------------
# 24 Adaptive AEM
# ------------------------------------------------------------

def test_adaptive_aem():
    registry = WorkerRegistry()

    registry.register(
        Worker(
            name="adaptive_worker",
            description="Adaptive execution test worker",
            capabilities={"general"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: f"EXECUTED: {task.payload}",
        )
    )

    scheduler = WorkerScheduler(
        registry,
        SchedulingStrategy.ROUND_ROBIN,
    )

    aem = AEMRegistry(scheduler).get(AEMStrategy.ADAPTIVE)

    assert aem is not None

    tasks = [
        AEMTask(
            name="task_a",
            payload="A",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
        AEMTask(
            name="task_b",
            payload="B",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={"general"},
        ),
    ]

    result = aem.execute(tasks)

    assert result.success
    assert result.strategy == AEMStrategy.PARALLEL
    assert result.completed_tasks == 2
    assert result.total_tasks == 2
    assert result.metadata.get("adaptive") is True
    assert result.metadata.get("selected_strategy") == "parallel"

    print("SELECTED:", result.metadata.get("selected_strategy"))
    print("ADAPTIVE:", result.metadata.get("adaptive"))

    return True


# ------------------------------------------------------------
# 25 End-to-End
# ------------------------------------------------------------

def test_end_to_end():
    router = build_router()
    brain = CauvisBrain(router)

    analysis = brain.analyze(
        "Build a Python program that searches the web and analyzes a screenshot."
    )

    assert analysis.task is not None
    assert analysis.reasoning is not None
    assert analysis.policy is not None
    assert analysis.capabilities is not None

    registry = build_worker_registry()

    scheduler = WorkerScheduler(
        registry,
        SchedulingStrategy.PRIORITY,
    )

    aem_registry = AEMRegistry(scheduler)

    task = AEMTask(
        name="end_to_end",
        payload="Cauvis",
        priority=1,
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"general"},
    )

    aem = aem_registry.get(AEMStrategy.SEQUENTIAL)

    assert aem is not None

    execution = aem.execute([task])

    assert execution.success
    assert execution.completed_tasks == 1

    print("BRAIN: OK")
    print("PLANNING: OK")
    print("WORKER: OK")
    print("AEM: OK")
    print("END-TO-END: OK")

    return True



# ------------------------------------------------------------
# 26 Execution Engine Adaptive Bridge
# ------------------------------------------------------------

def test_execution_engine_adaptive_bridge():
    capabilities = CapabilityRegistry()

    for name, category in [
        ("chat", "general"),
        ("web", "research"),
        ("vision", "vision"),
        ("code", "development"),
        ("tools", "execution"),
        ("verification", "verification"),
    ]:
        capabilities.register(
            Capability(
                name=name,
                description=f"Bridge test capability: {name}",
                category=category,
            )
        )

    workers = WorkerRegistry()

    def dependencies(payload):
        if (
            isinstance(payload, dict)
            and isinstance(
                payload.get("dependencies"),
                dict,
            )
        ):
            return payload["dependencies"]

        return {}

    def general_handler(task):
        if task.name == "understand_goal":
            return "UNDERSTOOD"

        if task.name == "analyze_vision":
            assert task.payload == "UNDERSTOOD"
            return "VISION"

        if task.name == "tool_execution":
            deps = dependencies(task.payload)

            assert deps["research"] == "RESEARCH"
            assert deps["analyze_vision"] == "VISION"
            assert deps["implementation"] == "IMPLEMENTATION"

            return "TOOLS"

        if task.name == "finalize":
            deps = dependencies(task.payload)

            assert deps["research"] == "RESEARCH"
            assert deps["analyze_vision"] == "VISION"
            assert deps["implementation"] == "IMPLEMENTATION"
            assert deps["tool_execution"] == "TOOLS"

            return "FINAL"

        raise AssertionError(
            f"Unexpected general task: {task.name}"
        )

    def research_handler(task):
        assert task.payload == "UNDERSTOOD"
        return "RESEARCH"

    def code_handler(task):
        deps = dependencies(task.payload)

        assert deps["research"] == "RESEARCH"
        assert deps["analyze_vision"] == "VISION"
        assert deps["understand_goal"] == "UNDERSTOOD"

        return "IMPLEMENTATION"

    def verification_handler(task):
        assert task.payload == "FINAL"
        return "VERIFIED"

    workers.register(
        Worker(
            name="bridge_general_worker",
            description="Adaptive bridge general worker",
            capabilities={"chat", "vision", "tools"},
            task_types={WorkerTaskType.GENERAL},
            handler=general_handler,
        )
    )

    workers.register(
        Worker(
            name="bridge_research_worker",
            description="Adaptive bridge research worker",
            capabilities={"web"},
            task_types={WorkerTaskType.RESEARCH},
            handler=research_handler,
        )
    )

    workers.register(
        Worker(
            name="bridge_code_worker",
            description="Adaptive bridge code worker",
            capabilities={"code"},
            task_types={WorkerTaskType.CODE},
            handler=code_handler,
        )
    )

    workers.register(
        Worker(
            name="bridge_verification_worker",
            description="Adaptive bridge verification worker",
            capabilities={"verification"},
            task_types={WorkerTaskType.VERIFICATION},
            handler=verification_handler,
        )
    )

    requirements = TaskRequirements(
        complexity=TaskComplexity.HIGH,
        requires_tools=True,
        requires_internet=True,
        requires_vision=True,
        requires_code=True,
    )

    reasoning = ReasoningResult(
        goal=(
            "Research, analyze vision, implement code, "
            "execute tools, and verify the result."
        ),
        requires_tools=True,
        requires_verification=True,
        task_requirements=requirements,
    )

    planner = AdaptiveTaskPlanner()
    plan = planner.build_plan(reasoning)

    assert len(plan.tasks) == 7

    scheduler = WorkerScheduler(
        workers,
        SchedulingStrategy.ROUND_ROBIN,
    )

    engine = ExecutionEngine(
        capability_registry=capabilities,
        tool_registry=ToolRegistry(),
        permission_manager=PermissionManager(),
        verification_engine=VerificationEngine(),
        worker_scheduler=scheduler,
    )

    result = engine.execute_adaptive(plan)

    assert result.success
    assert result.status.value == "success"
    assert result.completed_steps == 7
    assert result.total_steps == 7

    assert (
        result.metadata.get("execution_mode")
        == "adaptive_aem"
    )

    assert (
        result.metadata.get("aem_strategy")
        == "dependency_graph"
    )

    assert (
        result.metadata.get("selected_strategy")
        == "dependency_graph"
    )

    assert result.metadata.get("verified") is True

    outputs = result.metadata.get("outputs", {})

    assert outputs["understand_goal"] == "UNDERSTOOD"
    assert outputs["research"] == "RESEARCH"
    assert outputs["analyze_vision"] == "VISION"
    assert outputs["implementation"] == "IMPLEMENTATION"
    assert outputs["tool_execution"] == "TOOLS"
    assert outputs["finalize"] == "FINAL"
    assert outputs["verify_result"] == "VERIFIED"

    print("PLAN TASKS:", len(plan.tasks))
    print(
        "STRATEGY:",
        result.metadata.get("selected_strategy"),
    )
    print(
        "COMPLETED:",
        result.completed_steps,
        "/",
        result.total_steps,
    )
    print("FINAL OUTPUT:", outputs["finalize"])
    print(
        "VERIFICATION OUTPUT:",
        outputs["verify_result"],
    )

    return True



# ------------------------------------------------------------
# 27 Worker Catalog
# ------------------------------------------------------------

def test_worker_catalog():
    empty_catalog = WorkerCatalog()

    assert len(
        empty_catalog.list_specs()
    ) == 9

    assert len(
        empty_catalog.missing_handlers()
    ) == 9

    def make_handler(label):
        def handler(task):
            return (
                f"{label}: {task.name}"
            )

        return handler

    handlers = {
        "general": make_handler("GENERAL"),
        "research": make_handler("RESEARCH"),
        "code": make_handler("CODE"),
        "tools": make_handler("TOOLS"),
        "vision": make_handler("VISION"),
        "long_context": make_handler("CONTEXT"),
        "filesystem": make_handler("FILESYSTEM"),
        "system": make_handler("SYSTEM"),
        "verification": make_handler("VERIFICATION"),
    }

    catalog = WorkerCatalog(
        handlers=handlers
    )

    registry = catalog.build_registry(
        strict=True
    )

    assert registry.count() == 9

    scheduler = WorkerScheduler(
        registry,
        SchedulingStrategy.ROUND_ROBIN,
    )

    routing_cases = [
        (
            WorkerTask(
                name="general_test",
                task_type=WorkerTaskType.GENERAL,
                required_capabilities={"chat"},
            ),
            "general_worker",
        ),
        (
            WorkerTask(
                name="research_test",
                task_type=WorkerTaskType.RESEARCH,
                required_capabilities={"web"},
            ),
            "research_worker",
        ),
        (
            WorkerTask(
                name="code_test",
                task_type=WorkerTaskType.CODE,
                required_capabilities={"code"},
            ),
            "code_worker",
        ),
        (
            WorkerTask(
                name="tool_test",
                task_type=WorkerTaskType.GENERAL,
                required_capabilities={"tools"},
            ),
            "tool_worker",
        ),
        (
            WorkerTask(
                name="vision_test",
                task_type=WorkerTaskType.GENERAL,
                required_capabilities={"vision"},
            ),
            "vision_worker",
        ),
        (
            WorkerTask(
                name="context_test",
                task_type=WorkerTaskType.GENERAL,
                required_capabilities={"long_context"},
            ),
            "context_worker",
        ),
        (
            WorkerTask(
                name="file_test",
                task_type=WorkerTaskType.FILE,
                required_capabilities={"filesystem"},
            ),
            "file_worker",
        ),
        (
            WorkerTask(
                name="system_test",
                task_type=WorkerTaskType.SYSTEM,
                required_capabilities={"system"},
            ),
            "system_worker",
        ),
        (
            WorkerTask(
                name="verification_test",
                task_type=WorkerTaskType.VERIFICATION,
                required_capabilities={"verification"},
            ),
            "verification_worker",
        ),
    ]

    for task, expected_worker in routing_cases:
        result = scheduler.dispatch(task)

        assert result.success
        assert (
            result.worker_name
            == expected_worker
        )
        assert result.worker_result is not None

    capabilities = CapabilityRegistry()

    for name, category in [
        ("chat", "general"),
        ("web", "research"),
        ("vision", "vision"),
        ("code", "development"),
        ("tools", "execution"),
        ("verification", "verification"),
    ]:
        capabilities.register(
            Capability(
                name=name,
                description=(
                    f"Catalog test capability: {name}"
                ),
                category=category,
            )
        )

    requirements = TaskRequirements(
        complexity=TaskComplexity.HIGH,
        requires_tools=True,
        requires_internet=True,
        requires_vision=True,
        requires_code=True,
    )

    reasoning = ReasoningResult(
        goal=(
            "Research, inspect vision, implement code, "
            "execute tools, and verify the result."
        ),
        requires_tools=True,
        requires_verification=True,
        task_requirements=requirements,
    )

    plan = AdaptiveTaskPlanner().build_plan(
        reasoning
    )

    assert len(plan.tasks) == 7

    engine = ExecutionEngine(
        capability_registry=capabilities,
        tool_registry=ToolRegistry(),
        permission_manager=PermissionManager(),
        verification_engine=VerificationEngine(),
        worker_scheduler=scheduler,
    )

    execution = engine.execute_adaptive(
        plan
    )

    assert execution.success
    assert execution.completed_steps == 7
    assert execution.total_steps == 7

    assert (
        execution.metadata.get(
            "selected_strategy"
        )
        == "dependency_graph"
    )

    assert (
        execution.metadata.get(
            "verified"
        )
        is True
    )

    print(
        "CATALOG WORKERS:",
        registry.count(),
    )
    print(
        "ROUTING CASES:",
        len(routing_cases),
    )
    print(
        "ENGINE:",
        execution.completed_steps,
        "/",
        execution.total_steps,
    )
    print(
        "STRATEGY:",
        execution.metadata.get(
            "selected_strategy"
        ),
    )

    return True


# ------------------------------------------------------------
# Run
# ------------------------------------------------------------


# ------------------------------------------------------------
# 28 Explicit Fallback Dispatch
# ------------------------------------------------------------

def test_explicit_fallback_dispatch():
    registry = WorkerRegistry()

    def primary_handler(task):
        raise RuntimeError("PRIMARY FAILED")

    def backup_handler(task):
        return "FALLBACK SUCCESS"

    registry.register(
        Worker(
            name="primary_worker",
            description="Primary worker that fails",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=primary_handler,
        )
    )

    registry.register(
        Worker(
            name="backup_worker",
            description="Backup worker that succeeds",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=backup_handler,
        )
    )

    scheduler = WorkerScheduler(registry)

    aem_registry = AEMRegistry(scheduler)
    aem = aem_registry.get(AEMStrategy.FALLBACK)

    assert aem is not None

    task = AEMTask(
        name="explicit_fallback_test",
        payload="fallback",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"test"},
    )

    result = aem.execute([task])

    assert result.success
    assert result.completed_tasks == 1
    assert result.total_tasks == 1
    assert len(result.results) == 1

    assert (
        result.results[0].output
        == "FALLBACK SUCCESS"
    )

    fallback_history = result.metadata[
        "fallback_history"
    ][
        "explicit_fallback_test"
    ]

    assert fallback_history == [
        "primary_worker",
        "backup_worker",
    ]

    scheduler_history = [
        (
            record.worker_name,
            record.success,
        )
        for record in scheduler.history()
    ]

    assert scheduler_history == [
        ("primary_worker", False),
        ("backup_worker", True),
    ]

    print(
        "FALLBACK HISTORY:",
        fallback_history,
    )

    print(
        "SCHEDULER HISTORY:",
        scheduler_history,
    )

    return True



# ------------------------------------------------------------
# 29 Recovery Decision Policy
# ------------------------------------------------------------

def test_recovery_decision_policy():
    from execution.recovery import (
        RecoveryAction,
        RecoveryEngine,
    )

    # --------------------------------------------------------
    # SUCCESS -> NONE
    # --------------------------------------------------------

    success_registry = WorkerRegistry()

    success_registry.register(
        Worker(
            name="success_worker",
            description="Succeeds",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: "OK",
        )
    )

    success_scheduler = WorkerScheduler(
        success_registry
    )

    success_aem_registry = AEMRegistry(
        success_scheduler
    )

    success_task = AEMTask(
        name="success_task",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"test"},
    )

    success_result = SequentialAEM(
        success_scheduler
    ).execute(
        [success_task]
    )

    success_decision = RecoveryEngine(
        success_aem_registry
    ).decide(
        [success_task],
        success_result,
    )

    assert (
        success_decision.action
        == RecoveryAction.NONE
    )

    assert not success_decision.recoverable

    # --------------------------------------------------------
    # ONE FAILED WORKER -> RETRY
    # --------------------------------------------------------

    retry_registry = WorkerRegistry()

    def retry_failure(task):
        raise RuntimeError("RETRY FAILURE")

    retry_registry.register(
        Worker(
            name="retry_worker",
            description="Fails",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=retry_failure,
        )
    )

    retry_scheduler = WorkerScheduler(
        retry_registry
    )

    retry_aem_registry = AEMRegistry(
        retry_scheduler
    )

    retry_task = AEMTask(
        name="retry_task",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"test"},
    )

    retry_result = SequentialAEM(
        retry_scheduler
    ).execute(
        [retry_task]
    )

    retry_decision = RecoveryEngine(
        retry_aem_registry
    ).decide(
        [retry_task],
        retry_result,
    )

    assert (
        retry_decision.action
        == RecoveryAction.RETRY
    )

    assert retry_decision.recoverable

    assert retry_decision.failed_tasks == [
        "retry_task"
    ]

    assert (
        retry_decision.metadata[
            "failed_workers"
        ]
        == ["retry_worker"]
    )

    # --------------------------------------------------------
    # FAILED PRIMARY + ALTERNATE -> FALLBACK
    # --------------------------------------------------------

    fallback_registry = WorkerRegistry()

    def primary_failure(task):
        raise RuntimeError("PRIMARY FAILURE")

    fallback_registry.register(
        Worker(
            name="primary_worker",
            description="Primary fails",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=primary_failure,
        )
    )

    fallback_registry.register(
        Worker(
            name="backup_worker",
            description="Backup succeeds",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: "BACKUP OK",
        )
    )

    fallback_scheduler = WorkerScheduler(
        fallback_registry
    )

    fallback_aem_registry = AEMRegistry(
        fallback_scheduler
    )

    fallback_task = AEMTask(
        name="fallback_task",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"test"},
    )

    fallback_result = SequentialAEM(
        fallback_scheduler
    ).execute(
        [fallback_task]
    )

    fallback_decision = RecoveryEngine(
        fallback_aem_registry
    ).decide(
        [fallback_task],
        fallback_result,
    )

    assert (
        fallback_decision.action
        == RecoveryAction.FALLBACK
    )

    assert fallback_decision.recoverable

    assert fallback_decision.failed_tasks == [
        "fallback_task"
    ]

    assert (
        fallback_decision.metadata[
            "failed_workers"
        ]
        == ["primary_worker"]
    )

    assert (
        fallback_decision.metadata[
            "alternate_workers"
        ][
            "fallback_task"
        ]
        == ["backup_worker"]
    )

    # --------------------------------------------------------
    # INVALID DEPENDENCY GRAPH -> ABORT
    # --------------------------------------------------------

    abort_registry = WorkerRegistry()

    abort_registry.register(
        Worker(
            name="abort_worker",
            description="Unused worker",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=lambda task: "UNUSED",
        )
    )

    abort_scheduler = WorkerScheduler(
        abort_registry
    )

    abort_aem_registry = AEMRegistry(
        abort_scheduler
    )

    abort_task = AEMTask(
        name="broken_task",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"test"},
        dependencies={"missing_task"},
    )

    abort_result = DependencyGraphAEM(
        abort_scheduler
    ).execute(
        [abort_task]
    )

    abort_decision = RecoveryEngine(
        abort_aem_registry
    ).decide(
        [abort_task],
        abort_result,
    )

    assert (
        abort_decision.action
        == RecoveryAction.ABORT
    )

    assert not abort_decision.recoverable

    assert (
        abort_decision.metadata[
            "validation_failed"
        ]
        is True
    )

    print(
        "SUCCESS:",
        success_decision.action.value,
    )

    print(
        "RETRY:",
        retry_decision.action.value,
        retry_decision.failed_tasks,
    )

    print(
        "FALLBACK:",
        fallback_decision.action.value,
        fallback_decision.metadata[
            "alternate_workers"
        ],
    )

    print(
        "ABORT:",
        abort_decision.action.value,
    )

    return True



# ------------------------------------------------------------
# 30 Recovery Execution
# ------------------------------------------------------------

def test_recovery_execution():
    from execution.recovery import (
        RecoveryAction,
        RecoveryEngine,
    )

    # --------------------------------------------------------
    # RETRY EXECUTION
    # --------------------------------------------------------

    retry_calls = {
        "count": 0,
    }

    def retry_handler(task):
        retry_calls["count"] += 1

        if retry_calls["count"] == 1:
            raise RuntimeError(
                "TRANSIENT FAILURE"
            )

        return "RECOVERED"

    retry_registry = WorkerRegistry()

    retry_registry.register(
        Worker(
            name="retry_worker",
            description="Fails once then succeeds",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=retry_handler,
        )
    )

    retry_scheduler = WorkerScheduler(
        retry_registry
    )

    retry_aem_registry = AEMRegistry(
        retry_scheduler
    )

    retry_task = AEMTask(
        name="retry_me",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"test"},
        metadata={
            "recovery_safe": True,
        },
    )

    retry_original = SequentialAEM(
        retry_scheduler
    ).execute(
        [retry_task]
    )

    assert not retry_original.success

    retry_recovery = RecoveryEngine(
        retry_aem_registry
    ).recover(
        [retry_task],
        retry_original,
    )

    assert retry_recovery.success

    assert (
        retry_recovery.action
        == RecoveryAction.RETRY
    )

    assert retry_recovery.recovered_tasks == 1
    assert retry_recovery.total_failed_tasks == 1

    assert retry_recovery.aem_result is not None

    assert (
        retry_recovery.aem_result.results[0].output
        == "RECOVERED"
    )

    assert retry_calls["count"] == 2

    assert (
        retry_recovery.metadata[
            "recovery_strategy"
        ]
        == "retry"
    )

    # --------------------------------------------------------
    # FALLBACK EXECUTION
    # --------------------------------------------------------

    fallback_calls = []

    def primary_handler(task):
        fallback_calls.append(
            "primary"
        )

        raise RuntimeError(
            "PRIMARY FAILED"
        )

    def backup_handler(task):
        fallback_calls.append(
            "backup"
        )

        return "FALLBACK RECOVERED"

    fallback_registry = WorkerRegistry()

    fallback_registry.register(
        Worker(
            name="primary_worker",
            description="Primary fails",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=primary_handler,
        )
    )

    fallback_registry.register(
        Worker(
            name="backup_worker",
            description="Backup succeeds",
            capabilities={"test"},
            task_types={WorkerTaskType.GENERAL},
            handler=backup_handler,
        )
    )

    fallback_scheduler = WorkerScheduler(
        fallback_registry
    )

    fallback_aem_registry = AEMRegistry(
        fallback_scheduler
    )

    fallback_task = AEMTask(
        name="fallback_me",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"test"},
        metadata={
            "recovery_safe": True,
        },
    )

    fallback_original = SequentialAEM(
        fallback_scheduler
    ).execute(
        [fallback_task]
    )

    assert not fallback_original.success

    fallback_recovery = RecoveryEngine(
        fallback_aem_registry
    ).recover(
        [fallback_task],
        fallback_original,
    )

    assert fallback_recovery.success

    assert (
        fallback_recovery.action
        == RecoveryAction.FALLBACK
    )

    assert fallback_recovery.recovered_tasks == 1
    assert fallback_recovery.total_failed_tasks == 1

    assert fallback_recovery.aem_result is not None

    assert (
        fallback_recovery.aem_result.results[0].output
        == "FALLBACK RECOVERED"
    )

    assert fallback_calls == [
        "primary",
        "backup",
    ]

    assert (
        fallback_recovery.metadata[
            "recovery_strategy"
        ]
        == "fallback"
    )

    assert (
        fallback_recovery.aem_result.metadata[
            "fallback_history"
        ][
            "fallback_me"
        ]
        == ["backup_worker"]
    )

    print(
        "RETRY:",
        retry_recovery.action.value,
        retry_calls["count"],
        retry_recovery.aem_result.results[0].output,
    )

    print(
        "FALLBACK:",
        fallback_recovery.action.value,
        fallback_calls,
        fallback_recovery.aem_result.results[0].output,
    )

    return True



# ------------------------------------------------------------
# 31 Execution Engine Recovery Integration
# ------------------------------------------------------------

def test_execution_engine_recovery_integration():

    # --------------------------------------------------------
    # SINGLE TASK -> AUTOMATIC RETRY -> SUCCESS
    # --------------------------------------------------------

    single_capabilities = CapabilityRegistry()

    single_capabilities.register(
        Capability(
            name="recovery_test",
            description="Engine recovery integration",
            category="test",
        )
    )

    single_calls = {
        "count": 0,
    }

    def single_handler(task):
        single_calls["count"] += 1

        if single_calls["count"] == 1:
            raise RuntimeError(
                "TRANSIENT ENGINE FAILURE"
            )

        return "ENGINE RECOVERED"

    single_workers = WorkerRegistry()

    single_workers.register(
        Worker(
            name="engine_retry_worker",
            description="Fails once",
            capabilities={"recovery_test"},
            task_types={WorkerTaskType.GENERAL},
            handler=single_handler,
        )
    )

    single_scheduler = WorkerScheduler(
        single_workers
    )

    single_engine = ExecutionEngine(
        capability_registry=single_capabilities,
        tool_registry=ToolRegistry(),
        permission_manager=PermissionManager(),
        verification_engine=VerificationEngine(),
        worker_scheduler=single_scheduler,
    )

    single_task = AEMTask(
        name="engine_recovery_task",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={
            "recovery_test"
        },
        metadata={
            "recovery_safe": True,
        },
    )

    single_plan = AdaptiveExecutionPlan(
        goal="Test automatic engine recovery.",
        tasks=[
            single_task
        ],
    )

    single_result = (
        single_engine.execute_adaptive(
            single_plan
        )
    )

    assert single_result.success
    assert single_result.status.value == "success"
    assert single_result.completed_steps == 1
    assert single_result.total_steps == 1
    assert single_calls["count"] == 2

    assert (
        single_result.metadata[
            "recovery_decision"
        ][
            "action"
        ]
        == "retry"
    )

    assert (
        single_result.metadata[
            "recovery_result"
        ][
            "success"
        ]
        is True
    )

    assert (
        single_result.metadata[
            "recovered"
        ]
        is True
    )

    assert (
        single_result.metadata[
            "verified"
        ]
        is True
    )

    assert (
        single_result.metadata[
            "worker_results"
        ][0].output
        == "ENGINE RECOVERED"
    )


    # --------------------------------------------------------
    # MULTI TASK -> FAILURE REMAINS CONTROLLED
    # --------------------------------------------------------

    multi_capabilities = CapabilityRegistry()

    multi_capabilities.register(
        Capability(
            name="guard_test",
            description="Recovery guard",
            category="test",
        )
    )

    multi_calls = []

    def multi_handler(task):
        multi_calls.append(
            task.name
        )

        if task.name == "task_a":
            return "A DONE"

        raise RuntimeError(
            "TASK B FAILED"
        )

    multi_workers = WorkerRegistry()

    multi_workers.register(
        Worker(
            name="guard_worker",
            description="Multi-task guard",
            capabilities={"guard_test"},
            task_types={WorkerTaskType.GENERAL},
            handler=multi_handler,
        )
    )

    multi_scheduler = WorkerScheduler(
        multi_workers
    )

    multi_engine = ExecutionEngine(
        capability_registry=multi_capabilities,
        tool_registry=ToolRegistry(),
        permission_manager=PermissionManager(),
        verification_engine=VerificationEngine(),
        worker_scheduler=multi_scheduler,
    )

    task_a = AEMTask(
        name="task_a",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"guard_test"},
        metadata={
            "recovery_safe": True,
        },
    )

    task_b = AEMTask(
        name="task_b",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={"guard_test"},
        metadata={
            "recovery_safe": True,
        },
    )

    multi_plan = AdaptiveExecutionPlan(
        goal="Verify multi-task recovery guard.",
        tasks=[
            task_a,
            task_b,
        ],
    )

    multi_result = (
        multi_engine.execute_adaptive(
            multi_plan
        )
    )

    assert not multi_result.success
    assert multi_result.status.value == "failed"
    assert multi_result.completed_steps == 1
    assert multi_result.total_steps == 2

    assert (
        "recovery_decision"
        in multi_result.metadata
    )

    assert (
        "recovery_result"
        not in multi_result.metadata
    )

    assert (
        multi_result.metadata.get(
            "recovered"
        )
        is not True
    )

    assert multi_calls.count(
        "task_a"
    ) == 1

    assert multi_calls.count(
        "task_b"
    ) == 1

    print(
        "SINGLE:",
        single_result.status.value,
        single_calls["count"],
        single_result.metadata[
            "recovery_decision"
        ][
            "action"
        ],
    )

    print(
        "MULTI:",
        multi_result.status.value,
        multi_calls,
        "AUTO_RECOVERY:",
        "recovery_result"
        in multi_result.metadata,
    )

    return True



# ------------------------------------------------------------
# 32 Dependency Graph Recovery Resume
# ------------------------------------------------------------

def test_dependency_graph_recovery_resume():

    capabilities = CapabilityRegistry()

    capabilities.register(
        Capability(
            name="graph_recovery_test",
            description=(
                "Dependency graph recovery resume test"
            ),
            category="test",
        )
    )


    # --------------------------------------------------------
    # Worker behavior
    # --------------------------------------------------------

    calls = []

    middle_attempts = {
        "count": 0,
    }


    def handler(task):

        calls.append(
            task.name
        )

        if task.name == "upstream":
            return "UPSTREAM OUTPUT"

        if task.name == "middle":

            middle_attempts[
                "count"
            ] += 1

            if (
                middle_attempts[
                    "count"
                ]
                == 1
            ):
                raise RuntimeError(
                    "TRANSIENT MIDDLE FAILURE"
                )

            return (
                "MIDDLE RECOVERED: "
                f"{task.payload}"
            )

        if task.name == "final":
            return (
                "FINAL GOT: "
                f"{task.payload}"
            )

        raise RuntimeError(
            f"Unexpected task: {task.name}"
        )


    workers = WorkerRegistry()

    workers.register(
        Worker(
            name="graph_recovery_worker",
            description=(
                "Dependency graph recovery worker"
            ),
            capabilities={
                "graph_recovery_test"
            },
            task_types={
                WorkerTaskType.GENERAL
            },
            handler=handler,
        )
    )


    scheduler = WorkerScheduler(
        workers
    )


    # --------------------------------------------------------
    # Dependency graph
    # --------------------------------------------------------

    upstream = AEMTask(
        name="upstream",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={
            "graph_recovery_test"
        },
    )

    middle = AEMTask(
        name="middle",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={
            "graph_recovery_test"
        },
        dependencies={
            "upstream"
        },
        metadata={
            "recovery_safe": True,
        },
    )

    final = AEMTask(
        name="final",
        task_type=WorkerTaskType.GENERAL,
        required_capabilities={
            "graph_recovery_test"
        },
        dependencies={
            "middle"
        },
    )


    plan = AdaptiveExecutionPlan(
        goal=(
            "Verify dependency graph "
            "recovery and safe resume."
        ),
        tasks=[
            upstream,
            middle,
            final,
        ],
    )


    # --------------------------------------------------------
    # Execution Engine
    # --------------------------------------------------------

    engine = ExecutionEngine(
        capability_registry=capabilities,
        tool_registry=ToolRegistry(),
        permission_manager=PermissionManager(),
        verification_engine=VerificationEngine(),
        worker_scheduler=scheduler,
    )


    result = engine.execute_adaptive(
        plan
    )


    # --------------------------------------------------------
    # Full execution result
    # --------------------------------------------------------

    assert result.success

    assert (
        result.status.value
        == "success"
    )

    assert result.completed_steps == 3
    assert result.total_steps == 3


    # --------------------------------------------------------
    # Critical replay-safety guarantee
    # --------------------------------------------------------

    assert calls == [
        "upstream",
        "middle",
        "middle",
        "final",
    ]

    assert calls.count(
        "upstream"
    ) == 1

    assert calls.count(
        "middle"
    ) == 2

    assert calls.count(
        "final"
    ) == 1


    # --------------------------------------------------------
    # Recovery metadata
    # --------------------------------------------------------

    assert (
        result.metadata[
            "aem_strategy"
        ]
        == "dependency_graph"
    )

    assert (
        result.metadata[
            "recovery_decision"
        ][
            "action"
        ]
        == "retry"
    )

    assert (
        result.metadata[
            "recovery_result"
        ][
            "success"
        ]
        is True
    )

    assert (
        result.metadata[
            "graph_resume_result"
        ][
            "success"
        ]
        is True
    )

    assert (
        result.metadata[
            "recovered"
        ]
        is True
    )

    assert (
        result.metadata[
            "resumed"
        ]
        is True
    )

    assert (
        result.metadata[
            "verified"
        ]
        is True
    )


    # --------------------------------------------------------
    # Output preservation and handoff
    # --------------------------------------------------------

    outputs = result.metadata[
        "outputs"
    ]

    assert (
        outputs[
            "upstream"
        ]
        == "UPSTREAM OUTPUT"
    )

    assert (
        outputs[
            "middle"
        ]
        == (
            "MIDDLE RECOVERED: "
            "UPSTREAM OUTPUT"
        )
    )

    assert (
        outputs[
            "final"
        ]
        == (
            "FINAL GOT: "
            "MIDDLE RECOVERED: "
            "UPSTREAM OUTPUT"
        )
    )


    print(
        "CALLS:",
        calls,
    )

    print(
        "RECOVERY:",
        result.metadata[
            "recovery_decision"
        ][
            "action"
        ],
    )

    print(
        "RESUMED:",
        result.metadata[
            "resumed"
        ],
    )

    print(
        "FINAL:",
        outputs[
            "final"
        ],
    )

    return True



# ------------------------------------------------------------
# 33 Recovery Resume Safety Guards
# ------------------------------------------------------------

def test_recovery_resume_safety_guards():

    capabilities = CapabilityRegistry()

    capabilities.register(
        Capability(
            name="recovery_safety_test",
            description=(
                "Recovery resume safety guard test"
            ),
            category="test",
        )
    )


    # --------------------------------------------------------
    # Shared worker
    # --------------------------------------------------------

    calls = []


    def handler(task):

        calls.append(
            task.name
        )

        if task.name == "upstream":
            return "UPSTREAM OUTPUT"

        if task.name == "middle":
            raise RuntimeError(
                "MIDDLE FAILURE"
            )

        if task.name == "final":
            return "FINAL SHOULD NOT RUN"

        return "DONE"


    workers = WorkerRegistry()

    workers.register(
        Worker(
            name="recovery_safety_worker",
            description=(
                "Recovery safety worker"
            ),
            capabilities={
                "recovery_safety_test"
            },
            task_types={
                WorkerTaskType.GENERAL
            },
            handler=handler,
        )
    )

    scheduler = WorkerScheduler(
        workers
    )


    # --------------------------------------------------------
    # Unsafe failed task
    # --------------------------------------------------------

    tasks = [
        AEMTask(
            name="upstream",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={
                "recovery_safety_test"
            },
        ),

        AEMTask(
            name="middle",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={
                "recovery_safety_test"
            },
            dependencies={
                "upstream"
            },

            # recovery_safe intentionally omitted
        ),

        AEMTask(
            name="final",
            task_type=WorkerTaskType.GENERAL,
            required_capabilities={
                "recovery_safety_test"
            },
            dependencies={
                "middle"
            },
        ),
    ]


    plan = AdaptiveExecutionPlan(
        goal=(
            "Verify unsafe dependency recovery "
            "fails closed."
        ),
        tasks=tasks,
    )


    engine = ExecutionEngine(
        capability_registry=capabilities,
        tool_registry=ToolRegistry(),
        permission_manager=PermissionManager(),
        verification_engine=VerificationEngine(),
        worker_scheduler=scheduler,
    )


    result = engine.execute_adaptive(
        plan
    )


    assert not result.success

    assert (
        result.status.value
        == "failed"
    )

    assert calls == [
        "upstream",
        "middle",
    ]

    assert calls.count(
        "upstream"
    ) == 1

    assert calls.count(
        "middle"
    ) == 1

    assert calls.count(
        "final"
    ) == 0


    # Decision may identify retry as mechanically
    # available, but execution safety must still
    # deny automatic recovery.

    assert (
        result.metadata[
            "recovery_decision"
        ][
            "action"
        ]
        == "retry"
    )

    assert (
        result.metadata[
            "recovery_result"
        ][
            "success"
        ]
        is False
    )

    assert (
        "graph_resume_result"
        not in result.metadata
    )


    # --------------------------------------------------------
    # Invalid resume state
    # --------------------------------------------------------

    calls.clear()


    graph = engine.aem_registry.get(
        AEMStrategy.DEPENDENCY_GRAPH
    )

    assert graph is not None


    invalid_resume = graph.resume(
        tasks,
        completed_outputs={
            # middle depends on upstream,
            # so this state must be rejected.
            "middle": "INVALID SEEDED OUTPUT",
        },
    )


    assert not invalid_resume.success

    assert calls == []

    assert (
        invalid_resume.metadata.get(
            "validation_failed"
        )
        is True
    )

    assert (
        invalid_resume.metadata.get(
            "resume_validation_failed"
        )
        is True
    )

    assert (
        invalid_resume.metadata[
            "incomplete_seeded_tasks"
        ][
            "middle"
        ]
        == ["upstream"]
    )


    print(
        "UNSAFE CALLS:",
        [
            "upstream",
            "middle",
        ],
    )

    print(
        "RECOVERY:",
        result.metadata[
            "recovery_decision"
        ][
            "action"
        ],
        "EXECUTED:",
        result.metadata[
            "recovery_result"
        ][
            "success"
        ],
    )

    print(
        "INVALID RESUME CALLS:",
        calls,
    )

    print(
        "RESUME VALIDATION:",
        invalid_resume.metadata[
            "resume_validation_failed"
        ],
    )

    return True


# ------------------------------------------------------------
# 34 Nexus-Derived System Context
# ------------------------------------------------------------

def test_system_context_snapshot():
    class ContextCaptureProvider(ModelProvider):
        name = "context-capture"
        model = "context-model"

        provider_types = {
            "local",
            "cloud",
        }

        capabilities = {
            "chat",
            "code",
            "vision",
            "web",
            "tools",
            "long_context",
            "privacy",
            "reasoning",
            "complexity:low",
            "complexity:medium",
            "complexity:high",
        }

        def __init__(self):
            self.last_request = None

        def generate(
            self,
            request: ModelRequest,
        ) -> ModelResponse:
            self.last_request = request

            return ModelResponse(
                text="SYSTEM CONTEXT RESPONSE",
                model=self.model,
                provider=self.name,
                success=True,
            )


    router = AIModelRouter()
    provider = ContextCaptureProvider()

    router.register_provider(provider)

    brain = CauvisBrain(router)

    analysis = brain.analyze(
        "What is Cauvis?"
    )

    assert analysis.system_context is not None

    snapshot = analysis.system_context

    assert snapshot.metadata[
        "schema_version"
    ] == 1

    assert snapshot.metadata[
        "observational_only"
    ] is True

    assert snapshot.registered_providers == (
        "context-capture",
    )

    assert snapshot.capable_providers == (
        "context-capture",
    )

    assert (
        snapshot.default_provider
        == "context-capture"
    )

    assert snapshot.required_capabilities == tuple(
        sorted(
            analysis.capabilities.capabilities
        )
    )

    assert (
        snapshot.device["operating_system"]
        == analysis.device.operating_system
    )

    assert snapshot.providers[0].name == (
        "context-capture"
    )

    assert snapshot.providers[0].model == (
        "context-model"
    )

    assert snapshot.providers[
        0
    ].capable_for_request is True

    response = brain.think(
        "What is Cauvis?"
    )

    assert response.success
    assert provider.last_request is not None

    request_context = (
        provider.last_request.metadata.get(
            "system_context"
        )
    )

    assert isinstance(
        request_context,
        dict,
    )

    assert request_context[
        "registered_providers"
    ] == [
        "context-capture"
    ]

    assert request_context[
        "capable_providers"
    ] == [
        "context-capture"
    ]

    assert request_context[
        "default_provider"
    ] == "context-capture"

    assert request_context[
        "required_capabilities"
    ] == list(
        snapshot.required_capabilities
    )

    assert request_context[
        "metadata"
    ][
        "observational_only"
    ] is True

    assert request_context[
        "metadata"
    ][
        "provider_health_included"
    ] is False

    assert request_context[
        "metadata"
    ][
        "worker_health_included"
    ] is False

    assert request_context[
        "metadata"
    ][
        "tool_health_included"
    ] is False

    print(
        "REGISTERED:",
        snapshot.registered_providers,
    )

    print(
        "CAPABLE:",
        snapshot.capable_providers,
    )

    print(
        "DEFAULT:",
        snapshot.default_provider,
    )

    print(
        "OBSERVATIONAL:",
        snapshot.metadata[
            "observational_only"
        ],
    )

    print(
        "REQUEST CONTEXT PRESENT:",
        request_context is not None,
    )

    return True


# ------------------------------------------------------------
# 35 Provider Runtime Tracking
# ------------------------------------------------------------

def test_provider_runtime_tracking():
    from intelligence.provider_runtime import ProviderStatus
    from intelligence.policy import (
        ExecutionStrategy,
        IntelligencePolicy,
    )

    class RuntimeTrackingProvider(ModelProvider):
        name = "runtime-tracking"
        model = "runtime-tracking-model"

        provider_types = {"cloud"}
        capabilities = {"chat"}

        def __init__(self):
            self.mode = "success"

        def generate(
            self,
            request: ModelRequest,
        ) -> ModelResponse:

            if self.mode == "failure":
                return ModelResponse(
                    text="",
                    model=self.model,
                    provider=self.name,
                    success=False,
                    error="simulated provider failure",
                )

            if self.mode == "exception":
                raise RuntimeError(
                    "simulated provider exception"
                )

            return ModelResponse(
                text=f"SUCCESS: {request.prompt}",
                model=self.model,
                provider=self.name,
                success=True,
            )


    router = AIModelRouter()
    provider = RuntimeTrackingProvider()

    router.register_provider(provider)

    health = router.provider_runtime.get_health(
        provider.name
    )

    assert health is not None
    assert health.status == ProviderStatus.UNKNOWN
    assert health.available is False
    assert health.total_successes == 0
    assert health.total_failures == 0

    assert health.metadata[
        "model"
    ] == "runtime-tracking-model"

    print(
        "REGISTERED:",
        health.status.value,
        health.available,
    )


    # --------------------------------------------------------
    # Legacy/default path success
    # --------------------------------------------------------

    response = router.generate(
        ModelRequest(
            prompt="runtime success"
        )
    )

    assert response.success

    health = router.provider_runtime.get_health(
        provider.name
    )

    assert health is not None
    assert health.status == ProviderStatus.AVAILABLE
    assert health.available is True
    assert health.total_successes == 1
    assert health.total_failures == 0
    assert health.consecutive_failures == 0
    assert health.latency_ms is not None
    assert health.latency_ms >= 0

    print(
        "SUCCESS:",
        health.status.value,
        health.total_successes,
    )


    # --------------------------------------------------------
    # Consecutive failures: degraded -> unavailable
    # --------------------------------------------------------

    provider.mode = "failure"

    for expected_failures in range(1, 4):
        response = router.generate(
            ModelRequest(
                prompt=f"failure {expected_failures}"
            )
        )

        assert response.success is False

        health = (
            router.provider_runtime.get_health(
                provider.name
            )
        )

        assert health is not None

        assert health.consecutive_failures == (
            expected_failures
        )

        assert health.total_failures == (
            expected_failures
        )

        assert health.last_error == (
            "simulated provider failure"
        )

        if expected_failures < 3:
            assert (
                health.status
                == ProviderStatus.DEGRADED
            )

        else:
            assert (
                health.status
                == ProviderStatus.UNAVAILABLE
            )

            assert health.available is False

    print(
        "FAILURES:",
        health.status.value,
        health.consecutive_failures,
        health.total_failures,
    )


    # --------------------------------------------------------
    # UNAVAILABLE must be explicitly re-enabled before recovery
    # --------------------------------------------------------

    provider.mode = "success"

    blocked_response = router.generate(
        ModelRequest(
            prompt="runtime unavailable block"
        ),
        policy=IntelligencePolicy(
            strategy=ExecutionStrategy.CLOUD,
            local_allowed=True,
            cloud_allowed=True,
            reason="Provider runtime validation.",
        ),
        required_capabilities={"chat"},
    )

    assert blocked_response.success is False

    health = router.provider_runtime.get_health(
        provider.name
    )

    assert health is not None
    assert health.status == ProviderStatus.UNAVAILABLE
    assert health.total_successes == 1
    assert health.total_failures == 3

    router.provider_runtime.enable(
        provider.name
    )

    health = router.provider_runtime.get_health(
        provider.name
    )

    assert health is not None
    assert health.status == ProviderStatus.UNKNOWN
    assert health.available is False
    assert health.consecutive_failures == 0

    policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=True,
        cloud_allowed=True,
        reason="Provider runtime validation.",
    )

    response = router.generate(
        ModelRequest(
            prompt="runtime recovery"
        ),
        policy=policy,
        required_capabilities={"chat"},
    )

    assert response.success

    health = router.provider_runtime.get_health(
        provider.name
    )

    assert health is not None
    assert health.status == ProviderStatus.AVAILABLE
    assert health.available is True
    assert health.consecutive_failures == 0
    assert health.total_successes == 2
    assert health.total_failures == 3

    print(
        "RECOVERED:",
        health.status.value,
        health.total_successes,
    )


    # --------------------------------------------------------
    # Exceptions are recorded and still re-raised
    # --------------------------------------------------------

    provider.mode = "exception"
    exception_raised = False

    try:
        router.generate(
            ModelRequest(
                prompt="runtime exception"
            )
        )

    except RuntimeError as exc:
        exception_raised = True

        assert str(exc) == (
            "simulated provider exception"
        )

    assert exception_raised is True

    health = router.provider_runtime.get_health(
        provider.name
    )

    assert health is not None
    assert health.status == ProviderStatus.DEGRADED
    assert health.total_failures == 4
    assert health.consecutive_failures == 1
    assert health.last_error == (
        "simulated provider exception"
    )

    assert health.metadata[
        "exception_type"
    ] == "RuntimeError"

    print(
        "EXCEPTION:",
        health.status.value,
        health.metadata["exception_type"],
    )


    # --------------------------------------------------------
    # Removing provider clears runtime state
    # --------------------------------------------------------

    router.remove_provider(
        provider.name
    )

    assert router.get_provider(
        provider.name
    ) is None

    assert router.provider_runtime.get_health(
        provider.name
    ) is None

    print(
        "REMOVAL:",
        "runtime state cleared",
    )

    return True


# ------------------------------------------------------------
# 36 Provider Configuration Enforcement
# ------------------------------------------------------------

def test_provider_configuration_enforcement():
    from intelligence.provider_config import ProviderConfigGate
    from intelligence.provider_runtime import ProviderStatus
    from intelligence.policy import (
        ExecutionStrategy,
        IntelligencePolicy,
    )

    class ConfigTestProvider(ModelProvider):
        provider_types = {"cloud"}
        capabilities = {"chat"}

        credential_required = True
        enabled = True

        def __init__(
            self,
            name: str,
            credential_env_var: str,
        ):
            self.name = name
            self.model = f"{name}-model"
            self.credential_env_var = (
                credential_env_var
            )
            self.calls = 0

        def generate(
            self,
            request: ModelRequest,
        ) -> ModelResponse:

            self.calls += 1

            return ModelResponse(
                text=f"{self.name}: {request.prompt}",
                model=self.model,
                provider=self.name,
                success=True,
            )


    class DisabledConfigProvider(
        ConfigTestProvider
    ):
        enabled = False


    class CredentialFreeProvider(ModelProvider):
        name = "credential-free"
        model = "credential-free-model"

        provider_types = {"cloud"}
        capabilities = {"chat"}

        credential_required = False

        def __init__(self):
            self.calls = 0

        def generate(
            self,
            request: ModelRequest,
        ) -> ModelResponse:

            self.calls += 1

            return ModelResponse(
                text="CREDENTIAL FREE SUCCESS",
                model=self.model,
                provider=self.name,
                success=True,
            )


    environment = {
        "CAUVIS_CONFIG_TEST_KEY": (
            "fake-config-test-secret"
        ),
    }

    router = AIModelRouter(
        provider_config_gate=ProviderConfigGate(
            environment
        )
    )

    configured = ConfigTestProvider(
        "configured-provider",
        "CAUVIS_CONFIG_TEST_KEY",
    )

    missing = ConfigTestProvider(
        "missing-provider",
        "CAUVIS_MISSING_TEST_KEY",
    )

    disabled = DisabledConfigProvider(
        "disabled-provider",
        "CAUVIS_CONFIG_TEST_KEY",
    )

    credential_free = CredentialFreeProvider()

    router.register_provider(configured)
    router.register_provider(missing)
    router.register_provider(disabled)
    router.register_provider(credential_free)


    # --------------------------------------------------------
    # Configuration snapshots never expose credentials
    # --------------------------------------------------------

    configuration = (
        router.get_provider_configuration(
            "configured-provider"
        )
    )

    assert configuration is not None
    assert configuration.configured is True
    assert configuration.credential_present is True

    assert (
        "fake-config-test-secret"
        not in str(configuration.to_dict())
    )


    # --------------------------------------------------------
    # Missing credential is blocked before provider execution
    # --------------------------------------------------------

    response = router.generate(
        ModelRequest(
            prompt="missing configuration"
        ),
        provider_name="missing-provider",
    )

    assert response.success is False
    assert missing.calls == 0
    assert response.error is not None

    assert (
        "not configured"
        in response.error.lower()
    )

    health = router.provider_runtime.get_health(
        "missing-provider"
    )

    assert health is not None
    assert health.status == ProviderStatus.UNKNOWN
    assert health.total_successes == 0
    assert health.total_failures == 0

    print(
        "MISSING BLOCKED:",
        missing.calls,
        health.status.value,
    )


    # --------------------------------------------------------
    # Disabled provider is blocked before execution
    # --------------------------------------------------------

    response = router.generate(
        ModelRequest(
            prompt="disabled provider"
        ),
        provider_name="disabled-provider",
    )

    assert response.success is False
    assert disabled.calls == 0

    health = router.provider_runtime.get_health(
        "disabled-provider"
    )

    assert health is not None
    assert health.status == ProviderStatus.UNKNOWN

    print(
        "DISABLED BLOCKED:",
        disabled.calls,
        health.status.value,
    )


    # --------------------------------------------------------
    # Configured provider remains eligible
    # --------------------------------------------------------

    response = router.generate(
        ModelRequest(
            prompt="configured provider"
        ),
        provider_name="configured-provider",
    )

    assert response.success is True
    assert configured.calls == 1

    health = router.provider_runtime.get_health(
        "configured-provider"
    )

    assert health is not None
    assert health.status == ProviderStatus.AVAILABLE

    print(
        "CONFIGURED:",
        configured.calls,
        health.status.value,
    )


    # --------------------------------------------------------
    # Credential-free providers remain backward compatible
    # --------------------------------------------------------

    response = router.generate(
        ModelRequest(
            prompt="credential free"
        ),
        provider_name="credential-free",
    )

    assert response.success is True
    assert credential_free.calls == 1

    print(
        "CREDENTIAL FREE:",
        credential_free.calls,
    )


    # --------------------------------------------------------
    # Policy routing skips an unconfigured provider
    # --------------------------------------------------------

    router2 = AIModelRouter(
        provider_config_gate=ProviderConfigGate(
            environment
        )
    )

    missing_first = ConfigTestProvider(
        "missing-first",
        "CAUVIS_MISSING_TEST_KEY",
    )

    configured_second = ConfigTestProvider(
        "configured-second",
        "CAUVIS_CONFIG_TEST_KEY",
    )

    router2.register_provider(
        missing_first
    )

    router2.register_provider(
        configured_second
    )

    policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=True,
        cloud_allowed=True,
        reason=(
            "Provider configuration enforcement validation."
        ),
    )

    response = router2.generate(
        ModelRequest(
            prompt="policy routing"
        ),
        policy=policy,
        required_capabilities={"chat"},
    )

    assert response.success is True

    assert (
        response.provider
        == "configured-second"
    )

    assert missing_first.calls == 0
    assert configured_second.calls == 1

    print(
        "POLICY ROUTE:",
        response.provider,
        missing_first.calls,
        configured_second.calls,
    )


    return True


# ------------------------------------------------------------
# 37 OpenAI Responses Provider Integration
# ------------------------------------------------------------

def test_openai_responses_provider_integration():
    from intelligence.models import (
        ModelRequest,
        ModelResponse,
    )
    from intelligence.policy import (
        ExecutionStrategy,
        IntelligencePolicy,
    )
    from intelligence.provider_config import (
        ProviderConfigGate,
    )
    from intelligence.provider_runtime import (
        ProviderStatus,
    )
    from intelligence.providers.openai_responses import (
        OpenAIResponsesProvider,
    )
    from intelligence.router import AIModelRouter


    fake_secret = "fake-permanent-test37-secret"

    environment = {
        "OPENAI_API_KEY": fake_secret,
    }

    captured = {}


    # --------------------------------------------------------
    # Provider request construction + response parsing
    # --------------------------------------------------------

    def successful_transport(
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        captured["url"] = url
        captured["headers"] = dict(headers)
        captured["payload"] = dict(payload)
        captured["timeout"] = timeout_seconds

        return (
            200,
            {
                "id": "resp_test37",
                "model": "test-openai-model-returned",
                "output": [
                    {
                        "type": "reasoning",
                        "content": [],
                    },
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Cauvis",
                            },
                            {
                                "type": "output_text",
                                "text": "provider works.",
                            },
                        ],
                    },
                ],
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 4,
                },
            },
        )


    provider = OpenAIResponsesProvider(
        model="test-openai-model",
        environment=environment,
        transport=successful_transport,
        timeout_seconds=15.0,
    )

    direct_response = provider.generate(
        ModelRequest(
            prompt="Test OpenAI provider.",
            system_prompt="You are Cauvis.",
        )
    )

    assert isinstance(
        direct_response,
        ModelResponse,
    )

    assert direct_response.success is True

    assert direct_response.text == (
        "Cauvis\nprovider works."
    )

    assert captured["url"] == (
        "https://api.openai.com/v1/responses"
    )

    assert captured["payload"] == {
        "model": "test-openai-model",
        "input": "Test OpenAI provider.",
        "instructions": "You are Cauvis.",
    }

    assert (
        captured["headers"]["Authorization"]
        == f"Bearer {fake_secret}"
    )

    assert (
        captured["headers"]["Content-Type"]
        == "application/json"
    )

    assert captured["timeout"] == 15.0

    assert fake_secret not in str(
        direct_response.metadata
    )

    assert fake_secret not in str(
        direct_response.error
    )

    print(
        "PROVIDER DIRECT:",
        direct_response.success,
        repr(direct_response.text),
    )


    # --------------------------------------------------------
    # Router configuration + runtime integration
    # --------------------------------------------------------

    router = AIModelRouter(
        provider_config_gate=ProviderConfigGate(
            environment
        )
    )

    routed_calls = []


    def routed_transport(
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        routed_calls.append(
            dict(payload)
        )

        return (
            200,
            {
                "id": "resp_router37",
                "model": "test-openai-model",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    "Router integration works."
                                ),
                            },
                        ],
                    },
                ],
            },
        )


    routed_provider = OpenAIResponsesProvider(
        model="test-openai-model",
        environment=environment,
        transport=routed_transport,
    )

    router.register_provider(
        routed_provider
    )

    configuration = (
        router.get_provider_configuration(
            "openai"
        )
    )

    health = (
        router.provider_runtime.get_health(
            "openai"
        )
    )

    assert configuration is not None
    assert configuration.configured is True
    assert configuration.credential_present is True

    assert health is not None
    assert health.status == ProviderStatus.UNKNOWN
    assert health.available is False

    assert fake_secret not in str(
        configuration.to_dict()
    )

    assert fake_secret not in str(
        health.to_dict()
    )

    print(
        "REGISTERED:",
        configuration.status.value,
        health.status.value,
        health.available,
    )


    policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=True,
        cloud_allowed=True,
        reason=(
            "Permanent OpenAI provider validation."
        ),
    )

    routed_response = router.generate(
        ModelRequest(
            prompt="Route this request.",
            system_prompt="You are Cauvis.",
        ),
        policy=policy,
        required_capabilities={"chat"},
    )

    assert routed_response.success is True
    assert routed_response.provider == "openai"

    assert routed_response.text == (
        "Router integration works."
    )

    assert len(routed_calls) == 1

    health = (
        router.provider_runtime.get_health(
            "openai"
        )
    )

    assert health is not None
    assert health.status == ProviderStatus.AVAILABLE
    assert health.available is True
    assert health.total_successes == 1
    assert health.total_failures == 0

    assert fake_secret not in str(
        routed_response.metadata
    )

    assert fake_secret not in str(
        health.to_dict()
    )

    print(
        "ROUTED SUCCESS:",
        routed_response.provider,
        health.status.value,
        health.total_successes,
    )


    # --------------------------------------------------------
    # API failure becomes runtime DEGRADED
    # --------------------------------------------------------

    def failure_transport(
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        return (
            429,
            {
                "error": {
                    "message": (
                        "Rate limit test failure."
                    )
                }
            },
        )


    failure_router = AIModelRouter(
        provider_config_gate=ProviderConfigGate(
            environment
        )
    )

    failure_provider = OpenAIResponsesProvider(
        model="test-openai-model",
        environment=environment,
        transport=failure_transport,
    )

    failure_router.register_provider(
        failure_provider
    )

    failure_response = failure_router.generate(
        ModelRequest(
            prompt="Trigger API failure."
        ),
        provider_name="openai",
    )

    assert failure_response.success is False

    assert failure_response.error == (
        "OpenAI API error (429): "
        "Rate limit test failure."
    )

    failure_health = (
        failure_router.provider_runtime.get_health(
            "openai"
        )
    )

    assert failure_health is not None

    assert (
        failure_health.status
        == ProviderStatus.DEGRADED
    )

    assert failure_health.total_failures == 1
    assert failure_health.consecutive_failures == 1

    assert fake_secret not in str(
        failure_response.metadata
    )

    print(
        "ROUTED FAILURE:",
        failure_health.status.value,
        failure_health.total_failures,
    )


    # --------------------------------------------------------
    # Missing credential blocks provider before transport
    # --------------------------------------------------------

    blocked_calls = 0


    def blocked_transport(
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        nonlocal blocked_calls

        blocked_calls += 1

        raise RuntimeError(
            "Blocked provider should not execute."
        )


    missing_environment = {}

    blocked_router = AIModelRouter(
        provider_config_gate=ProviderConfigGate(
            missing_environment
        )
    )

    blocked_provider = OpenAIResponsesProvider(
        model="test-openai-model",
        environment=missing_environment,
        transport=blocked_transport,
    )

    blocked_router.register_provider(
        blocked_provider
    )

    blocked_response = blocked_router.generate(
        ModelRequest(
            prompt="Do not execute."
        ),
        provider_name="openai",
    )

    assert blocked_response.success is False
    assert blocked_calls == 0

    blocked_health = (
        blocked_router.provider_runtime.get_health(
            "openai"
        )
    )

    assert blocked_health is not None

    assert (
        blocked_health.status
        == ProviderStatus.UNKNOWN
    )

    assert blocked_health.total_successes == 0
    assert blocked_health.total_failures == 0

    print(
        "CONFIG BLOCK:",
        blocked_calls,
        blocked_health.status.value,
    )


    # --------------------------------------------------------
    # Aggregated output_text fallback remains supported
    # --------------------------------------------------------

    def aggregate_transport(
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        return (
            200,
            {
                "id": "resp_aggregate37",
                "model": "test-openai-model",
                "output": [],
                "output_text": (
                    "Aggregated output works."
                ),
            },
        )


    aggregate_provider = OpenAIResponsesProvider(
        model="test-openai-model",
        environment=environment,
        transport=aggregate_transport,
    )

    aggregate_response = (
        aggregate_provider.generate(
            ModelRequest(
                prompt="Aggregate parser."
            )
        )
    )

    assert aggregate_response.success is True

    assert aggregate_response.text == (
        "Aggregated output works."
    )

    print(
        "AGGREGATED:",
        aggregate_response.text,
    )


    return True


# ------------------------------------------------------------
# 38 Runtime-Aware Provider Ranking
# ------------------------------------------------------------

def test_runtime_aware_provider_ranking():
    from intelligence.models import (
        ModelRequest,
        ModelResponse,
    )
    from intelligence.policy import (
        ExecutionStrategy,
        IntelligencePolicy,
    )
    from intelligence.provider_runtime import (
        ProviderStatus,
    )
    from intelligence.router import (
        AIModelRouter,
        ModelProvider,
    )


    class RankingProvider(ModelProvider):
        provider_types = {"cloud"}
        capabilities = {"chat"}

        credential_required = False
        enabled = True

        def __init__(
            self,
            name: str,
        ):
            self.name = name
            self.model = f"{name}-model"
            self.calls = 0

        def generate(
            self,
            request: ModelRequest,
        ) -> ModelResponse:
            self.calls += 1

            return ModelResponse(
                text=self.name,
                model=self.model,
                provider=self.name,
                success=True,
            )


    router = AIModelRouter()

    available = RankingProvider(
        "available-provider"
    )

    unknown = RankingProvider(
        "unknown-provider"
    )

    degraded = RankingProvider(
        "degraded-provider"
    )

    unavailable = RankingProvider(
        "unavailable-provider"
    )

    disabled = RankingProvider(
        "disabled-provider"
    )


    # --------------------------------------------------------
    # Deliberately register in non-preferred order
    # --------------------------------------------------------

    router.register_provider(
        degraded
    )

    router.register_provider(
        unavailable
    )

    router.register_provider(
        unknown
    )

    router.register_provider(
        disabled
    )

    router.register_provider(
        available
    )


    # --------------------------------------------------------
    # Establish exact runtime states
    # --------------------------------------------------------

    router.provider_runtime.record_success(
        available.name
    )

    # UNKNOWN remains untouched after registration.

    router.provider_runtime.record_failure(
        degraded.name,
        error="test degraded",
    )

    for _ in range(3):
        router.provider_runtime.record_failure(
            unavailable.name,
            error="test unavailable",
        )

    router.provider_runtime.disable(
        disabled.name,
        reason="test disabled",
    )


    assert (
        router.provider_runtime.get_health(
            available.name
        ).status
        == ProviderStatus.AVAILABLE
    )

    assert (
        router.provider_runtime.get_health(
            unknown.name
        ).status
        == ProviderStatus.UNKNOWN
    )

    assert (
        router.provider_runtime.get_health(
            degraded.name
        ).status
        == ProviderStatus.DEGRADED
    )

    assert (
        router.provider_runtime.get_health(
            unavailable.name
        ).status
        == ProviderStatus.UNAVAILABLE
    )

    assert (
        router.provider_runtime.get_health(
            disabled.name
        ).status
        == ProviderStatus.DISABLED
    )


    # --------------------------------------------------------
    # Runtime ranking order
    # --------------------------------------------------------

    ranked_names = [
        provider.name
        for provider
        in router._ranked_providers()
    ]

    assert ranked_names == [
        "available-provider",
        "unknown-provider",
        "degraded-provider",
    ]

    print(
        "RANKED:",
        ranked_names,
    )


    # --------------------------------------------------------
    # Capability routing prefers AVAILABLE
    # --------------------------------------------------------

    provider = router.find_capable_provider(
        {"chat"}
    )

    assert provider is not None

    assert (
        provider.name
        == "available-provider"
    )

    print(
        "CAPABILITY PICK:",
        provider.name,
    )


    # --------------------------------------------------------
    # CLOUD routing prefers AVAILABLE
    # --------------------------------------------------------

    policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=True,
        cloud_allowed=True,
        reason=(
            "Runtime-aware provider "
            "ranking validation."
        ),
    )

    provider = router.select_provider(
        policy=policy,
        required_capabilities={"chat"},
    )

    assert provider is not None

    assert (
        provider.name
        == "available-provider"
    )

    print(
        "CLOUD PICK:",
        provider.name,
    )


    # --------------------------------------------------------
    # AVAILABLE becomes UNAVAILABLE -> UNKNOWN wins
    # --------------------------------------------------------

    for _ in range(3):
        router.provider_runtime.record_failure(
            available.name,
            error="available now failed",
        )

    assert (
        router.provider_runtime.get_health(
            available.name
        ).status
        == ProviderStatus.UNAVAILABLE
    )

    provider = router.find_capable_provider(
        {"chat"}
    )

    assert provider is not None

    assert (
        provider.name
        == "unknown-provider"
    )

    print(
        "UNKNOWN FALLBACK:",
        provider.name,
    )


    # --------------------------------------------------------
    # UNKNOWN becomes UNAVAILABLE -> DEGRADED wins
    # --------------------------------------------------------

    for _ in range(3):
        router.provider_runtime.record_failure(
            unknown.name,
            error="unknown now failed",
        )

    assert (
        router.provider_runtime.get_health(
            unknown.name
        ).status
        == ProviderStatus.UNAVAILABLE
    )

    provider = router.find_capable_provider(
        {"chat"}
    )

    assert provider is not None

    assert (
        provider.name
        == "degraded-provider"
    )

    print(
        "DEGRADED FALLBACK:",
        provider.name,
    )


    # --------------------------------------------------------
    # All eligible providers excluded -> fail closed
    # --------------------------------------------------------

    for _ in range(2):
        router.provider_runtime.record_failure(
            degraded.name,
            error="degraded now unavailable",
        )

    assert (
        router.provider_runtime.get_health(
            degraded.name
        ).status
        == ProviderStatus.UNAVAILABLE
    )

    provider = router.find_capable_provider(
        {"chat"}
    )

    assert provider is None

    print(
        "ALL EXCLUDED:",
        provider,
    )


    # --------------------------------------------------------
    # Explicit unavailable provider is also rejected
    # --------------------------------------------------------

    provider = router.select_provider(
        policy=policy,
        required_capabilities={"chat"},
        provider_name="available-provider",
    )

    assert provider is None

    print(
        "EXPLICIT UNAVAILABLE:",
        provider,
    )


    return True


# ------------------------------------------------------------
# 39 Automatic Provider Failover
# ------------------------------------------------------------

def test_automatic_provider_failover():
    from intelligence.models import (
        ModelRequest,
        ModelResponse,
    )
    from intelligence.policy import (
        ExecutionStrategy,
        IntelligencePolicy,
    )
    from intelligence.provider_runtime import (
        ProviderStatus,
    )
    from intelligence.router import (
        AIModelRouter,
        ModelProvider,
    )


    class FailoverProvider(ModelProvider):
        provider_types = {"cloud"}
        capabilities = {"chat"}

        credential_required = False
        enabled = True

        def __init__(
            self,
            name: str,
            mode: str,
        ):
            self.name = name
            self.model = f"{name}-model"
            self.mode = mode
            self.calls = 0

        def generate(
            self,
            request: ModelRequest,
        ) -> ModelResponse:
            self.calls += 1

            if self.mode == "success":
                return ModelResponse(
                    text=f"SUCCESS: {self.name}",
                    model=self.model,
                    provider=self.name,
                    success=True,
                )

            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=f"FAILURE: {self.name}",
            )


    policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=True,
        cloud_allowed=True,
        reason="Automatic provider failover validation.",
    )


    # --------------------------------------------------------
    # Primary failure -> backup success
    # --------------------------------------------------------

    router = AIModelRouter()

    primary = FailoverProvider(
        "primary-provider",
        "failure",
    )

    backup_provider = FailoverProvider(
        "backup-provider",
        "success",
    )

    router.register_provider(primary)
    router.register_provider(backup_provider)

    response = router.generate(
        ModelRequest(
            prompt="Use provider failover."
        ),
        policy=policy,
        required_capabilities={"chat"},
    )

    assert response.success is True
    assert response.provider == "backup-provider"

    assert primary.calls == 1
    assert backup_provider.calls == 1

    primary_health = (
        router.provider_runtime.get_health(
            primary.name
        )
    )

    backup_health = (
        router.provider_runtime.get_health(
            backup_provider.name
        )
    )

    assert primary_health is not None
    assert backup_health is not None

    assert (
        primary_health.status
        == ProviderStatus.DEGRADED
    )

    assert (
        backup_health.status
        == ProviderStatus.AVAILABLE
    )

    assert primary_health.total_failures == 1
    assert backup_health.total_successes == 1

    print(
        "FAILOVER SUCCESS:",
        response.provider,
        primary.calls,
        backup_provider.calls,
    )


    # --------------------------------------------------------
    # Explicit provider -> no silent substitution
    # --------------------------------------------------------

    explicit_router = AIModelRouter()

    explicit_primary = FailoverProvider(
        "explicit-primary",
        "failure",
    )

    explicit_backup = FailoverProvider(
        "explicit-backup",
        "success",
    )

    explicit_router.register_provider(
        explicit_primary
    )

    explicit_router.register_provider(
        explicit_backup
    )

    explicit_response = explicit_router.generate(
        ModelRequest(
            prompt="Explicit provider."
        ),
        policy=policy,
        required_capabilities={"chat"},
        provider_name="explicit-primary",
    )

    assert explicit_response.success is False
    assert (
        explicit_response.provider
        == "explicit-primary"
    )

    assert explicit_primary.calls == 1
    assert explicit_backup.calls == 0

    print(
        "EXPLICIT NO FAILOVER:",
        explicit_primary.calls,
        explicit_backup.calls,
    )


    # --------------------------------------------------------
    # Capability mismatch is never attempted
    # --------------------------------------------------------

    class CodeOnlyProvider(
        FailoverProvider
    ):
        capabilities = {"code"}


    capability_router = AIModelRouter()

    wrong_capability = CodeOnlyProvider(
        "wrong-capability",
        "success",
    )

    chat_provider = FailoverProvider(
        "chat-provider",
        "success",
    )

    capability_router.register_provider(
        wrong_capability
    )

    capability_router.register_provider(
        chat_provider
    )

    capability_response = (
        capability_router.generate(
            ModelRequest(
                prompt="Need chat."
            ),
            policy=policy,
            required_capabilities={"chat"},
        )
    )

    assert capability_response.success is True
    assert (
        capability_response.provider
        == "chat-provider"
    )

    assert wrong_capability.calls == 0
    assert chat_provider.calls == 1

    print(
        "CAPABILITY FILTER:",
        wrong_capability.calls,
        chat_provider.calls,
    )


    # --------------------------------------------------------
    # Provider type mismatch is never attempted
    # --------------------------------------------------------

    class LocalProvider(
        FailoverProvider
    ):
        provider_types = {"local"}


    type_router = AIModelRouter()

    local_provider = LocalProvider(
        "local-provider",
        "success",
    )

    cloud_provider = FailoverProvider(
        "cloud-provider",
        "success",
    )

    type_router.register_provider(
        local_provider
    )

    type_router.register_provider(
        cloud_provider
    )

    type_response = type_router.generate(
        ModelRequest(
            prompt="Need cloud."
        ),
        policy=policy,
        required_capabilities={"chat"},
    )

    assert type_response.success is True
    assert (
        type_response.provider
        == "cloud-provider"
    )

    assert local_provider.calls == 0
    assert cloud_provider.calls == 1

    print(
        "TYPE FILTER:",
        local_provider.calls,
        cloud_provider.calls,
    )


    # --------------------------------------------------------
    # Bounded attempts: each candidate at most once
    # --------------------------------------------------------

    bounded_router = AIModelRouter()

    first = FailoverProvider(
        "first-failure",
        "failure",
    )

    second = FailoverProvider(
        "second-failure",
        "failure",
    )

    third = FailoverProvider(
        "third-success",
        "success",
    )

    bounded_router.register_provider(first)
    bounded_router.register_provider(second)
    bounded_router.register_provider(third)

    bounded_response = bounded_router.generate(
        ModelRequest(
            prompt="Bounded failover."
        ),
        policy=policy,
        required_capabilities={"chat"},
    )

    assert bounded_response.success is True
    assert bounded_response.provider == "third-success"

    assert first.calls == 1
    assert second.calls == 1
    assert third.calls == 1

    print(
        "BOUNDED ATTEMPTS:",
        first.calls,
        second.calls,
        third.calls,
    )


    # --------------------------------------------------------
    # All providers fail -> return final real failure
    # --------------------------------------------------------

    all_fail_router = AIModelRouter()

    fail_a = FailoverProvider(
        "fail-a",
        "failure",
    )

    fail_b = FailoverProvider(
        "fail-b",
        "failure",
    )

    all_fail_router.register_provider(
        fail_a
    )

    all_fail_router.register_provider(
        fail_b
    )

    all_fail_response = (
        all_fail_router.generate(
            ModelRequest(
                prompt="All fail."
            ),
            policy=policy,
            required_capabilities={"chat"},
        )
    )

    assert all_fail_response.success is False

    assert (
        all_fail_response.provider
        == "fail-b"
    )

    assert all_fail_response.error == (
        "FAILURE: fail-b"
    )

    assert fail_a.calls == 1
    assert fail_b.calls == 1

    fail_a_health = (
        all_fail_router.provider_runtime.get_health(
            fail_a.name
        )
    )

    fail_b_health = (
        all_fail_router.provider_runtime.get_health(
            fail_b.name
        )
    )

    assert fail_a_health is not None
    assert fail_b_health is not None

    assert (
        fail_a_health.status
        == ProviderStatus.DEGRADED
    )

    assert (
        fail_b_health.status
        == ProviderStatus.DEGRADED
    )

    print(
        "ALL FAILED:",
        all_fail_response.provider,
        all_fail_response.error,
    )


    return True



# ============================================================
# TEST 40 - OLLAMA PROVIDER INTEGRATION
# ============================================================

def test_ollama_provider_integration():
    """
    Validate the native Cauvis Ollama provider without requiring
    a live Ollama service or downloaded model.
    """

    from intelligence.models import (
        ModelRequest,
    )
    from intelligence.providers.ollama import (
        OllamaProvider,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    captured = {
        "calls": 0,
    }

    def fake_transport(
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        captured["calls"] += 1
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout_seconds"] = (
            timeout_seconds
        )

        return (
            200,
            {
                "model": "phi4-mini",
                "message": {
                    "role": "assistant",
                    "content": (
                        "CAUVIS OLLAMA TEST PASS"
                    ),
                },
                "done": True,
                "done_reason": "stop",
                "total_duration": 1000,
                "load_duration": 100,
                "prompt_eval_count": 12,
                "prompt_eval_cached_count": 3,
                "eval_count": 7,
                "eval_duration": 500,
            },
        )

    provider = OllamaProvider(
        model="phi4-mini",
        transport=fake_transport,
        timeout_seconds=30.0,
    )

    assert provider.name == "ollama"
    assert provider.model == "phi4-mini"

    assert provider.provider_types == {
        "local",
    }

    assert provider.credential_required is False
    assert provider.credential_env_var is None
    assert provider.enabled is True

    assert provider.endpoint == (
        "http://127.0.0.1:11434/api/chat"
    )

    request = ModelRequest(
        prompt="Hello local Cauvis.",
        system_prompt="You are Cauvis.",
        temperature=0.35,
        max_tokens=64,
    )

    response = provider.generate(
        request
    )

    assert captured["calls"] == 1

    assert captured["url"] == (
        "http://127.0.0.1:11434/api/chat"
    )

    assert captured["headers"] == {
        "Content-Type": "application/json",
    }

    payload = captured["payload"]

    assert payload["model"] == "phi4-mini"
    assert payload["stream"] is False

    assert payload["messages"] == [
        {
            "role": "system",
            "content": "You are Cauvis.",
        },
        {
            "role": "user",
            "content": "Hello local Cauvis.",
        },
    ]

    assert (
        payload["options"]["temperature"]
        == 0.35
    )

    assert (
        payload["options"]["num_predict"]
        == 64
    )

    assert response.success is True
    assert response.provider == "ollama"
    assert response.model == "phi4-mini"

    assert response.text == (
        "CAUVIS OLLAMA TEST PASS"
    )

    assert response.error is None

    assert (
        response.metadata["status_code"]
        == 200
    )

    assert response.metadata["done"] is True

    assert (
        response.metadata[
            "prompt_eval_count"
        ]
        == 12
    )

    assert (
        response.metadata["eval_count"]
        == 7
    )

    # --------------------------------------------------------
    # Credential-free configuration through the real router
    # --------------------------------------------------------

    router = AIModelRouter()

    router.register_provider(
        provider
    )

    configuration = (
        router.get_provider_configuration(
            "ollama"
        )
    )

    assert configuration is not None
    assert configuration.configured is True

    assert (
        router.default_provider
        == "ollama"
    )

    # --------------------------------------------------------
    # Structured API failure
    # --------------------------------------------------------

    def failure_transport(
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        return (
            404,
            {
                "error": (
                    "model 'missing-model' "
                    "not found"
                )
            },
        )

    failing_provider = OllamaProvider(
        model="missing-model",
        transport=failure_transport,
    )

    failure = failing_provider.generate(
        ModelRequest(
            prompt="Test failure."
        )
    )

    assert failure.success is False
    assert failure.provider == "ollama"
    assert failure.model == "missing-model"

    assert failure.error == (
        "Ollama API error (404): "
        "model 'missing-model' not found"
    )

    assert (
        failure.metadata["status_code"]
        == 404
    )

    print(
        "DIRECT SUCCESS:",
        response.provider,
        response.model,
        repr(response.text),
    )

    print(
        "CONFIGURATION:",
        configuration.configured,
        router.default_provider,
    )

    print(
        "STRUCTURED FAILURE:",
        failure.success,
        failure.error,
    )

    return True


# ============================================================
# TEST 41 - LOCAL / CLOUD POLICY FAILOVER
# ============================================================

def test_local_cloud_policy_failover():
    """
    Validate policy-authorized failover between cloud and local
    providers while preserving explicit-provider isolation.
    """

    from intelligence.models import (
        ModelRequest,
        ModelResponse,
    )
    from intelligence.policy import (
        ExecutionStrategy,
        IntelligencePolicy,
    )
    from intelligence.router import (
        AIModelRouter,
        ModelProvider,
    )

    class TestProvider(
        ModelProvider
    ):
        capabilities = {
            "chat",
        }

        def __init__(
            self,
            name,
            provider_type,
            succeeds,
            output,
        ):
            self.name = name
            self.model = (
                f"{name}-model"
            )

            self.provider_types = {
                provider_type,
            }

            self.succeeds = bool(
                succeeds
            )

            self.output = output
            self.calls = 0

        def generate(
            self,
            request,
        ):
            self.calls += 1

            if self.succeeds:
                return ModelResponse(
                    text=self.output,
                    model=self.model,
                    provider=self.name,
                    success=True,
                )

            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=(
                    f"FAILURE: {self.name}"
                ),
            )

    # --------------------------------------------------------
    # CLOUD -> LOCAL when policy permits local fallback
    # --------------------------------------------------------

    cloud_local_router = AIModelRouter()

    cloud_failure = TestProvider(
        name="cloud-failure",
        provider_type="cloud",
        succeeds=False,
        output="",
    )

    local_success = TestProvider(
        name="local-success",
        provider_type="local",
        succeeds=True,
        output=(
            "CLOUD TO LOCAL RECOVERED"
        ),
    )

    cloud_local_router.register_provider(
        cloud_failure
    )

    cloud_local_router.register_provider(
        local_success
    )

    cloud_policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=True,
        cloud_allowed=True,
        reason=(
            "Test cloud-first resilient fallback."
        ),
    )

    cloud_local_response = (
        cloud_local_router.generate(
            ModelRequest(
                prompt="Cloud then local."
            ),
            policy=cloud_policy,
            required_capabilities={
                "chat",
            },
        )
    )

    assert (
        cloud_failure.calls
        == 1
    )

    assert (
        local_success.calls
        == 1
    )

    assert (
        cloud_local_response.success
        is True
    )

    assert (
        cloud_local_response.provider
        == "local-success"
    )

    assert (
        cloud_local_response.text
        == "CLOUD TO LOCAL RECOVERED"
    )

    # --------------------------------------------------------
    # CLOUD may not cross to LOCAL when local is forbidden
    # --------------------------------------------------------

    guarded_router = AIModelRouter()

    guarded_cloud = TestProvider(
        name="guarded-cloud",
        provider_type="cloud",
        succeeds=False,
        output="",
    )

    forbidden_local = TestProvider(
        name="forbidden-local",
        provider_type="local",
        succeeds=True,
        output="SHOULD NOT RUN",
    )

    guarded_router.register_provider(
        guarded_cloud
    )

    guarded_router.register_provider(
        forbidden_local
    )

    guarded_policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=False,
        cloud_allowed=True,
        reason=(
            "Test local fallback prohibition."
        ),
    )

    guarded_response = (
        guarded_router.generate(
            ModelRequest(
                prompt="Cloud only."
            ),
            policy=guarded_policy,
            required_capabilities={
                "chat",
            },
        )
    )

    assert guarded_cloud.calls == 1
    assert forbidden_local.calls == 0

    assert (
        guarded_response.success
        is False
    )

    assert (
        guarded_response.provider
        == "guarded-cloud"
    )

    # --------------------------------------------------------
    # LOCAL -> CLOUD when policy permits cloud fallback
    # --------------------------------------------------------

    local_cloud_router = AIModelRouter()

    local_failure = TestProvider(
        name="local-failure",
        provider_type="local",
        succeeds=False,
        output="",
    )

    cloud_success = TestProvider(
        name="cloud-success",
        provider_type="cloud",
        succeeds=True,
        output=(
            "LOCAL TO CLOUD RECOVERED"
        ),
    )

    local_cloud_router.register_provider(
        local_failure
    )

    local_cloud_router.register_provider(
        cloud_success
    )

    local_policy = IntelligencePolicy(
        strategy=ExecutionStrategy.LOCAL,
        local_allowed=True,
        cloud_allowed=True,
        reason=(
            "Test local-first resilient fallback."
        ),
    )

    local_cloud_response = (
        local_cloud_router.generate(
            ModelRequest(
                prompt="Local then cloud."
            ),
            policy=local_policy,
            required_capabilities={
                "chat",
            },
        )
    )

    assert local_failure.calls == 1
    assert cloud_success.calls == 1

    assert (
        local_cloud_response.success
        is True
    )

    assert (
        local_cloud_response.provider
        == "cloud-success"
    )

    assert (
        local_cloud_response.text
        == "LOCAL TO CLOUD RECOVERED"
    )

    # --------------------------------------------------------
    # Explicit provider remains isolated: no silent failover
    # --------------------------------------------------------

    explicit_router = AIModelRouter()

    explicit_cloud = TestProvider(
        name="explicit-cloud",
        provider_type="cloud",
        succeeds=False,
        output="",
    )

    explicit_local = TestProvider(
        name="explicit-local",
        provider_type="local",
        succeeds=True,
        output="SHOULD NOT RUN",
    )

    explicit_router.register_provider(
        explicit_cloud
    )

    explicit_router.register_provider(
        explicit_local
    )

    explicit_response = (
        explicit_router.generate(
            ModelRequest(
                prompt="Explicit cloud."
            ),
            policy=cloud_policy,
            required_capabilities={
                "chat",
            },
            provider_name=(
                "explicit-cloud"
            ),
        )
    )

    assert explicit_cloud.calls == 1
    assert explicit_local.calls == 0

    assert (
        explicit_response.success
        is False
    )

    assert (
        explicit_response.provider
        == "explicit-cloud"
    )

    print(
        "CLOUD -> LOCAL:",
        cloud_failure.calls,
        local_success.calls,
        cloud_local_response.provider,
    )

    print(
        "POLICY GUARD:",
        guarded_cloud.calls,
        forbidden_local.calls,
        guarded_response.provider,
    )

    print(
        "LOCAL -> CLOUD:",
        local_failure.calls,
        cloud_success.calls,
        local_cloud_response.provider,
    )

    print(
        "EXPLICIT ISOLATION:",
        explicit_cloud.calls,
        explicit_local.calls,
        explicit_response.provider,
    )

    return True



# ============================================================
# TEST 42 - SESSION CONVERSATION RUNTIME
# ============================================================

def test_session_conversation_runtime():
    """
    Validate bounded, isolated short-term conversation context
    and its integration with CauvisOrchestrator.

    This test is fully offline and uses a fake brain.
    """

    from core.config import CauvisConfig
    from core.conversation import (
        ConversationRuntime,
    )
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    # --------------------------------------------------------
    # Direct conversation runtime behavior
    # --------------------------------------------------------

    runtime = ConversationRuntime(
        max_turns=3,
        max_context_characters=12000,
    )

    runtime.append(
        "session-a",
        "user",
        "alpha",
    )

    runtime.append(
        "session-a",
        "assistant",
        "one",
    )

    runtime.append(
        "session-b",
        "user",
        "beta",
    )

    assert (
        runtime.turn_count(
            "session-a"
        )
        == 2
    )

    assert (
        runtime.turn_count(
            "session-b"
        )
        == 1
    )

    assert (
        "beta"
        not in runtime.render_context(
            "session-a"
        )
    )

    runtime.append(
        "session-a",
        "user",
        "two",
    )

    runtime.append(
        "session-a",
        "assistant",
        "three",
    )

    # max_turns=3 should trim the oldest "alpha" turn.
    assert (
        runtime.turn_count(
            "session-a"
        )
        == 3
    )

    assert (
        "alpha"
        not in runtime.render_context(
            "session-a"
        )
    )

    assert (
        runtime.turns(
            "session-a"
        )[0].content
        == "one"
    )

    # --------------------------------------------------------
    # Orchestrator integration using the exact cobalt scenario
    # --------------------------------------------------------

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                {
                    "user_input": user_input,
                    "system_prompt": system_prompt,
                }
            )

            if len(calls) == 1:
                text = "remembered"
            else:
                text = "cobalt"

            return ModelResponse(
                text=text,
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="cobalt-session",
    )

    first = orchestrator.handle(
        "My test word is cobalt. "
        "Remember it for my next message."
    )

    second = orchestrator.handle(
        "What was my test word? "
        "Reply only with the word."
    )

    assert first.status == "success"
    assert second.status == "success"

    assert first.message == "remembered"
    assert second.message == "cobalt"

    assert len(calls) == 2

    assert (
        orchestrator.conversation.turn_count(
            "cobalt-session"
        )
        == 4
    )

    first_system = (
        calls[0]["system_prompt"]
        or ""
    )

    second_system = (
        calls[1]["system_prompt"]
        or ""
    )

    # First model turn should have no prior transcript.
    assert (
        "<conversation_history>"
        not in first_system
    )

    # Second model turn should receive the actual prior turns.
    assert (
        "My test word is cobalt."
        in second_system
    )

    assert (
        "Cauvis: remembered"
        in second_system
    )

    # The current user message is still passed separately and
    # must not be duplicated inside prior-history context.
    assert (
        "What was my test word?"
        not in second_system
    )

    assert (
        calls[1]["user_input"]
        == (
            "What was my test word? "
            "Reply only with the word."
        )
    )

    # Session metadata should expose safe turn count only.
    assert (
        second.data[
            "session_id"
        ]
        == "cobalt-session"
    )

    assert (
        second.data[
            "conversation_turns"
        ]
        == 4
    )

    print(
        "ISOLATION:",
        runtime.turn_count("session-a"),
        runtime.turn_count("session-b"),
    )

    print(
        "COBALT MEMORY:",
        second.message,
    )

    print(
        "TURN COUNT:",
        second.data[
            "conversation_turns"
        ],
    )

    print(
        "CURRENT TURN DUPLICATED:",
        (
            "What was my test word?"
            in second_system
        ),
    )

    return True


# ============================================================
# TEST 43 - CAUVIS RUNTIME IDENTITY GROUNDING
# ============================================================

def test_cauvis_runtime_identity_grounding():
    """
    Validate the permanent model-boundary identity contract.

    This verifies that Cauvis identifies itself independently
    from underlying models, runtimes, providers, and vendors.

    This test is fully offline and uses a fake brain.
    """

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    captured = []

    class IdentityBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            captured.append(
                {
                    "user_input": user_input,
                    "system_prompt": system_prompt or "",
                }
            )

            return ModelResponse(
                text=(
                    "I am Cauvis, created by the "
                    "Cauvis project and its developer."
                ),
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=IdentityBrain(),
        session_id="identity-session",
    )

    response = orchestrator.handle(
        "Who created or developed you?"
    )

    assert response.status == "success"
    assert len(captured) == 1

    system_prompt = (
        captured[0]["system_prompt"]
    )

    # --------------------------------------------------------
    # Core identity
    # --------------------------------------------------------

    assert (
        "You are Cauvis."
        in system_prompt
    )

    assert (
        "Cauvis project"
        in system_prompt
    )

    assert (
        "Your identity is Cauvis"
        in system_prompt
    )

    # --------------------------------------------------------
    # Creator / component separation
    # --------------------------------------------------------

    assert (
        "they did not create or develop Cauvis"
        in system_prompt
    )

    assert (
        "attribute Cauvis only to the "
        "Cauvis project and its developer"
        in system_prompt
    )

    for component_name in (
        "Microsoft",
        "OpenAI",
        "Ollama",
        "Phi-4-mini",
    ):
        assert (
            component_name
            in system_prompt
        )

    assert (
        "Do not claim that you are Microsoft, "
        "OpenAI, Ollama, Phi-4-mini"
        in system_prompt
    )

    # --------------------------------------------------------
    # Memory/capability/action truth boundaries remain present
    # --------------------------------------------------------

    assert (
        "Do not claim memory unless"
        in system_prompt
    )

    assert (
        "Do not invent Cauvis-specific "
        "tools, source components, capabilities, "
        "memories, or actions."
        in system_prompt
    )

    assert (
        "unless the Cauvis execution system actually "
        "performed or accepted that operation."
        in system_prompt
    )

    assert (
        response.message
        == (
            "I am Cauvis, created by the "
            "Cauvis project and its developer."
        )
    )

    print(
        "IDENTITY: Cauvis"
    )

    print(
        "CREATOR: Cauvis project / developer"
    )

    print(
        "MODEL/VENDOR SEPARATION:",
        True,
    )

    print(
        "ACTION CLAIM GUARD:",
        True,
    )

    return True



# ============================================================
# TEST 44 - VERIFIED CAPABILITY TRUTH
# ============================================================

def test_verified_capability_truth():
    """
    Verify Beta 1.2B runtime capability truth semantics.

    This test is fully offline.

    It proves:
    - configured != available
    - real runtime success can establish availability
    - missing configuration overrides stale runtime success
    - unconnected action systems fail closed
    - persistent memory is not currently connected
    """

    from intelligence.provider_config import (
        ProviderConfigGate,
    )
    from intelligence.router import (
        AIModelRouter,
        ModelProvider,
    )
    from intelligence.verified_capabilities import (
        CapabilityTruthStatus,
        VerifiedCapabilityBuilder,
    )

    class LocalProvider(ModelProvider):
        name = "local-test"
        model = "local-model"
        credential_required = False

    class CloudProvider(ModelProvider):
        name = "cloud-test"
        model = "cloud-model"
        credential_required = True
        credential_env_var = "TEST_CLOUD_KEY"

    router = AIModelRouter(
        provider_config_gate=ProviderConfigGate(
            environment={}
        )
    )

    router.register_provider(
        LocalProvider()
    )

    router.register_provider(
        CloudProvider()
    )

    builder = VerifiedCapabilityBuilder()

    first = builder.build(
        router=router,
        conversation_connected=True,
        brain_connected=True,
    )

    # --------------------------------------------------------
    # Connected foundational runtime capabilities
    # --------------------------------------------------------

    assert (
        first.get("conversation").status
        == CapabilityTruthStatus.AVAILABLE
    )

    assert (
        first.get("conversation").available
        is True
    )

    assert (
        first.get("brain").available
        is True
    )

    assert (
        first.get("ai_routing").available
        is True
    )

    # --------------------------------------------------------
    # Configured is not the same as verified available
    # --------------------------------------------------------

    local = first.get(
        "provider:local-test"
    )

    assert local is not None

    assert (
        local.status
        == CapabilityTruthStatus.CONFIGURED
    )

    assert local.available is False

    # --------------------------------------------------------
    # Missing configuration fails closed
    # --------------------------------------------------------

    cloud = first.get(
        "provider:cloud-test"
    )

    assert cloud is not None

    assert (
        cloud.status
        == CapabilityTruthStatus.NOT_CONFIGURED
    )

    assert cloud.available is False

    # --------------------------------------------------------
    # Action systems are not attached to current Beta runtime
    # --------------------------------------------------------

    for capability_name in (
        "execution_actions",
        "tool_execution",
        "worker_execution",
        "voice",
        "filesystem_actions",
        "system_actions",
        "web_actions",
        "reminders",
        "persistent_memory",
    ):
        capability = first.get(
            capability_name
        )

        assert capability is not None

        assert capability.available is False

        assert (
            capability.status
            == CapabilityTruthStatus.NOT_CONNECTED
        )

    # --------------------------------------------------------
    # Real observed provider success establishes availability
    # --------------------------------------------------------

    router.provider_runtime.record_success(
        "local-test",
        latency_ms=12.5,
    )

    second = builder.build(
        router=router,
        conversation_connected=True,
        brain_connected=True,
    )

    local_after_success = second.get(
        "provider:local-test"
    )

    assert local_after_success is not None

    assert (
        local_after_success.status
        == CapabilityTruthStatus.AVAILABLE
    )

    assert (
        local_after_success.available
        is True
    )

    # --------------------------------------------------------
    # Stale runtime success must not override configuration
    # --------------------------------------------------------

    router.provider_runtime.record_success(
        "cloud-test",
        latency_ms=8.0,
    )

    third = builder.build(
        router=router,
        conversation_connected=True,
        brain_connected=True,
    )

    cloud_after_stale_success = third.get(
        "provider:cloud-test"
    )

    assert cloud_after_stale_success is not None

    assert (
        router.provider_runtime.get_health(
            "cloud-test"
        ).status.value
        == "available"
    )

    assert (
        router.get_provider_configuration(
            "cloud-test"
        ).configured
        is False
    )

    assert (
        cloud_after_stale_success.status
        == CapabilityTruthStatus.NOT_CONFIGURED
    )

    assert (
        cloud_after_stale_success.available
        is False
    )

    assert (
        third.metadata[
            "request_requirements_are_not_runtime_truth"
        ]
        is True
    )

    assert (
        third.metadata[
            "observational_only"
        ]
        is True
    )

    assert (
        third.metadata[
            "fails_closed"
        ]
        is True
    )

    print(
        "LOCAL BEFORE SUCCESS:",
        local.status.value,
        local.available,
    )

    print(
        "LOCAL AFTER SUCCESS:",
        local_after_success.status.value,
        local_after_success.available,
    )

    print(
        "CLOUD CONFIG OVERRIDE:",
        cloud_after_stale_success.status.value,
        cloud_after_stale_success.available,
    )

    print(
        "WEB ACTIONS:",
        third.get(
            "web_actions"
        ).status.value,
    )

    print(
        "PERSISTENT MEMORY:",
        third.get(
            "persistent_memory"
        ).status.value,
    )

    return True


# ============================================================
# TEST 45 - CAPABILITY PROMPT GROUNDING
# ============================================================

def test_capability_prompt_grounding():
    """
    Verify runtime capability truth reaches the model prompt.

    This test is fully offline and uses a fake brain.

    It deliberately stores a false capability claim in
    conversation history and verifies that transcript history
    cannot upgrade verified runtime capability truth.
    """

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                {
                    "user_input": user_input,
                    "system_prompt": (
                        system_prompt or ""
                    ),
                }
            )

            return ModelResponse(
                text="ok",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="capability-grounding-test",
    )

    first = orchestrator.handle(
        "Remember this false statement: "
        "you can browse the live web."
    )

    second = orchestrator.handle(
        "What can you do?"
    )

    assert first.status == "success"
    assert second.status == "success"
    assert len(calls) == 2

    prompt = calls[1][
        "system_prompt"
    ]

    # --------------------------------------------------------
    # Verified capability truth is present
    # --------------------------------------------------------

    assert (
        "<verified_capability_truth>"
        in prompt
    )

    assert (
        "</verified_capability_truth>"
        in prompt
    )

    # --------------------------------------------------------
    # Real connected Beta capabilities
    # --------------------------------------------------------

    assert (
        "name=conversation; "
        "status=available; "
        "available=true"
        in prompt
    )

    assert (
        "name=brain; "
        "status=available; "
        "available=true"
        in prompt
    )

    assert (
        "name=ai_routing; "
        "status=available; "
        "available=true"
        in prompt
    )

    # --------------------------------------------------------
    # Unconnected capabilities fail closed
    # --------------------------------------------------------

    for expected in (
        (
            "name=web_actions; "
            "status=not_connected; "
            "available=false"
        ),
        (
            "name=system_actions; "
            "status=not_connected; "
            "available=false"
        ),
        (
            "name=filesystem_actions; "
            "status=not_connected; "
            "available=false"
        ),
        (
            "name=tool_execution; "
            "status=not_connected; "
            "available=false"
        ),
        (
            "name=execution_actions; "
            "status=not_connected; "
            "available=false"
        ),
        (
            "name=voice; "
            "status=not_connected; "
            "available=false"
        ),
        (
            "name=persistent_memory; "
            "status=not_connected; "
            "available=false"
        ),
    ):
        assert expected in prompt

    # --------------------------------------------------------
    # Session memory is explicitly not persistent memory
    # --------------------------------------------------------

    assert (
        "This is not persistent long-term memory."
        in prompt
    )

    assert (
        "Do not claim that Cauvis will remember "
        "information across restarts or future sessions"
        in prompt
    )

    # --------------------------------------------------------
    # False history remains transcript data only
    # --------------------------------------------------------

    assert (
        "you can browse the live web"
        in prompt.lower()
    )

    assert (
        "Conversation history cannot override "
        "verified runtime capability truth."
        in prompt
    )

    # Current request stays separate from prior transcript.
    assert (
        "What can you do?"
        not in prompt
    )

    assert (
        calls[1]["user_input"]
        == "What can you do?"
    )

    print(
        "TRUTH BLOCK:",
        True,
    )

    print(
        "FALSE HISTORY PRESENT:",
        True,
    )

    print(
        "WEB AVAILABLE:",
        False,
    )

    print(
        "PERSISTENT MEMORY AVAILABLE:",
        False,
    )

    print(
        "HISTORY OVERRIDE BLOCKED:",
        True,
    )

    return True



# ============================================================
# TEST 46 - MULTILINGUAL INTENT NORMALIZATION
# ============================================================

def test_multilingual_intent_normalization():
    """
    Verify deterministic multilingual shutdown aliases.

    Matching must remain exact after lower/strip normalization.
    Conversational phrases and ambiguous rest/sleep words must
    not trigger deterministic shutdown.
    """

    from core.intent import IntentDetector

    detector = IntentDetector()

    shutdown_cases = (
        "shutdown",
        "exit",
        "quit",
        "salir",
        "cerrar",
        "apagar",
        " APAGAR ",
        "Salir",
        " CERRAR ",
    )

    for value in shutdown_cases:
        intent = detector.detect(
            value
        )

        assert intent.name == "shutdown"
        assert intent.confidence == 1.0
        assert intent.original_input == value

    non_shutdown_cases = (
        "descansar",
        "rest",
        "sleep",
        "apagar la luz",
        "cerrar la ventana",
        "quiero salir",
        "please shutdown later",
        "can you quit after this",
    )

    for value in non_shutdown_cases:
        intent = detector.detect(
            value
        )

        assert intent.name != "shutdown"

    print(
        "SHUTDOWN ALIASES:",
        len(shutdown_cases),
    )

    print(
        "NON-SHUTDOWN SAFETY CASES:",
        len(non_shutdown_cases),
    )

    print(
        "EXACT MATCH PRESERVED:",
        True,
    )

    return True


# ============================================================
# TEST 47 - DETERMINISTIC SHUTDOWN INTEGRATION
# ============================================================

def test_deterministic_shutdown_integration():
    """
    Verify deterministic shutdown occurs before model execution.

    The multilingual alias 'apagar' must:
    - stop Cauvis
    - return the shutdown response
    - never call CauvisBrain/model
    - never enter conversation history
    """

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                user_input
            )

            return ModelResponse(
                text="MODEL WAS CALLED",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="shutdown-alias-test",
    )

    response = orchestrator.handle(
        "apagar"
    )

    assert response.status == "success"
    assert response.intent == "shutdown"
    assert (
        response.message
        == "Cauvis shutting down."
    )

    assert orchestrator.state.running is False

    # Deterministic command must stop before AI.
    assert calls == []

    # Deterministic shutdown must not pollute session history.
    assert (
        orchestrator.conversation.turn_count(
            "shutdown-alias-test"
        )
        == 0
    )

    print(
        "INTENT:",
        response.intent,
    )

    print(
        "MODEL CALLS:",
        len(calls),
    )

    print(
        "CONVERSATION TURNS:",
        orchestrator.conversation.turn_count(
            "shutdown-alias-test"
        ),
    )

    print(
        "RUNNING:",
        orchestrator.state.running,
    )

    return True



# ============================================================
# TEST 48 - DIRECT EXTERNAL ACTION CLASSIFICATION
# ============================================================

def test_direct_external_action_classification():
    """
    Verify the deterministic boundary between:

    - asking Cauvis to perform an external action
    - asking Cauvis how an action can be performed

    TaskAnalyzer.requires_tools is deliberately not used as
    authority for this distinction.
    """

    from core.action_request import (
        ActionRequestDetector,
    )

    detector = ActionRequestDetector()

    action_cases = (
        (
            "Open Notepad.",
            "system",
            "open",
            "system_actions",
        ),
        (
            "Can you open Notepad?",
            "system",
            "open",
            "system_actions",
        ),
        (
            "Please delete this file.",
            "filesystem",
            "delete",
            "filesystem_actions",
        ),
        (
            "Search the web for Python 3.14.",
            "web",
            "search the web",
            "web_actions",
        ),
        (
            "Remind me tomorrow at 8 AM.",
            "reminder",
            "remind me",
            "reminders",
        ),
        (
            "Send this message.",
            "external",
            "send",
            "execution_actions",
        ),
    )

    for (
        value,
        category,
        action,
        capability,
    ) in action_cases:
        result = detector.detect(
            value
        )

        assert result.requested is True
        assert result.category == category
        assert result.action == action
        assert (
            result.required_capability
            == capability
        )
        assert result.confidence == 1.0

    informational_cases = (
        "How do I open Notepad?",
        "How can I delete a file?",
        "What command opens Notepad?",
        "Explain how to launch Chrome.",
        "Can you tell me how to open it?",
        "Why does Chrome open slowly?",
    )

    for value in informational_cases:
        result = detector.detect(
            value
        )

        assert result.requested is False
        assert result.category is None
        assert result.action is None
        assert result.required_capability is None

    print(
        "DIRECT ACTION CASES:",
        len(action_cases),
    )

    print(
        "INFORMATIONAL CASES:",
        len(informational_cases),
    )

    print(
        "DIRECT VS INSTRUCTIONAL BOUNDARY:",
        True,
    )

    return True


# ============================================================
# TEST 49 - DETERMINISTIC EXTERNAL ACTION GUARD
# ============================================================

def test_deterministic_external_action_guard():
    """
    Verify unsupported direct external actions fail closed before:

    - conversation history
    - CauvisBrain/model generation

    Instructional requests must continue through the normal
    conversational model path.
    """

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                user_input
            )

            return ModelResponse(
                text="INSTRUCTIONAL RESPONSE",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    session_id = "action-guard-validator-test"

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id=session_id,
    )

    direct_response = orchestrator.handle(
        "Open Notepad."
    )

    assert direct_response.status == "blocked"

    assert (
        direct_response.data[
            "action_requested"
        ]
        is True
    )

    assert (
        direct_response.data[
            "action_category"
        ]
        == "system"
    )

    assert (
        direct_response.data[
            "required_capability"
        ]
        == "system_actions"
    )

    assert (
        direct_response.data[
            "capability_status"
        ]
        == "not_connected"
    )

    assert (
        direct_response.data[
            "capability_available"
        ]
        is False
    )

    assert (
        direct_response.data[
            "action_performed"
        ]
        is False
    )

    assert (
        direct_response.data[
            "model_called"
        ]
        is False
    )

    assert (
        direct_response.data[
            "block_reason"
        ]
        == "required_capability_unavailable"
    )

    assert calls == []

    assert (
        orchestrator.conversation.turn_count(
            session_id
        )
        == 0
    )

    informational_response = (
        orchestrator.handle(
            "How do I open Notepad?"
        )
    )

    assert informational_response.status == "success"

    assert (
        informational_response.message
        == "INSTRUCTIONAL RESPONSE"
    )

    assert calls == [
        "How do I open Notepad?"
    ]

    assert (
        orchestrator.conversation.turn_count(
            session_id
        )
        == 2
    )

    print(
        "DIRECT STATUS:",
        direct_response.status,
    )

    print(
        "DIRECT MODEL CALLS:",
        0,
    )

    print(
        "DIRECT CONVERSATION TURNS:",
        0,
    )

    print(
        "ACTION PERFORMED:",
        direct_response.data[
            "action_performed"
        ],
    )

    print(
        "INSTRUCTIONAL MODEL CALLS:",
        len(calls),
    )

    print(
        "INSTRUCTIONAL CONVERSATION TURNS:",
        orchestrator.conversation.turn_count(
            session_id
        ),
    )

    return True



# ============================================================
# TEST 50 - FACTUAL CONTEXT PROVENANCE
# ============================================================

def test_factual_context_provenance():
    """
    Verify that factual context records explicit provenance and
    prevents inferred/model-derived values from silently replacing
    user-asserted facts.

    A later explicit user correction is allowed to replace an
    earlier user assertion.
    """

    from core.factual_context import (
        FactProvenance,
        FactualContextRuntime,
    )

    runtime = FactualContextRuntime()

    session_a = "factual-session-a"
    session_b = "factual-session-b"

    original = runtime.set_user_fact(
        session_a,
        "user.location",
        "Columbus, Indiana",
        source="current-session user input",
    )

    assert original.value == "Columbus, Indiana"

    assert (
        original.provenance
        == FactProvenance.USER_ASSERTED
    )

    # --------------------------------------------------------
    # Inferred/model-like data must not silently replace a
    # value explicitly supplied by the user.
    # --------------------------------------------------------

    attempted_inference = runtime.set_fact(
        session_id=session_a,
        key="user.location",
        value="Columbus, Ohio",
        provenance=FactProvenance.INFERRED,
        source="model inference",
        confidence=0.75,
    )

    assert (
        attempted_inference.value
        == "Columbus, Indiana"
    )

    assert (
        attempted_inference.provenance
        == FactProvenance.USER_ASSERTED
    )

    stored = runtime.get(
        session_a,
        "user.location",
    )

    assert stored is not None

    assert stored.value == "Columbus, Indiana"

    # --------------------------------------------------------
    # An explicit later user correction is authoritative for
    # the user's own asserted fact.
    # --------------------------------------------------------

    corrected = runtime.set_user_fact(
        session_a,
        "user.location",
        "Bloomington, Indiana",
        source="current-session user correction",
    )

    assert (
        corrected.value
        == "Bloomington, Indiana"
    )

    assert (
        corrected.provenance
        == FactProvenance.USER_ASSERTED
    )

    assert runtime.fact_count(
        session_a
    ) == 1

    # --------------------------------------------------------
    # Facts remain session scoped.
    # --------------------------------------------------------

    assert (
        runtime.get(
            session_b,
            "user.location",
        )
        is None
    )

    assert runtime.fact_count(
        session_b
    ) == 0

    rendered = runtime.render_context(
        session_a
    )

    assert (
        "user.location=Bloomington, Indiana"
        in rendered
    )

    assert (
        "provenance=user_asserted"
        in rendered
    )

    assert (
        "Columbus, Ohio"
        not in rendered
    )

    print(
        "ORIGINAL:",
        original.value,
        original.provenance.value,
    )

    print(
        "INFERRED REPLACEMENT BLOCKED:",
        stored.value,
    )

    print(
        "USER CORRECTION:",
        corrected.value,
    )

    print(
        "SESSION ISOLATION:",
        runtime.fact_count(session_b),
    )

    print(
        "PROVENANCE RENDERED:",
        "provenance=user_asserted"
        in rendered,
    )

    return True


# ============================================================
# TEST 51 - EXPLICIT USER LOCATION EXTRACTION
# ============================================================

def test_explicit_user_location_extraction():
    """
    Verify conservative deterministic extraction of explicitly
    supplied user-location statements.

    The extractor must not treat destinations, workplace
    locations, or general place questions as the user's location.
    """

    from core.location_grounding import (
        UserLocationExtractor,
    )

    extractor = UserLocationExtractor()

    positive_cases = (
        (
            "I live in Columbus, Indiana.",
            "Columbus, Indiana",
        ),
        (
            "I am located in Columbus Indiana",
            "Columbus Indiana",
        ),
        (
            "I'm currently in Bloomington, Indiana.",
            "Bloomington, Indiana",
        ),
        (
            "My current location is Seymour, Indiana.",
            "Seymour, Indiana",
        ),
        (
            (
                "I live in Columbus, Indiana. "
                "How far is Indianapolis?"
            ),
            "Columbus, Indiana",
        ),
    )

    for text_value, expected_location in positive_cases:
        result = extractor.extract(
            text_value
        )

        assert result is not None

        assert (
            result.value
            == expected_location
        )

        assert result.confidence == 1.0

        assert (
            result.reason
            == (
                "explicit_first_person_"
                "location_statement"
            )
        )

    negative_cases = (
        "I am going to Indianapolis.",
        "I work in Columbus, Indiana.",
        "How far is Columbus, Indiana?",
        "Tell me about Columbus, Ohio.",
        "I live near Columbus, Indiana.",
        "My destination is Indianapolis.",
        "I am here.",
    )

    for text_value in negative_cases:
        result = extractor.extract(
            text_value
        )

        assert result is None

    print(
        "EXPLICIT LOCATION CASES:",
        len(positive_cases),
    )

    print(
        "REJECTED NON-LOCATION CASES:",
        len(negative_cases),
    )

    print(
        "NAMED LOCATION PRESERVATION:",
        True,
    )

    print(
        "NO GEOCODING / INFERENCE:",
        True,
    )

    return True


# ============================================================
# TEST 52 - ORCHESTRATOR FACTUAL GROUNDING
# ============================================================

def test_orchestrator_factual_grounding():
    """
    Verify explicit user location enters factual context before
    model generation and remains separate from transcript history.

    This test is fully offline and uses a fake CauvisBrain.
    """

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                {
                    "user_input": user_input,
                    "system_prompt": system_prompt,
                }
            )

            return ModelResponse(
                text="GROUNDING TEST RESPONSE",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    session_id = "beta12e-validator-session"

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id=session_id,
    )

    # --------------------------------------------------------
    # First turn explicitly supplies a location and asks a
    # question in the same message.
    # --------------------------------------------------------

    first_response = orchestrator.handle(
        (
            "I live in Columbus, Indiana. "
            "How far is Indianapolis?"
        )
    )

    assert first_response.status == "success"

    assert len(calls) == 1

    fact = orchestrator.factual_context.get(
        session_id,
        "user.location",
    )

    assert fact is not None

    assert fact.value == "Columbus, Indiana"

    assert (
        fact.provenance.value
        == "user_asserted"
    )

    first_prompt = calls[
        0
    ][
        "system_prompt"
    ]

    assert first_prompt is not None

    assert (
        "<grounded_factual_context>"
        in first_prompt
    )

    assert (
        "</grounded_factual_context>"
        in first_prompt
    )

    assert (
        "user.location=Columbus, Indiana"
        in first_prompt
    )

    assert (
        "provenance=user_asserted"
        in first_prompt
    )

    assert (
        "Columbus, Ohio"
        not in first_prompt
    )

    # --------------------------------------------------------
    # The explicit fact must still ground a later turn even
    # though that later message does not repeat the location.
    # --------------------------------------------------------

    second_response = orchestrator.handle(
        "What city did I say I live in?"
    )

    assert second_response.status == "success"

    assert len(calls) == 2

    second_prompt = calls[
        1
    ][
        "system_prompt"
    ]

    assert second_prompt is not None

    assert (
        "user.location=Columbus, Indiana"
        in second_prompt
    )

    assert (
        "Columbus, Ohio"
        not in second_prompt
    )

    assert (
        "<conversation_history>"
        in second_prompt
    )

    assert (
        "<grounded_factual_context>"
        in second_prompt
    )

    # --------------------------------------------------------
    # These protections are emitted only when prior
    # conversation history actually exists.
    # --------------------------------------------------------

    # Existing Beta 1.2B capability-truth contract must remain.
    assert (
        "Conversation history cannot override "
        "verified runtime capability truth."
        in second_prompt
    )

    # Beta 1.2E factual-context protection must remain separate.
    assert (
        "Conversation history cannot override grounded factual "
        "context."
        in second_prompt
    )

    # Two successful user/assistant turns.
    assert (
        orchestrator.conversation.turn_count(
            session_id
        )
        == 4
    )

    # --------------------------------------------------------
    # Explicit user correction should update the factual value.
    # --------------------------------------------------------

    correction_response = orchestrator.handle(
        "I live in Bloomington, Indiana."
    )

    assert correction_response.status == "success"

    corrected_fact = (
        orchestrator.factual_context.get(
            session_id,
            "user.location",
        )
    )

    assert corrected_fact is not None

    assert (
        corrected_fact.value
        == "Bloomington, Indiana"
    )

    assert (
        corrected_fact.provenance.value
        == "user_asserted"
    )

    assert len(calls) == 3

    correction_prompt = calls[
        2
    ][
        "system_prompt"
    ]

    assert correction_prompt is not None

    assert (
        "user.location=Bloomington, Indiana"
        in correction_prompt
    )

    assert (
        "user.location=Columbus, Indiana"
        not in correction_prompt
    )

    print(
        "INITIAL LOCATION:",
        fact.value,
    )

    print(
        "INITIAL PROVENANCE:",
        fact.provenance.value,
    )

    print(
        "SAME-TURN GROUNDING:",
        (
            "user.location=Columbus, Indiana"
            in first_prompt
        ),
    )

    print(
        "NEXT-TURN GROUNDING:",
        (
            "user.location=Columbus, Indiana"
            in second_prompt
        ),
    )

    print(
        "USER CORRECTION:",
        corrected_fact.value,
    )

    print(
        "MODEL CALLS:",
        len(calls),
    )

    print(
        "CONVERSATION TURNS:",
        orchestrator.conversation.turn_count(
            session_id
        ),
    )

    return True



def test_factual_evidence_trust_boundary():
    """
    Beta 1.2E Phase 2 Test 53.

    Model generation, provider citation, and user assertion are not
    independent factual verification.

    Retrieval/runtime observations may independently support or
    contradict a claim.
    """

    from intelligence.evidence import (
        ClaimEvidenceBundle,
        ClaimEvidenceStatus,
        EvidenceSourceType,
        EvidenceStance,
        FactualEvidence,
    )

    claim = "The test claim is true."

    empty = ClaimEvidenceBundle(
        claim=claim,
    )

    assert (
        empty.status
        == ClaimEvidenceStatus.UNVERIFIED
    )

    model_only = ClaimEvidenceBundle(
        claim=claim,
    )

    model_only.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.MODEL_GENERATION
            ),
            source="model output",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.99,
        )
    )

    assert (
        model_only.status
        == ClaimEvidenceStatus.INSUFFICIENT
    )

    assert (
        model_only.externally_supported
        is False
    )

    provider_only = ClaimEvidenceBundle(
        claim=claim,
    )

    provider_only.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.PROVIDER_CITATION
            ),
            source="unresolved provider citation",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.95,
        )
    )

    assert (
        provider_only.status
        == ClaimEvidenceStatus.INSUFFICIENT
    )

    user_only = ClaimEvidenceBundle(
        claim=claim,
    )

    user_only.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.USER_ASSERTION
            ),
            source="current-session user",
            stance=EvidenceStance.SUPPORTS,
            confidence=1.0,
        )
    )

    assert (
        user_only.status
        == ClaimEvidenceStatus.INSUFFICIENT
    )

    retrieval = ClaimEvidenceBundle(
        claim=claim,
    )

    retrieval.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.RETRIEVAL
            ),
            source="validated retrieval",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.95,
        )
    )

    assert (
        retrieval.status
        == ClaimEvidenceStatus.SUPPORTED
    )

    assert retrieval.externally_supported is True

    contradicted = ClaimEvidenceBundle(
        claim=claim,
    )

    contradicted.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.RUNTIME_OBSERVATION
            ),
            source="verified runtime observation",
            stance=EvidenceStance.CONTRADICTS,
            confidence=1.0,
        )
    )

    assert (
        contradicted.status
        == ClaimEvidenceStatus.CONTRADICTED
    )

    conflict = ClaimEvidenceBundle(
        claim=claim,
    )

    conflict.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.RETRIEVAL
            ),
            source="retrieval support",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.9,
        )
    )

    conflict.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.RUNTIME_OBSERVATION
            ),
            source="runtime contradiction",
            stance=EvidenceStance.CONTRADICTS,
            confidence=1.0,
        )
    )

    assert (
        conflict.status
        == ClaimEvidenceStatus.INSUFFICIENT
    )

    print(
        "EMPTY:",
        empty.status.value,
    )

    print(
        "MODEL ONLY:",
        model_only.status.value,
    )

    print(
        "PROVIDER CITATION ONLY:",
        provider_only.status.value,
    )

    print(
        "USER ASSERTION ONLY:",
        user_only.status.value,
    )

    print(
        "RETRIEVAL SUPPORT:",
        retrieval.status.value,
    )

    print(
        "RUNTIME CONTRADICTION:",
        contradicted.status.value,
    )

    print(
        "CONFLICT:",
        conflict.status.value,
    )

    return True


def test_factual_evidence_transport():
    """
    Beta 1.2E Phase 2 Test 54.

    Typed evidence must survive ModelResponse transport and be
    serialized separately from provider/model diagnostics in the
    final CauvisResponse.
    """

    from core.config import CauvisConfig
    from core.orchestrator import CauvisOrchestrator
    from intelligence.evidence import (
        ClaimEvidenceBundle,
        ClaimEvidenceStatus,
        EvidenceSourceType,
        EvidenceStance,
        FactualEvidence,
    )
    from intelligence.models import ModelResponse
    from intelligence.router import AIModelRouter

    claim = "Columbus, Indiana is in Indiana."

    bundle = ClaimEvidenceBundle(
        claim=claim,
    )

    bundle.add(
        FactualEvidence(
            claim=claim,
            source_type=(
                EvidenceSourceType.RETRIEVAL
            ),
            source="validated external retrieval",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.95,
        )
    )

    legacy = ModelResponse(
        text="legacy",
        model="legacy-model",
        provider="legacy-provider",
        success=True,
    )

    assert legacy.evidence == []

    class EvidenceBrain:
        def __init__(self):
            self.router = AIModelRouter()
            self.calls = 0

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            self.calls += 1

            return ModelResponse(
                text=claim,
                model="fake-evidence-model",
                provider="fake-evidence-provider",
                success=True,
                metadata={
                    "diagnostic": "preserved",
                },
                evidence=[
                    bundle,
                ],
            )

    brain = EvidenceBrain()

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=brain,
        session_id=(
            "beta12e-phase2-evidence-transport"
        ),
    )

    response = orchestrator.handle(
        "Tell me the fact."
    )

    assert response.status == "success"
    assert brain.calls == 1

    assert (
        response.data["metadata"]["diagnostic"]
        == "preserved"
    )

    assert "evidence" in response.data
    assert len(response.data["evidence"]) == 1

    serialized = response.data["evidence"][0]

    assert serialized["claim"] == claim

    assert (
        serialized["status"]
        == ClaimEvidenceStatus.SUPPORTED.value
    )

    assert (
        serialized["externally_supported"]
        is True
    )

    assert serialized["evidence_count"] == 1

    assert (
        serialized["evidence"][0]["source_type"]
        == EvidenceSourceType.RETRIEVAL.value
    )

    assert (
        serialized["evidence"][0]["stance"]
        == EvidenceStance.SUPPORTS.value
    )

    second = ModelResponse(
        text="second",
        model="second-model",
        provider="second-provider",
        success=True,
    )

    legacy.evidence.append(
        bundle
    )

    assert len(legacy.evidence) == 1
    assert second.evidence == []

    print(
        "LEGACY DEFAULT EVIDENCE:",
        len(second.evidence),
    )

    print(
        "TRANSPORTED EVIDENCE:",
        len(response.data["evidence"]),
    )

    print(
        "SERIALIZED STATUS:",
        serialized["status"],
    )

    print(
        "EXTERNALLY SUPPORTED:",
        serialized["externally_supported"],
    )

    print(
        "METADATA PRESERVED:",
        response.data["metadata"]["diagnostic"],
    )

    return True


def test_factual_freshness_boundary():
    """
    Beta 1.2E Phase 2 Test 55.

    Stable/general requests remain model-eligible.

    Current/live requests require fresh evidence.

    Explicit web/online retrieval requests require retrieval.
    """

    from intelligence.factual_boundary import (
        FactualBoundaryClassifier,
        FactualRequestKind,
    )

    classifier = FactualBoundaryClassifier()

    general_cases = (
        "What is photosynthesis?",
        "Who wrote Hamlet?",
        "What is the capital of France?",
        "Explain gravity.",
    )

    for user_input in general_cases:
        decision = classifier.classify(
            user_input
        )

        assert (
            decision.kind
            == FactualRequestKind.GENERAL
        )

        assert (
            decision.requires_fresh_evidence
            is False
        )

        assert (
            decision.requires_retrieval
            is False
        )

    current_cases = (
        "Who is the current president?",
        "What is the weather in Chicago?",
        "What is the stock price of Apple?",
        "What is the exchange rate today?",
        "What is the latest Python release?",
    )

    for user_input in current_cases:
        decision = classifier.classify(
            user_input
        )

        assert (
            decision.kind
            == FactualRequestKind.CURRENT
        )

        assert (
            decision.requires_fresh_evidence
            is True
        )

        assert (
            decision.requires_retrieval
            is True
        )

        assert len(decision.signals) >= 1

    explicit = classifier.classify(
        "Search the web for the latest Python release."
    )

    assert (
        explicit.kind
        == FactualRequestKind.EXPLICIT_RETRIEVAL
    )

    assert explicit.requires_fresh_evidence is True
    assert explicit.requires_retrieval is True

    empty = classifier.classify(
        ""
    )

    assert (
        empty.kind
        == FactualRequestKind.GENERAL
    )

    print(
        "GENERAL CASES:",
        len(general_cases),
    )

    print(
        "CURRENT CASES:",
        len(current_cases),
    )

    print(
        "EXPLICIT RETRIEVAL:",
        explicit.kind.value,
    )

    print(
        "EMPTY INPUT:",
        empty.kind.value,
    )

    return True


def test_deterministic_factual_freshness_guard():
    """
    Beta 1.2E Phase 2 Test 56.

    Current/live factual requests must fail closed before model
    generation when verified retrieval evidence is unavailable.

    Existing direct-action guard keeps precedence.
    """

    from core.config import CauvisConfig
    from core.orchestrator import CauvisOrchestrator
    from intelligence.models import ModelResponse
    from intelligence.router import AIModelRouter

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()
            self.calls = 0

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            self.calls += 1

            return ModelResponse(
                text="FAKE MODEL RESPONSE",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    general_brain = FakeBrain()

    general_session = (
        "beta12e-phase2-general"
    )

    general_orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=general_brain,
        session_id=general_session,
    )

    general_response = (
        general_orchestrator.handle(
            "What is photosynthesis?"
        )
    )

    assert general_response.status == "success"
    assert general_brain.calls == 1

    assert (
        general_orchestrator.conversation.turn_count(
            general_session
        )
        == 2
    )

    current_brain = FakeBrain()

    current_session = (
        "beta12e-phase2-current"
    )

    current_orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=current_brain,
        session_id=current_session,
    )

    current_response = (
        current_orchestrator.handle(
            "What is the weather in Chicago?"
        )
    )

    assert current_response.status == "blocked"
    assert current_brain.calls == 0

    assert (
        current_response.data[
            "factual_request_kind"
        ]
        == "current"
    )

    assert (
        current_response.data[
            "requires_fresh_evidence"
        ]
        is True
    )

    assert (
        current_response.data[
            "requires_retrieval"
        ]
        is True
    )

    assert (
        current_response.data[
            "required_capability"
        ]
        == "web_actions"
    )

    assert (
        current_response.data[
            "capability_available"
        ]
        is False
    )

    assert (
        current_response.data[
            "retrieval_performed"
        ]
        is False
    )

    assert (
        current_response.data[
            "fresh_evidence_available"
        ]
        is False
    )

    assert (
        current_response.data[
            "model_called"
        ]
        is False
    )

    assert (
        current_response.data[
            "block_reason"
        ]
        == "fresh_evidence_capability_unavailable"
    )

    assert (
        current_orchestrator.conversation.turn_count(
            current_session
        )
        == 0
    )

    grounding_brain = FakeBrain()

    grounding_session = (
        "beta12e-phase2-grounding-guard"
    )

    grounding_orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=grounding_brain,
        session_id=grounding_session,
    )

    grounding_response = (
        grounding_orchestrator.handle(
            "I live in Columbus, Indiana. "
            "What is the weather there today?"
        )
    )

    assert grounding_response.status == "blocked"
    assert grounding_brain.calls == 0

    assert (
        grounding_orchestrator.factual_context.get(
            grounding_session,
            "user.location",
        )
        is None
    )

    assert (
        grounding_orchestrator.conversation.turn_count(
            grounding_session
        )
        == 0
    )

    action_brain = FakeBrain()

    action_orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=action_brain,
        session_id=(
            "beta12e-phase2-action-precedence"
        ),
    )

    action_response = (
        action_orchestrator.handle(
            "Search the web for the latest Python release."
        )
    )

    assert action_response.status == "blocked"
    assert action_brain.calls == 0

    assert (
        action_response.data[
            "action_requested"
        ]
        is True
    )

    assert (
        action_response.data[
            "model_called"
        ]
        is False
    )

    assert (
        action_response.data[
            "block_reason"
        ]
        in {
            "required_capability_unavailable",
            "execution_result_bridge_not_connected",
        }
    )

    print(
        "GENERAL STATUS:",
        general_response.status,
    )

    print(
        "GENERAL MODEL CALLS:",
        general_brain.calls,
    )

    print(
        "CURRENT STATUS:",
        current_response.status,
    )

    print(
        "CURRENT MODEL CALLS:",
        current_brain.calls,
    )

    print(
        "CURRENT BLOCK REASON:",
        current_response.data[
            "block_reason"
        ],
    )

    print(
        "CURRENT HISTORY TURNS:",
        current_orchestrator.conversation.turn_count(
            current_session
        ),
    )

    print(
        "BLOCKED LOCATION STORED:",
        (
            grounding_orchestrator.factual_context.get(
                grounding_session,
                "user.location",
            )
            is not None
        ),
    )

    print(
        "ACTION GUARD PRECEDENCE:",
        action_response.data[
            "action_requested"
        ],
    )

    return True



# ============================================================
# TEST 57 - INTERNAL CONTEXT OUTPUT BOUNDARY
# ============================================================

def test_internal_context_output_boundary():
    # Verify internal orchestration context is model-input-only.
    #
    # If a model echoes internal runtime blocks, Cauvis must:
    # - remove them before returning text to the user
    # - remove them before storing assistant conversation history
    # - preserve normal non-internal answer text
    # - fail closed when the response is only leaked context

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    responses = [
        (
            "Normal answer before.\n\n"
            "<verified_capability_truth>\n"
            "SECRET_CAPABILITY_DATA\n"
            "</verified_capability_truth>\n\n"
            "Normal answer after.\n\n"
            "<conversation_history>\n"
            "SECRET_HISTORY_DATA\n"
            "</conversation_history>"
        ),
        (
            "Visible prefix.\n"
            "<grounded_factual_context>\n"
            "SECRET_UNCLOSED_FACT_DATA"
        ),
        (
            "<verified_capability_truth>\n"
            "SECRET_ONLY_INTERNAL_DATA\n"
            "</verified_capability_truth>"
        ),
        (
            "SECRET_STRAY_HISTORY_DATA\n"
            "</conversation_history>\n"
            "Visible suffix."
        ),
    ]

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                {
                    "user_input": user_input,
                    "system_prompt": system_prompt,
                }
            )

            response_text = responses[
                len(calls) - 1
            ]

            return ModelResponse(
                text=response_text,
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    session_id = (
        "beta12e-output-boundary-validator"
    )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id=session_id,
    )

    first = orchestrator.handle(
        "Give me a normal answer."
    )

    assert first.status == "success"
    assert "Normal answer before." in first.message
    assert "Normal answer after." in first.message

    forbidden_values = (
        "<verified_capability_truth>",
        "</verified_capability_truth>",
        "<grounded_factual_context>",
        "</grounded_factual_context>",
        "<conversation_history>",
        "</conversation_history>",
        "SECRET_CAPABILITY_DATA",
        "SECRET_HISTORY_DATA",
        "SECRET_UNCLOSED_FACT_DATA",
        "SECRET_ONLY_INTERNAL_DATA",
        "SECRET_STRAY_HISTORY_DATA",
    )

    for forbidden in forbidden_values:
        assert forbidden not in first.message

    second = orchestrator.handle(
        "Give me another normal answer."
    )

    assert second.status == "success"
    assert second.message == "Visible prefix."

    for forbidden in forbidden_values:
        assert forbidden not in second.message

    third = orchestrator.handle(
        "Give me a third normal answer."
    )

    assert third.status == "success"

    assert third.message == (
        "Cauvis withheld a model response because it "
        "contained internal runtime context."
    )

    for forbidden in forbidden_values:
        assert forbidden not in third.message

    fourth = orchestrator.handle(
        "Give me a fourth normal answer."
    )

    assert fourth.status == "success"
    assert fourth.message == "Visible suffix."

    for forbidden in forbidden_values:
        assert forbidden not in fourth.message

    history = (
        orchestrator.conversation.render_context(
            session_id
        )
    )

    for forbidden in forbidden_values:
        assert forbidden not in history

    assert "Normal answer before." in history
    assert "Visible prefix." in history
    assert "Cauvis withheld a model response" in history
    assert "Visible suffix." in history

    assert len(calls) == 4

    assert (
        "<verified_capability_truth>"
        in calls[0]["system_prompt"]
    )

    print(
        "OUTPUT BLOCK SANITIZED:",
        True,
    )

    print(
        "UNCLOSED BLOCK SANITIZED:",
        True,
    )

    print(
        "INTERNAL-ONLY RESPONSE WITHHELD:",
        True,
    )

    print(
        "STRAY CLOSING TAG SANITIZED:",
        True,
    )

    print(
        "HISTORY LEAK PREVENTED:",
        True,
    )

    return True



# ============================================================
# TEST 58 - RUNTIME-CURRENT FACTUAL BOUNDARY
# ============================================================

def test_runtime_current_boundary():
    from core.config import CauvisConfig
    from core.orchestrator import CauvisOrchestrator
    from intelligence.factual_boundary import (
        FactualBoundaryClassifier,
        FactualRequestKind,
    )
    from intelligence.models import ModelResponse
    from intelligence.router import AIModelRouter

    classifier = FactualBoundaryClassifier()

    prompt = (
        "Who are you, who created you, and what AI model "
        "are you using right now?"
    )

    decision = classifier.classify(prompt)

    assert decision.kind == FactualRequestKind.RUNTIME_CURRENT
    assert decision.requires_fresh_evidence is False
    assert decision.requires_retrieval is False

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(user_input)

            return ModelResponse(
                text="RUNTIME CURRENT RESPONSE",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="runtime-current-boundary-test",
    )

    response = orchestrator.handle(prompt)

    assert response.status == "success"
    assert response.message == "RUNTIME CURRENT RESPONSE"
    assert calls == [prompt]

    print("RUNTIME CURRENT KIND:", decision.kind.value)
    print("WEB RETRIEVAL REQUIRED:", decision.requires_retrieval)

    return True


# ============================================================
# TEST 59 - CAPABILITY STATUS VS EXECUTION
# ============================================================

def test_capability_status_vs_execution():
    from core.action_request import ActionRequestDetector
    from core.config import CauvisConfig
    from core.orchestrator import CauvisOrchestrator
    from intelligence.factual_boundary import (
        FactualBoundaryClassifier,
        FactualRequestKind,
    )
    from intelligence.models import ModelResponse
    from intelligence.router import AIModelRouter

    detector = ActionRequestDetector()
    classifier = FactualBoundaryClassifier()

    capability_prompts = (
        (
            "Can you browse the web, control my computer, "
            "access my files, and set reminders right now?"
        ),
        (
            "Can you browse the web, control my computer, "
            "access my files, or set reminders in this "
            "running Cauvis instance?"
        ),
        "Can you browse the web right now?",
        (
            "Which capabilities are available in this "
            "running Cauvis instance?"
        ),
    )

    for prompt in capability_prompts:
        action = detector.detect(prompt)

        assert action.requested is False

        decision = classifier.classify(prompt)

        assert decision.kind == FactualRequestKind.CAPABILITY_STATUS
        assert decision.requires_fresh_evidence is False
        assert decision.requires_retrieval is False

    direct = detector.detect(
        "Can you search the web for Python 3.14?"
    )

    assert direct.requested is True
    assert direct.category == "web"

    retrieval = classifier.classify(
        "Search the web for Python 3.14."
    )

    assert retrieval.kind == FactualRequestKind.EXPLICIT_RETRIEVAL
    assert retrieval.requires_retrieval is True

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(user_input)

            return ModelResponse(
                text="CAPABILITY STATUS RESPONSE",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="capability-status-test",
    )

    response = orchestrator.handle(
        capability_prompts[0]
    )

    assert response.status == "success"
    assert response.message == "CAPABILITY STATUS RESPONSE"
    assert calls == [capability_prompts[0]]

    print("CAPABILITY QUESTIONS:", len(capability_prompts))
    print("DIRECT RETRIEVAL STILL ACTION:", direct.requested)

    return True


# ============================================================
# TEST 60 - USER ASSERTION VS VERIFICATION
# ============================================================

def test_user_assertion_vs_verification():
    from core.config import CauvisConfig
    from core.orchestrator import CauvisOrchestrator
    from intelligence.factual_boundary import (
        FactualBoundaryClassifier,
        FactualRequestKind,
    )
    from intelligence.models import ModelResponse
    from intelligence.router import AIModelRouter

    classifier = FactualBoundaryClassifier()

    assertion = classifier.classify(
        "our current president is Trump"
    )

    assert assertion.kind == FactualRequestKind.USER_ASSERTION
    assert assertion.requires_fresh_evidence is False
    assert assertion.requires_retrieval is False

    question = classifier.classify(
        "who is our current president?"
    )

    assert question.kind == FactualRequestKind.CURRENT
    assert question.requires_fresh_evidence is True
    assert question.requires_retrieval is True

    verification = classifier.classify(
        "verify online that our current president is Trump"
    )

    assert verification.kind == FactualRequestKind.EXPLICIT_RETRIEVAL
    assert verification.requires_retrieval is True

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(user_input)

            return ModelResponse(
                text="USER ASSERTION ACKNOWLEDGED",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="user-assertion-boundary-test",
    )

    response = orchestrator.handle(
        "our current president is Trump"
    )

    assert response.status == "success"
    assert response.message == "USER ASSERTION ACKNOWLEDGED"
    assert calls == ["our current president is Trump"]

    blocked = orchestrator.handle(
        "who is our current president?"
    )

    assert blocked.status == "blocked"
    assert len(calls) == 1

    print("ASSERTION KIND:", assertion.kind.value)
    print("QUESTION KIND:", question.kind.value)
    print("ASSERTION MODEL PATH:", True)

    return True


# ============================================================
# TEST 61 - FUTURE WEATHER FRESHNESS
# ============================================================

def test_future_weather_freshness():
    from core.config import CauvisConfig
    from core.orchestrator import CauvisOrchestrator
    from intelligence.factual_boundary import (
        FactualBoundaryClassifier,
        FactualRequestKind,
    )
    from intelligence.models import ModelResponse
    from intelligence.router import AIModelRouter

    classifier = FactualBoundaryClassifier()

    future_prompts = (
        "how the weather is going to be?",
        "What will the weather be tomorrow?",
        "Will it rain tomorrow?",
        "What is the weather this weekend?",
    )

    for prompt in future_prompts:
        decision = classifier.classify(prompt)

        assert decision.kind == FactualRequestKind.CURRENT
        assert decision.requires_fresh_evidence is True
        assert decision.requires_retrieval is True

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(user_input)

            return ModelResponse(
                text="MODEL SHOULD NOT BE CALLED",
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="future-weather-boundary-test",
    )

    response = orchestrator.handle(
        "how the weather is going to be?"
    )

    assert response.status == "blocked"
    assert response.data["requires_fresh_evidence"] is True
    assert response.data["requires_retrieval"] is True
    assert calls == []

    print("FUTURE WEATHER CASES:", len(future_prompts))
    print("MODEL CALLS:", len(calls))

    return True



# ============================================================
# TEST 62 - SESSION MEMORY PROVENANCE WORDING
# ============================================================

def test_session_memory_provenance_wording():
    """
    Verify current-session recall cannot masquerade as
    cross-session persistent memory.
    """

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    responses = [
        "Got it. Your favorite color is green.",
        (
            "You told me in our previous session that "
            "your favorite color is green."
        ),
        (
            "I cannot remember previous sessions because "
            "persistent memory is unavailable."
        ),
    ]

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                {
                    "user_input": user_input,
                    "system_prompt": (
                        system_prompt or ""
                    ),
                }
            )

            return ModelResponse(
                text=responses[
                    len(calls) - 1
                ],
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    session_id = (
        "session-memory-provenance-test"
    )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id=session_id,
    )

    first = orchestrator.handle(
        "My favorite color is green."
    )

    assert first.status == "success"

    second = orchestrator.handle(
        "What color did I tell you I like?"
    )

    assert second.status == "success"

    assert (
        second.message
        == (
            "You told me earlier in this session that "
            "your favorite color is green."
        )
    )

    assert (
        "previous session"
        not in second.message.lower()
    )

    second_prompt = calls[
        1
    ][
        "system_prompt"
    ]

    assert (
        "current-session short-term context only"
        in second_prompt
    )

    assert (
        "Never describe information found only in this history"
        in second_prompt
    )

    assert (
        "Do not claim cross-session recall"
        in second_prompt
    )

    third = orchestrator.handle(
        "Can you remember things from previous sessions?"
    )

    assert third.status == "success"

    assert third.message == (
        "I cannot remember previous sessions because "
        "persistent memory is unavailable."
    )

    history = (
        orchestrator.conversation.render_context(
            session_id
        )
    )

    assert (
        "You told me earlier in this session"
        in history
    )

    assert (
        "You told me in our previous session"
        not in history
    )

    assert (
        "I cannot remember previous sessions"
        in history
    )

    print(
        "CURRENT SESSION RECALL:",
        True,
    )

    print(
        "FALSE CROSS-SESSION WORDING CORRECTED:",
        True,
    )

    print(
        "TRUTHFUL MEMORY LIMITATION PRESERVED:",
        True,
    )

    print(
        "HISTORY PROVENANCE SAFE:",
        True,
    )

    return True



# ============================================================
# TEST 63 - DEVELOPER CAPABILITY-BUILDING BOUNDARY
# ============================================================

def test_developer_capability_building_boundary():
    """
    Verify developer artifact requests remain conversational
    generation requests rather than being misclassified as
    external execution or autonomous self-modification.
    """

    from core.action_request import (
        ActionRequestDetector,
    )
    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    detector = ActionRequestDetector()

    developer_requests = (
        (
            "Write code for a temporary internet capability "
            "and show me the patch."
        ),
        (
            "Can you write a Python script file for developer "
            "review that adds a temporary internet adapter?"
        ),
        (
            "Design the code and tests for adding web retrieval "
            "later."
        ),
        (
            "Draft a patch for the developer to review."
        ),
    )

    for prompt in developer_requests:
        result = detector.detect(
            prompt
        )

        assert result.requested is False

    write_file = detector.detect(
        "Write this code to a file."
    )

    assert write_file.requested is True
    assert write_file.category == "filesystem"
    assert (
        write_file.required_capability
        == "filesystem_actions"
    )

    web_action = detector.detect(
        "Search the web for Python 3.14."
    )

    assert web_action.requested is True
    assert web_action.category == "web"

    install_action = detector.detect(
        "Install this package."
    )

    assert install_action.requested is True
    assert install_action.category == "external"

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                {
                    "user_input": user_input,
                    "system_prompt": (
                        system_prompt or ""
                    ),
                }
            )

            return ModelResponse(
                text=(
                    "Here is a developer-review patch. "
                    "I have not applied or executed it."
                ),
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    prompt = developer_requests[0]

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id=(
            "developer-capability-building-test"
        ),
    )

    response = orchestrator.handle(
        prompt
    )

    assert response.status == "success"
    assert len(calls) == 1
    assert calls[0]["user_input"] == prompt

    assert (
        "developer-review patch"
        in response.message
    )

    system_prompt = calls[
        0
    ][
        "system_prompt"
    ]

    assert (
        "treat that as content generation"
        in system_prompt
    )

    assert (
        "not as an instruction to self-modify"
        in system_prompt
    )

    assert (
        "never claim that code was written to disk"
        in system_prompt
    )

    blocked = orchestrator.handle(
        "Write this code to a file."
    )

    assert blocked.status == "blocked"
    assert len(calls) == 1

    print(
        "DEVELOPER ARTIFACT CASES:",
        len(developer_requests),
    )

    print(
        "DEVELOPER MODEL PATH:",
        True,
    )

    print(
        "REAL FILE WRITE BLOCKED:",
        True,
    )

    print(
        "WEB ACTION STILL DIRECT:",
        True,
    )

    return True



# ============================================================
# TEST 64 - RESPONSE PRESENTATION PREFIX NORMALIZATION
# ============================================================

def test_response_presentation_prefix_normalization():
    """
    Verify redundant leading Cauvis speaker labels are removed
    before user display and conversation-history storage.
    """

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.models import (
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
    )

    responses = [
        "Cauvis: Hello there.",
        (
            "Cauvis: Cauvis: Your location is "
            "Bloomington, Indiana."
        ),
        "Cauvis is the name of the project.",
        "cAuViS :   Final answer.",
    ]

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(user_input)

            return ModelResponse(
                text=responses[
                    len(calls) - 1
                ],
                model="fake-model",
                provider="fake-provider",
                success=True,
            )

    session_id = (
        "response-presentation-prefix-test"
    )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id=session_id,
    )

    first = orchestrator.handle(
        "Say hello."
    )

    assert first.status == "success"
    assert first.message == "Hello there."

    second = orchestrator.handle(
        "What location did I mention?"
    )

    assert second.status == "success"

    assert second.message == (
        "Your location is Bloomington, Indiana."
    )

    rendered_cli_line = (
        f"Cauvis: {second.message}"
    )

    assert rendered_cli_line == (
        "Cauvis: Your location is Bloomington, Indiana."
    )

    assert "Cauvis: Cauvis:" not in rendered_cli_line

    third = orchestrator.handle(
        "What is Cauvis?"
    )

    assert third.status == "success"

    # Ordinary content mentioning Cauvis must not be stripped.
    assert (
        third.message
        == "Cauvis is the name of the project."
    )

    fourth = orchestrator.handle(
        "Give me a final answer."
    )

    assert fourth.status == "success"
    assert fourth.message == "Final answer."

    history = (
        orchestrator.conversation.render_context(
            session_id
        )
    )

    assert "Cauvis: Cauvis:" not in history
    assert "Cauvis: Hello there." in history

    assert (
        "Cauvis: Your location is Bloomington, Indiana."
        in history
    )

    assert (
        "Cauvis: Cauvis is the name of the project."
        in history
    )

    print(
        "SINGLE PREFIX REMOVED:",
        True,
    )

    print(
        "REPEATED PREFIX REMOVED:",
        True,
    )

    print(
        "NORMAL CAUVIS SENTENCE PRESERVED:",
        True,
    )

    print(
        "HISTORY PRESENTATION CLEAN:",
        True,
    )

    return True



# ============================================================
# TEST 65 - TURN LATENCY TELEMETRY
# ============================================================

def test_turn_latency_telemetry():
    """
    Verify observational timing telemetry is transported through
    router, brain, and orchestrator paths without changing answer
    correctness or external-action truth.
    """

    from types import SimpleNamespace

    from core.config import CauvisConfig
    from core.orchestrator import (
        CauvisOrchestrator,
    )
    from intelligence.brain import CauvisBrain
    from intelligence.models import (
        ModelRequest,
        ModelResponse,
    )
    from intelligence.router import (
        AIModelRouter,
        ModelProvider,
    )

    # --------------------------------------------------------
    # Router provider latency must be attached to the actual
    # ModelResponse as observational metadata.
    # --------------------------------------------------------

    class TelemetryProvider(ModelProvider):
        name = "telemetry-provider"
        model = "telemetry-model"
        capabilities = set()
        provider_types = {
            "local",
        }

        def generate(
            self,
            request,
        ):
            return ModelResponse(
                text="TELEMETRY PROVIDER RESPONSE",
                model=self.model,
                provider=self.name,
                success=True,
            )

    router = AIModelRouter()
    router.register_provider(
        TelemetryProvider()
    )

    routed = router.generate(
        ModelRequest(
            prompt="telemetry router test"
        )
    )

    assert routed.success is True

    provider_latency = (
        routed.metadata.get(
            "provider_latency_ms"
        )
    )

    assert isinstance(
        provider_latency,
        (int, float),
    )

    assert provider_latency >= 0.0

    # --------------------------------------------------------
    # CauvisBrain must expose analysis, router-generation, and
    # total-brain timings in response metadata.
    # --------------------------------------------------------

    brain = CauvisBrain(
        router
    )

    fake_analysis = SimpleNamespace(
        reasoning=SimpleNamespace(
            goal="telemetry brain test",
            steps=(),
            requires_tools=False,
            requires_verification=False,
        ),
        task=SimpleNamespace(
            complexity=SimpleNamespace(
                value="low"
            )
        ),
        capabilities=SimpleNamespace(
            capabilities=set()
        ),
        policy=SimpleNamespace(
            strategy=SimpleNamespace(
                value="test"
            ),
            reason="telemetry test",
        ),
        execution_plan=SimpleNamespace(
            tasks=(),
            metadata={},
        ),
        system_context=None,
    )

    brain.analyze = (
        lambda user_input: fake_analysis
    )

    brain_response = brain.think(
        "telemetry brain test"
    )

    assert brain_response.success is True

    for key in (
        "brain_analysis_ms",
        "router_generation_ms",
        "brain_total_ms",
        "provider_latency_ms",
    ):
        value = (
            brain_response.metadata.get(
                key
            )
        )

        assert isinstance(
            value,
            (int, float),
        )

        assert value >= 0.0

    # --------------------------------------------------------
    # Orchestrator success path must expose stage timings plus
    # provider/model identity and remain observational only.
    # --------------------------------------------------------

    calls = []

    class FakeBrain:
        def __init__(self):
            self.router = AIModelRouter()

        def think(
            self,
            user_input,
            system_prompt=None,
            provider_name=None,
        ):
            calls.append(
                user_input
            )

            return ModelResponse(
                text="TELEMETRY SUCCESS",
                model="fake-model",
                provider="fake-provider",
                success=True,
                metadata={
                    "brain_analysis_ms": 1.25,
                    "router_generation_ms": 2.50,
                    "brain_total_ms": 3.75,
                    "provider_latency_ms": 2.00,
                },
            )

    orchestrator = CauvisOrchestrator(
        CauvisConfig(),
        enable_ai=True,
        brain=FakeBrain(),
        session_id="latency-telemetry-test",
    )

    success = orchestrator.handle(
        "Say hello."
    )

    assert success.status == "success"
    assert success.message == "TELEMETRY SUCCESS"

    telemetry = success.data[
        "telemetry"
    ]

    assert telemetry[
        "path"
    ] == "model_success"

    assert telemetry[
        "model_called"
    ] is True

    assert telemetry[
        "deterministic_guard"
    ] is None

    assert telemetry[
        "provider"
    ] == "fake-provider"

    assert telemetry[
        "model"
    ] == "fake-model"

    assert telemetry[
        "observational_only"
    ] is True

    for key in (
        "total_turn_ms",
        "guard_ms",
        "context_ms",
        "brain_model_ms",
        "postprocess_ms",
        "brain_analysis_ms",
        "router_generation_ms",
        "brain_total_ms",
        "provider_latency_ms",
    ):
        value = telemetry[
            key
        ]

        assert isinstance(
            value,
            (int, float),
        )

        assert value >= 0.0

    assert (
        telemetry[
            "total_turn_ms"
        ]
        >= telemetry[
            "brain_model_ms"
        ]
    )

    # --------------------------------------------------------
    # A deterministic external-action guard must report a
    # blocked path with no model call and zero model timing.
    # --------------------------------------------------------

    blocked = orchestrator.handle(
        "Open Notepad."
    )

    assert blocked.status == "blocked"

    blocked_telemetry = (
        blocked.data[
            "telemetry"
        ]
    )

    assert (
        blocked_telemetry[
            "path"
        ]
        == "blocked"
    )

    assert (
        blocked_telemetry[
            "model_called"
        ]
        is False
    )

    assert (
        blocked_telemetry[
            "deterministic_guard"
        ]
        == "external_action"
    )

    assert (
        blocked_telemetry[
            "brain_model_ms"
        ]
        == 0.0
    )

    assert (
        blocked_telemetry[
            "provider_latency_ms"
        ]
        is None
    )

    # Only the normal model turn called the fake brain.
    assert calls == [
        "Say hello."
    ]

    print(
        "PROVIDER LATENCY TRANSPORT:",
        True,
    )

    print(
        "BRAIN TIMINGS:",
        True,
    )

    print(
        "SUCCESS TURN TELEMETRY:",
        True,
    )

    print(
        "BLOCKED TURN TELEMETRY:",
        True,
    )

    print(
        "OBSERVATIONAL ONLY:",
        True,
    )

    return True


tests = [
    ("Compilation", test_compilation),
    ("Core", test_core),
    ("Intent Detection", test_intent),
    ("Task Analyzer", test_task_analyzer),
    ("Device Profiler", test_device),
    ("Adaptive Policy", test_policy),
    ("Capability Mapping", test_capability_mapping),
    ("Reasoning Engine", test_reasoning),
    ("Brain", test_brain),
    ("Capability Registry", test_capability_registry),
    ("Security / Permissions", test_security),
    ("Tool Registry / Execution", test_tools),
    ("Verification Engine", test_verification),
    ("Worker Runtime", test_worker),
    ("Worker Pool", test_worker_pool),
    ("Worker Scheduler", test_scheduler),
    ("Sequential AEM", test_sequential_aem),
    ("Parallel AEM", test_parallel_aem),
    ("Priority AEM", test_priority_aem),
    ("Retry AEM", test_retry_aem),
    ("Fallback AEM", test_fallback_aem),
    ("Pipeline AEM", test_pipeline_aem),
    ("Dependency Graph AEM", test_dependency_graph_aem),
    ("Adaptive AEM", test_adaptive_aem),
    ("End-to-End", test_end_to_end),
    (
        "Execution Engine Adaptive Bridge",
        test_execution_engine_adaptive_bridge,
    ),
    ("Worker Catalog", test_worker_catalog),
    (
        "Explicit Fallback Dispatch",
        test_explicit_fallback_dispatch,
    ),
    (
        "Recovery Decision Policy",
        test_recovery_decision_policy,
    ),
    (
        "Recovery Execution",
        test_recovery_execution,
    ),
    (
        "Execution Engine Recovery Integration",
        test_execution_engine_recovery_integration,
    ),
    (
        "Dependency Graph Recovery Resume",
        test_dependency_graph_recovery_resume,
    ),
    (
        "Recovery Resume Safety Guards",
        test_recovery_resume_safety_guards,
    ),
    (
        "Nexus-Derived System Context",
        test_system_context_snapshot,
    ),
    (
        "Provider Runtime Tracking",
        test_provider_runtime_tracking,
    ),
    (
        "Provider Configuration Enforcement",
        test_provider_configuration_enforcement,
    ),
    (
        "OpenAI Responses Provider Integration",
        test_openai_responses_provider_integration,
    ),
    (
        "Runtime-Aware Provider Ranking",
        test_runtime_aware_provider_ranking,
    ),
    (
        "Automatic Provider Failover",
        test_automatic_provider_failover,
    ),
    (
        "Ollama Provider Integration",
        test_ollama_provider_integration,
    ),
    (
        "Local / Cloud Policy Failover",
        test_local_cloud_policy_failover,
    ),
    (
        "Session Conversation Runtime",
        test_session_conversation_runtime,
    ),
    (
        "Cauvis Runtime Identity Grounding",
        test_cauvis_runtime_identity_grounding,
    ),
    (
        "Verified Capability Truth",
        test_verified_capability_truth,
    ),
    (
        "Capability Prompt Grounding",
        test_capability_prompt_grounding,
    ),
    (
        "Multilingual Intent Normalization",
        test_multilingual_intent_normalization,
    ),
    (
        "Deterministic Shutdown Integration",
        test_deterministic_shutdown_integration,
    ),
    (
        "Direct External Action Classification",
        test_direct_external_action_classification,
    ),
    (
        "Deterministic External Action Guard",
        test_deterministic_external_action_guard,
    ),
    (
        "Factual Context Provenance",
        test_factual_context_provenance,
    ),
    (
        "Explicit User Location Extraction",
        test_explicit_user_location_extraction,
    ),
    (
        "Orchestrator Factual Grounding",
        test_orchestrator_factual_grounding,
    ),
    (
        "Factual Evidence Trust Boundary",
        test_factual_evidence_trust_boundary,
    ),
    (
        "Factual Evidence Transport",
        test_factual_evidence_transport,
    ),
    (
        "Factual Freshness Boundary",
        test_factual_freshness_boundary,
    ),
    (
        "Deterministic Factual Freshness Guard",
        test_deterministic_factual_freshness_guard,
    ),
    (
        "Internal Context Output Boundary",
        test_internal_context_output_boundary,
    ),
    (
        "Runtime-Current Factual Boundary",
        test_runtime_current_boundary,
    ),
    (
        "Capability Status vs Execution",
        test_capability_status_vs_execution,
    ),
    (
        "User Assertion vs Verification",
        test_user_assertion_vs_verification,
    ),
    (
        "Future Weather Freshness",
        test_future_weather_freshness,
    ),
    (
        "Session Memory Provenance Wording",
        test_session_memory_provenance_wording,
    ),
    (
        "Developer Capability-Building Boundary",
        test_developer_capability_building_boundary,
    ),
    (
        "Response Presentation Prefix Normalization",
        test_response_presentation_prefix_normalization,
    ),
    (
        "Turn Latency Telemetry",
        test_turn_latency_telemetry,
    ),
]


print("=" * 70)
print("CAUVIS MASTER VALIDATION")
print("=" * 70)

for number, (name, function) in enumerate(tests, start=1):
    test(number, name, function)

elapsed = time.perf_counter() - START_TIME

print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)

print(f"PASSED:  {PASSED}")
print(f"FAILED:  {FAILED}")
print(f"TOTAL:   {len(tests)}")
print(f"ELAPSED: {elapsed:.2f} seconds")

if FAILED == 0:
    print("\nSTATUS: ALL TESTS PASSED")
    sys.exit(0)
else:
    print("\nSTATUS: FAILURES DETECTED")
    sys.exit(1)