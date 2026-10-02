from sqlalchemy import func, select
from sqlalchemy.orm import Session

from caching_service import transformer
from caching_service.models import Payload
from caching_service.service import create_payload

LIST_1 = ["first string", "second string", "third string"]
LIST_2 = ["other string", "another string", "last string"]


def test_output_interleaves_transformed_lists(session):
    payload, created = create_payload(session, LIST_1, LIST_2)

    assert created
    assert payload.output == (
        "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
    )


def test_repeated_request_reuses_payload_without_transformer_calls(session, transform_calls):
    first, _ = create_payload(session, LIST_1, LIST_2)
    transform_calls.clear()

    second, created = create_payload(session, LIST_1, LIST_2)

    assert not created
    assert second.id == first.id
    assert transform_calls == []


def test_transformer_is_called_once_per_distinct_string(session, transform_calls):
    payload, _ = create_payload(session, ["a", "a"], ["a", "b"])

    assert payload.output == "A, A, A, B"
    assert sorted(transform_calls) == ["a", "b"]


def test_cached_strings_are_reused_by_other_payloads(session, transform_calls):
    create_payload(session, ["a"], ["b"])
    transform_calls.clear()

    payload, created = create_payload(session, ["a"], ["c"])

    assert created
    assert payload.output == "A, C"
    assert transform_calls == ["c"]


def test_swapped_lists_are_a_different_payload(session):
    first, _ = create_payload(session, ["a"], ["b"])
    second, created = create_payload(session, ["b"], ["a"])

    assert created
    assert second.id != first.id
    assert second.output == "B, A"


def test_concurrent_duplicate_request_returns_the_stored_payload(engine, session, monkeypatch):
    winner_ids = []

    def transform_while_other_request_wins(value):
        monkeypatch.setattr(transformer, "transform", str.upper)
        with Session(engine) as other_session:
            winner, _ = create_payload(other_session, ["x"], ["y"])
            winner_ids.append(winner.id)
        return value.upper()

    monkeypatch.setattr(transformer, "transform", transform_while_other_request_wins)

    payload, created = create_payload(session, ["x"], ["y"])

    assert not created
    assert [payload.id] == winner_ids
    assert session.scalar(select(func.count()).select_from(Payload)) == 1
