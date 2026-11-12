"""Discovery, manifest readers of the less common ecosystems (spec 12, section 2.1).

Go, Rust, JVM, Ruby and requirements files are read with regular expressions or tomllib;
each reader is checked on a small hand-written manifest.
"""

from peo.discovery import parse_manifest, stacks_of


def stacks(rel: str, ecosystem: str, text: str) -> list[dict]:
    return stacks_of([parse_manifest(rel, ecosystem, text)])


GO_MOD = """module example.test/app

go 1.22

require github.com/spf13/cobra v1.8.0 // indirect

require (
\tgithub.com/stretchr/testify v1.9.0
)
"""


def test_manifest_go_mod():
    m = parse_manifest("go.mod", "go", GO_MOD)
    assert m.deps == {"github.com/spf13/cobra": "v1.8.0", "github.com/stretchr/testify": "v1.9.0"}
    assert stacks("go.mod", "go", GO_MOD) == [{"id": "go", "confidence": "fact", "evidence": "go.mod"}]


CARGO = """[package]
name = "app"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = "1"

[dev-dependencies]
insta = "1.39"
"""


def test_manifest_cargo_toml():
    m = parse_manifest("Cargo.toml", "rust", CARGO)
    assert m.deps == {"serde": "1.0", "tokio": "1", "insta": "1.39"}
    assert stacks("Cargo.toml", "rust", CARGO) == [{"id": "rust", "confidence": "fact", "evidence": "Cargo.toml"}]


POM = """<project>
  <artifactId>app</artifactId>
  <parent><artifactId>spring-boot-starter-parent</artifactId><version>3.3.0</version></parent>
  <dependencies>
    <dependency><groupId>org.springframework.boot</groupId>
      <artifactId> spring-boot-starter-web </artifactId></dependency>
  </dependencies>
</project>
"""


def test_manifest_pom_xml():
    m = parse_manifest("pom.xml", "jvm", POM)
    assert {"app", "spring-boot-starter-parent", "spring-boot-starter-web"} <= set(m.deps)
    got = {s["id"]: s for s in stacks("pom.xml", "jvm", POM)}
    assert set(got) == {"java", "spring"}
    assert got["spring"]["evidence"] == "pom.xml: spring-boot-starter-parent, spring-boot-starter-web"
    assert "version" not in got["spring"]           # pom.xml carries no constraint per artifact


GRADLE_KTS = """plugins {
    id("org.springframework.boot") version "3.3.0"
    kotlin("jvm") version "2.0.0"
}
dependencies {
    implementation("org.jetbrains.kotlin:kotlin-stdlib:2.0.0")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
}
"""


def test_manifest_build_gradle_kts():
    m = parse_manifest("build.gradle.kts", "jvm", GRADLE_KTS)
    assert m.deps["kotlin-stdlib"] == "2.0.0"
    assert m.deps["junit-jupiter"] == "5.10.2"
    assert "org.springframework.boot" in m.deps
    ids = [s["id"] for s in stacks("build.gradle.kts", "jvm", GRADLE_KTS)]
    assert ids == ["java", "kotlin", "spring"]


GEMFILE = """source "https://rubygems.org"
gem "rails", "~> 7.1"
gem 'puma'
  gem "rspec-rails", group: :test
"""


def test_manifest_gemfile():
    m = parse_manifest("Gemfile", "ruby", GEMFILE)
    assert m.deps == {"rails": "~> 7.1", "puma": "", "rspec-rails": ""}
    assert stacks("Gemfile", "ruby", GEMFILE) == [{"id": "rails", "confidence": "fact",
                                                  "evidence": "Gemfile: rails"}]


REQUIREMENTS = """# web
Django==5.0.6
fastapi[standard]>=0.110 ; python_version >= "3.11"
-r dev.txt
pytest
"""


def test_manifest_requirements_txt():
    m = parse_manifest("requirements.txt", "python", REQUIREMENTS)
    assert m.deps == {"django": "==5.0.6", "fastapi": ">=0.110", "pytest": ""}
    got = {s["id"]: s for s in stacks("requirements.txt", "python", REQUIREMENTS)}
    assert got["django"]["version"] == "5"
    assert "version" not in got["fastapi"]
    assert got["pytest"]["evidence"] == "requirements.txt: pytest"
