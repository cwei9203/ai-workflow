"""Deterministic, evidence-based discovery for project contracts.

Discovery deliberately stops short of making architectural decisions.  It only
records facts that can be supported by files in the repository and leaves the
contract in ``needs_review`` for the semantic onboarding pass.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union


PathLike = Union[str, os.PathLike]

_LANGUAGE_ORDER = (
    "TypeScript",
    "JavaScript",
    "Python",
    "Rust",
    "Go",
    "C#",
    "Java",
    "Kotlin",
    "C++",
    "C",
    "Swift",
    "Ruby",
    "PHP",
    "Scala",
    "Shell",
    "PowerShell",
)

_EXTENSION_LANGUAGES = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".py": "Python",
    ".pyi": "Python",
    ".rs": "Rust",
    ".go": "Go",
    ".cs": "C#",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hh": "C++",
    ".hpp": "C++",
    ".hxx": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
}

_SCAN_PRUNE_DIRECTORIES = {
    ".ai-workflow",
    ".git",
    ".hg",
    ".mypy_cache",
    ".next",
    ".nox",
    ".nuxt",
    ".pytest_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
    "venv",
}

_SOURCE_ROOT_CANDIDATES = ("src", "source", "sources", "lib", "app", "apps", "packages")
_TEST_ROOT_CANDIDATES = ("tests", "test", "spec", "specs", "__tests__")
_DOCUMENTATION_ROOT_CANDIDATES = ("docs", "doc", "documentation")
_GENERATED_ROOT_CANDIDATES = (
    "build",
    "dist",
    "generated",
    "gen",
    "out",
    "target",
    "coverage",
    ".next",
    ".nuxt",
)
_PROTECTED_ROOT_CANDIDATES = ("node_modules", "vendor", "third_party", "external")

_COMMON_PACKAGE_SCRIPTS = (
    "build",
    "test",
    "lint",
    "typecheck",
    "check",
    "format",
    "verify",
    "generate",
    "docs",
    "clean",
)

_COMMAND_DESCRIPTIONS = {
    "build": "Build the project",
    "test": "Run the test suite",
    "lint": "Run lint checks",
    "typecheck": "Run static type checks",
    "check": "Run project checks",
    "format": "Format project files",
    "verify": "Run the project verification suite",
    "generate": "Generate project artifacts",
    "docs": "Build or check documentation",
    "clean": "Remove generated build artifacts",
}


class _DiscoveryBuilder:
    """Collect contract facts while keeping provenance in one place."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.language_sources: Dict[str, List[str]] = {}
        self.platform_sources: Dict[str, List[str]] = {}
        self.evidence: List[Dict[str, str]] = []
        self.warnings: List[str] = []
        self.name_candidates: List[Tuple[int, str, str]] = []
        self.commands: Dict[str, Dict[str, str]] = {}

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def add_evidence(self, fact: str, source: str, value: str = "") -> None:
        item = {"fact": fact, "source": source}
        if value:
            item["value"] = value
        if item not in self.evidence:
            self.evidence.append(item)

    def add_language(self, language: str, source: str) -> None:
        sources = self.language_sources.setdefault(language, [])
        if source not in sources:
            sources.append(source)

    def add_platform(self, platform: str, source: str) -> None:
        sources = self.platform_sources.setdefault(platform, [])
        if source not in sources:
            sources.append(source)

    def add_name(self, name: Any, source: str, priority: int) -> None:
        if isinstance(name, str) and name.strip():
            self.name_candidates.append((priority, name.strip(), source))

    def add_command(self, name: str, run: str, description: str, source: str) -> None:
        if name in self.commands:
            return
        self.commands[name] = {
            "run": run,
            "description": description,
        }
        self.add_evidence("commands.%s" % name, source, run)


def _read_text(path: Path, builder: _DiscoveryBuilder) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        builder.warnings.append("Could not read %s: %s" % (builder.relative(path), error))
        return None


def _load_json(path: Path, builder: _DiscoveryBuilder) -> Optional[Mapping[str, Any]]:
    text = _read_text(path, builder)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except (TypeError, ValueError) as error:
        builder.warnings.append("Could not parse %s as JSON: %s" % (builder.relative(path), error))
        return None
    if not isinstance(value, Mapping):
        builder.warnings.append("Expected %s to contain a JSON object" % builder.relative(path))
        return None
    return value


