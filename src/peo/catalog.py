"""Catalog loader and validator (spec 13). Standard library only.

Not imported by gate.py or context.py.

`validate(path)` reads a catalog folder and returns every problem in one `Report`; it never writes,
never runs a process and never uses the network. Messages hold paths relative to the catalog only.
"""

import re
import tomllib
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any, NamedTuple

from peo import expr
from peo.validate import load_schema
from peo.validate import validate as validate_schema

MAX_BYTES = 1024 * 1024
CAPABILITY_ID = re.compile(r"^[a-z]+(\.[a-z0-9-]+)+$")
ANSWER_READ = re.compile(r"^answers(?:\['([^']*)'\]|\.([A-Za-z_][A-Za-z0-9_]*))")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STRENGTHS = ("hard", "soft")
# Bidirectional controls that can hide text (13 section 1): U+061C, U+200E, U+200F, U+202A-U+202E,
# U+2066-U+2069.
BIDI_CONTROLS = frozenset({0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)})
QUESTION_KINDS = ("confirm", "choice", "text")
MAX_OPTIONS = 4
EXPRESSION_KEYS = ("when", "ask_if", "recommend_if", "for_each")
# Fields of peo.toml the CLI reads itself (spec 13 section 7.1): a question may feed them
# without any expression reading them.
PEO_TOML_CONSUMED = frozenset({"project.mission", "project.languages.artifacts", "commands.verify",
                               "gates.mode", "backbone.id"})


def _bidi_in(node: Any) -> set[int]:
    """Bidirectional controls in any decoded string of a parsed document, keys included."""
    if isinstance(node, str):
        return {ord(c) for c in node if ord(c) in BIDI_CONTROLS}
    if isinstance(node, list):
        return set().union(*map(_bidi_in, node)) if node else set()
    if isinstance(node, dict):
        return set().union(*(_bidi_in(k) | _bidi_in(v) for k, v in node.items())) if node else set()
    return set()


@cache
def _entry_schema():
    return load_schema("tool-entry")


class CatalogNotFound(Exception):
    """The catalog folder does not exist (exit code 2, not a catalog error)."""


class CatalogError(NamedTuple):
    file: str        # path relative to the catalog folder
    location: str    # JSON pointer, or empty
    code: str        # short and stable
    message: str     # one line, English


@dataclass
class Report:
    root: str
    errors: list[CatalogError] = field(default_factory=list)
    warnings: list[CatalogError] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


