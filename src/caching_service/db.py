from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from caching_service.config import settings

# SQLite connections refuse to be used outside the thread that created them,
# but FastAPI may run a sync dependency and its endpoint in different
# threadpool threads. Each request still gets its own session.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
