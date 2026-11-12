"""Selection signals (spec 12, section 7)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import PurePosixPath

from peo.discovery.docs import LIST_ITEM, docs_dir, readmes

AUTH_PACKAGES = ("keycloak*", "laravel/socialite", "laravel/passport", "laravel/sanctum",
                 "next-auth", "@nestjs/passport", "passport", "openid-client", "authlib",
                 "django-allauth")
RICH_RENDERING = ("three", "gsap", "pixi.js", "@react-three/fiber")
TERMS = {"auth": ("Keycloak", "OIDC", "SSO"),
         "public_surface": ("formulaire", "contact", "API publique", "public API", "contact form")}
CODE_PATTERNS = ("<form", "FormRequest", "@Post(")
RENDER_EXTENSIONS = (".vue", ".tsx", ".jsx")
DESIGN_TERMS = ("border-radius", "couleur", "color", "token", "font", "typographie", "spacing")
NAMES = ("auth", "public_surface", "frontend_heavy", "design_rules_in_instructions")

Reader = Callable[[str], str | None]


def _yes(confidence: str, evidence: str) -> dict:
    return {"value": True, "confidence": confidence, "evidence": evidence}


def _matches(name: str, pattern: str) -> bool:
    return name.startswith(pattern[:-1]) if pattern.endswith("*") else name == pattern


def _dependency(manifests, patterns) -> dict | None:
    for manifest in sorted(manifests, key=lambda m: m.path):
        names = sorted(n for n in manifest.deps if any(_matches(n, p) for p in patterns))
        if names:
            return _yes("fact", f"{manifest.path}: {', '.join(names)}")
    return None


def _mention(files: list[str], read: Reader, terms) -> dict | None:
    regex = re.compile("|".join(rf"(?<!\w){re.escape(t)}(?!\w)" for t in terms), re.I)
    for rel in readmes(files) + docs_dir(files):
        for number, line in enumerate((read(rel) or "").splitlines(), 1):
            match = regex.search(line)
            if match:
                return _yes("likely", f"{rel}:{number} mentions {match.group(0)}")
    return None


def _code(code_files: list[str], read: Reader) -> dict | None:
    for rel in code_files:
        for number, line in enumerate((read(rel) or "").splitlines(), 1):
            pattern = next((p for p in CODE_PATTERNS if p in line), None)
            if pattern:
                return _yes("fact", f"{rel}:{number} contains {pattern}")
    return None


def _render_share(code_files: list[str], loc: Callable[[str], int]) -> dict | None:
    total = sum(loc(f) for f in code_files)
    render = sum(loc(f) for f in code_files if f.endswith(RENDER_EXTENSIONS))
    if total and render / total > 0.4:
        share = round(100 * render / total)
        return _yes("fact", f"{share}% of code lines in .vue/.tsx/.jsx")
    return None


def _design_rules(files: list[str], read: Reader) -> dict | None:
    for rel in ("CLAUDE.md", "AGENTS.md"):
        if rel not in files:
            continue
        rules = [line for line in (read(rel) or "").splitlines()
                 if LIST_ITEM.match(line) and any(t in line.lower() for t in DESIGN_TERMS)]
        if len(rules) >= 3:
            return _yes("fact", f"{rel}: {len(rules)} design rules")
    return None


def signals(files: list[str], manifests, read: Reader, code_files: list[str],
            loc: Callable[[str], int]) -> dict:
    """The four signals, always present; dependency or code before a mention in the docs."""
    found = {
        "auth": _dependency(manifests, AUTH_PACKAGES) or _mention(files, read, TERMS["auth"]),
        "public_surface": _code(code_files, read) or _mention(files, read, TERMS["public_surface"]),
        "frontend_heavy": _dependency(manifests, RICH_RENDERING) or _render_share(code_files, loc),
        "design_rules_in_instructions": _design_rules(files, read),
    }
    absent = {"value": False, "confidence": "fact"}
    return {name: found[name] or absent | {"evidence": f"no {name} indicator"} for name in NAMES}


def code_files(files: list[str], extensions: list[str]) -> list[str]:
    """Tracked code files: extension in the language table (spec 12 §2.2 rule 7), sorted."""
    return sorted(f for f in files if PurePosixPath(f).suffix.lstrip(".") in extensions)