def _toml_value(text: str, sections: Sequence[str], key: str) -> Optional[str]:
    """Read a simple quoted scalar without depending on tomllib (Python 3.9)."""

    wanted = set(sections)
    current = ""
    section_pattern = re.compile(r"^\s*\[\s*([^]]+?)\s*\]\s*(?:#.*)?$")
    value_pattern = re.compile(
        r"^\s*%s\s*=\s*([\"'])(.*?)\1\s*(?:#.*)?$" % re.escape(key)
    )
    for line in text.splitlines():
        section_match = section_pattern.match(line)
        if section_match:
            current = section_match.group(1).strip()
            continue
        if current not in wanted:
            continue
        value_match = value_pattern.match(line)
        if value_match:
            return value_match.group(2).strip()
    return None


def _package_manager(package: Mapping[str, Any], root: Path) -> Tuple[str, str]:
    declared = package.get("packageManager")
    if isinstance(declared, str):
        manager = declared.split("@", 1)[0].strip().lower()
        if manager in {"npm", "pnpm", "yarn", "bun"}:
            return manager, "package.json#packageManager"
    lock_files = (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
        ("bun.lock", "bun"),
        ("package-lock.json", "npm"),
        ("npm-shrinkwrap.json", "npm"),
    )
    for filename, manager in lock_files:
        if (root / filename).is_file():
            return manager, filename
    return "npm", "package.json"


def _package_script_command(manager: str, script: str) -> str:
    if manager == "pnpm":
        return "pnpm test" if script == "test" else "pnpm run %s" % script
    if manager == "npm":
        return "npm test" if script == "test" else "npm run %s" % script
    if manager == "yarn":
        return "yarn %s" % script
    return "bun run %s" % script


def _discover_package_json(builder: _DiscoveryBuilder) -> None:
    path = builder.root / "package.json"
    if not path.is_file():
        return
    package = _load_json(path, builder)
    if package is None:
        return

    builder.add_name(package.get("name"), "package.json#name", 10)
    builder.add_platform("Node.js", "package.json")
    manager, manager_source = _package_manager(package, builder.root)
    builder.add_evidence("package_manager", manager_source, manager)
    if manager_source == "package.json":
        builder.warnings.append(
            "No package manager declaration or lock file was found; npm commands are a conventional fallback and must be reviewed"
        )

    scripts = package.get("scripts", {})
    if scripts is None:
        scripts = {}
    if not isinstance(scripts, Mapping):
        builder.warnings.append("package.json#scripts is not an object")
        return
    for script in _COMMON_PACKAGE_SCRIPTS:
        value = scripts.get(script)
        if not isinstance(value, str) or not value.strip():
            continue
        builder.add_command(
            script,
            _package_script_command(manager, script),
            _COMMAND_DESCRIPTIONS[script],
            "package.json#scripts.%s" % script,
        )


def _discover_toml_projects(builder: _DiscoveryBuilder) -> None:
    cargo = builder.root / "Cargo.toml"
    if cargo.is_file():
        text = _read_text(cargo, builder)
        if text is not None:
            builder.add_name(_toml_value(text, ("package",), "name"), "Cargo.toml#package.name", 30)
        builder.add_language("Rust", "Cargo.toml")
        builder.add_platform("Cargo", "Cargo.toml")
        builder.add_command("rust_build", "cargo build", "Build Rust targets", "Cargo.toml")
        builder.add_command("rust_test", "cargo test", "Run Rust tests", "Cargo.toml")

    pyproject = builder.root / "pyproject.toml"
    if pyproject.is_file():
        text = _read_text(pyproject, builder)
        if text is not None:
            name = _toml_value(text, ("project", "tool.poetry"), "name")
            builder.add_name(name, "pyproject.toml#project.name", 20)
            if "[tool.pytest.ini_options]" in text:
                builder.add_command(
                    "python_test",
                    "python -m pytest",
                    "Run Python tests with pytest",
                    "pyproject.toml#tool.pytest.ini_options",
                )
        builder.add_language("Python", "pyproject.toml")
        builder.add_platform("Python", "pyproject.toml")


def _discover_go(builder: _DiscoveryBuilder) -> None:
    path = builder.root / "go.mod"
    if not path.is_file():
        return
    text = _read_text(path, builder)
    if text is not None:
        match = re.search(r"(?m)^\s*module\s+([^\s]+)", text)
        if match:
            module = match.group(1).strip()
            name = module.rstrip("/").rsplit("/", 1)[-1]
            builder.add_name(name, "go.mod#module", 40)
    builder.add_language("Go", "go.mod")
    builder.add_platform("Go", "go.mod")
    builder.add_command("go_build", "go build ./...", "Build all Go packages", "go.mod")
    builder.add_command("go_test", "go test ./...", "Run all Go tests", "go.mod")


