"""Narrow supported HTTP contract; extra provider response fields are ignored.
References and review date: docs/verification/phase5.9/API_CONTRACT.md.
"""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,128}$')]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class TextFormat(StrictRequest):
    type: Literal['json_schema']
    schema_: dict = Field(alias='schema')


class Text(StrictRequest):
    format: TextFormat


class Delegation(StrictRequest):
    enabled: Literal[False]


class Agent(StrictRequest):
    model: str = Field(min_length=1, max_length=128)
    instructions: str = Field(max_length=8192)
    tools: list = Field(max_length=0)
    multi_agent: Delegation
    text: Text


class Network(StrictRequest):
    access: Literal['disabled']


class InlineFile(StrictRequest):
    type: Literal['inline']
    path: Literal['/workspace/inputs/evidence.json']
    data: str = Field(max_length=174764)


class Environment(StrictRequest):
    type: Literal['openai_hosted']
    container_size: Literal['small']
    network: Network
    files: list[InlineFile] = Field(min_length=1, max_length=1)


class CreateSession(StrictRequest):
    agent: Agent
    environment: Environment
    input: str = Field(min_length=1, max_length=1024)
    stream: Literal[False]


class CancelEvent(StrictRequest):
    type: Literal['agent.session.input.cancel']


class CancelRequest(StrictRequest):
    events: list[CancelEvent] = Field(min_length=1, max_length=1)


class Wire(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True)


class TokenDetail(Wire):
    cached_tokens: int = Field(ge=0)


class OutputDetail(Wire):
    reasoning_tokens: int = Field(ge=0)


class TokenUsage(Wire):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    input_tokens_details: TokenDetail | None = None
    output_tokens_details: OutputDetail | None = None


class Session(Wire):
    id: Identifier
    object: Literal['agent.session']
    status: Literal['idle','in_progress','requires_action','failed']
    required_actions: list[dict] = Field(default_factory=list, max_length=100)
    error: str | None = None  # Beta contract is a string, not GA's structured error.
    usage: TokenUsage | None = None


class TurnError(Wire):
    code: str
    message: str


class Turn(Wire):
    id: Identifier
    object: Literal['agent.session.turn']
    session_id: Identifier
    subagent_id: str | None
    status: Literal['queued','in_progress','waiting','completed','failed','cancelled']
    error: TurnError | None = None
    usage: TokenUsage | None = None


class Page(Wire):
    object: Literal['list']
    data: list[dict] = Field(max_length=100)
    has_more: bool
    last_id: Identifier | None = None


class Content(Wire):
    type: Literal['input_text','output_text','input_image']
    text: str | None = None


class Message(Wire):
    id: Identifier | None = None
    type: Literal['message']
    role: Literal['user','assistant']
    phase: Literal['commentary','final_answer'] | None
    status: Literal['in_progress','completed','incomplete']
    turn_id: Identifier
    content: list[Content] = Field(max_length=100)


class Deleted(Wire):
    id: Identifier
    object: Literal['agent.session.deleted']
    deleted: Literal[True]