class _Run:
    def __init__(self, root: Path, today: date):
        self.root, self.today = root, today
        self.errors: list[CatalogError] = []
        self.warnings: list[CatalogError] = []
        self.answers: set[str] = set()   # answer ids read by any expression (rule S-5)

    def error(self, file: str, location: str, code: str, message: str) -> None:
        self.errors.append(CatalogError(file, location, code, message))

    def toml(self, rel: str) -> dict | None:
        """Parse one file: bounded read, strict UTF-8, TOML. None (and an error) when it fails."""
        path = self.root / rel
        if path.stat().st_size > MAX_BYTES:
            self.error(rel, "", "too-large", "file is larger than 1 MiB")
            return None
        with path.open("rb") as f:
            raw = f.read(MAX_BYTES + 1)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            self.error(rel, "", "encoding", "file is not valid UTF-8")
            return None
        hidden = sorted({ord(c) for c in text if ord(c) in BIDI_CONTROLS})
        if hidden:      # before tomllib, so the cause is named even when the TOML is also invalid
            names = ", ".join(f"U+{cp:04X}" for cp in hidden)
            self.error(rel, "", "bidi", f"contains bidirectional control characters ({names})")
            return None
        try:
            doc = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            self.error(rel, "", "toml", f"invalid TOML: {exc}")
            return None
        decoded = sorted(_bidi_in(doc))     # a \u202E escape only exists after decoding
        if decoded:
            names = ", ".join(f"U+{cp:04X}" for cp in decoded)
            self.error(rel, "", "bidi", f"contains bidirectional control characters ({names})")
            return None
        return doc

    def tables(self, rel: str, where: str, value: Any) -> list[dict]:
        """The tables of an array-of-tables key; anything else is an error, not a crash."""
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            self.error(rel, where, "shape", "expected an array of tables")
            return []
        return value

    def expression(self, rel: str, location: str, text: Any, it: bool = False) -> None:
        """Parse one `when` expression; the paths it reads are kept for rule S-5."""
        if not isinstance(text, str):
            self.error(rel, location, "expression", "an expression must be a string")
            return
        try:
            for path in expr.reads(expr.parse(text, it=it)):
                m = ANSWER_READ.match(path)
                if m:
                    self.answers.add(m.group(1) or m.group(2))
        except expr.ExprError as exc:
            self.error(rel, location, "expression", f"invalid expression {text[:200]!r}: {exc}")

    def files(self, folder: Path) -> list[Path]:
        """Regular files and folders below `folder`, sorted; symbolic links are ignored."""
        return sorted(p for p in folder.iterdir() if not p.is_symlink())

    def table_file(self, rel: str) -> dict | None:
        if not (self.root / rel).is_file() or (self.root / rel).is_symlink():
            self.error(rel, "", "missing", f"missing {rel}")
            return None
        return self.toml(rel)

    def capabilities(self) -> dict[str, bool]:
        doc = self.table_file("capabilities.toml")
        found: dict[str, bool] = {}
        caps = self.tables("capabilities.toml", "/capabilities", (doc or {}).get("capabilities"))
        for i, cap in enumerate(caps):
            where = f"/capabilities/{i}"
            cid = cap.get("id")
            if not isinstance(cid, str) or not CAPABILITY_ID.match(cid):
                self.error("capabilities.toml", where, "capability",
                           f"invalid capability id {cid!r}")
            elif cid in found:
                self.error("capabilities.toml", where, "duplicate",
                           f"duplicate capability {cid!r}")
            elif not isinstance(cap.get("exclusive", False), bool):
                self.error("capabilities.toml", where, "capability",
                           f"capability {cid!r}: exclusive must be true or false")
            else:
                found[cid] = cap.get("exclusive", False)
        return found

    def rules(self, capabilities: dict[str, bool]) -> int:
        doc = self.table_file("requirements.toml")
        seen: set[str] = set()
        rules = self.tables("requirements.toml", "/rules", (doc or {}).get("rules"))
        for i, rule in enumerate(rules):
            where = f"/rules/{i}"
            rid = rule.get("id")
            if not isinstance(rid, str):
                self.error("requirements.toml", where, "rule", "rule without a string id")
            elif rid in seen:
                self.error("requirements.toml", where, "duplicate", f"duplicate rule id {rid!r}")
            seen.add(str(rid))
            for key in ("when", "for_each"):
                if key in rule:
                    self.expression("requirements.toml", f"{where}/{key}", rule[key],
                                    it=key == "when" and "for_each" in rule)
            need = rule.get("require")
            if not isinstance(need, dict):
                self.error("requirements.toml", where, "rule", f"rule {rid!r} has no require table")
                continue
            cap = need.get("capability")
            if not isinstance(cap, str) or cap not in capabilities:
                self.error("requirements.toml", where, "unknown-capability",
                           f"unknown capability {need.get('capability')!r}")
            if not isinstance(need.get("strength"), str) or need["strength"] not in STRENGTHS:
                self.error("requirements.toml", where, "rule",
                           f"strength {need.get('strength')!r} is not hard or soft")
        return len(rules)

    def date_of(self, rel: str, location: str, text: Any) -> date | None:
        try:
            if isinstance(text, str) and ISO_DATE.match(text):
                return date.fromisoformat(text)
        except ValueError:
            pass
        self.error(rel, location, "date", f"{text!r} is not a date in YYYY-MM-DD form")
        return None

    def entry(self, rel: str, kind_dir: str, name: str, doc: dict,
              capabilities: dict[str, bool]) -> bool:
        """Check one entry; True when it passed the schema, so its structure can be trusted."""
        schema_errors = validate_schema(doc, _entry_schema())
        for e in schema_errors:
            self.error(rel, e.path, "schema", e.message)
        if schema_errors:
            return False
        if doc["kind"] != kind_dir:
            self.error(rel, "/kind", "path",
                       f"kind {doc['kind']!r} does not match its folder {kind_dir!r}")
        if doc["id"] != name:
            self.error(rel, "/id", "path", f"id {doc['id']!r} does not match file name {name!r}")
        for cap in doc["capabilities"].get("provides", []):
            if cap not in capabilities:
                self.error(rel, "/capabilities/provides", "unknown-capability",
                           f"unknown capability {cap!r}")
        when = doc.get("selection", {}).get("when", {})
        for key in ("any", "all", "not"):
            for i, text in enumerate(when.get(key, [])):
                self.expression(rel, f"/selection/when/{key}/{i}", text)
        notes, checked = doc["notes"], doc["source"].get("checked")
        evaluated = self.date_of(rel, "/notes/evaluated", notes.get("evaluated"))
        review_by = self.date_of(rel, "/notes/review_by", notes.get("review_by"))
        if checked is not None:
            self.date_of(rel, "/source/checked", checked)
        if evaluated and review_by and review_by < evaluated:
            self.error(rel, "/notes/review_by", "date", "review_by is before evaluated")
        if review_by and review_by < self.today:
            self.warnings.append(CatalogError(rel, "/notes/review_by", "W_REVIEW_EXPIRED",
                                              f"review_by {review_by} is in the past"))
        return True

    def references(self, rel: str, doc: dict, known: set[str]) -> None:
        refs = [(f"/relations/{k}", r) for k in ("requires", "conflicts", "overlaps")
                for r in doc.get("relations", {}).get(k, [])]
        refs += [("/prerequisites", p["fix"]) for p in doc.get("prerequisites", []) if "fix" in p]
        for where, ref in refs:
            if ref not in known:
                self.error(rel, where, "unknown-entry", f"unknown entry {ref!r}")

    def opaque(self) -> int:
        """Backbone and recipe tables keep their own format; only their expressions are checked."""
        count = 0
        for folder in ("backbones", "recipes"):
            base = self.root / folder
            if not base.is_dir() or base.is_symlink():
                continue
            for path in (p for p in self.files(base) if p.is_file() and p.suffix == ".toml"):
                rel = path.relative_to(self.root).as_posix()
                doc = self.toml(rel)
                if doc is not None:
                    count += 1
                    self.walk(rel, "", doc)
        return count

    def walk(self, rel: str, where: str, node: Any) -> None:
        if isinstance(node, list):
            for i, item in enumerate(node):
                self.walk(rel, f"{where}/{i}", item)
        elif isinstance(node, dict):
            for key, value in node.items():
                here = f"{where}/{key}"
                if key in EXPRESSION_KEYS:
                    texts = value if isinstance(value, list) else [value]
                    for i, text in enumerate(texts):
                        self.expression(rel, here if not isinstance(value, list) else f"{here}/{i}",
                                        text, it=key == "when" and "for_each" in node)
                else:
                    self.walk(rel, here, value)

    def question_shape(self, where: str, q: dict, options: list, seen: set[str]) -> None:
        def bad(message: str) -> None:
            self.error("questions.toml", where, "question", message)

        qid = q.get("id")
        if not isinstance(qid, str):
            bad("question without a string id")
        elif qid in seen:
            bad(f"duplicate question id {qid!r}")
        seen.add(str(qid))
        rnd = q.get("round")
        if not isinstance(rnd, int) or isinstance(rnd, bool) or rnd < 1:
            bad(f"question {qid!r}: round must be an integer >= 1")
        if q.get("kind") not in QUESTION_KINDS:
            bad(f"question {qid!r}: kind must be one of {', '.join(QUESTION_KINDS)}")
        if len(options) > MAX_OPTIONS:
            bad(f"question {qid!r}: at most {MAX_OPTIONS} options")

    def questions(self) -> int:
        path = self.root / "questions.toml"
        if not path.is_file() or path.is_symlink():
            return 0
        doc = self.toml("questions.toml") or {}
        found = self.tables("questions.toml", "/questions", doc.get("questions"))
        seen: set[str] = set()
        for i, question in enumerate(found):
            where = f"/questions/{i}"
            options = self.tables("questions.toml", f"{where}/options", question.get("options"))
            self.question_shape(where, question, options, seen)
            if "ask_if" in question:
                self.expression("questions.toml", f"{where}/ask_if", question["ask_if"])
            for j, option in enumerate(options):
                if "recommend_if" in option:
                    self.expression("questions.toml", f"{where}/options/{j}/recommend_if",
                                    option["recommend_if"])
        for i, question in enumerate(found):          # S-5, once every expression has been read
            feeds = question.get("feeds")
            qid = question.get("id")
            if not (isinstance(feeds, list) and feeds and all(isinstance(f, str) for f in feeds)):
                self.error("questions.toml", f"/questions/{i}/feeds", "question",
                           f"question {qid!r}: feeds must be a non-empty list of strings")
                continue
            for feed in feeds:
                key = feed[len("answers['"):-2] if feed.startswith("answers['") else feed
                if feed not in PEO_TOML_CONSUMED and key not in self.answers:
                    self.error("questions.toml", f"/questions/{i}/feeds", "unconsumed",
                               f"question {qid!r} feeds {feed!r}, which nothing reads")
        return len(found)

    def entries(self, capabilities: dict[str, bool]) -> int:
        tools = self.root / "tools"
        if not tools.is_dir() or tools.is_symlink():
            self.error("tools", "", "missing", "missing tools/ folder")
            return 0
        loaded: list[tuple[str, dict]] = []     # entries that passed the schema
        count = 0
        known: set[str] = set()
        declared: dict[str, list[str]] = {}     # reference -> files that declare it
        for kind_dir in (p for p in self.files(tools) if p.is_dir()):
            for path in (p for p in self.files(kind_dir) if p.is_file() and p.suffix == ".toml"):
                rel = path.relative_to(self.root).as_posix()
                known.add(f"{kind_dir.name}:{path.stem}")
                doc = self.toml(rel)
                if doc is None:
                    continue
                count += 1
                if self.entry(rel, kind_dir.name, path.stem, doc, capabilities):
                    loaded.append((rel, doc))
                declared.setdefault(f"{doc.get('kind')}:{doc.get('id')}", []).append(rel)
        for key, files in declared.items():
            if len(files) > 1:      # reject every file of the pair, not only the later one
                for rel in files:
                    self.error(rel, "/id", "duplicate", f"duplicate entry {key!r}")
        for rel, doc in loaded:
            self.references(rel, doc, known)
        return count


def validate(path: str | Path, today: date | None = None) -> Report:
    """Check the catalog folder at `path`; `today` is injectable so the output is reproducible."""
    root = Path(path)
    if not root.is_dir():
        raise CatalogNotFound(f"catalog folder not found: {root.name}")
    run = _Run(root, today or date.today())
    capabilities = run.capabilities()
    rules = run.rules(capabilities)
    entries = run.entries(capabilities)
    opaque = run.opaque()
    questions = run.questions()
    order = lambda e: (e.file, e.location, e.message)  # noqa: E731
    return Report(root=root.resolve().name, errors=sorted(run.errors, key=order),
                  warnings=sorted(run.warnings, key=order),
                  counts={"capabilities": len(capabilities), "entries": entries, "opaque": opaque,
                          "questions": questions, "rules": rules})
