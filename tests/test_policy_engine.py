from __future__ import annotations

import json
import unittest
from pathlib import Path

from coding_agent.policy.engine import PolicyEngine
from coding_agent.policy.loader import PolicyConfigurationError, PolicyLoader
from coding_agent.policy.models import (
    ApprovalMode,
    PolicyAction,
    PolicyInput,
    PolicyLayer,
    PolicyRule,
    WorkspaceTrust,
)
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.contracts import ToolCategory, ToolRisk, ToolSpec

from tests.support import WorkspaceTestCase


FIXTURES = Path(__file__).parent / "fixtures" / "policies"


class PolicyEngineTests(WorkspaceTestCase):
    def policy_input(
        self,
        *risks: ToolRisk,
        tool: str = "repo.create_file",
        mode: ApprovalMode = ApprovalMode.ASK,
        trust: WorkspaceTrust = WorkspaceTrust.TRUSTED,
        arguments: dict[str, object] | None = None,
    ) -> PolicyInput:
        return PolicyInput(tool, arguments or {}, "EDITING", frozenset(risks), mode, trust)

    def test_builtin_remote_deny_cannot_be_overridden_by_trusted_allow(self) -> None:
        allow = PolicyRule(
            "trusted-remote",
            PolicyLayer.TRUSTED,
            PolicyAction.ALLOW,
            "REMOTE_ALLOW",
            tool="git.push",
        )
        decision = PolicyEngine((allow,)).evaluate(
            self.policy_input(ToolRisk.REMOTE_WRITE, tool="git.push", mode=ApprovalMode.AUTO_EDIT)
        )

        self.assertEqual(decision.action, PolicyAction.DENY)
        self.assertEqual(decision.layer, PolicyLayer.BUILTIN)
        self.assertEqual(decision.rule_id, "builtin.remote-write")

    def test_mode_and_workspace_trust_matrix_is_conservative(self) -> None:
        engine = PolicyEngine()
        cases = (
            (ApprovalMode.READ_ONLY, WorkspaceTrust.TRUSTED, ToolRisk.WORKSPACE_WRITE, PolicyAction.DENY),
            (ApprovalMode.ASK, WorkspaceTrust.TRUSTED, ToolRisk.WORKSPACE_WRITE, PolicyAction.ASK),
            (ApprovalMode.AUTO_EDIT, WorkspaceTrust.TRUSTED, ToolRisk.WORKSPACE_WRITE, PolicyAction.ALLOW),
            (ApprovalMode.AUTO_EDIT, WorkspaceTrust.TRUSTED, ToolRisk.PROCESS, PolicyAction.ASK),
            (ApprovalMode.AUTO_EDIT, WorkspaceTrust.UNTRUSTED, ToolRisk.PROCESS, PolicyAction.DENY),
            (ApprovalMode.AUTO_EDIT, WorkspaceTrust.TRUSTED, ToolRisk.NETWORK, PolicyAction.ASK),
        )
        for mode, trust, risk, expected in cases:
            with self.subTest(mode=mode, trust=trust, risk=risk):
                decision = engine.evaluate(self.policy_input(risk, mode=mode, trust=trust))
                self.assertEqual(decision.action, expected)
                self.assertEqual(decision.requires_approval, expected is PolicyAction.ASK)

    def test_matching_deny_wins_and_explanation_redacts_arguments(self) -> None:
        rule = PolicyRule(
            "deny-profile",
            PolicyLayer.TRUSTED,
            PolicyAction.DENY,
            "PROFILE_DENIED",
            tool="test.run",
            argument_equals=(("profile", "secret"),),
        )
        decision = PolicyEngine((rule,)).evaluate(
            self.policy_input(
                ToolRisk.PROCESS,
                tool="test.run",
                arguments={"profile": "secret", "api_key": "sk-" + "x" * 24},
            )
        )

        self.assertEqual(decision.rule_id, "deny-profile")
        self.assertEqual(decision.redacted_arguments["api_key"], "[REDACTED]")
        self.assertNotIn("x" * 24, json.dumps(decision.to_dict()))

    def test_loader_accepts_trusted_rules_and_rejects_workspace_widening(self) -> None:
        loader = PolicyLoader(WorkspacePaths.create(self.test_root).ensure())
        trusted = loader.load_explicit(FIXTURES / "trusted-rules.toml")
        workspace_policy = self.test_root / "policy.toml"
        workspace_policy.write_bytes((FIXTURES / "workspace-narrowing.toml").read_bytes())

        narrowed = loader.load_workspace_narrowing("policy.toml")

        self.assertEqual([item.id for item in trusted], ["trusted-read", "deny-secret-profile"])
        self.assertEqual(narrowed[0].layer, PolicyLayer.WORKSPACE)
        workspace_policy.write_bytes((FIXTURES / "invalid-workspace-widening.toml").read_bytes())
        with self.assertRaisesRegex(PolicyConfigurationError, "only deny"):
            loader.load_workspace_narrowing("policy.toml")

    def test_loader_rejects_unknown_keys_and_executable_predicates(self) -> None:
        policy = self.test_root / "policy.toml"
        policy.write_text(
            "version=1\n[[rules]]\nid='bad'\naction='deny'\n"
            "tool='repo.read_file'\nexpression='__import__(\"os\")'\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(PolicyConfigurationError, "unknown rule keys"):
            PolicyLoader(WorkspacePaths.create(self.test_root).ensure()).load_explicit(policy)

    def test_tool_risks_are_stably_json_serializable(self) -> None:
        spec = ToolSpec(
            "repo.create_file",
            ToolCategory.MUTATION,
            False,
            True,
            frozenset({"EDITING"}),
            risks=frozenset({ToolRisk.WORKSPACE_WRITE}),
        )

        payload = spec.to_dict()

        self.assertEqual(payload["risks"], ["workspace-write"])
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
