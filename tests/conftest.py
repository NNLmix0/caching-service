import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from caching_service import transformer
from caching_service.api import app
from caching_service.db import get_session
from caching_service.models import Base


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def transform_calls(monkeypatch):
    """Every string that reached the transformer, in call order."""
    calls = []
    real_transform = transformer.transform

    def recording_transform(value):
        calls.append(value)
        return real_transform(value)

    monkeypatch.setattr(transformer, "transform", recording_transform)
    return calls
