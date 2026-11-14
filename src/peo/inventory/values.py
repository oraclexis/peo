"""Pure NF14 rules of the Inventory; see spec 14 §3.3.

No input or output, no logging, and no exception message ever carries a value.
"""

import posixpath
import re
import urllib.parse

# Patterns of the $defs of inventory.schema.json (a test checks they are equal).
EVENT = "^[A-Za-z]{1,64}$"
NAME = "^[A-Za-z_][A-Za-z0-9_.-]{0,127}$"
MATCHER = "^[A-Za-z0-9_|*.()^$-]{0,200}$"
PLUGIN_ID = "^[A-Za-z0-9._-]{1,128}(@[A-Za-z0-9._-]{1,128})?$"
TOOL_REF = ("^(claude-plugin|mcp|cli|vendored-skill|framework|ci-check|rule|peo)"
            ":[a-z0-9][a-z0-9._-]*$")
LOCATION = ("^(env|mcp#([0-9]+/)?[0-9]+\\.(env|headers|url)"
            "|hook:[A-Za-z]{1,64}#[0-9]+\\.[0-9]+\\.(url|headers))$")
RULE = "^((Read|Edit|Write)(\\(.*\\))?|WebFetch(\\(domain:.*\\))?)$"
VERSION = "^[0-9]+\\.[0-9]+\\.[0-9]+$"

_KINDS = {"event": EVENT, "name": NAME, "key": NAME, "matcher": MATCHER,
          "plugin_id": PLUGIN_ID, "tool_ref": TOOL_REF}
_FALLBACK = {"matcher": "other"}

SENSITIVE_TOKENS = frozenset({"token", "secret", "key", "apikey", "password", "passwd", "pwd",
                              "auth", "authorization", "cookie", "credential", "credentials"})
TRANSPORTS = frozenset({"stdio", "http", "sse", "ws", "streamable-http"})
PACKAGE_LAUNCHERS = frozenset({"npx", "uvx", "bunx", "pnpm-dlx"})
_PACKAGE_OPTIONS = {"npx": ("--package", "-p"), "uvx": ("--from",)}

_VAR = r"[A-Za-z_][A-Za-z0-9_]*"
_REFERENCE = re.compile(r"\$\{" + _VAR + r"(:-)?\}")
_DEFAULT_START = re.compile(r"\$\{" + _VAR + r":-")
# Scheme bounded to 32 characters: an unbounded one is quadratic on a 1 MiB run of letters.
_USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.-]{0,31}://[^/\s:@]*:[^/\s@]*@")
_CAMEL = re.compile(r"([a-z])([A-Z])")
_NPM = re.compile(r"(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*")
_PEP503 = re.compile(r"[a-z0-9]([a-z0-9._-]*[a-z0-9])?")
_COMMAND = re.compile(r"[a-z0-9][a-z0-9._-]*")
_HOST = re.compile(r"[a-z0-9.-]{1,214}")
_VERSION_CUT = re.compile(r"==|>=|<=|~=|!=|<|>|\[")


def identifier(kind: str, s: object) -> str | None:
    """`s` if it matches the whole grammar of `kind`, else the fallback (None, or "other")."""
    if isinstance(s, str) and re.fullmatch(_KINDS[kind], s):
        return s
    return _FALLBACK.get(kind)


def _has_default(value: str) -> bool:
    """Contains ${NAME:-x}, x non-empty; linear (a [^}]+ regex is quadratic without a `}`)."""
    last = value.rfind("}")
    return any(m.end() < last and value[m.end()] != "}" for m in _DEFAULT_START.finditer(value))


def value_form(value: object) -> str:
    if not isinstance(value, str):
        return "literal"
    if value == "":
        return "empty"
    if _REFERENCE.fullmatch(value):
        return "reference"
    if _has_default(value):
        return "literal"
    return "interpolated" if _REFERENCE.search(value) else "literal"


def is_sensitive_name(name: object) -> bool:
    if not isinstance(name, str):
        return False
    tokens = re.split(r"[_.\-]", _CAMEL.sub(r"\1_\2", name))
    return any(t.lower() in SENSITIVE_TOKENS for t in tokens)


def url_sensitive_name(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        query = urllib.parse.urlsplit(url).query
    except ValueError:
        return False
    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    return any(is_sensitive_name(k) for k, _ in pairs)


def value_hint(value: object) -> str | None:
    return "url-userinfo" if isinstance(value, str) and _USERINFO.search(value) else None


def args_hint(server: dict) -> str | None:
    args = server.get("args")
    if isinstance(args, list) and any(value_hint(a) for a in args):
        return "url-userinfo"
    return None


def mcp_transport(server: dict) -> str:
    if "type" in server:
        kind = server["type"]
        return kind if isinstance(kind, str) and kind in TRANSPORTS else "other"
    return "other" if "url" in server else "stdio"


def _package(launcher: str, args: list[str]) -> str | None:
    options = _PACKAGE_OPTIONS.get(launcher, ())
    value = None
    for i, arg in enumerate(args):
        if arg in options:
            value = args[i + 1] if i + 1 < len(args) else None
            break
        prefix = next((o + "=" for o in options if arg.startswith(o + "=")), None)
        if prefix:
            value = arg[len(prefix):]
            break
    if value is None:
        value = next((a for a in args if not a.startswith("-")), None)
    if value is None:
        return None
    at = value.find("@", 1 if value.startswith("@") else 0)
    if at > 0:
        value = value[:at]
    cut = _VERSION_CUT.search(value)
    if cut:
        value = value[:cut.start()]
    if len(value) <= 214 and (_NPM.fullmatch(value) or _PEP503.fullmatch(value)):
        return value
    return None


def _url_host(url: str) -> str | None:
    if "${" in url:
        return None
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
        if parts.username is not None or parts.password is not None or "@" in parts.netloc:
            return None
    except ValueError:
        return None
    return host if host and _HOST.fullmatch(host) else None


def mcp_identity(server: dict) -> dict:
    """In-memory projection of an MCP server, passed to `identify`; never emitted."""
    launcher = package = command_name = url_host = None
    command = server.get("command")
    args = server.get("args")
    args = [a for a in args if isinstance(a, str)] if isinstance(args, list) else []
    if isinstance(command, str):
        base = posixpath.basename(command)
        if base in ("npx", "uvx", "bunx", "docker"):
            launcher = base
        elif base == "pnpm" and args[:1] == ["dlx"]:
            launcher, args = "pnpm-dlx", args[1:]
        else:
            launcher = "other"
        if launcher in PACKAGE_LAUNCHERS:
            package = _package(launcher, args)
        elif launcher == "other" and "${" not in base and _COMMAND.fullmatch(base):
            command_name = base
    url = server.get("url")
    if isinstance(url, str):
        url_host = _url_host(url)
    return {"transport": mcp_transport(server), "launcher": launcher, "package": package,
            "command_name": command_name, "url_host": url_host}


def classify_permission(rule: object) -> str:
    """keep (emitted whole), ignore (read, never emitted) or invalid (family invalid)."""
    if not isinstance(rule, str):
        return "invalid"
    if rule.split("(", 1)[0] not in ("Read", "Edit", "Write", "WebFetch"):
        return "ignore"
    return "keep" if re.fullmatch(RULE, rule) else "invalid"
