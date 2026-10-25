from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_network_semantic_judge(monkeypatch: pytest.MonkeyPatch):
    """Unit/integration tests opt into mocked semantic classification explicitly."""

    monkeypatch.setenv("GUARD_SEMANTIC_JUDGE_ENABLED", "false")
