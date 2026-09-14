from dataclasses import dataclass, field
from typing import Any

from intelligence.models import ModelRequest, ModelResponse
from intelligence.router import AIModelRouter
from intelligence.reasoning import ReasoningEngine, ReasoningResult
from intelligence.task import TaskAnalyzer, TaskRequirements
from intelligence.device import DeviceProfiler, DeviceProfile
from intelligence.policy import AdaptivePolicyEngine, IntelligencePolicy
from intelligence.capabilities import CapabilityMapper, CapabilitySet
from intelligence.system_context import (
    SystemContextBuilder,
    SystemContextSnapshot,
)

from execution.planner import (
    AdaptiveExecutionPlan,
    AdaptiveTaskPlanner,
)


@dataclass
class BrainAnalysis:
    """
    Complete analysis of a user request before execution.
    """

    user_input: str
    task: TaskRequirements
    capabilities: CapabilitySet
    reasoning: ReasoningResult
    device: DeviceProfile
    policy: IntelligencePolicy
    execution_plan: AdaptiveExecutionPlan | None = None
    system_context: SystemContextSnapshot | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CauvisBrain:
    """
    Central intelligence coordinator for Cauvis.

    The brain analyzes requests, determines requirements,
    evaluates the device, creates an adaptive execution plan,
    selects an execution strategy, and asks the router to
    select an appropriate AI provider.

    The brain does not directly execute actions.
    """

    def __init__(
        self,
        router: AIModelRouter,
        reasoning_engine: ReasoningEngine | None = None,
        task_analyzer: TaskAnalyzer | None = None,
        device_profiler: DeviceProfiler | None = None,
        policy_engine: AdaptivePolicyEngine | None = None,
        capability_mapper: CapabilityMapper | None = None,
        task_planner: AdaptiveTaskPlanner | None = None,
        system_context_builder: SystemContextBuilder | None = None,
    ):
        self.router = router

        self.reasoning_engine = (
            reasoning_engine or ReasoningEngine()
        )

        self.task_analyzer = (
            task_analyzer or TaskAnalyzer()
        )

        self.device_profiler = (
            device_profiler or DeviceProfiler()
        )

        self.policy_engine = (
            policy_engine or AdaptivePolicyEngine()
        )

        self.capability_mapper = (
            capability_mapper or CapabilityMapper()
        )

        self.task_planner = (
            task_planner or AdaptiveTaskPlanner()
        )

        self.system_context_builder = (
            system_context_builder
            or SystemContextBuilder(router)
        )

        self._device_profile: DeviceProfile | None = None

    # ---------------------------------------------------------
    # DEVICE
    # ---------------------------------------------------------

    def get_device_profile(self) -> DeviceProfile:
        """
        Return the current device profile.

        The profile is cached so Cauvis does not repeatedly
        scan the hardware for every request.
        """

        if self._device_profile is None:
            self._device_profile = (
                self.device_profiler.profile()
            )

        return self._device_profile

    def refresh_device_profile(self) -> DeviceProfile:
        """
        Force Cauvis to rescan the device.
        """

        self._device_profile = (
            self.device_profiler.profile()
        )

        return self._device_profile

    # ---------------------------------------------------------
    # ANALYSIS
    # ---------------------------------------------------------

    def analyze(self, user_input: str) -> BrainAnalysis:
        """
        Analyze a request from beginning to execution planning.

        This method does not execute the resulting plan.
        """

        # Step 1: Determine what the task requires.
        task = self.task_analyzer.analyze(
            user_input
        )

        # Step 2: Convert requirements into standardized
        # capabilities that the router and execution system
        # understand.
        capabilities = self.capability_mapper.map(
            task
        )

        # Step 3: Build a reasoning plan using the exact
        # same task analysis.
        reasoning = self.reasoning_engine.analyze(
            user_input,
            task=task,
        )

        # Step 4: Determine what hardware and environment
        # Cauvis currently has available.
        device = self.get_device_profile()

        # Step 5: Build a read-only snapshot of what Cauvis
        # can currently prove about its runtime environment.
        # Stage 1 is observational only and does not alter
        # routing, policy, permissions, or execution.
        system_context = self.system_context_builder.build(
            capabilities.capabilities,
            device,
        )

        # Step 6: Decide how Cauvis should execute the task.
        policy = self.policy_engine.evaluate(
            device,
            task,
        )

        # Step 7: Convert reasoning into an executable
        # adaptive task plan.
        execution_plan = self.task_planner.build_plan(
            reasoning
        )

        return BrainAnalysis(
            user_input=user_input,
            task=task,
            capabilities=capabilities,
            reasoning=reasoning,
            device=device,
            policy=policy,
            execution_plan=execution_plan,
            system_context=system_context,
            metadata={
                "capability_count": len(
                    capabilities.capabilities
                ),
                "device_cached": True,
                "plan_task_count": len(
                    execution_plan.tasks
                ),
                "plan_adaptive": execution_plan.metadata.get(
                    "adaptive",
                    False,
                ),
            },
        )

    # ---------------------------------------------------------
    # THINK
    # ---------------------------------------------------------

    def think(
        self,
        user_input: str,
        system_prompt: str | None = None,
        provider_name: str | None = None,
    ) -> ModelResponse:
        """
        Analyze the request and route it to the
        appropriate AI provider.

        The execution plan is generated during analysis,
        but execution remains outside the brain.
        """

        analysis = self.analyze(
            user_input
        )

        request = ModelRequest(
            prompt=analysis.reasoning.goal,
            system_prompt=system_prompt,
            metadata={
                "task": analysis.task,
                "capabilities": sorted(
                    analysis.capabilities.capabilities
                ),
                "reasoning_steps": (
                    analysis.reasoning.steps
                ),
                "requires_tools": (
                    analysis.reasoning.requires_tools
                ),
                "requires_verification": (
                    analysis.reasoning.requires_verification
                ),
                "execution_strategy": (
                    analysis.policy.strategy.value
                ),
                "policy_reason": (
                    analysis.policy.reason
                ),
                "execution_plan": (
                    analysis.execution_plan
                ),
                "system_context": (
                    analysis.system_context.to_dict()
                    if analysis.system_context
                    else None
                ),
            },
        )

        response = self.router.generate(
            request=request,
            policy=analysis.policy,
            required_capabilities=(
                analysis.capabilities.capabilities
            ),
            provider_name=provider_name,
        )

        # Add Cauvis analysis information to the response.
        response.metadata.update(
            {
                "execution_strategy": (
                    analysis.policy.strategy.value
                ),
                "capabilities": sorted(
                    analysis.capabilities.capabilities
                ),
                "task_complexity": (
                    analysis.task.complexity.value
                ),
                "plan_task_count": len(
                    analysis.execution_plan.tasks
                )
                if analysis.execution_plan
                else 0,
            }
        )

        return response