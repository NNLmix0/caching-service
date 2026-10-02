import io
import json
import sys
from contextlib import nullcontext

import httpx2
import pytest

from caching_service.cli import CacheCli, main

BODY = json.dumps({"list_1": ["a", "b"], "list_2": ["c", "d"]})


@pytest.fixture
def run_cli(client, monkeypatch):
    """Run the CLI entry point with HTTP calls routed to the in-process app."""
    monkeypatch.setattr(httpx2, "Client", lambda base_url: nullcontext(client))

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["cache-cli", *args])
        main()

    return run


def test_repeat_reports_created_then_reused_payload(run_cli, capsys):
    run_cli("--repeat", "2", "--json", BODY)

    first, second = map(json.loads, capsys.readouterr().out.splitlines())
    assert first == {"status": 201, "id": first["id"], "output": "A, C, B, D"}
    assert second == {**first, "status": 200}


def test_input_file_and_output_file(run_cli, tmp_path, capsys):
    input_file = tmp_path / "in.json"
    output_file = tmp_path / "out.jsonl"
    input_file.write_text(BODY)

    run_cli("-i", str(input_file), "-o", str(output_file))

    assert json.loads(output_file.read_text())["output"] == "A, C, B, D"
    assert capsys.readouterr().out == ""


def test_dash_reads_input_from_stdin(run_cli, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(BODY))

    run_cli("-i", "-")

    assert json.loads(capsys.readouterr().out)["output"] == "A, C, B, D"


def test_capital_h_sets_host():
    cli = CacheCli(_cli_parse_args=["-H", "http://example.test:1234", "-j", BODY])

    assert str(cli.host) == "http://example.test:1234/"


def test_lowercase_h_shows_help(run_cli, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_cli("-h")

    assert exit_info.value.code == 0
    assert "--host" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ([], "exactly one of --input and --json"),
        (["-i", "in.json", "-j", BODY], "exactly one of --input and --json"),
        (["-j", BODY, "-r", "0"], "--repeat"),
        (["-j", BODY, "-H", "not-a-url"], "--host"),
        (["-j", "not json"], "--json"),
        (["-i", "missing.json"], "missing.json"),
    ],
    ids=["no input", "two inputs", "zero repeat", "bad host", "bad json", "missing file"],
)
def test_invalid_arguments_exit_with_message(run_cli, args, message):
    with pytest.raises(SystemExit) as exit_info:
        run_cli(*args)

    assert message in exit_info.value.code


def test_server_rejection_is_reported(run_cli):
    with pytest.raises(SystemExit) as exit_info:
        run_cli("-j", json.dumps({"list_1": ["a", "b"], "list_2": ["c"]}))

    assert "422" in exit_info.value.code
    assert "same length" in exit_info.value.code
