"""Loader rules of spec 13 section 1 that are not one of A2.x on their own: files, references, dates, order."""

import os
from datetime import date

import pytest

from peo.catalog import CatalogNotFound, validate

from .conftest import CAPABILITIES, demo_tool

TODAY = date(2026, 11, 18)


def messages(report):
    return [f"{e.file} {e.location} {e.message}" for e in report.errors]


def test_all_errors_of_two_entries_come_in_one_run_sorted(make_catalog):
    bad = demo_tool().replace('data_path   = "none"\n', "").replace('fail_mode   = "open"\n', "")
    root = make_catalog(tools={"b": bad.replace('"demo"', '"b"'), "a": bad.replace('"demo"', '"a"')})
    report = validate(root, today=TODAY)
    assert {e.file for e in report.errors} == {"tools/cli/a.toml", "tools/cli/b.toml"}
    assert len(report.errors) >= 4
    assert report.errors == sorted(report.errors, key=lambda e: (e.file, e.location, e.message))


def test_a_declared_id_must_match_the_file_name_and_be_unique(make_catalog):
    root = make_catalog(tools={"a": demo_tool().replace('"demo"', '"a"'), "b": demo_tool().replace('"demo"', '"a"')})
    text = " | ".join(messages(validate(root, today=TODAY)))
    assert "tools/cli/b.toml" in text and "duplicate" in text and "does not match" in text


def test_the_folder_must_match_the_kind(make_catalog):
    root = make_catalog(extra={"tools/mcp/demo.toml": demo_tool()})
    assert any("tools/mcp/demo.toml" in m and "kind" in m for m in messages(validate(root, today=TODAY)))


@pytest.mark.parametrize("line, old, new", [
    ("requires", 'requires = []', 'requires = ["cli:ghost"]'),
    ("conflicts", "overlaps = []", 'overlaps = []\nconflicts = ["cli:ghost"]'),
])
def test_a_reference_to_an_absent_entry_is_rejected(make_catalog, line, old, new):
    report = validate(make_catalog(tools={"demo": demo_tool().replace(old, new)}), today=TODAY)
    assert any("cli:ghost" in m for m in messages(report)), line


def test_a_prerequisite_fix_to_an_absent_entry_is_rejected(make_catalog):
    extra = '\n[[prerequisites]]\ncheck = "bin:ghost"\nfix = "cli:ghost"\nblocking = true\n'
    text = demo_tool().replace("\n[surface]", extra + "\n[surface]")
    assert any("cli:ghost" in m for m in messages(validate(make_catalog(tools={"demo": text}), today=TODAY)))


def test_a_provided_capability_must_exist(make_catalog):
    text = demo_tool().replace('provides = ["nav.symbols"]', 'provides = ["nav.ghost"]')
    assert any("nav.ghost" in m for m in messages(validate(make_catalog(tools={"demo": text}), today=TODAY)))


def test_a_file_over_one_mebibyte_is_rejected_without_being_read_whole(make_catalog):
    root = make_catalog(extra={"tools/cli/big.toml": "# " + "x" * (1024 * 1024) + "\n"})
    assert any("tools/cli/big.toml" in m and "1 MiB" in m for m in messages(validate(root, today=TODAY)))


def test_a_symbolic_link_is_ignored(make_catalog, tmp_path):
    root = make_catalog()
    outside = tmp_path / "outside.toml"
    outside.write_text(demo_tool().replace('"demo"', '"linked"'))
    os.symlink(outside, root / "tools" / "cli" / "linked.toml")
    report = validate(root, today=TODAY)
    assert report.errors == [] and report.counts["entries"] == 1


def test_invalid_toml_names_the_file_and_the_line_and_the_other_files_still_load(make_catalog):
    root = make_catalog(tools={"demo": demo_tool(), "broken": 'id = "broken"\nkind = \n'})
    report = validate(root, today=TODAY)
    assert [e.file for e in report.errors] == ["tools/cli/broken.toml"]
    assert "line 2" in report.errors[0].location + report.errors[0].message
    assert report.counts["entries"] == 1


def test_invalid_utf8_is_rejected(make_catalog):
    root = make_catalog()
    (root / "tools" / "cli" / "demo.toml").write_bytes(b'id = "\xff"\n')
    assert any("UTF-8" in m for m in messages(validate(root, today=TODAY)))


