import asyncio

import pytest

from openapi_mcp.config import AuthConfig, Config
from openapi_mcp.executor import call_tool
from openapi_mcp.spec import load_spec
from openapi_mcp.tools import ToolDef, build_tools

from conftest import PETSTORE


@pytest.fixture
def tools():
    return {t.name: t for t in build_tools(load_spec(PETSTORE))}


def run(coro):
    return asyncio.run(coro)


def test_get_with_path_query_and_header(tools, fake_api):
    base, seen = fake_api
    r = run(call_tool(tools["getPet"], {"petId": 7, "X-Request-Id": "abc"}, Config(), base))
    assert not r.is_error and '"id": 7' in r.text
    assert seen[-1]["path"] == "/v1/pets/7" and seen[-1]["headers"]["X-Request-Id"] == "abc"

    r = run(call_tool(tools["listPets"], {"limit": 5, "status": "available"}, Config(), base))
    assert r.status == 200 and seen[-1]["path"] == "/v1/pets?limit=5&status=available"


def test_write_blocked_without_flag(tools, fake_api):
    base, seen = fake_api
    r = run(call_tool(tools["createPet"], {"body": {"name": "Bob"}}, Config(), base))
    assert r.is_error and "read-only" in r.text and seen == []


def test_write_allowed_with_flag(tools, fake_api):
    base, seen = fake_api
    r = run(call_tool(tools["createPet"], {"body": {"name": "Bob"}}, Config(allow_write=True), base))
    assert r.status == 201 and seen[-1]["body"] == {"name": "Bob"}


def test_bearer_auth_injected_and_redacted(tools, fake_api, monkeypatch):
    base, seen = fake_api
    monkeypatch.setenv("PET_TOKEN", "s3cr3t-token")
    cfg = Config(auth=AuthConfig(type="bearer", env="PET_TOKEN"))
    r = run(call_tool(tools["listPets"], {}, cfg, base))
    assert seen[-1]["headers"]["Authorization"] == "Bearer s3cr3t-token"
    assert "s3cr3t-token" not in r.text


def test_api_key_in_header_and_query(tools, fake_api, monkeypatch):
    base, seen = fake_api
    monkeypatch.setenv("PET_KEY", "k-123")
    run(call_tool(tools["listPets"], {}, Config(auth=AuthConfig(type="api_key", env="PET_KEY", header="X-API-Key")), base))
    assert seen[-1]["headers"]["X-API-Key"] == "k-123"
    run(call_tool(tools["listPets"], {}, Config(auth=AuthConfig(type="api_key", env="PET_KEY", query="api_key")), base))
    assert "api_key=k-123" in seen[-1]["path"]


def test_missing_secret_fails_fast(tools):
    with pytest.raises(ValueError, match="NOPE_TOKEN"):
        run(call_tool(tools["listPets"], {}, Config(auth=AuthConfig(type="bearer", env="NOPE_TOKEN")), "http://x"))


def test_input_validation(tools, fake_api):
    base, seen = fake_api
    assert "missing required" in run(call_tool(tools["getPet"], {}, Config(), base)).text
    assert "unknown argument" in run(call_tool(tools["listPets"], {"evil": 1}, Config(), base)).text
    assert seen == []


def test_large_response_truncated(fake_api):
    base, _ = fake_api
    tool = ToolDef(name="big", description="", method="get", path="/big", input_schema={"type": "object", "properties": {}})
    r = run(call_tool(tool, {}, Config(max_response_chars=100), base))
    assert "[truncated" in r.text and len(r.text) < 400


def test_http_error_and_timeout(tools, fake_api):
    base, _ = fake_api
    tool = ToolDef(name="nope", description="", method="get", path="/missing", input_schema={"type": "object", "properties": {}})
    assert run(call_tool(tool, {}, Config(), base)).is_error
    r = run(call_tool(tools["listPets"], {}, Config(timeout=1), "http://10.255.255.1"))
    assert r.is_error and "request failed" in r.text