def _discover_other_manifests(builder: _DiscoveryBuilder) -> None:
    root = builder.root

    if (root / "pytest.ini").is_file() or (root / "conftest.py").is_file():
        source = "pytest.ini" if (root / "pytest.ini").is_file() else "conftest.py"
        builder.add_language("Python", source)
        builder.add_platform("Python", source)
        builder.add_command("python_test", "python -m pytest", "Run Python tests with pytest", source)

    if (root / "requirements.txt").is_file() or (root / "setup.py").is_file() or (root / "setup.cfg").is_file():
        source = next(
            name
            for name in ("requirements.txt", "setup.py", "setup.cfg")
            if (root / name).is_file()
        )
        builder.add_language("Python", source)
        builder.add_platform("Python", source)

    solution_files = sorted(root.glob("*.sln"), key=lambda item: item.name.casefold())
    project_files = sorted(root.glob("*.csproj"), key=lambda item: item.name.casefold())
    if solution_files or project_files:
        source_path = solution_files[0] if solution_files else project_files[0]
        source = builder.relative(source_path)
        builder.add_language("C#", source)
        builder.add_platform(".NET", source)
        target = _shell_quote_relative(source)
        builder.add_command("dotnet_build", "dotnet build %s" % target, "Build .NET projects", source)
        builder.add_command("dotnet_test", "dotnet test %s" % target, "Run .NET tests", source)

    pom = root / "pom.xml"
    if pom.is_file():
        builder.add_language("Java", "pom.xml")
        builder.add_platform("JVM", "pom.xml")
        builder.add_command("maven_build", "mvn package", "Build the Maven project", "pom.xml")
        builder.add_command("maven_test", "mvn test", "Run Maven tests", "pom.xml")

    gradle_source = None
    for candidate in ("gradlew", "build.gradle.kts", "build.gradle"):
        if (root / candidate).is_file():
            gradle_source = candidate
            break
    if gradle_source is not None:
        if (root / "build.gradle.kts").is_file():
            builder.add_language("Kotlin", "build.gradle.kts")
        else:
            builder.add_language("Java", gradle_source)
        builder.add_platform("JVM", gradle_source)
        executable = "./gradlew" if (root / "gradlew").is_file() else "gradle"
        builder.add_command("gradle_build", "%s build" % executable, "Build the Gradle project", gradle_source)
        builder.add_command("gradle_test", "%s test" % executable, "Run Gradle tests", gradle_source)


def _shell_quote_relative(path: str) -> str:
    if re.match(r"^[A-Za-z0-9_./-]+$", path):
        return path
    return '"%s"' % path.replace('"', '\\"')


def _scan_languages(builder: _DiscoveryBuilder, limit: int = 20000) -> None:
    visited = 0
    stopped = False
    for directory, directory_names, filenames in os.walk(str(builder.root), followlinks=False):
        directory_names[:] = sorted(
            (
                name
                for name in directory_names
                if name not in _SCAN_PRUNE_DIRECTORIES and not (Path(directory) / name).is_symlink()
            ),
            key=str.casefold,
        )
        for filename in sorted(filenames, key=str.casefold):
            visited += 1
            if visited > limit:
                stopped = True
                break
            language = _EXTENSION_LANGUAGES.get(Path(filename).suffix.lower())
            if language is None:
                continue
            source_path = Path(directory) / filename
            builder.add_language(language, builder.relative(source_path))
        if stopped:
            break
    if stopped:
        builder.warnings.append(
            "Language scan stopped after %d files; review language detection manually" % limit
        )


def _existing_directories(root: Path, candidates: Iterable[str]) -> List[str]:
    return [candidate for candidate in candidates if (root / candidate).is_dir()]


def _discover_read_first(root: Path) -> List[str]:
    entries = {path.name.casefold(): path.name for path in root.iterdir() if path.is_file()}
    result: List[str] = []
    for candidate in (
        "README.md",
        "README.rst",
        "README.txt",
        "ARCHITECTURE.md",
        "CONTRIBUTING.md",
        "DEVELOPING.md",
        "AGENTS.md",
        "CLAUDE.md",
    ):
        actual = entries.get(candidate.casefold())
        if actual is not None and actual not in result:
            result.append(actual)
    for directory in _DOCUMENTATION_ROOT_CANDIDATES:
        docs_root = root / directory
        if not docs_root.is_dir():
            continue
        docs_entries = {path.name.casefold(): path.name for path in docs_root.iterdir() if path.is_file()}
        for candidate in ("README.md", "index.md", "architecture.md"):
            actual = docs_entries.get(candidate.casefold())
            if actual is not None:
                value = "%s/%s" % (directory, actual)
                if value not in result:
                    result.append(value)
    return result


