"""Pure NF14 rules of the Inventory (peo.inventory.values); spec 14 §3.3, spec 16 F3.

Outside tests/inventory/: values is pure, and hypothesis refuses function-scoped fixtures,
autouse included.
"""

import json
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from peo.inventory import values
from peo.validate import load_schema

NPM = r"^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$"
PEP503 = r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$"
COMMAND = r"^[a-z0-9][a-z0-9._-]*$"
HOST = r"^[a-z0-9.-]{1,214}$"
LAUNCHERS = {"npx", "uvx", "bunx", "pnpm-dlx", "docker", "other", None}
TRANSPORTS = {"stdio", "http", "sse", "ws", "streamable-http", "other"}


@pytest.mark.parametrize("const, key", [
    ("EVENT", "event"), ("NAME", "name"), ("MATCHER", "matcher"), ("PLUGIN_ID", "plugin_id"),
    ("TOOL_REF", "tool_ref"), ("LOCATION", "location"), ("RULE", "rule"), ("VERSION", "version"),
])
def test_values_constants_are_the_schema_patterns(const, key):
    assert getattr(values, const) == load_schema("inventory").root["$defs"][key]["pattern"]


@pytest.mark.parametrize("kind, good, bad, fallback", [
    ("event", "PreToolUse", "Pre:ToolUse", None),
    ("name", "github", "fixture/x", None),
    ("key", "GITHUB_TOKEN", "A=B", None),
    ("matcher", "Edit|Write", "Bash(rm:*)", "other"),
    ("plugin_id", "egm@egm", "egm:x@egm", None),
    ("tool_ref", "mcp:serena", "serena", None),
])
def test_values_identifier(kind, good, bad, fallback):
    assert values.identifier(kind, good) == good
    assert values.identifier(kind, bad) == fallback
    assert values.identifier(kind, good + "\n") == fallback
    assert values.identifier(kind, None) == fallback


@pytest.mark.parametrize("value, form", [
    ("", "empty"),
    ("${TOKEN}", "reference"),
    ("${TOKEN:-}", "reference"),
    ("${TOKEN:-x}", "literal"),
    ("a${TOKEN:-x}b", "literal"),
    ("Bearer ${TOKEN}", "interpolated"),
    ("Bearer ${TOKEN:-}", "interpolated"),
    ("plain text", "literal"),
    ("${1BAD}", "literal"),
    (5, "literal"),
    (None, "literal"),
])
def test_values_value_form(value, form):
    assert values.value_form(value) == form


@pytest.mark.parametrize("name, sensitive", [
    ("GITHUB_TOKEN", True), ("apiKey", True), ("X-Auth-Token", True), ("Authorization", True),
    ("Proxy-Authorization", True), ("Cookie", True), ("db.password", True), ("APIKEY", True),
    ("AUTHOR", False), ("KEYCLOAK_REALM", False), ("KEYBOARD", False), ("NODE_ENV", False),
])
def test_values_is_sensitive_name(name, sensitive):
    assert values.is_sensitive_name(name) is sensitive


def test_values_url_sensitive_name():
    assert values.url_sensitive_name("https://h/?access_token=x") is True
    assert values.url_sensitive_name("https://h/?page=2") is False
    assert values.url_sensitive_name("https://h/") is False


def test_values_hints():
    assert values.value_hint("postgresql://u:p@h/db") == "url-userinfo"
    assert values.value_hint("https://h/db") is None
    assert values.value_hint(5) is None
    assert values.args_hint({"command": "npx", "args": ["pkg", "postgresql://u:p@h/db"]}) == "url-userinfo"
    assert values.args_hint({"command": "npx", "args": ["pkg", "https://h/db"]}) is None
    assert values.args_hint({"command": "npx"}) is None


@pytest.mark.parametrize("server, expected", [
    ({"command": "npx", "args": ["-y", "@playwright/mcp@1.2"]},
     {"launcher": "npx", "package": "@playwright/mcp", "command_name": None}),
    ({"command": "npx", "args": ["-p", "pkg-a", "tool"]},
     {"launcher": "npx", "package": "pkg-a", "command_name": None}),
    ({"command": "uvx", "args": ["pkg==1.0"]},
     {"launcher": "uvx", "package": "pkg", "command_name": None}),
    ({"command": "uvx", "args": ["--from", "pkg-b", "cmd"]},
     {"launcher": "uvx", "package": "pkg-b", "command_name": None}),
    ({"command": "pnpm", "args": ["dlx", "some-pkg"]},
     {"launcher": "pnpm-dlx", "package": "some-pkg", "command_name": None}),
    ({"command": "/usr/local/bin/serena", "args": ["start-mcp-server"]},
     {"launcher": "other", "package": None, "command_name": "serena"}),
    ({"command": "docker", "args": ["run", "-i", "--rm", "-e", "TOKEN=x", "image"]},
     {"launcher": "docker", "package": None, "command_name": None}),
    ({"command": "npx", "args": ["AKIAIOSFODNN7EXAMPLE"]},
     {"launcher": "npx", "package": None, "command_name": None}),
    ({"command": "npx", "args": ["ghp_AbCdEf0123456789"]},
     {"launcher": "npx", "package": None, "command_name": None}),
])
def test_values_mcp_identity_local(server, expected):
    identity = values.mcp_identity(server)
    assert set(identity) == {"transport", "launcher", "package", "command_name", "url_host"}
    assert identity == {"transport": "stdio", "url_host": None, **expected}


