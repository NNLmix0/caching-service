import uuid

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CachedTransform(Base):
    __tablename__ = "cached_transform"

    input: Mapped[str] = mapped_column(primary_key=True)
    output: Mapped[str]


class Payload(Base):
    __tablename__ = "payload"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Hash of the request's input lists. The unique constraint is what guarantees
    # that the same input always maps to the same payload id.
    input_hash: Mapped[str] = mapped_column(unique=True)
    output: Mapped[str]
