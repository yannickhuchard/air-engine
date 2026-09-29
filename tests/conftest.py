from copy import deepcopy
import json
import os
from pathlib import Path
import pytest
from air.storage import Store, metadata

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example():
    return json.loads((ROOT / "examples/scope.json").read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path):
    # PostgreSQL integration runs in an explicitly disposable database in CI.
    url = os.environ.get("AIR_TEST_DATABASE_URL")
    if url and os.environ.get("AIR_TEST_ALLOW_RESET") != "yes":
        pytest.fail("AIR_TEST_ALLOW_RESET=yes required for disposable PostgreSQL test database")
    result = Store(url or f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    if url:
        metadata.drop_all(result.engine)
    result.migrate()
    yield result
    if url:
        metadata.drop_all(result.engine)
    result.engine.dispose()
