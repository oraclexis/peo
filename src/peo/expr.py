"""Parser and evaluator of the `when` language (spec 13, section 3). Standard library only; no eval.

`parse` checks an expression and returns a tree; `reads` lists the external paths it reads;
`evaluate` computes a tree over a context and never raises.
"""

import re
from functools import cache
from re import _constants, _parser  # private, bounded by a consistency test (research D2)

ROOTS = ("profile", "answers", "selection")
OPERATORS = ("==", "!=", ">=", "<=", ">", "<")
WORD_OPERATORS = ("in", "contains", "matches")
MAX_DEPTH = 50
MAX_PATTERN = 200
MAX_INPUT = 512          # longer strings never match (spec 13, section 3)
LARGE = 8                # a repeat of more than 8 occurrences is `large`
MAX_LARGE_REPEATS = 2
_TOKEN = re.compile(r"""
    (?P<space>\s+)
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<string>'[^']*'|"[^"]*")
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>==|!=|>=|<=|>|<)
  | (?P<punct>[()\[\].,])
""", re.VERBOSE)


_REPEATS = (_constants.MAX_REPEAT, _constants.MIN_REPEAT, _constants.POSSESSIVE_REPEAT)


def check_pattern(regex: str) -> str | None:
    """Why `regex` could backtrack without bound, or None (research D2).

    Refused: a back-reference or an assertion; a large repeat (`*`, `+`, `{n,}`, or more than 8
    occurrences) that holds another repeat of more than one occurrence or an alternative; more
    than two large repeats. Together with the 512-character input cap, this bounds the work of
    `fullmatch` without a timer. Assumes `regex` already compiles.
    """
    large = 0

    def walk(sub, inside: bool) -> str | None:
        nonlocal large
        for op, av in sub:
            if op in (_constants.GROUPREF, _constants.GROUPREF_EXISTS):
                return "back-reference"
            if op in (_constants.ASSERT, _constants.ASSERT_NOT):
                return "lookahead or lookbehind assertion"
            if op in _REPEATS:
                lo, hi, body = av
                is_large = hi > LARGE
                if inside and hi > 1:
                    return "nested repeat inside an unbounded or large repeat"
                large += is_large
                if large > MAX_LARGE_REPEATS:
                    return f"more than {MAX_LARGE_REPEATS} unbounded repeats"
                found = walk(body, inside or is_large)
            elif op is _constants.SUBPATTERN:
                found = walk(av[-1], inside)
            elif op is _constants.ATOMIC_GROUP:
                found = walk(av, inside)
            elif op is _constants.BRANCH:
                if inside:
                    return "alternative inside an unbounded or large repeat"
                found = next(filter(None, (walk(branch, inside) for branch in av[1])), None)
            else:
                continue
            if found:
                return found
        return None

    return walk(_parser.parse(regex), False)


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
    def __init__(self, text: str, it: bool = False):
        self.tokens = _tokens(text)
        self.i = 0
        self.depth = 0
        self.scopes: list[bool] = [it]   # True while `it` is bound: in any(...) or a for_each rule

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
        problem = check_pattern(regex)
        if problem:
            raise ExprError(f"pattern not allowed: {problem}", pos)
        return ("str", regex)

    def operand(self) -> tuple:
        kind, value, pos = self.tok
        if kind == "number":
            self.i += 1
            try:
                return ("num", float(value) if "." in value else int(value))
            except ValueError:      # an integer over Python's digit limit
                raise ExprError("number too large", pos) from None
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
        self.enter()
        items = []
        if not self.accept("punct", "]"):
            items.append(self.operand())
            while self.accept("punct", ","):
                items.append(self.operand())
            self.expect("punct", "]")
        self.depth -= 1
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


def parse(text: str, *, it: bool = False) -> tuple:
    """Return the tree of `text`, or raise ExprError. Nesting is capped, so no RecursionError.

    `it` allows the element name at the top level: the `when` of a rule that has `for_each`.
    """
    try:
        return _Parser(text, it).parse()
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


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _equal(a: object, b: object) -> bool:
    """Equality that keeps booleans apart from numbers: `true == 1` is false."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _order(op: str, a: object, b: object) -> bool:
    if not ((_is_number(a) and _is_number(b)) or (isinstance(a, str) and isinstance(b, str))):
        return False
    return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]    # type: ignore[operator]


def _within(item: object, collection: object) -> bool:
    if isinstance(collection, list):
        return any(_equal(item, element) for element in collection)
    return isinstance(item, str) and isinstance(collection, str) and item in collection


@cache
def _compiled(regex: str):
    return re.compile(regex)


def _lookup(node: tuple, ctx: dict) -> object:
    _, root, segments = node
    if root == "selection" and segments and segments[0] not in ("selected", "covered"):
        return None
    value: object = ctx.get(root)
    for seg in segments:
        key = seg[1] if isinstance(seg, tuple) else seg
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def evaluate(node: tuple, ctx: dict) -> object:
    """Value of a parsed tree over `ctx` (`profile`, `answers`, `selection`, `it`); never raises.

    A path that does not exist is `None`; a comparison that makes no sense is false.
    """
    kind = node[0]
    if kind == "path":
        return _lookup(node, ctx)
    if kind in ("str", "num", "lit"):
        return node[1]
    if kind == "list":
        return [evaluate(item, ctx) for item in node[1]]
    if kind == "not":
        return not holds(node[1], ctx)
    if kind == "and":
        return all(holds(part, ctx) for part in node[1])
    if kind == "or":
        return any(holds(part, ctx) for part in node[1])
    if kind == "any":
        items = evaluate(node[1], ctx)
        return isinstance(items, list) and any(
            holds(node[2], {**ctx, "it": item}) for item in items)
    _, op, left_node, right_node = node
    left, right = evaluate(left_node, ctx), evaluate(right_node, ctx)
    if op == "==":
        return _equal(left, right)
    if op == "!=":
        return not _equal(left, right)
    if op == "in":
        return _within(left, right)
    if op == "contains":
        return _within(right, left)
    if op == "matches":
        ok = isinstance(left, str) and len(left) <= MAX_INPUT
        return ok and _compiled(right).fullmatch(left) is not None
    return _order(op, left, right)


def holds(node: tuple, ctx: dict) -> bool:
    """`evaluate`, read as a condition: null, false, zero, empty are false."""
    return bool(evaluate(node, ctx))
