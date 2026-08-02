"""Shared helpers for mocking OpenAI-compatible LLM responses in tests."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeFunction:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    function: FakeFunction


@dataclass
class FakeMessage:
    content: str | None = None
    tool_calls: list[FakeToolCall] = field(default_factory=list)


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class FakeChatResponse:
    choices: list[FakeChoice]
    usage: FakeUsage = field(default_factory=FakeUsage)


def tool_call_response(name: str, arguments: dict[str, Any], **usage_kw: int) -> FakeChatResponse:
    import json

    prompt = usage_kw.get("prompt_tokens", 100)
    completion = usage_kw.get("completion_tokens", 50)
    return FakeChatResponse(
        choices=[
            FakeChoice(
                message=FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            function=FakeFunction(
                                name=name,
                                arguments=json.dumps(arguments),
                            )
                        )
                    ]
                )
            )
        ],
        usage=FakeUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        ),
    )


def text_response(content: str, **usage_kw: int) -> FakeChatResponse:
    prompt = usage_kw.get("prompt_tokens", 80)
    completion = usage_kw.get("completion_tokens", 40)
    return FakeChatResponse(
        choices=[FakeChoice(message=FakeMessage(content=content))],
        usage=FakeUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        ),
    )
