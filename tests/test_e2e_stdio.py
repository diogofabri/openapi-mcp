"""End to end: spawn the server over stdio and drive it with the official MCP client."""
import asyncio
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from conftest import PETSTORE

ROOT = Path(__file__).resolve().parents[1]


async def session_run(base_url, extra_args=(), env=None):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "openapi_mcp", "serve", "--spec", PETSTORE, "--base-url", base_url, *extra_args],
        cwd=str(ROOT),
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            listed = await s.list_tools()
            got = await s.call_tool("getPet", {"petId": 42})
            denied = await s.call_tool("createPet", {"body": {"name": "Bob"}})
            return listed, got, denied


def test_list_and_call_over_stdio(fake_api):
    base, seen = fake_api
    listed, got, denied = asyncio.run(session_run(base, env={"PET_TOKEN": "tok-e2e"}))
    names = {t.name for t in listed.tools}
    assert names == {"listPets", "getPet", "get_stats"}          # read-only by default
    get_pet = next(t for t in listed.tools if t.name == "getPet")
    assert get_pet.input_schema["required"] == ["petId"]
    assert get_pet.annotations.read_only_hint is True

    assert not got.is_error and '"id": 42' in got.content[0].text
    assert seen[-1]["path"] == "/v1/pets/42"

    assert denied.is_error and "unknown tool" in denied.content[0].text  # write op not even listed


def test_write_and_auth_over_stdio(fake_api):
    base, seen = fake_api
    args = ["--allow-write", "--auth-type", "bearer", "--auth-env", "PET_TOKEN"]
    listed, _, created = asyncio.run(session_run(base, args, env={"PET_TOKEN": "tok-e2e"}))
    assert "createPet" in {t.name for t in listed.tools}
    assert not created.is_error and seen[-1]["method"] == "POST" and seen[-1]["body"] == {"name": "Bob"}
    assert seen[-1]["headers"]["Authorization"] == "Bearer tok-e2e"
    assert "tok-e2e" not in created.content[0].text
