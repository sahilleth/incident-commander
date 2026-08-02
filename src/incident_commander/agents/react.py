"""ReAct loop engine for worker agents."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from incident_commander.config import Settings
from incident_commander.llm.llm_client import LLMClientPool
from incident_commander.llm.usage import LLMUsageAccumulator


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class ReActTool:
    name: str
    description: str
    handler: ToolHandler
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReActStepRecord:
    iteration: int
    thought: str
    action: str | None
    action_input: dict[str, Any]
    observation: str


@dataclass
class ReActResult:
    summary: str
    iterations: int
    tools_called: list[str]
    steps: list[ReActStepRecord] = field(default_factory=list)
    finished: bool = True
    error: str | None = None


@dataclass
class DeterministicStep:
    """Rule-based ReAct step: thought label + async action."""

    thought: str
    action_name: str
    run: Callable[[], Awaitable[Any]]
    stop_if: Callable[[Any], bool] | None = None


class ReActLoop:
    def __init__(
        self,
        settings: Settings,
        worker_name: str,
        usage_accumulator: LLMUsageAccumulator | None = None,
    ) -> None:
        self.settings = settings
        self.worker_name = worker_name
        self._usage = usage_accumulator
        self._pool = LLMClientPool(settings, usage_accumulator=usage_accumulator)

    async def run_deterministic(
        self,
        goal: str,
        steps: list[DeterministicStep],
        max_iterations: int | None = None,
    ) -> ReActResult:
        limit = max_iterations or self.settings.max_worker_iterations
        tools_called: list[str] = []
        records: list[ReActStepRecord] = []
        summary = goal
        iteration = 0

        for step in steps:
            if iteration >= limit:
                break
            iteration += 1
            try:
                observation = await step.run()
                obs_text = _format_observation(observation)
            except Exception as exc:
                obs_text = f"ERROR: {exc}"
                records.append(
                    ReActStepRecord(
                        iteration=iteration,
                        thought=step.thought,
                        action=step.action_name,
                        action_input={},
                        observation=obs_text,
                    )
                )
                tools_called.append(step.action_name)
                continue

            tools_called.append(step.action_name)
            records.append(
                ReActStepRecord(
                    iteration=iteration,
                    thought=step.thought,
                    action=step.action_name,
                    action_input={},
                    observation=obs_text,
                )
            )
            if step.stop_if and step.stop_if(observation):
                summary = obs_text
                break
            summary = obs_text

        return ReActResult(
            summary=summary,
            iterations=iteration,
            tools_called=tools_called,
            steps=records,
        )

    async def run_llm(
        self,
        goal: str,
        tools: list[ReActTool],
        context: dict[str, Any],
        max_iterations: int | None = None,
    ) -> ReActResult:
        if not self._pool.has_client():
            return ReActResult(
                summary="LLM not configured",
                iterations=0,
                tools_called=[],
                finished=False,
                error="no_llm",
            )

        limit = max_iterations or self.settings.max_worker_iterations
        tool_map = {t.name: t for t in tools}
        tools_called: list[str] = []
        records: list[ReActStepRecord] = []
        history_lines: list[str] = []
        tool_specs = _openai_tool_specs(tools)

        for iteration in range(1, limit + 1):
            prompt = self._build_prompt(goal, tools, context, history_lines)
            try:
                response = await self._pool.chat_completion(
                    model=self.settings.resolved_llm_model(),
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                f"You are worker agent \"{self.worker_name}\" using a ReAct loop. "
                                "Call tools to gather evidence. When you have enough information, "
                                "respond with plain text (no tool call) summarizing findings."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    tools=tool_specs,
                )
                message = response.choices[0].message
            except Exception as exc:
                return ReActResult(
                    summary="LLM ReAct failed",
                    iterations=iteration,
                    tools_called=tools_called,
                    steps=records,
                    finished=False,
                    error=str(exc),
                )

            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                summary = (message.content or "").strip() or "Investigation complete"
                records.append(
                    ReActStepRecord(
                        iteration=iteration,
                        thought="LLM finished without further tool calls",
                        action=None,
                        action_input={},
                        observation=summary,
                    )
                )
                return ReActResult(
                    summary=summary,
                    iterations=iteration,
                    tools_called=tools_called,
                    steps=records,
                    finished=True,
                )

            call = tool_calls[0]
            action = call.function.name
            try:
                action_input = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                action_input = {}

            thought = f"LLM selected tool {action}"

            if action not in tool_map:
                obs_text = "Invalid or missing action; stopping loop"
                records.append(
                    ReActStepRecord(
                        iteration=iteration,
                        thought=thought,
                        action=action,
                        action_input=action_input,
                        observation=obs_text,
                    )
                )
                break

            try:
                observation = await tool_map[action].handler(action_input)
                obs_text = _format_observation(observation)
            except Exception as exc:
                obs_text = f"ERROR: {exc}"

            tools_called.append(action)
            records.append(
                ReActStepRecord(
                    iteration=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=obs_text,
                )
            )
            history_lines.append(
                f"Iter {iteration}: action={action} -> {obs_text[:300]}"
            )

        return ReActResult(
            summary=records[-1].observation if records else goal,
            iterations=len(records),
            tools_called=tools_called,
            steps=records,
            finished=False,
        )

    def _build_prompt(
        self,
        goal: str,
        tools: list[ReActTool],
        context: dict[str, Any],
        history: list[str],
    ) -> str:
        tool_specs = [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in tools
        ]
        history_text = "\n".join(history) if history else "None"
        return f"""Goal: {goal}

Context:
{json.dumps(context, default=str)}

Available tools (also registered for function calling):
{json.dumps(tool_specs)}

Previous steps:
{history_text}

Call one tool per turn when more evidence is needed. When done, reply with plain text only.
"""


def _openai_tool_specs(tools: list[ReActTool]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters or {"type": "object", "properties": {}},
            },
        }
        for t in tools
    ]


def _format_observation(observation: Any) -> str:
    if observation is None:
        return "null"
    if isinstance(observation, (list, dict)):
        return json.dumps(observation, default=str)[:2000]
    return str(observation)[:2000]
