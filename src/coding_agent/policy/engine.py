"""Deterministic policy precedence with immutable safety baselines."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from ..tools.contracts import ToolRisk
from .models import (
    ApprovalMode,
    PolicyAction,
    PolicyDecision,
    PolicyInput,
    PolicyLayer,
    PolicyRule,
    WorkspaceTrust,
)


class PolicyEngine:
    def __init__(self, rules: tuple[PolicyRule, ...] = ()) -> None:
        ids = [item.id for item in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("policy rule ids must be unique")
        self.rules = tuple(rules)

    def evaluate(self, value: PolicyInput) -> PolicyDecision:
        baseline = self._baseline(value)
        matching = [item for item in self.rules if item.matches(value)]
        if baseline.action is PolicyAction.DENY:
            return self._decision(baseline, value.arguments)
        denied = self._select(matching, PolicyAction.DENY)
        if denied:
            return self._decision(denied, value.arguments)
        if baseline.action is PolicyAction.ASK:
            return self._decision(baseline, value.arguments)
        asked = self._select(matching, PolicyAction.ASK)
        if asked:
            return self._decision(asked, value.arguments)
        allowed = self._select(matching, PolicyAction.ALLOW)
        return self._decision(allowed or baseline, value.arguments)

    @staticmethod
    def _baseline(value: PolicyInput) -> PolicyRule:
        risks = value.risks
        if ToolRisk.REMOTE_WRITE in risks:
            return _builtin("builtin.remote-write", PolicyAction.DENY, "REMOTE_WRITE_DENIED", risks)
        if ToolRisk.DESTRUCTIVE in risks:
            return _builtin("builtin.destructive", PolicyAction.DENY, "DESTRUCTIVE_DENIED", risks)
        if ToolRisk.PROCESS in risks and value.workspace_trust is WorkspaceTrust.UNTRUSTED:
            return _builtin("builtin.untrusted-process", PolicyAction.DENY, "PROCESS_ISOLATION_REQUIRED", risks)
        non_read = risks - {ToolRisk.READ}
        if value.mode is ApprovalMode.READ_ONLY and non_read:
            return _builtin("session.read-only", PolicyAction.DENY, "READ_ONLY_MODE", risks, PolicyLayer.SESSION)
        if ToolRisk.NETWORK in risks:
            return _builtin("session.network", PolicyAction.ASK, "NETWORK_APPROVAL_REQUIRED", risks, PolicyLayer.SESSION)
        if ToolRisk.PROCESS in risks:
            return _builtin("session.process", PolicyAction.ASK, "PROCESS_APPROVAL_REQUIRED", risks, PolicyLayer.SESSION)
        if ToolRisk.WORKSPACE_WRITE in risks:
            action = PolicyAction.ALLOW if value.mode is ApprovalMode.AUTO_EDIT else PolicyAction.ASK
            code = "AUTO_EDIT_BOUNDED_WRITE" if action is PolicyAction.ALLOW else "WRITE_APPROVAL_REQUIRED"
            return _builtin("session.workspace-write", action, code, risks, PolicyLayer.SESSION)
        return _builtin("builtin.read", PolicyAction.ALLOW, "READ_ALLOWED", risks)

    @staticmethod
    def _select(rules: list[PolicyRule], action: PolicyAction) -> PolicyRule | None:
        priority = {PolicyLayer.WORKSPACE: 0, PolicyLayer.TRUSTED: 1, PolicyLayer.SESSION: 2, PolicyLayer.BUILTIN: 3}
        candidates = [item for item in rules if item.action is action]
        return min(candidates, key=lambda item: (priority[item.layer], item.id)) if candidates else None

    @staticmethod
    def _decision(rule: PolicyRule, arguments: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(rule.action, rule.id, rule.layer, rule.reason_code, _redact(arguments))


def _builtin(
    rule_id: str,
    action: PolicyAction,
    reason: str,
    risks: frozenset[ToolRisk],
    layer: PolicyLayer = PolicyLayer.BUILTIN,
) -> PolicyRule:
    return PolicyRule(rule_id, layer, action, reason, effects=risks)


def _redact(value: Any, key: str = "") -> Any:
    sensitive = ("secret", "token", "password", "api_key", "authorization", "credential")
    if any(item in key.lower() for item in sensitive):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): _redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact(item) for item in value]
    if isinstance(value, str) and re.search(r"\bsk-[A-Za-z0-9_-]{8,}", value):
        return "[REDACTED]"
    return value