def _manifest_paths(root: Path) -> List[str]:
    fixed = (
        "package.json",
        "pnpm-workspace.yaml",
        "tsconfig.json",
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "CMakeLists.txt",
        "Makefile",
    )
    result = [name for name in fixed if (root / name).is_file()]
    result.extend(path.name for path in sorted(root.glob("*.sln"), key=lambda item: item.name.casefold()))
    result.extend(path.name for path in sorted(root.glob("*.csproj"), key=lambda item: item.name.casefold()))
    return result


def _record_collected_evidence(builder: _DiscoveryBuilder) -> None:
    for language in _LANGUAGE_ORDER:
        for source in builder.language_sources.get(language, []):
            builder.add_evidence("project.languages.%s" % language, source)
    for platform in sorted(builder.platform_sources, key=str.casefold):
        for source in builder.platform_sources[platform]:
            builder.add_evidence("project.platforms.%s" % platform, source)


def discover_project(root: PathLike) -> Dict[str, Any]:
    """Return a deterministic first-pass project contract for *root*.

    The function does not execute repository code or external tools.  Commands
    are included only when a manifest or configuration file provides evidence
    for the corresponding ecosystem or script.
    """

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError("Project root does not exist: %s" % root_path)
    if not root_path.is_dir():
        raise NotADirectoryError("Project root is not a directory: %s" % root_path)

    builder = _DiscoveryBuilder(root_path)
    _discover_package_json(builder)
    _discover_toml_projects(builder)
    _discover_go(builder)
    _discover_other_manifests(builder)
    _scan_languages(builder)

    # A package manifest is strong Node.js evidence, but it is not sufficient
    # to call a TypeScript project JavaScript when tsconfig/source evidence says
    # otherwise.
    if (root_path / "tsconfig.json").is_file():
        builder.add_language("TypeScript", "tsconfig.json")
    if "Node.js" in builder.platform_sources and not any(
        language in builder.language_sources for language in ("TypeScript", "JavaScript")
    ):
        builder.add_language("JavaScript", "package.json")

    name = root_path.name
    name_source = "repository directory"
    if builder.name_candidates:
        _, name, name_source = min(builder.name_candidates, key=lambda item: (item[0], item[1]))
    builder.add_evidence("project.name", name_source, name)
    _record_collected_evidence(builder)

    manifests = _manifest_paths(root_path)
    for manifest in manifests:
        builder.add_evidence("project.manifests", manifest)

    source_roots = _existing_directories(root_path, _SOURCE_ROOT_CANDIDATES)
    test_roots = _existing_directories(root_path, _TEST_ROOT_CANDIDATES)
    documentation_roots = _existing_directories(root_path, _DOCUMENTATION_ROOT_CANDIDATES)
    generated_paths = ["%s/**" % path for path in _existing_directories(root_path, _GENERATED_ROOT_CANDIDATES)]
    protected_paths = ["%s/**" % path for path in _existing_directories(root_path, _PROTECTED_ROOT_CANDIDATES)]
    read_first = _discover_read_first(root_path)

    for path in source_roots:
        builder.add_evidence("project.source_roots", path)
    for path in test_roots:
        builder.add_evidence("project.test_roots", path)
    for path in documentation_roots:
        builder.add_evidence("project.documentation_roots", path)
    for path in generated_paths:
        builder.add_evidence("paths.generated", path[:-3])
    for path in protected_paths:
        builder.add_evidence("paths.protected", path[:-3])
    for path in read_first:
        builder.add_evidence("context.read_first", path)

    review_notes = [
        "Add a concise project summary and confirm the discovered project facts.",
        "Document architecture boundaries, protected paths, and generation triggers where applicable.",
        "Configure default and changed-file verification commands, then run a strict diagnostic and dry run.",
    ]

    return {
        "$schema": "./project.schema.json",
        "schema_version": 1,
        "project": {
            "name": name,
            "summary": "",
            "languages": [language for language in _LANGUAGE_ORDER if language in builder.language_sources],
            "platforms": sorted(builder.platform_sources, key=str.casefold),
            "manifests": manifests,
            "source_roots": source_roots,
            "test_roots": test_roots,
            "documentation_roots": documentation_roots,
        },
        "context": {
            "read_first": read_first,
            "architecture_boundaries": [],
        },
        "paths": {
            "protected": protected_paths,
            "generated": generated_paths,
        },
        "generation": {"rules": []},
        "commands": builder.commands,
        "verification": {
            "default": [],
            "rules": [],
        },
        "onboarding": {
            "status": "needs_review",
            "review_notes": review_notes,
        },
        "discovery": {
            "evidence": builder.evidence,
            "warnings": builder.warnings,
        },
    }


__all__ = ["discover_project"]
