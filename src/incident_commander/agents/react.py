"""ReAct loop engine for worker agents."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from incident_commander.config import Settings
from incident_commander.llm.groq_client import GroqClientPool


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
    def __init__(self, settings: Settings, worker_name: str) -> None:
        self.settings = settings
        self.worker_name = worker_name
        self._pool = GroqClientPool(settings)

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

        for iteration in range(1, limit + 1):
            prompt = self._build_prompt(goal, tools, context, history_lines)
            try:
                response = await self._pool.chat_completion(
                    model=self.settings.resolved_llm_model(),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content or "{}"
                decision = json.loads(raw)
            except Exception as exc:
                return ReActResult(
                    summary="LLM ReAct failed",
                    iterations=iteration,
                    tools_called=tools_called,
                    steps=records,
                    finished=False,
                    error=str(exc),
                )

            thought = str(decision.get("thought", ""))
            finished = bool(decision.get("finished", False))
            summary = str(decision.get("summary", ""))
            action = decision.get("action")
            action_input = decision.get("action_input") or {}

            if finished:
                records.append(
                    ReActStepRecord(
                        iteration=iteration,
                        thought=thought,
                        action=None,
                        action_input={},
                        observation=summary or "finished",
                    )
                )
                return ReActResult(
                    summary=summary or "Investigation complete",
                    iterations=iteration,
                    tools_called=tools_called,
                    steps=records,
                )

            if not action or action not in tool_map:
                records.append(
                    ReActStepRecord(
                        iteration=iteration,
                        thought=thought,
                        action=str(action),
                        action_input=action_input,
                        observation="Invalid or missing action; stopping loop",
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
                f"Iter {iteration}: thought={thought} action={action} -> {obs_text[:300]}"
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
        return f"""You are worker agent "{self.worker_name}" using a ReAct loop (Reason + Act).

Goal: {goal}

Context:
{json.dumps(context, default=str)}

Available tools:
{json.dumps(tool_specs)}

Previous steps:
{history_text}

Respond with JSON only:
{{
  "thought": "reasoning for next step",
  "action": "tool_name or null if done",
  "action_input": {{}},
  "finished": false,
  "summary": "final summary when finished"
}}

When you have enough information, set finished=true, action=null, and provide summary.
Use at most one tool per iteration. Prefer gathering evidence before finishing.
"""


def _format_observation(observation: Any) -> str:
    if observation is None:
        return "null"
    if isinstance(observation, (list, dict)):
        return json.dumps(observation, default=str)[:2000]
    return str(observation)[:2000]
