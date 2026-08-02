"""Unit tests for agents/react.py run_llm."""

from unittest.mock import AsyncMock

import pytest

from incident_commander.agents.react import ReActLoop, ReActTool
from incident_commander.config import Settings
from tests.llm_mocks import FakeFunction, FakeMessage, FakeToolCall, text_response, tool_call_response


@pytest.fixture
def react_loop(tmp_path):
    settings = Settings(
        incident_db_path=tmp_path / "react.db",
        groq_api_key="test-key",
        groq_api_key_fallback="",
    )
    return ReActLoop(settings, "test_worker")


def _bad_json_tool_response(name: str) -> object:
    from tests.llm_mocks import FakeChatResponse, FakeChoice, FakeUsage

    return FakeChatResponse(
        choices=[
            FakeChoice(
                message=FakeMessage(
                    tool_calls=[
                        FakeToolCall(function=FakeFunction(name=name, arguments="{not-json"))
                    ]
                )
            )
        ],
        usage=FakeUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.mark.asyncio
async def test_run_llm_tool_then_finish(react_loop):
    calls: list[str] = []

    async def handler(_input):
        calls.append("ran")
        return {"found": 1}

    tools = [
        ReActTool(
            name="lookup",
            description="lookup data",
            handler=handler,
            parameters={"type": "object", "properties": {}},
        )
    ]

    react_loop._pool.chat_completion = AsyncMock(
        side_effect=[
            tool_call_response("lookup", {}),
            text_response("done investigating"),
        ]
    )

    result = await react_loop.run_llm("test goal", tools, {}, max_iterations=3)

    assert result.finished
    assert result.tools_called == ["lookup"]
    assert calls == ["ran"]
    assert len(result.steps) == 2


@pytest.mark.asyncio
async def test_run_llm_unknown_tool_stops(react_loop):
    handler = AsyncMock()
    react_loop._pool.chat_completion = AsyncMock(
        return_value=tool_call_response("nonexistent_tool", {})
    )
    tools = [
        ReActTool(
            name="real_tool",
            description="real",
            handler=handler,
            parameters={"type": "object", "properties": {}},
        )
    ]

    result = await react_loop.run_llm("goal", tools, {}, max_iterations=3)

    assert not result.finished
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_llm_handler_error_continues(react_loop):
    async def boom(_):
        raise RuntimeError("handler failed")

    tools = [
        ReActTool(
            name="fragile",
            description="fragile",
            handler=boom,
            parameters={"type": "object", "properties": {}},
        )
    ]

    react_loop._pool.chat_completion = AsyncMock(
        side_effect=[
            tool_call_response("fragile", {}),
            text_response("continued after error"),
        ]
    )

    result = await react_loop.run_llm("goal", tools, {}, max_iterations=3)

    assert result.finished
    assert "ERROR: handler failed" in result.steps[0].observation


@pytest.mark.asyncio
async def test_run_llm_malformed_arguments_defaults_empty(react_loop):
    async def handler(inp):
        return inp

    tools = [
        ReActTool(
            name="echo",
            description="echo",
            handler=handler,
            parameters={"type": "object", "properties": {}},
        )
    ]

    react_loop._pool.chat_completion = AsyncMock(
        side_effect=[
            _bad_json_tool_response("echo"),
            text_response("finished"),
        ]
    )

    result = await react_loop.run_llm("goal", tools, {}, max_iterations=3)

    assert result.steps[0].action_input == {}


@pytest.mark.asyncio
async def test_run_llm_max_iterations_not_finished(react_loop):
    react_loop._pool.chat_completion = AsyncMock(
        return_value=tool_call_response("noop", {})
    )

    async def noop(_):
        return "still searching"

    tools = [
        ReActTool(
            name="noop",
            description="noop",
            handler=noop,
            parameters={"type": "object", "properties": {}},
        )
    ]

    result = await react_loop.run_llm("goal", tools, {}, max_iterations=2)

    assert not result.finished
    assert result.iterations == 2
    assert result.summary == "still searching"


@pytest.mark.asyncio
async def test_run_llm_chat_completion_error(react_loop):
    react_loop._pool.chat_completion = AsyncMock(side_effect=RuntimeError("network down"))
    tools = [
        ReActTool(
            name="t",
            description="t",
            handler=AsyncMock(),
            parameters={"type": "object", "properties": {}},
        )
    ]

    result = await react_loop.run_llm("goal", tools, {}, max_iterations=2)

    assert not result.finished
    assert result.error is not None
    assert "network down" in result.error
