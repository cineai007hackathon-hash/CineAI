from collections.abc import AsyncGenerator

from pydantic import BaseModel, Field

from google.adk.agents import Agent, BaseAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from .prompts.root_agent_prompt import ROOT_AGENT_INSTRUCTION


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

weather_agent = Agent(
    name="weather_agent",
    model="gemini-2.5-flash",
    description="Checks weather and environmental feasibility for a scene.",
    instruction=(
        "Inspect the structured scene brief. Return JSON matching the output schema. "
        "Set is_weather_fine to true only when the scene's weather and environmental "
        "requirements are feasible; otherwise set it to false. Never invent a forecast."
    ),
    output_schema=WeatherResult,
    output_key="weather_result",
    tools=[],
)

location_agent = Agent(
    name="location_agent",
    model="gemini-2.5-flash",
    description="Checks location, access, and permit feasibility for a scene.",
    instruction=(
        "Inspect the structured scene brief. Return JSON matching the output schema. "
        "Set is_location_fine to true only when location, access, and permit details "
        "are explicitly feasible; otherwise set it to false. Flag missing information."
    ),
    output_schema=LocationResult,
    output_key="location_result",
    tools=[],
)

camera_agent = Agent(
    name="camera_agent",
    model="gemini-2.5-flash",
    description="Checks camera inventory and creates camera preparation tasks for a scene.",
    instruction=(
        "Inspect the scene brief and return only JSON matching the output schema. "
        "Check camera requirements and report the camera_id, camera_status, missing_items, "
        "and expected_items. Set ready_for_shooting true only when camera needs are met."
    ),
    output_schema=CameraResult,
    output_key="camera_result",
    tools=[],
)

stunt_agent = Agent(
    name="stunt_agent",
    model="gemini-2.5-flash",
    description="Checks stunt safety requirements and readiness for a scene.",
    instruction=(
        "Inspect the scene brief and return only JSON matching the output schema. "
        "Report stunt_id, stunt_status, safety requirements, missing items, and blockers. "
        "Set ready_for_shooting true only when the stunt department is ready."
    ),
    output_schema=StuntResult,
    output_key="stunt_result",
    tools=[],
)

cast_agent = Agent(
    name="cast_agent",
    model="gemini-2.5-flash",
    description="Checks cast availability and creates cast preparation tasks for a scene.",
    instruction=(
        "Inspect the scene brief and return only JSON matching the output schema. "
        "Report cast_status and cast_members_availability for every named actor. "
        "Set ready_for_shooting true only when all required cast members are available."
    ),
    output_schema=CastResult,
    output_key="cast_result",
    tools=[],
)


replan_agent = Agent(
    name="replan_agent",
    model="gemini-2.5-flash",
    description="Finds alternative scenes or schedules when a department is not ready.",
    instruction=(
        "Read the five department JSON results from session state: weather_result, "
        "location_result, camera_result, stunt_result, and cast_result. Identify every "
        "department whose ready_for_shooting is false. Recommend the next possible scene "
        "or schedule alternative using database/search tools when available. For location_id "
        "and camera_id, use direct lookup or combinational search. Return only JSON matching "
        "the output schema, with scores and probabilities between 0 and 1. Include metadata "
        "updates so department results can be changed later without losing their history."
    ),
    output_schema=ReplanResult,
    output_key="replan_result",
    tools=[],
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
                "Runs five parallel department checks and invokes replanning for failures."
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
        results = {key: ctx.state.get(key, {}) for key in result_keys}
        failed_departments = [
            result.get("department", key.removesuffix("_result"))
            for key, result in results.items()
            if not _read_boolean(result, "ready_for_shooting")
        ]
        ctx.state["failed_departments"] = failed_departments
        ctx.state["all_departments_ready"] = not failed_departments
        ctx.state["agent_metadata"] = {
            key: result.get("metadata", {}) for key, result in results.items()
        }

        if failed_departments:
            async for event in self.replan.run_async(ctx):
                yield event


def _read_boolean(result: object, key: str) -> bool:
    """Read a persisted structured-agent value without treating missing data as true."""
    if isinstance(result, dict):
        return result.get(key) is True
    return getattr(result, key, False) is True


production_workflow = ProductionWorkflow()


root_agent = Agent(
    name="ad_multi_agent",
    model="gemini-2.5-flash",
    description=(
        "Assistant Director orchestrator that turns a screenplay scene into a "
        "structured production brief and coordinates the relevant department agents."
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[production_workflow],
    tools=[],
)