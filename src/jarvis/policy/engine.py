"""
Central PolicyEngine for authorization, security evaluation, and permission checks across Jarvis capabilities.
"""

import logging, uuid
from typing import Any, Dict, List, Optional
from jarvis.policy.schemas import (
    SecurityContext,
    TrustLevel,
    PolicyDecision,
    PolicyRule,
    PolicyEvaluationResult,
    AuditEntry,
)
from jarvis.resource.schemas import ResourcePermission

logger = logging.getLogger("jarvis.policy.engine")


class PolicyEngine:
    """
    Central authorization engine evaluating permissions, security policies,
    and trust levels across all capabilities and platforms.
    """

    def __init__(self) -> None:
        self._rules: List[PolicyRule] = []
        self._audit_log: List[AuditEntry] = []

        # Register standard default security rules
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        # Default rule: System action allow
        self.add_rule(
            PolicyRule(
                rule_id="rule-default-allow",
                name="Default System Action Rule",
                target_capability="*",
                target_action="*",
                required_trust_level=TrustLevel.SANDBOXED,
                decision=PolicyDecision.ALLOW,
                description="Allow actions meeting sandboxed trust level",
            )
        )
        # High risk action rule: Shell or delete requires approval if not full trust
        self.add_rule(
            PolicyRule(
                rule_id="rule-high-risk-delete",
                name="High Risk Delete Action",
                target_capability="tools",
                target_action="file_delete",
                required_trust_level=TrustLevel.USER_CONFIRMED,
                required_permissions=[ResourcePermission.DELETE],
                decision=PolicyDecision.REQUIRES_APPROVAL,
                description="Delete operations require explicit user approval",
            )
        )

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)

    def evaluate_action(
        self,
        capability_name: str,
        action_name: str,
        security_context: Optional[SecurityContext] = None,
        required_permissions: Optional[List[ResourcePermission]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        ctx = security_context or SecurityContext()

        # Check required permissions
        if required_permissions:
            for perm in required_permissions:
                if perm not in ctx.granted_permissions:
                    res = PolicyEvaluationResult(
                        decision=PolicyDecision.DENY,
                        reason=f"Missing required permission: {perm.value}",
                    )
                    self._record_audit(ctx, capability_name, action_name, res)
                    return res

        # Check matching rules in reverse priority order
        matched_decision = PolicyDecision.ALLOW
        reason = "Allowed by default policy"
        rule_id = "rule-default-allow"

        for rule in reversed(self._rules):
            if rule.target_capability in ("*", capability_name):
                if rule.target_action in ("*", action_name):
                    matched_decision = rule.decision
                    reason = f"Matched rule '{rule.name}'"
                    rule_id = rule.rule_id
                    break

        result = PolicyEvaluationResult(
            decision=matched_decision,
            reason=reason,
            rule_id=rule_id,
        )
        self._record_audit(ctx, capability_name, action_name, result)
        return result

    def _record_audit(
        self,
        security_context: SecurityContext,
        capability_name: str,
        action_name: str,
        result: PolicyEvaluationResult,
    ) -> None:
        entry = AuditEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:8]}",
            security_context=security_context,
            capability_name=capability_name,
            action_name=action_name,
            decision=result.decision,
            reason=result.reason,
        )
        self._audit_log.append(entry)

    def get_audit_log(self) -> List[AuditEntry]:
        return list(self._audit_log)
