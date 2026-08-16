"""Tests for Phase 66 — Docker + Deployment configuration.

Verifies Docker files, docker-compose, CI/CD pipeline exist and are valid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_ROOT = ROOT.parent  # /home/z/my-project


# ---------------------------------------------------------------------------
# Tests: Dockerfile
# ---------------------------------------------------------------------------


class TestDockerfile:
    def test_dockerfile_exists(self):
        assert (ROOT / "Dockerfile").is_file()

    def test_dockerfile_uses_python_312(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "python:3.12" in content

    def test_dockerfile_exposes_port_8080(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "EXPOSE 8080" in content

    def test_dockerfile_has_healthcheck(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "HEALTHCHECK" in content
        assert "/api/health" in content

    def test_dockerfile_sets_pythonpath(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "PYTHONPATH=/app" in content

    def test_dockerfile_copies_metaengine(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "COPY" in content
        assert "metaengine/" in content

    def test_dockerfile_runs_api_server(self):
        content = (ROOT / "Dockerfile").read_text()
        assert "metaengine.api_server" in content
        assert "CMD" in content


# ---------------------------------------------------------------------------
# Tests: docker-compose.yml
# ---------------------------------------------------------------------------


class TestDockerCompose:
    def test_compose_exists(self):
        assert (ROOT / "docker-compose.yml").is_file()

    def test_compose_has_api_service(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "metaengine-api" in content

    def test_compose_has_bridge_service(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "llm-bridge" in content

    def test_compose_has_dashboard_service(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "dashboard" in content

    def test_compose_has_gateway_service(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "gateway" in content

    def test_compose_has_volumes(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "volumes" in content
        assert "metaengine-storage" in content

    def test_compose_has_networks(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "networks" in content
        assert "metaengine-net" in content

    def test_compose_has_restart_policy(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "restart: unless-stopped" in content

    def test_compose_has_healthchecks(self):
        content = (ROOT / "docker-compose.yml").read_text()
        assert "healthcheck" in content


# ---------------------------------------------------------------------------
# Tests: LLM Bridge Dockerfile
# ---------------------------------------------------------------------------


class TestBridgeDockerfile:
    def test_bridge_dockerfile_exists(self):
        path = DEPLOY_ROOT / "mini-services" / "llm-bridge" / "Dockerfile.bridge"
        assert path.is_file()

    def test_bridge_dockerfile_uses_bun(self):
        path = DEPLOY_ROOT / "mini-services" / "llm-bridge" / "Dockerfile.bridge"
        content = path.read_text()
        assert "bun" in content.lower()

    def test_bridge_dockerfile_exposes_port_3031(self):
        path = DEPLOY_ROOT / "mini-services" / "llm-bridge" / "Dockerfile.bridge"
        content = path.read_text()
        assert "EXPOSE 3031" in content

    def test_bridge_dockerfile_has_healthcheck(self):
        path = DEPLOY_ROOT / "mini-services" / "llm-bridge" / "Dockerfile.bridge"
        content = path.read_text()
        assert "HEALTHCHECK" in content


# ---------------------------------------------------------------------------
# Tests: Dashboard Dockerfile
# ---------------------------------------------------------------------------


class TestDashboardDockerfile:
    def test_dashboard_dockerfile_exists(self):
        assert (ROOT / "Dockerfile.dashboard").is_file()

    def test_dashboard_dockerfile_uses_node(self):
        content = (ROOT / "Dockerfile.dashboard").read_text()
        assert "node" in content.lower()

    def test_dashboard_dockerfile_exposes_port_3000(self):
        content = (ROOT / "Dockerfile.dashboard").read_text()
        assert "EXPOSE 3000" in content

    def test_dashboard_dockerfile_has_memory_limit(self):
        content = (ROOT / "Dockerfile.dashboard").read_text()
        assert "max-old-space-size" in content


# ---------------------------------------------------------------------------
# Tests: .dockerignore
# ---------------------------------------------------------------------------


class TestDockerignore:
    def test_dockerignore_exists(self):
        assert (ROOT / ".dockerignore").is_file()

    def test_dockerignore_excludes_node_modules(self):
        content = (ROOT / ".dockerignore").read_text()
        assert "node_modules" in content

    def test_dockerignore_excludes_pycache(self):
        content = (ROOT / ".dockerignore").read_text()
        assert "__pycache__" in content

    def test_dockerignore_excludes_git(self):
        content = (ROOT / ".dockerignore").read_text()
        assert ".git" in content


# ---------------------------------------------------------------------------
# Tests: CI/CD Pipeline
# ---------------------------------------------------------------------------


class TestCICD:
    def test_ci_file_exists(self):
        path = DEPLOY_ROOT / ".github" / "workflows" / "ci.yml"
        assert path.is_file()

    def test_ci_has_test_job(self):
        content = (DEPLOY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "test" in content.lower()
        assert "pytest" in content

    def test_ci_has_build_job(self):
        content = (DEPLOY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "build" in content.lower()
        assert "docker" in content.lower()

    def test_ci_has_deploy_job(self):
        content = (DEPLOY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "deploy" in content.lower()

    def test_ci_triggers_on_push(self):
        content = (DEPLOY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "push" in content
        assert "branches" in content

    def test_ci_triggers_on_tags(self):
        content = (DEPLOY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "tags" in content


# ---------------------------------------------------------------------------
# Tests: .env.example + DEPLOYMENT.md
# ---------------------------------------------------------------------------


class TestDeploymentDocs:
    def test_env_example_exists(self):
        assert (ROOT / ".env.example").is_file()

    def test_env_example_has_turso_token(self):
        content = (ROOT / ".env.example").read_text()
        assert "TURSO_DB_TOKEN" in content

    def test_deployment_guide_exists(self):
        assert (ROOT / "DEPLOYMENT.md").is_file()

    def test_deployment_guide_has_docker_compose(self):
        content = (ROOT / "DEPLOYMENT.md").read_text()
        assert "docker-compose" in content

    def test_deployment_guide_has_quick_start(self):
        content = (ROOT / "DEPLOYMENT.md").read_text()
        assert "Quick Start" in content or "quick start" in content.lower()

    def test_deployment_guide_has_services_table(self):
        content = (ROOT / "DEPLOYMENT.md").read_text()
        assert "metaengine-api" in content
        assert "llm-bridge" in content
        assert "dashboard" in content
        assert "gateway" in content


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_dockerfile_doesnt_modify_code(self):
        content = (ROOT / "Dockerfile").read_text()
        # Dockerfile copies files, doesn't modify source code
        assert "COPY" in content
        assert "RUN sed" not in content  # no in-place code modification
        assert "RUN echo" not in content or "echo" not in content.split("RUN")[1][:50]

    def test_env_example_no_secrets(self):
        content = (ROOT / ".env.example").read_text()
        # Should not contain actual tokens
        assert "eyJ" not in content  # no JWT tokens
        assert "your_turso" in content or "your_" in content

    def test_ci_pipeline_runs_tests(self):
        content = (DEPLOY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        # CI must run tests before building/deploying
        assert "pytest" in content
        assert "needs: test" in content or "needs: test" in content.replace(" ", "")
