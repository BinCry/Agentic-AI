"""Typed values for deterministic policy matching and explanation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ..tools.contracts import ToolRisk


class PolicyAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class ApprovalMode(StrEnum):
    READ_ONLY = "read-only"
    ASK = "ask"
    AUTO_EDIT = "auto-edit"


class WorkspaceTrust(StrEnum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class PolicyLayer(StrEnum):
    BUILTIN = "builtin"
    TRUSTED = "trusted"
    WORKSPACE = "workspace"
    SESSION = "session"


Scalar = str | int | float | bool


@dataclass(slots=True, frozen=True)
class PolicyInput:
    tool_name: str
    arguments: Mapping[str, Any]
    workflow_state: str
    risks: frozenset[ToolRisk]
    mode: ApprovalMode = ApprovalMode.ASK
    workspace_trust: WorkspaceTrust = WorkspaceTrust.TRUSTED

    def __post_init__(self) -> None:
        if not self.tool_name or not self.workflow_state or not isinstance(self.arguments, Mapping):
            raise ValueError("policy input requires tool, state, and argument mapping")
        if not self.risks or any(not isinstance(item, ToolRisk) for item in self.risks):
            raise ValueError("policy input requires typed risks")


@dataclass(slots=True, frozen=True)
class PolicyRule:
    id: str
    layer: PolicyLayer
    action: PolicyAction
    reason_code: str
    tool: str | None = None
    tool_prefix: str | None = None
    effects: frozenset[ToolRisk] = field(default_factory=frozenset)
    modes: frozenset[ApprovalMode] = field(default_factory=frozenset)
    workspace_trust: frozenset[WorkspaceTrust] = field(default_factory=frozenset)
    argument_equals: tuple[tuple[str, Scalar], ...] = ()
    command_prefix: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.id):
            raise ValueError("policy rule id is invalid")
        if not self.reason_code or (self.tool and self.tool_prefix):
            raise ValueError("policy rule reason or tool matcher is invalid")
        if not (self.tool or self.tool_prefix or self.effects):
            raise ValueError("policy rule requires a tool or effect matcher")
        if any(not key or not isinstance(value, (str, int, float, bool)) for key, value in self.argument_equals):
            raise ValueError("argument_equals supports scalar equality only")
        if any(not isinstance(item, str) or not item for item in self.command_prefix):
            raise ValueError("command_prefix requires non-empty argv strings")

    def matches(self, value: PolicyInput) -> bool:
        if self.tool is not None and value.tool_name != self.tool:
            return False
        if self.tool_prefix is not None and not value.tool_name.startswith(self.tool_prefix):
            return False
        if self.effects and not self.effects.issubset(value.risks):
            return False
        if self.modes and value.mode not in self.modes:
            return False
        if self.workspace_trust and value.workspace_trust not in self.workspace_trust:
            return False
        if any(value.arguments.get(key) != expected for key, expected in self.argument_equals):
            return False
        if self.command_prefix:
            command = value.arguments.get("command")
            if not isinstance(command, (list, tuple)) or tuple(command[: len(self.command_prefix)]) != self.command_prefix:
                return False
        return True


@dataclass(slots=True, frozen=True)
class PolicyDecision:
    action: PolicyAction
    rule_id: str
    layer: PolicyLayer
    reason_code: str
    redacted_arguments: Mapping[str, Any]

    @property
    def requires_approval(self) -> bool:
        return self.action is PolicyAction.ASK

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "requires_approval": self.requires_approval,
            "rule_id": self.rule_id,
            "layer": self.layer.value,
            "reason_code": self.reason_code,
            "arguments": dict(self.redacted_arguments),
        }
