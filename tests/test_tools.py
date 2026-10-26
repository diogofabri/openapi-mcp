import json

import pytest

from openapi_mcp.config import Config
from openapi_mcp.spec import SpecError, load_spec, resolve
from openapi_mcp.tools import build_tools

from conftest import PETSTORE


@pytest.fixture
def tools():
    return {t.name: t for t in build_tools(load_spec(PETSTORE))}


def test_one_tool_per_operation(tools):
    assert set(tools) == {"listPets", "createPet", "getPet", "deletePet", "get_stats"}


def test_names_are_valid_mcp_identifiers(tools):
    for name in tools:
        assert len(name) <= 64 and all(c.isalnum() or c in "_-" for c in name)


def test_query_params_and_component_refs(tools):
    schema = tools["listPets"].input_schema
    assert schema["properties"]["limit"]["maximum"] == 100          # from #/components/parameters
    assert schema["properties"]["status"]["enum"] == ["available", "pending", "adopted"]  # from #/components/schemas
    assert "required" not in schema
    assert tools["listPets"].bindings["status"].location == "query"


def test_path_level_params_are_required(tools):
    schema = tools["getPet"].input_schema
    assert schema["properties"]["petId"]["type"] == "integer"
    assert "petId" in schema["required"]
    assert tools["getPet"].bindings["X-Request-Id"].location == "header"


def test_request_body(tools):
    t = tools["createPet"]
    assert t.is_write and t.body_content_type == "application/json"
    body = t.input_schema["properties"]["body"]
    assert body["required"] == ["name"] and "owner" in body["properties"]
    assert t.input_schema["required"] == ["body"]


def test_recursive_schema_is_cut():
    doc = load_spec(PETSTORE)
    owner = resolve({"$ref": "#/components/schemas/Owner"}, doc)
    inner = owner["properties"]["pets"]["items"]
    assert "recursive" in inner["description"]
    json.dumps(owner)  # finite, serializable


def test_schemas_are_valid_json_schema_objects(tools):
    for t in tools.values():
        s = t.input_schema
        assert s["type"] == "object" and isinstance(s["properties"], dict)
        assert set(s.get("required", [])) <= set(s["properties"])
        assert "$ref" not in json.dumps(s)


def test_read_only_by_default_and_filters(tools):
    all_tools = list(tools.values())
    assert {t.name for t in Config().select(all_tools)} == {"listPets", "getPet", "get_stats"}
    assert {t.name for t in Config(allow_write=True, exclude=["tag:admin"]).select(all_tools)} == {"listPets", "createPet", "getPet"}
    assert {t.name for t in Config(include=["getPet"]).select(all_tools)} == {"getPet"}


def test_rejects_swagger_2(tmp_path):
    p = tmp_path / "old.json"
    p.write_text('{"swagger": "2.0", "paths": {}}')
    with pytest.raises(SpecError):
        load_spec(str(p))
