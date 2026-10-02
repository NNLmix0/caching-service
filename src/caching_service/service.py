import hashlib
import json
from itertools import chain

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from caching_service import transformer
from caching_service.models import CachedTransform, Payload


def create_payload(session: Session, list_1: list[str], list_2: list[str]) -> tuple[Payload, bool]:
    """Return the payload for the given input and whether it was newly created."""
    input_hash = _hash_input(list_1, list_2)
    existing = session.scalar(select(Payload).where(Payload.input_hash == input_hash))
    if existing:
        return existing, False

    transformed = _transform_with_cache(session, {*list_1, *list_2})
    interleaved = chain.from_iterable(zip(list_1, list_2, strict=True))
    payload = Payload(input_hash=input_hash, output=", ".join(transformed[s] for s in interleaved))
    session.add(payload)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request stored the same payload or cache entry first.
        # Its rows are visible now, so a second pass will reuse them.
        session.rollback()
        return create_payload(session, list_1, list_2)
    return payload, True


def _hash_input(list_1: list[str], list_2: list[str]) -> str:
    # Identity is based on the input rather than the output, so a repeated
    # request is recognised without calling the transformer at all. JSON keeps
    # list boundaries unambiguous: ["a, b"] and ["a", "b"] must not collide.
    return hashlib.sha256(json.dumps([list_1, list_2]).encode()).hexdigest()


def _transform_with_cache(session: Session, values: set[str]) -> dict[str, str]:
    """Transform each distinct value, calling the transformer only on cache misses."""
    rows = session.execute(
        select(CachedTransform.input, CachedTransform.output).where(
            CachedTransform.input.in_(values)
        )
    )
    transformed = {row.input: row.output for row in rows}
    for value in values - transformed.keys():
        transformed[value] = transformer.transform(value)
        session.add(CachedTransform(input=value, output=transformed[value]))
    return transformed