@pytest.mark.parametrize("url, host", [
    ("https://Api.Example.test:8443/x?y", "api.example.test"),
    ("https://u:p@h/", None),
    ("https://${HOST}/", None),
])
def test_values_mcp_identity_url_host(url, host):
    identity = values.mcp_identity({"type": "http", "url": url})
    assert identity == {"transport": "http", "launcher": None, "package": None,
                        "command_name": None, "url_host": host}


@pytest.mark.parametrize("server, transport", [
    ({"command": "x"}, "stdio"),
    ({"type": "stdio", "command": "x"}, "stdio"),
    ({"url": "https://h/"}, "other"),
    ({"type": "http", "url": "https://h/"}, "http"),
    ({"type": "x", "url": "https://h/"}, "other"),
])
def test_values_mcp_transport(server, transport):
    assert values.mcp_transport(server) == transport


@pytest.mark.parametrize("rule, verdict", [
    ("Read(./a)", "keep"), ("Read", "keep"), ("WebFetch(domain:localhost:3000)", "keep"),
    ("Read(a\nb)", "invalid"), ("WebFetch(x)", "invalid"), (5, "invalid"),
    ("Bash(curl -H x)", "ignore"),
])
def test_values_classify_permission(rule, verdict):
    assert values.classify_permission(rule) == verdict


KINDS = {"event": "EVENT", "name": "NAME", "key": "NAME", "matcher": "MATCHER",
         "plugin_id": "PLUGIN_ID", "tool_ref": "TOOL_REF"}


@given(kind=st.sampled_from(sorted(KINDS)), s=st.text(max_size=40))
def test_values_property_identifier(kind, s):
    fallback = "other" if kind == "matcher" else None
    pattern = getattr(values, KINDS[kind])
    assert values.identifier(kind, s) == (s if re.fullmatch(pattern, s) else fallback)


ARG = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=30)
SERVER = st.fixed_dictionaries({}, optional={
    "command": st.one_of(st.sampled_from(["npx", "uvx", "bunx", "pnpm", "docker", "/bin/serena"]), ARG),
    "args": st.lists(st.one_of(st.sampled_from(["-y", "-p", "--package", "--from", "dlx"]), ARG),
                     max_size=5),
    "type": st.one_of(st.sampled_from(sorted(TRANSPORTS)), ARG),
    "url": st.one_of(st.just("https://Api.Example.test:8443/x"), ARG.map(lambda s: "https://" + s)),
})


@given(server=SERVER)
def test_values_property_identity_grammar(server):
    identity = values.mcp_identity(server)
    assert identity["transport"] in TRANSPORTS
    assert identity["launcher"] in LAUNCHERS
    package = identity["package"]
    assert package is None or (len(package) <= 214
                               and (re.fullmatch(NPM, package) or re.fullmatch(PEP503, package)))
    assert identity["command_name"] is None or re.fullmatch(COMMAND, identity["command_name"])
    assert identity["url_host"] is None or re.fullmatch(HOST, identity["url_host"])


SECRET = st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=8,
                 max_size=40).filter(lambda s: re.search("[A-Z]", s) and re.search("[0-9]", s))


@given(env=SECRET, header=SECRET, arg=SECRET, url=SECRET,
       launcher=st.sampled_from(["npx", "uvx", "bunx", "serena"]))
def test_values_property_no_value_leaks(env, header, arg, url, launcher):
    server = {"command": launcher, "args": [arg], "env": {"API_TOKEN": env},
              "headers": {"Authorization": header}, "url": url}
    entries = [{"key": values.identifier("key", k), "form": values.value_form(v),
                "sensitive_name": values.is_sensitive_name(k), "value_hint": values.value_hint(v)}
               for k, v in [("API_TOKEN", env), ("Authorization", header)]]
    entries.append({"key": "url", "form": values.value_form(url),
                    "sensitive_name": values.url_sensitive_name(url),
                    "value_hint": values.value_hint(url)})
    out = json.dumps([values.mcp_identity(server), values.mcp_transport(server),
                      values.args_hint(server), entries])
    for secret in (env, header, arg, url):
        assert secret not in out
