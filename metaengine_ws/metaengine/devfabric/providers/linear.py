from __future__ import annotations

import json
from typing import Any, Mapping, Protocol

from ..models import PrivacyClass, TaskEnvelope
from .external import ConnectorPolicyError, ConnectorReceipt, require_write_intent, sanitize_task


class LinearTransport(Protocol):
    def find_project(self, name: str) -> Mapping[str, Any] | None: ...
    def find_issue_by_task_hash(self, project_id: str, task_hash: str) -> Mapping[str, Any] | None: ...
    def create_issue(
        self, project_id: str, title: str, description: str, task_hash: str
    ) -> Mapping[str, Any]: ...


class LinearProjectionAdapter:
    connector_id = "linear"

    def __init__(self, transport: LinearTransport):
        self._transport = transport

    def _project(self, project_name: str) -> Mapping[str, Any]:
        project = self._transport.find_project(project_name)
        if not project:
            raise ConnectorPolicyError("LINEAR_PROJECT_NOT_FOUND")
        return project

    def read_projection(self, task_hash: str, *, project_name: str) -> dict[str, Any] | None:
        project = self._project(project_name)
        issue = self._transport.find_issue_by_task_hash(str(project["id"]), task_hash)
        return dict(issue) if issue else None

    def project_task(
        self,
        task: TaskEnvelope,
        *,
        project_name: str,
        write_intent: str | None,
    ) -> ConnectorReceipt:
        require_write_intent("PROJECT_TASK", write_intent)
        safe = sanitize_task(task)
        project = self._project(project_name)
        project_id = str(project["id"])
        existing = self._transport.find_issue_by_task_hash(project_id, task.task_hash)
        if existing:
            return ConnectorReceipt.create(
                connector_id=self.connector_id,
                operation="PROJECT_TASK",
                object_hash=task.task_hash,
                status="PASS",
                reason_code="DEDUPED",
                remote_id=str(existing.get("id")) if existing.get("id") else None,
            )

        if task.privacy_class is PrivacyClass.P2:
            title = f"Metaengine task {task.task_id}"
        else:
            title = task.objective.strip()[:120] or f"Metaengine task {task.task_id}"
        description = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        issue = dict(self._transport.create_issue(project_id, title, description, task.task_hash))
        return ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="PROJECT_TASK",
            object_hash=task.task_hash,
            status="PASS",
            reason_code="OK",
            remote_id=str(issue.get("id")) if issue.get("id") else None,
        )
