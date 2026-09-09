"""Film AD multi-agent system — ADK root + department workflow."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from pydantic import BaseModel, Field

from google.adk.agents import Agent, BaseAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext

from . import env_bootstrap  # noqa: F401  — load .env into os.environ first
from .config.settings import settings
from .prompts.camera_agent_prompt import CAMERA_AGENT_INSTRUCTION
from .prompts.cast_agent_prompt import CAST_AGENT_INSTRUCTION
from .prompts.location_agent_prompt import LOCATION_AGENT_INSTRUCTION
from .prompts.replan_agent_prompt import REPLAN_AGENT_INSTRUCTION
from .prompts.root_agent_prompt import ROOT_AGENT_INSTRUCTION
from .prompts.stunt_agent_prompt import STUNT_AGENT_INSTRUCTION
from .prompts.weather_agent_prompt import WEATHER_AGENT_INSTRUCTION
from .tools.db_tools import (
    check_camera_for_scene,
    check_cast_for_scene,
    check_location_for_scene,
    check_stunt_for_scene,
    check_weather_for_scene,
    find_scenes,
    get_scene_bundle,
    list_candidate_scenes_for_replan,
)

MODEL = settings.model_name


class DepartmentResult(BaseModel):
    department: str
    status: str = Field(description="READY, BLOCKED, or NEEDS_REVIEW")
    ready_for_shooting: bool
    reason: str = ""
    missing_items: list[str] = Field(default_factory=list)
    expected_items: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class WeatherResult(DepartmentResult):
    department: str = "weather"
    current_weather: str = ""
    is_weather_fine: bool


class LocationResult(DepartmentResult):
    department: str = "location"
    location_id: str = ""
    loc_status: str = ""
    is_location_fine: bool


class CameraResult(DepartmentResult):
    department: str = "camera"
    camera_id: str = ""
    camera_status: str = ""


class StuntResult(DepartmentResult):
    department: str = "stunt"
    stunt_id: str = ""
    stunt_status: str = ""


class CastResult(DepartmentResult):
    department: str = "cast"
    cast_status: str = ""
    cast_members_availability: dict[str, bool] = Field(default_factory=dict)


class ReplanOption(BaseModel):
    scene_id: str
    score: float = Field(ge=0, le=1)
    probability: float = Field(ge=0, le=1)
    rationale: str
    required_changes: list[str] = Field(default_factory=list)


class ReplanResult(BaseModel):
    status: str
    failed_departments: list[str] = Field(default_factory=list)
    search_strategy: str
    recommended_scene: str | None = None
    alternatives: list[ReplanOption] = Field(default_factory=list)
    metadata_updates: dict[str, object] = Field(default_factory=dict)


def _weather_tools() -> list:
    tools: list = [check_weather_for_scene]
    if settings.use_live_weather_mcp:
        from .mcp.weather_mcp import get_weather_mcp_toolset

        tools.append(get_weather_mcp_toolset())
    return tools


def _location_tools() -> list:
    tools: list = [check_location_for_scene, get_scene_bundle]
    if settings.use_live_location_mcp:
        from .mcp.location_mcp import get_location_mcp_toolset

        tools.append(get_location_mcp_toolset())
    return tools


weather_agent = Agent(
    name="weather_agent",
    model=MODEL,
    description="Checks weather feasibility for a scene using the production DB.",
    instruction=WEATHER_AGENT_INSTRUCTION,
    output_schema=WeatherResult,
    output_key="weather_result",
    tools=_weather_tools(),
)

location_agent = Agent(
    name="location_agent",
    model=MODEL,
    description="Checks location/permit feasibility for a scene using the production DB.",
    instruction=LOCATION_AGENT_INSTRUCTION,
    output_schema=LocationResult,
    output_key="location_result",
    tools=_location_tools(),
)

camera_agent = Agent(
    name="camera_agent",
    model=MODEL,
    description="Checks camera inventory/schedule readiness for a scene from the DB.",
    instruction=CAMERA_AGENT_INSTRUCTION,
    output_schema=CameraResult,
    output_key="camera_result",
    tools=[check_camera_for_scene, get_scene_bundle],
)

stunt_agent = Agent(
    name="stunt_agent",
    model=MODEL,
    description="Checks stunt safety checklist readiness for a scene from the DB.",
    instruction=STUNT_AGENT_INSTRUCTION,
    output_schema=StuntResult,
    output_key="stunt_result",
    tools=[check_stunt_for_scene, get_scene_bundle],
)

cast_agent = Agent(
    name="cast_agent",
    model=MODEL,
    description="Checks cast availability for a scene from the production DB.",
    instruction=CAST_AGENT_INSTRUCTION,
    output_schema=CastResult,
    output_key="cast_result",
    tools=[check_cast_for_scene, get_scene_bundle],
)

replan_agent = Agent(
    name="replan_agent",
    model=MODEL,
    description="Finds alternative scenes/schedules when a department check fails.",
    instruction=REPLAN_AGENT_INSTRUCTION,
    output_schema=ReplanResult,
    output_key="replan_result",
    tools=[list_candidate_scenes_for_replan, get_scene_bundle, find_scenes],
)


class ProductionWorkflow(BaseAgent):
    """Run all department checks in parallel and replan when any check fails."""

    def __init__(self, **kwargs):
        department_checks = ParallelAgent(
            name="department_checks",
            description="Runs all five production readiness checks concurrently.",
            sub_agents=[
                weather_agent,
                location_agent,
                camera_agent,
                stunt_agent,
                cast_agent,
            ],
        )
        super().__init__(
            name="production_workflow",
            description=(
                "Runs five parallel department DB checks and invokes replanning "
                "when any department is not ready."
            ),
            sub_agents=[department_checks, replan_agent],
            **kwargs,
        )

    @property
    def department_checks(self) -> ParallelAgent:
        return self.sub_agents[0]

    @property
    def replan(self) -> Agent:
        return self.sub_agents[1]

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator:
        async for event in self.department_checks.run_async(ctx):
            yield event

        result_keys = (
            "weather_result",
            "location_result",
            "camera_result",
            "stunt_result",
            "cast_result",
        )
        session_state = ctx.session.state
        results = {key: session_state.get(key, {}) for key in result_keys}
        failed_departments = [
            result.get("department", key.removesuffix("_result"))
            for key, result in results.items()
            if not _read_boolean(result, "ready_for_shooting")
        ]
        session_state["failed_departments"] = failed_departments
        session_state["all_departments_ready"] = not failed_departments
        session_state["agent_metadata"] = {
            key: result.get("metadata", {}) for key, result in results.items()
        }

        if failed_departments and settings.enable_replan_on_failure:
            async for event in self.replan.run_async(ctx):
                yield event


def _read_boolean(result: object, key: str) -> bool:
    """Read a persisted structured-agent value without treating missing data as true."""
    if isinstance(result, dict):
        return result.get(key) is True
    return getattr(result, key, False) is True


production_workflow = ProductionWorkflow()


def _root_tools() -> list:
    tools: list = [get_scene_bundle, find_scenes]
    if settings.use_docling_mcp:
        from .mcp.docling_rag_mcp import get_docling_mcp_toolset, get_watsonx_dl_retrieval_mcp

        tools.append(get_docling_mcp_toolset())
        if settings.use_watsonx_rag:
            watsonx_tool = get_watsonx_dl_retrieval_mcp()
            if watsonx_tool:
                tools.append(watsonx_tool)
    return tools


root_agent = Agent(
    name="ad_multi_agent",
    model=MODEL,
    description=(
        "Assistant Director orchestrator that resolves a scene from the production "
        "DB and coordinates weather, location, camera, stunt, and cast agents."
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[production_workflow],
    tools=_root_tools(),
)
