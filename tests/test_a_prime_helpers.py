"""Helpers of the A′ local test (spec 16 §2.3): example files skipped, values matched as whole words."""

from tests.test_a_prime import env_values, leaked_names


def test_env_values_skip_example_files(tmp_path):
    (tmp_path / ".env.example").write_text("JWT_SECRET=secret\n")
    (tmp_path / ".env").write_text("API_TOKEN=abcdef123\n")
    assert env_values(tmp_path) == [("API_TOKEN", "abcdef123")]


def test_values_match_as_whole_words_only():
    values = [("A", "secret"), ("B", "abcdef123")]
    assert leaked_names(values, "validate-secret-scan.yaml abcdef1234") == []
    assert leaked_names(values, "No known secret scanner") == ["A"]
    assert leaked_names(values, '"abcdef123"') == ["B"]
