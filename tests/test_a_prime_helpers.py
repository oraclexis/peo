"""Helpers of the A′ local test (spec 16 §2.3): example files skipped, values matched as whole words."""

from tests.test_a_prime import env_values, leaked_names, without_paths


def test_env_values_skip_example_files(tmp_path):
    (tmp_path / ".env.example").write_text("JWT_SECRET=secret\n")
    (tmp_path / ".env").write_text("API_TOKEN=abcdef123\n")
    assert env_values(tmp_path) == [("API_TOKEN", "abcdef123")]


def test_values_match_as_whole_words_only():
    values = [("A", "secret"), ("B", "abcdef123")]
    assert leaked_names(values, "validate-secret-scan.yaml abcdef1234") == []
    assert leaked_names(values, "No known secret scanner") == ["A"]
    assert leaked_names(values, '"abcdef123"') == ["B"]


def test_a_value_that_is_a_piece_of_a_path_is_no_leak(tmp_path):
    (tmp_path / "deploy" / "sql").mkdir(parents=True)
    (tmp_path / "deploy" / "sql" / "nest_admin.sql").write_text("-- schema\n")
    (tmp_path / ".env").write_text("DB_DATABASE=nest_admin\n")
    values = env_values(tmp_path)
    assert leaked_names(values, '{"path": "deploy/sql/nest_admin.sql"}') == ["DB_DATABASE"]
    assert leaked_names(values, without_paths(tmp_path, '{"path": "deploy/sql/nest_admin.sql"}')) == []


def test_removing_paths_keeps_a_value_found_elsewhere(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "nest_admin.sql").write_text("x\n")
    (tmp_path / ".env").write_text("DB_DATABASE=nest_admin\n")
    text = without_paths(tmp_path, "a/nest_admin.sql and nest_admin")
    assert leaked_names(env_values(tmp_path), text) == ["DB_DATABASE"]
