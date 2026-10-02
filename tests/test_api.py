import uuid

import pytest

BODY = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}


def test_post_creates_payload_readable_by_id(client):
    created = client.post("/payload", json=BODY)
    assert created.status_code == 201

    fetched = client.get(f"/payload/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == {
        "output": (
            "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
        )
    }


def test_repeated_post_returns_same_id_without_transformer_calls(client, transform_calls):
    first = client.post("/payload", json=BODY)
    transform_calls.clear()

    second = client.post("/payload", json=BODY)

    assert second.status_code == 200
    assert second.json() == first.json()
    assert transform_calls == []


def test_get_unknown_id_returns_404(client):
    assert client.get(f"/payload/{uuid.uuid4()}").status_code == 404


def test_get_malformed_id_returns_422(client):
    assert client.get("/payload/not-a-uuid").status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"list_1": ["a", "b"], "list_2": ["c"]},
        {"list_1": [], "list_2": []},
        {"list_1": [1], "list_2": ["a"]},
        {"list_1": ["a"]},
    ],
    ids=["length mismatch", "empty lists", "non-string item", "missing list"],
)
def test_invalid_body_is_rejected_before_transforming(client, transform_calls, body):
    assert client.post("/payload", json=body).status_code == 422
    assert transform_calls == []
