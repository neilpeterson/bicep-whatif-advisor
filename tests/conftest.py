"""Shared test fixtures for bicep-whatif-advisor."""

import json
import os
from pathlib import Path
from typing import List, Optional, Tuple, Union

import pytest

from bicep_whatif_advisor.providers import Provider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# MockProvider
# ---------------------------------------------------------------------------

class MockProvider(Provider):
    """Mock LLM provider for testing. Records calls and returns canned JSON."""

    def __init__(self, response: Union[dict, str, None] = None):
        self.response = response or {}
        self.calls: List[Tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.response, str):
            return self.response
        return json.dumps(self.response)


# ---------------------------------------------------------------------------
# Fixture file loaders (session-scoped — read once)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def create_only_fixture():
    return (FIXTURES_DIR / "create_only.txt").read_text()


@pytest.fixture(scope="session")
def mixed_changes_fixture():
    return (FIXTURES_DIR / "mixed_changes.txt").read_text()


@pytest.fixture(scope="session")
def deletes_fixture():
    return (FIXTURES_DIR / "deletes.txt").read_text()


@pytest.fixture(scope="session")
def no_changes_fixture():
    return (FIXTURES_DIR / "no_changes.txt").read_text()


@pytest.fixture(scope="session")
def large_output_fixture():
    return (FIXTURES_DIR / "large_output.txt").read_text()


@pytest.fixture(scope="session")
def noisy_changes_fixture():
    return (FIXTURES_DIR / "noisy_changes.txt").read_text()


# ---------------------------------------------------------------------------
# Sample LLM responses
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_standard_response():
    return {
        "resources": [
            {
                "resource_name": "appinsights-diag",
                "resource_type": "ApiManagement/diagnostics",
                "action": "Create",
                "summary": "Creates Application Insights diagnostics",
                "confidence_level": "high",
                "confidence_reason": "New resource creation",
            },
            {
                "resource_name": "apim-policy",
                "resource_type": "ApiManagement/policies",
                "action": "Create",
                "summary": "Creates global APIM policy",
                "confidence_level": "high",
                "confidence_reason": "New resource creation",
            },
        ],
        "overall_summary": "2 resources will be created.",
    }


@pytest.fixture
def sample_standard_response_with_noise():
    return {
        "resources": [
            {
                "resource_name": "myvnet",
                "resource_type": "Network/virtualNetworks",
                "action": "Modify",
                "summary": "Address space change from /16 to /8",
                "confidence_level": "high",
                "confidence_reason": "Real config change",
            },
            {
                "resource_name": "myvnet-etag",
                "resource_type": "Network/virtualNetworks",
                "action": "Modify",
                "summary": "etag update",
                "confidence_level": "low",
                "confidence_reason": "Metadata-only change",
            },
        ],
        "overall_summary": "1 real change, 1 noise.",
    }


@pytest.fixture
def sample_ci_response_safe():
    return {
        "resources": [
            {
                "resource_name": "newstorage",
                "resource_type": "Storage/storageAccounts",
                "action": "Create",
                "summary": "Creates a new storage account",
                "risk_level": "low",
                "risk_reason": None,
                "confidence_level": "high",
                "confidence_reason": "New resource creation",
            },
        ],
        "overall_summary": "1 new storage account.",
        "risk_assessment": {
            "drift": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "No drift detected",
            },
            "operations": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "Only creating new resources",
            },
        },
        "verdict": {
            "safe": True,
            "highest_risk_bucket": "none",
            "overall_risk_level": "low",
            "reasoning": "Safe to deploy. Only adding a new storage account.",
        },
    }


@pytest.fixture
def sample_ci_response_unsafe():
    return {
        "resources": [
            {
                "resource_name": "prod-db",
                "resource_type": "Sql/servers/databases",
                "action": "Delete",
                "summary": "Deletes production database",
                "risk_level": "high",
                "risk_reason": "Stateful resource deletion",
                "confidence_level": "high",
                "confidence_reason": "Real deletion",
            },
        ],
        "overall_summary": "1 database deletion.",
        "risk_assessment": {
            "drift": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "No drift detected",
            },
            "operations": {
                "risk_level": "high",
                "concerns": ["Deletion of production database"],
                "reasoning": "Stateful resource deletion is high risk",
            },
        },
        "verdict": {
            "safe": False,
            "highest_risk_bucket": "operations",
            "overall_risk_level": "high",
            "reasoning": "Unsafe. Deleting a production database.",
        },
    }


@pytest.fixture
def sample_ci_response_with_intent():
    return {
        "resources": [
            {
                "resource_name": "newstorage",
                "resource_type": "Storage/storageAccounts",
                "action": "Create",
                "summary": "Creates a new storage account",
                "risk_level": "low",
                "risk_reason": None,
                "confidence_level": "high",
                "confidence_reason": "New resource creation",
            },
        ],
        "overall_summary": "1 new storage account.",
        "risk_assessment": {
            "drift": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "No drift",
            },
            "intent": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "Matches PR intent",
            },
            "operations": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "Low risk operations",
            },
        },
        "verdict": {
            "safe": True,
            "highest_risk_bucket": "none",
            "overall_risk_level": "low",
            "reasoning": "Safe. All buckets low risk.",
        },
    }


# ---------------------------------------------------------------------------
# Environment variable helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def github_env(monkeypatch):
    """Set GitHub Actions environment variables."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/test")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/42/merge")


@pytest.fixture
def azdevops_env(monkeypatch):
    """Set Azure DevOps pipeline environment variables."""
    monkeypatch.setenv("TF_BUILD", "True")
    monkeypatch.setenv("AGENT_ID", "1")
    monkeypatch.setenv("SYSTEM_PULLREQUEST_PULLREQUESTID", "99")
    monkeypatch.setenv("SYSTEM_PULLREQUEST_TARGETBRANCH", "refs/heads/main")
    monkeypatch.setenv("SYSTEM_PULLREQUEST_SOURCEBRANCH", "refs/heads/feature/test")
    monkeypatch.setenv("BUILD_REPOSITORY_NAME", "myrepo")
    monkeypatch.setenv("BUILD_REPOSITORY_ID", "repo-guid")
    monkeypatch.setenv("SYSTEM_COLLECTIONURI", "https://dev.azure.com/myorg/")
    monkeypatch.setenv("SYSTEM_TEAMPROJECT", "myproject")


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all CI-related environment variables."""
    for var in [
        "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_BASE_REF",
        "GITHUB_HEAD_REF", "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH",
        "GITHUB_REF", "GITHUB_TOKEN",
        "TF_BUILD", "AGENT_ID",
        "SYSTEM_PULLREQUEST_PULLREQUESTID", "SYSTEM_PULLREQUEST_TARGETBRANCH",
        "SYSTEM_PULLREQUEST_SOURCEBRANCH", "BUILD_REPOSITORY_NAME",
        "BUILD_REPOSITORY_ID", "SYSTEM_COLLECTIONURI", "SYSTEM_TEAMPROJECT",
        "SYSTEM_ACCESSTOKEN",
        "ANTHROPIC_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT",
        "OLLAMA_HOST", "WHATIF_PROVIDER", "WHATIF_MODEL",
    ]:
        monkeypatch.delenv(var, raising=False)
