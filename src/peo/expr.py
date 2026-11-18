"""Parser of the `when` language (spec 13, section 3). Standard library only; no eval.

`parse` checks an expression and returns a tree; `reads` lists the external paths it reads.
Evaluation belongs to the Selector (R4b), not here.
"""

import re

ROOTS = ("profile", "answers", "selection")
OPERATORS = ("==", "!=", ">=", "<=", ">", "<")
WORD_OPERATORS = ("in", "contains", "matches")
MAX_DEPTH = 50
MAX_PATTERN = 200
_TOKEN = re.compile(r"""
    (?P<space>\s+)
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<string>'[^']*'|"[^"]*")
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>==|!=|>=|<=|>|<)
  | (?P<punct>[()\[\].,])
""", re.VERBOSE)


class ExprError(ValueError):
    """The text is not an expression of the language; `position` is an index into it."""

    def __init__(self, message: str, position: int):
        super().__init__(f"{message} (at {position})")
        self.message = message
        self.position = position


def _tokens(text: str) -> list[tuple[str, str, int]]:
    out, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            raise ExprError(f"unexpected character {text[pos]!r}", pos)
        if m.lastgroup != "space":
            out.append((m.lastgroup, m.group(), pos))
        pos = m.end()
    out.append(("end", "", len(text)))
    return out


class _Parser:
    def __init__(self, text: str):
        self.tokens = _tokens(text)
        self.i = 0
        self.depth = 0
        self.scopes: list[bool] = [False]       # True while inside any(path, expr): `it` is bound

    @property
    def tok(self) -> tuple[str, str, int]:
        return self.tokens[self.i]

    def error(self, message: str) -> ExprError:
        return ExprError(message, self.tok[2])

    def accept(self, kind: str, value: str | None = None) -> bool:
        if self.tok[0] == kind and (value is None or self.tok[1] == value):
            self.i += 1
            return True
        return False

    def expect(self, kind: str, value: str | None = None) -> None:
        if not self.accept(kind, value):
            raise self.error(f"expected {value or kind}")

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.error("expression nested too deeply")

    def parse(self) -> tuple:
        node = self.or_expr()
        if self.tok[0] != "end":
            raise self.error(f"unexpected {self.tok[1]!r}")
        return node

    def or_expr(self) -> tuple:
        self.enter()
        parts = [self.and_expr()]
        while self.accept("name", "or"):
            parts.append(self.and_expr())
        self.depth -= 1
        return parts[0] if len(parts) == 1 else ("or", tuple(parts))

    def and_expr(self) -> tuple:
        parts = [self.unary()]
        while self.accept("name", "and"):
            parts.append(self.unary())
        return parts[0] if len(parts) == 1 else ("and", tuple(parts))

    def unary(self) -> tuple:
        if self.accept("name", "not"):
            self.enter()
            node = ("not", self.unary())
            self.depth -= 1
            return node
        return self.comparison()

    def comparison(self) -> tuple:
        left = self.operand()
        kind, value, _ = self.tok
        if kind == "op" or (kind == "name" and value in WORD_OPERATORS):
            self.i += 1
            if value == "matches":
                return ("cmp", value, left, self.pattern())
            return ("cmp", value, left, self.operand())
        return left

    def pattern(self) -> tuple:
        kind, value, pos = self.tok
        if kind != "string":
            raise ExprError("matches needs a string literal", pos)
        self.i += 1
        regex = value[1:-1]
        if len(regex) > MAX_PATTERN:
            raise ExprError(f"pattern longer than {MAX_PATTERN} characters", pos)
        try:
            re.compile(regex)
        except re.error as e:
            raise ExprError(f"not a regular expression ({e})", pos) from None
        return ("str", regex)

    def operand(self) -> tuple:
        kind, value, pos = self.tok
        if kind == "number":
            self.i += 1
            return ("num", float(value) if "." in value else int(value))
        if kind == "string":
            self.i += 1
            return ("str", value[1:-1])
        if kind == "punct" and value == "(":
            self.i += 1
            self.enter()
            node = self.or_expr()
            self.depth -= 1
            self.expect("punct", ")")
            return node
        if kind == "punct" and value == "[":
            return self.list_()
        if kind == "name":
            if value in ("true", "false", "null"):
                self.i += 1
                return ("lit", {"true": True, "false": False, "null": None}[value])
            if value == "any":
                return self.any_()
            return self.path()
        raise self.error("expected an operand")

    def list_(self) -> tuple:
        self.expect("punct", "[")
        items = []
        if not self.accept("punct", "]"):
            items.append(self.operand())
            while self.accept("punct", ","):
                items.append(self.operand())
            self.expect("punct", "]")
        return ("list", tuple(items))

    def any_(self) -> tuple:
        self.i += 1
        self.expect("punct", "(")
        target = self.path()
        self.expect("punct", ",")
        self.scopes.append(True)
        self.enter()
        body = self.or_expr()
        self.depth -= 1
        self.scopes.pop()
        self.expect("punct", ")")
        return ("any", target, body)

    def path(self) -> tuple:
        kind, root, pos = self.tok
        if root not in ROOTS and not (root == "it" and self.scopes[-1]):
            raise ExprError(f"unknown root {root!r}", pos)
        self.i += 1
        segments = []
        while True:
            if self.accept("punct", "."):
                if self.tok[0] != "name":
                    raise self.error("expected a name after '.'")
                segments.append(self.tok[1])
                self.i += 1
            elif self.accept("punct", "["):
                if self.tok[0] != "string":
                    raise self.error("expected a string key")
                segments.append(("key", self.tok[1][1:-1]))
                self.i += 1
                self.expect("punct", "]")
            else:
                return ("path", root, tuple(segments))


def parse(text: str) -> tuple:
    """Return the tree of `text`, or raise ExprError. Nesting is capped, so no RecursionError."""
    try:
        return _Parser(text).parse()
    except RecursionError:                      # pragma: no cover - MAX_DEPTH stops it first
        raise ExprError("expression nested too deeply", 0) from None


def _format(node: tuple) -> str:
    _, root, segments = node
    out = root
    for seg in segments:
        out += f"['{seg[1]}']" if isinstance(seg, tuple) else f".{seg}"
    return out


def reads(node: tuple) -> frozenset[str]:
    """External paths read by an expression: `profile.a.b`, `answers['q.x']`. `it` is not one."""
    found: set[str] = set()

    def walk(n: tuple) -> None:
        kind = n[0]
        if kind == "path":
            if n[1] != "it":
                found.add(_format(n))
        elif kind in ("or", "and", "list"):
            for child in n[1]:
                walk(child)
        elif kind == "not":
            walk(n[1])
        elif kind == "cmp":
            walk(n[2])
            walk(n[3])
        elif kind == "any":
            walk(n[1])
            walk(n[2])

    walk(node)
    return frozenset(found)
