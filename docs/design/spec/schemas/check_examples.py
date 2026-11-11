import json, pathlib, sys, tomllib
from jsonschema import Draft202012Validator
D = pathlib.Path(sys.argv[1])
S = {p.name.replace(".schema.json", ""): json.loads(p.read_text()) for p in D.glob("*.schema.json")}
for s in S.values(): Draft202012Validator.check_schema(s)
def load(p):
    if p.suffix == ".toml": return [tomllib.loads(p.read_text())]
    if p.suffix == ".ndjson": return [json.loads(l) for l in p.read_text().splitlines() if l]
    return [json.loads(p.read_text())]
def schema_for(name):
    for k, key in [("profile","profile"),("selection","selection"),("plan","plan"),("lock","lock"),("history","history-event"),("peo.","peo-config"),("tool.","tool-entry")]:
        if name.startswith(k): return key
ok = True
for sub, expect_valid in [("examples", True), ("invalid", False)]:
    for p in sorted((D/sub).iterdir()):
        key = schema_for(p.name); v = Draft202012Validator(S[key])
        errs = [e for doc in load(p) for e in v.iter_errors(doc)]
        good = (not errs) == expect_valid
        ok &= good
        print(("PASS" if good else "FAIL"), sub, p.name, "->", key, "" if expect_valid else f"({len(errs)} error(s): {errs[0].message[:80] if errs else '-'})")
        if expect_valid and errs:
            for e in errs[:5]: print("   ", list(e.path), e.message[:150])
sys.exit(0 if ok else 1)
