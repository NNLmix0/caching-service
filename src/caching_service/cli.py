import json
import sys
from pathlib import Path
from typing import Any, Self

import httpx2
from pydantic import Field, HttpUrl, Json, PositiveInt, ValidationError, model_validator
from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict


class CacheCli(BaseSettings):
    """Send a payload to the caching service and print the generated output."""

    model_config = SettingsConfigDict(
        cli_prog_name="cache-cli",
        cli_hide_none_type=True,
        cli_shortcuts={"host": "H", "repeat": "r", "input": "i", "json": "j", "output": "o"},
        # -H must stay distinct from -h, which argparse reserves for --help.
        case_sensitive=True,
        # Keeps unrelated environment variables such as HOST from leaking in.
        env_prefix="CACHE_CLI_",
    )

    host: HttpUrl = Field(HttpUrl("http://localhost:8000"), description="points to the server")
    repeat: PositiveInt = Field(1, description="number of iterations")
    input: str | None = Field(None, description='input file ("-" for stdin)')
    json_: Json[Any] | None = Field(None, alias="json", description="input as a JSON string")
    output: str = Field("-", description='output file ("-" for stdout)')

    @model_validator(mode="after")
    def exactly_one_input_source(self) -> Self:
        if (self.input is None) == (self.json_ is None):
            raise ValueError("provide exactly one of --input and --json")
        return self

    def cli_cmd(self) -> None:
        body = self.json_ if self.input is None else json.loads(_read(self.input))
        lines = []
        with httpx2.Client(base_url=str(self.host)) as client:
            for _ in range(self.repeat):
                created = client.post("/payload", json=body).raise_for_status()
                payload_id = created.json()["id"]
                fetched = client.get(f"/payload/{payload_id}").raise_for_status()
                # The status tells a fresh payload (201) from a reused one (200),
                # which is what repeating the request is meant to show.
                result = {"status": created.status_code, "id": payload_id, **fetched.json()}
                lines.append(json.dumps(result))
        _write(self.output, "\n".join(lines) + "\n")


def _read(source: str) -> str:
    return sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")


def _write(target: str, text: str) -> None:
    if target == "-":
        sys.stdout.write(text)
    else:
        Path(target).write_text(text, encoding="utf-8")


def _describe(error: dict[str, Any]) -> str:
    option = "".join(f"--{name}: " for name in error["loc"])
    return f"cache-cli: error: {option}{error['msg']}"


def main() -> None:
    try:
        CliApp.run(CacheCli)
    except ValidationError as error:
        sys.exit("\n".join(_describe(e) for e in error.errors()))
    except httpx2.HTTPStatusError as error:
        sys.exit(f"cache-cli: error: {error}\n{error.response.text}")
    except (OSError, ValueError, httpx2.HTTPError) as error:
        sys.exit(f"cache-cli: error: {error}")
