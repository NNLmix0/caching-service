from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from caching_service.config import settings

engine = create_engine(settings.database_url)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