def test_a_folder_without_tools_is_a_catalog_error_and_an_absent_folder_is_not_found(tmp_path):
    (tmp_path / "empty").mkdir()
    report = validate(tmp_path / "empty", today=TODAY)
    assert any("tools" in e.message for e in report.errors)
    with pytest.raises(CatalogNotFound):
        validate(tmp_path / "nowhere", today=TODAY)


def test_review_by_before_evaluated_is_an_error(make_catalog):
    text = demo_tool().replace('review_by = "2027-02-11"', 'review_by = "2026-10-01"')
    assert any("review_by" in m for m in messages(validate(make_catalog(tools={"demo": text}), today=TODAY)))


def test_an_expired_review_by_is_a_warning_and_not_an_error(make_catalog):
    root = make_catalog()
    report = validate(root, today=date(2027, 3, 1))
    assert report.errors == []
    assert [(w.code, w.file) for w in report.warnings] == [("W_REVIEW_EXPIRED", "tools/cli/demo.toml")]
    assert validate(root, today=TODAY).warnings == []


def test_a_malformed_date_is_an_error(make_catalog):
    text = demo_tool().replace('evaluated = "2026-11-11"', 'evaluated = "2026-13-45"')
    assert any("evaluated" in m for m in messages(validate(make_catalog(tools={"demo": text}), today=TODAY)))


@pytest.mark.parametrize("requirements, needle", [
    ('[[rules]]\nid = "r"\nrequire = { capability = "nav.ghost", strength = "soft" }\n', "nav.ghost"),
    ('[[rules]]\nid = "r"\nrequire = { capability = "nav.symbols", strength = "maybe" }\n', "maybe"),
    ('[[rules]]\nid = "r"\nrequire = { capability = "nav.symbols", strength = "soft" }\n'
     '[[rules]]\nid = "r"\nrequire = { capability = "nav.symbols", strength = "hard" }\n', "duplicate"),
])
def test_requirements_are_checked(make_catalog, requirements, needle):
    report = validate(make_catalog(requirements=requirements), today=TODAY)
    assert any(needle in m for m in messages(report)) and all(e.file == "requirements.toml" for e in report.errors)


def test_a_capability_id_must_have_the_dotted_form(make_catalog):
    report = validate(make_catalog(capabilities=CAPABILITIES + '\n[[capabilities]]\nid = "Bad Id"\nexclusive = false\n'),
                      today=TODAY)
    assert any("Bad Id" in m for m in messages(report))


def test_counts_and_messages_hold_no_absolute_path(make_catalog):
    root = make_catalog(tools={"demo": demo_tool().replace('provides = ["nav.symbols"]', 'provides = ["x.y"]')})
    report = validate(root, today=TODAY)
    assert report.counts == {"capabilities": 2, "entries": 1, "opaque": 0, "questions": 0, "rules": 1}
    assert not any(str(root.parent) in m for m in messages(report))


def test_a_duplicate_entry_rejects_both_files(make_catalog):
    twin = demo_tool().replace('"demo"', '"a"')
    report = validate(make_catalog(tools={"a": twin, "b": twin}), today=TODAY)
    flagged = {e.file for e in report.errors if "duplicate" in e.message}
    assert flagged == {"tools/cli/a.toml", "tools/cli/b.toml"}


def test_a_capability_exclusive_flag_must_be_a_boolean(make_catalog):
    caps = CAPABILITIES + '\n[[capabilities]]\nid = "a.b"\nexclusive = "yes"\n'
    report = validate(make_catalog(capabilities=caps), today=TODAY)
    assert [e.file for e in report.errors] == ["capabilities.toml"]
    assert "exclusive" in report.errors[0].message


def test_a_toml_under_an_unknown_kind_folder_is_rejected_and_other_files_are_ignored(make_catalog):
    root = make_catalog(extra={"tools/weird/demo.toml": demo_tool(), "tools/cli/notes.txt": "hi\n"})
    report = validate(root, today=TODAY)
    assert [e.file for e in report.errors] == ["tools/weird/demo.toml"]
    assert any("kind" in e.message for e in report.errors)
