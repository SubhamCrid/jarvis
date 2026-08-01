"""
ApprovalManager for managing human approval requests for sensitive runtime operations.
"""

from typing import Dict, List, Optional
from jarvis.runtime.schemas import ApprovalRequest, PlanStep, ExecutionState


class ApprovalManager:
    """
    Manages human approval request lifecycle for gated runtime operations.
    """

    def __init__(self) -> None:
        self._requests: Dict[str, ApprovalRequest] = {}

    def request_approval(
        self, goal_id: str, step: PlanStep, reason: str = "High risk operation"
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            goal_id=goal_id,
            step_id=step.step_id,
            capability_name=step.capability_name,
            action_name=step.action_name,
            reason=reason,
        )
        step.state = ExecutionState.WAITING_APPROVAL
        self._requests[req.request_id] = req
        return req

    def grant_approval(self, request_id: str, approved: bool = True) -> Optional[ApprovalRequest]:
        req = self._requests.get(request_id)
        if req:
            req.approved = approved
        return req

    def get_pending_requests(self) -> List[ApprovalRequest]:
        return [r for r in self._requests.values() if r.approved is None]
