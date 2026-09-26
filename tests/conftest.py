from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dgro.config import Settings
from dgro.runtime import Runtime, build_runtime
from dgro.web.app import create_app


def make_settings(tmp_path, **overrides) -> Settings:
    values = dict(
        _env_file=None,
        data_dir=tmp_path,
        llm="fake",
        email_mode="sandbox",
        send_delay_seconds=0,
        requester_name="Anna Nowak",
        requester_email="anna@example.org",
        requester_phone="+48 600 000 000",
        workers=1,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def rt(settings) -> Runtime:
    runtime = build_runtime(settings)
    yield runtime
    runtime.engine.dispose()


@pytest.fixture
def client(rt) -> TestClient:
    # Jobs are run explicitly with rt.worker.run_pending() so tests are deterministic.
    with TestClient(create_app(rt, start_worker=False)) as test_client:
        yield test_client
