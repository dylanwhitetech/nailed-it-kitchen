"""Release publication and promotion steps for the trusted release workflow.

Run only from `.github/workflows/release.yml` on trusted `main` events. The tool never
creates versions or tags: release-please owns them. It publishes the OCI chart for
releases that are not yet in GHCR, reusing the SHA-tagged images that CI already
published, and opens (never merges) the k3s-infrastructure promotion PR.

Subcommands:
    publish: Publish charts for existing release-please releases that are missing in GHCR.
    promote: Bump the exact chart pin in a k3s-infrastructure checkout and open a PR.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

OWNER = "dylanwhitetech"
APP_REPO = f"{OWNER}/nailed-it-kitchen"
CHART_NAME = "naileditkitchen"
CHART_REGISTRY = f"oci://ghcr.io/{OWNER}/charts"
CHART_REF = f"{CHART_REGISTRY}/{CHART_NAME}"
CHART_DIR = f"deploy/chart/{CHART_NAME}"
IMAGE_COMPONENTS = ("api", "web")
REQUIRED_PLATFORMS = frozenset({"linux/amd64", "linux/arm64"})
INFRA_REPO = f"{OWNER}/k3s-infrastructure"
INFRA_BASE_BRANCH = "main"
INFRA_HELMRELEASE_PATH = f"kubernetes/apps/{CHART_NAME}/helmrelease.yaml"
INFRA_HELMRELEASE_NAME = CHART_NAME
INFRA_HELMRELEASE_NAMESPACE = CHART_NAME
RECENT_RELEASES = 10

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_KEY_LINE_RE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z0-9_.-]+):(?P<rest>.*)$")
_VALUE_RE = re.compile(
    r"^(?P<value>\s*(?:\"[^\"]*\"|'[^']*'|[^\s#][^#]*?|))(?P<comment>\s+#.*)?\s*$"
)

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


class ReleaseError(Exception):
    """A release step cannot continue safely; the message says what a human must check."""


class ImagesNotPublished(ReleaseError):
    """CI has not published the SHA-tagged images for a release commit."""


def run_command(cmd: Sequence[str]) -> subprocess.CompletedProcess:
    """Run a command without a shell and capture text output."""
    return subprocess.run(list(cmd), capture_output=True, text=True, check=False)


def _checked(runner: Runner, cmd: Sequence[str]) -> str:
    result = runner(cmd)
    if result.returncode != 0:
        raise ReleaseError(f"`{' '.join(cmd)}` failed: {result.stderr.strip()}")
    return result.stdout


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a plain MAJOR.MINOR.PATCH version.

    Raises:
        ReleaseError: The version is not plain SemVer; pre-release/build suffixes are unused.
    """
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise ReleaseError(f"{version!r} is not a MAJOR.MINOR.PATCH version")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def _render_scalar(old_value: str, new_value: str) -> str:
    if old_value.startswith("'"):
        return f"'{new_value}'"
    if old_value.startswith('"') or yaml.safe_load(new_value) != new_value:
        return f'"{new_value}"'
    return new_value


def _document_bounds(lines: list[str]) -> list[tuple[int, int]]:
    bounds, start = [], 0
    for index, line in enumerate(lines):
        if line.rstrip() == "---":
            bounds.append((start, index))
            start = index + 1
    bounds.append((start, len(lines)))
    if len(bounds) > 1 and not any(
        line.strip() for line in lines[bounds[0][0] : bounds[0][1]]
    ):
        bounds.pop(0)
    return bounds


def set_yaml_scalar(
    text: str, path: Sequence[str], value: str, *, document: int = 0
) -> str:
    """Set one block-mapping scalar while keeping comments, quoting style and layout.

    The edit is verified by re-parsing: the result must equal the original document with
    only `path` changed, so an unsupported layout fails instead of producing a wrong file.

    Args:
        text: YAML text, possibly with several `---` documents.
        path: Mapping keys from the document root to the scalar.
        value: New string value.
        document: Index of the document to edit.

    Raises:
        ReleaseError: The key is missing, ambiguous or not a plain scalar, or the edit
            would change anything else.
    """
    lines = text.split("\n")
    start, end = _document_bounds(lines)[document]
    stack: list[tuple[int, str]] = []
    matches: list[int] = []
    for index in range(start, end):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if line.lstrip().startswith("- "):
            stack.append((indent, "-"))
            continue
        match = _KEY_LINE_RE.match(line)
        if not match:
            continue
        key = match.group("key")
        if [entry[1] for entry in stack] + [key] == list(path):
            matches.append(index)
        stack.append((indent, key))

    dotted = ".".join(path)
    if len(matches) != 1:
        raise ReleaseError(f"expected exactly one `{dotted}` key, found {len(matches)}")
    index = matches[0]
    match = _KEY_LINE_RE.match(lines[index])
    value_match = _VALUE_RE.match(match.group("rest"))
    if not value_match:
        raise ReleaseError(f"`{dotted}` is not a plain scalar line")
    rendered = _render_scalar(value_match.group("value").strip(), value)
    comment = value_match.group("comment") or ""
    lines[index] = f"{match.group('indent')}{match.group('key')}: {rendered}{comment}"
    updated = "\n".join(lines)

    expected = copy.deepcopy(list(yaml.safe_load_all(text)))
    node = expected[document]
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    if list(yaml.safe_load_all(updated)) != expected:
        raise ReleaseError(f"editing `{dotted}` would change more than that value")
    return updated


def get_path(data: object, path: Sequence[str]) -> object:
    """Return a nested mapping value, or None when any key is missing."""
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


@dataclass(frozen=True)
class Image:
    """A published multi-arch image index for one component."""

    component: str
    repository: str
    digest: str


def inspect_image(runner: Runner, component: str, source_sha: str) -> Image:
    """Verify CI's SHA-tagged multi-arch image for one component.

    Raises:
        ImagesNotPublished: The SHA tag does not exist.
        ReleaseError: The image lacks a required platform or the source revision.
    """
    repository = f"ghcr.io/{OWNER}/{CHART_NAME}-{component}"
    ref = f"{repository}:{source_sha}"
    cmd = [
        "docker",
        "buildx",
        "imagetools",
        "inspect",
        ref,
        "--format",
        "{{json .Manifest}}",
    ]
    result = runner(cmd)
    if result.returncode != 0:
        if "not found" in result.stderr:
            raise ImagesNotPublished(f"CI has not published {ref}")
        raise ReleaseError(f"could not inspect {ref}: {result.stderr.strip()}")
    manifest = json.loads(result.stdout)
    platforms = {
        f"{entry['platform']['os']}/{entry['platform']['architecture']}"
        for entry in manifest.get("manifests", [])
        if "platform" in entry
    }
    missing = REQUIRED_PLATFORMS - platforms
    if missing:
        raise ReleaseError(f"{ref} is missing platforms: {', '.join(sorted(missing))}")
    revision = manifest.get("annotations", {}).get("org.opencontainers.image.revision")
    if revision != source_sha:
        raise ReleaseError(f"{ref} has revision {revision!r}, expected {source_sha}")
    digest = manifest.get("digest", "")
    if not DIGEST_RE.fullmatch(digest):
        raise ReleaseError(f"{ref} returned an invalid digest {digest!r}")
    return Image(component, repository, digest)


def chart_exists(runner: Runner, version: str) -> bool:
    """Return whether a chart version is in GHCR; published versions are never replaced."""
    result = runner(["helm", "show", "chart", CHART_REF, "--version", version])
    if result.returncode == 0:
        return True
    if "not found" in result.stderr:
        return False
    raise ReleaseError(
        f"could not check {CHART_REF}:{version}: {result.stderr.strip()}"
    )


def published_chart(runner: Runner, version: str) -> tuple[str, str]:
    """Return the source SHA (`appVersion`) and digest of a published chart version.

    Raises:
        ReleaseError: The version is not published or does not carry a full source SHA.
    """
    parse_semver(version)
    result = runner(["helm", "show", "chart", CHART_REF, "--version", version])
    if result.returncode != 0:
        raise ReleaseError(
            f"{CHART_REF}:{version} is not available: {result.stderr.strip()}"
        )
    match = re.search(r"Digest:\s*(sha256:[0-9a-f]{64})", result.stderr + result.stdout)
    chart = yaml.safe_load(result.stdout)
    source_sha = str(chart.get("appVersion", "")) if isinstance(chart, dict) else ""
    if not match or not SHA_RE.fullmatch(source_sha):
        raise ReleaseError(
            f"{CHART_REF}:{version} lacks a digest or full source SHA appVersion"
        )
    return source_sha, match.group(1)


def prepare_chart(
    chart_dir: Path, version: str, source_sha: str, images: Sequence[Image]
) -> None:
    """Pin the extracted release chart to the release commit and image digests.

    Only the packaged copy changes: `appVersion` becomes the full source SHA and each
    image gets the SHA tag plus the index digest. The chart version must already equal
    the release-please version.

    Raises:
        ReleaseError: The chart does not match the release contract.
    """
    chart_file = chart_dir / "Chart.yaml"
    values_file = chart_dir / "values.yaml"
    chart_text = chart_file.read_text(encoding="utf-8")
    chart = yaml.safe_load(chart_text)
    if chart.get("name") != CHART_NAME:
        raise ReleaseError(
            f"Chart.yaml name is {chart.get('name')!r}, expected {CHART_NAME!r}"
        )
    if str(chart.get("version")) != version:
        raise ReleaseError(
            f"Chart.yaml version {chart.get('version')!r} does not match release {version}; "
            "release-please must own the chart version"
        )
    source_url = f"https://github.com/{APP_REPO}"
    if source_url not in (chart.get("sources") or []):
        raise ReleaseError(
            f"Chart.yaml sources must include {source_url} for package linkage"
        )
    chart_file.write_text(
        set_yaml_scalar(chart_text, ["appVersion"], source_sha), encoding="utf-8"
    )

    values_text = values_file.read_text(encoding="utf-8")
    values = yaml.safe_load(values_text)
    for image in images:
        configured = get_path(values, [image.component, "image", "repository"])
        if configured != image.repository:
            raise ReleaseError(
                f"values {image.component}.image.repository is {configured!r}, "
                f"expected {image.repository}"
            )
        values_text = set_yaml_scalar(
            values_text, [image.component, "image", "tag"], source_sha
        )
        values_text = set_yaml_scalar(
            values_text, [image.component, "image", "digest"], image.digest
        )
    values_file.write_text(values_text, encoding="utf-8")


@dataclass(frozen=True)
class Release:
    """A release-please GitHub Release and the commit its tag points to."""

    version: str
    tag: str
    sha: str


def list_releases(runner: Runner, repo: str) -> list[Release]:
    """Return recent published `vX.Y.Z` releases, oldest first."""
    output = _checked(
        runner, ["gh", "api", f"repos/{repo}/releases?per_page={RECENT_RELEASES}"]
    )
    releases = []
    for item in json.loads(output):
        tag = item.get("tag_name", "")
        if item.get("draft") or item.get("prerelease") or not tag.startswith("v"):
            continue
        version = tag[1:]
        if not SEMVER_RE.fullmatch(version):
            continue
        sha = _checked(
            runner, ["gh", "api", f"repos/{repo}/commits/{tag}", "--jq", ".sha"]
        ).strip()
        if not SHA_RE.fullmatch(sha):
            raise ReleaseError(f"tag {tag} resolved to an invalid commit {sha!r}")
        releases.append(Release(version, tag, sha))
    return sorted(releases, key=lambda release: parse_semver(release.version))


def extract_chart(runner: Runner, source_sha: str, destination: Path) -> Path:
    """Extract the chart directory from the release commit with `git archive`."""
    archive = destination / "chart.tar"
    _checked(
        runner,
        [
            "git",
            "archive",
            "--format=tar",
            f"--output={archive}",
            source_sha,
            CHART_DIR,
        ],
    )
    with tarfile.open(archive) as tar:
        tar.extractall(destination / "src", filter="data")
    return destination / "src" / CHART_DIR


def publish_release(runner: Runner, release: Release, workdir: Path) -> str:
    """Package and push one chart version and return the pushed chart digest."""
    images = [
        inspect_image(runner, component, release.sha) for component in IMAGE_COMPONENTS
    ]
    chart_dir = extract_chart(runner, release.sha, workdir)
    prepare_chart(chart_dir, release.version, release.sha, images)
    _checked(runner, ["helm", "lint", str(chart_dir)])
    dist = workdir / "dist"
    dist.mkdir()
    _checked(runner, ["helm", "package", str(chart_dir), "--destination", str(dist)])
    package = dist / f"{CHART_NAME}-{release.version}.tgz"
    result = runner(["helm", "push", str(package), CHART_REGISTRY])
    if result.returncode != 0:
        raise ReleaseError(f"helm push failed: {result.stderr.strip()}")
    match = re.search(r"Digest:\s*(sha256:[0-9a-f]{64})", result.stdout + result.stderr)
    if not match:
        raise ReleaseError("helm push did not report a chart digest")
    return match.group(1)


def publish(runner: Runner, repo: str, trigger_sha: str | None) -> list[dict[str, str]]:
    """Publish every recent release whose chart is missing from GHCR.

    A release whose images CI has not yet published is deferred, because the CI
    completion for that commit starts another run; it fails when that commit triggered
    this run, or when no trigger commit is given (manual runs).

    Returns:
        Published releases as dicts with version, source_sha and chart_digest.
    """
    published = []
    for release in list_releases(runner, repo):
        if chart_exists(runner, release.version):
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                digest = publish_release(runner, release, Path(tmp))
            except ImagesNotPublished as error:
                if trigger_sha and release.sha != trigger_sha:
                    print(f"::notice::Deferred {release.tag}: {error}")
                    continue
                raise
        published.append(
            {
                "version": release.version,
                "source_sha": release.sha,
                "chart_digest": digest,
            }
        )
    return published


def update_helmrelease(text: str, version: str) -> tuple[str, str]:
    """Return the HelmRelease text with its exact chart pin set to `version`, and the old pin.

    Raises:
        ReleaseError: The file is not the expected single HelmRelease, or the change would
            downgrade (rollback is a reviewed revert, not an automated downgrade).
    """
    documents = list(yaml.safe_load_all(text))
    targets = [
        index
        for index, doc in enumerate(documents)
        if isinstance(doc, dict)
        and doc.get("kind") == "HelmRelease"
        and get_path(doc, ["metadata", "name"]) == INFRA_HELMRELEASE_NAME
        and get_path(doc, ["metadata", "namespace"]) == INFRA_HELMRELEASE_NAMESPACE
    ]
    if len(targets) != 1:
        raise ReleaseError(
            f"{INFRA_HELMRELEASE_PATH} must contain exactly one HelmRelease "
            f"{INFRA_HELMRELEASE_NAMESPACE}/{INFRA_HELMRELEASE_NAME}"
        )
    doc = documents[targets[0]]
    if get_path(doc, ["spec", "chart", "spec", "chart"]) != CHART_NAME:
        raise ReleaseError(f"HelmRelease spec.chart.spec.chart must be {CHART_NAME!r}")
    current = str(get_path(doc, ["spec", "chart", "spec", "version"]))
    if parse_semver(version) < parse_semver(current):
        raise ReleaseError(f"refusing to downgrade the pin from {current} to {version}")
    if current == version:
        return text, current
    path = ["spec", "chart", "spec", "version"]
    return set_yaml_scalar(text, path, version, document=targets[0]), current


def promotion_body(
    version: str, source_sha: str, chart_digest: str, previous: str, run_url: str
) -> str:
    """Render the promotion PR body with the k3s-infrastructure PR template headings."""
    return f"""## Summary

- Promote the Nailed It Kitchen chart from `{previous}` to `{version}`, published by the trusted
  release workflow in `{APP_REPO}`. Opened automatically; a human reviews and merges it.

## Linked issue

Not applicable: automated promotion of release
[v{version}](https://github.com/{APP_REPO}/releases/tag/v{version}).

## What changed

- `{INFRA_HELMRELEASE_PATH}`: `spec.chart.spec.version` `{previous}` -> `{version}`.
- Chart: `{CHART_REF}:{version}` (`{chart_digest}`); its images and `appVersion` pin source
  commit `{source_sha}`.
- Guidance updated? not applicable

## Validation

- [ ] Render checks (`kubectl kustomize` for `kubernetes/platform`, `kubernetes/apps`, and `kubernetes/clusters/homelab`)
- [ ] Schema checks (`kubeconform`) when applicable
- [ ] Policy checks (`conftest`) when applicable
- [ ] Helm chart render checks when applicable
- [ ] Server-side dry-run apply check when applicable
- [ ] Docs updated when behavior/workflow changed

Not run by the release workflow; this repository's pull request checks validate the change.
Release run: {run_url}

## Deployment and ops impact

- [ ] No deployment impact
- [ ] Ansible/bootstrap impact
- [x] Flux/Kubernetes reconciliation impact
- [ ] DNS/ingress impact
- [ ] Storage/NFS impact

## AI customization checklist

- [x] Not applicable
- [ ] Updated `AGENTS.md`, `.github/agents/`, `.github/skills/`, or `CONTRIBUTING.md` if needed
- [ ] Followed the `copilot-authoring` skill and cited official docs or the field note that motivated the change
- [ ] Referenced upstream `awesome-copilot` artifacts for new/updated skills or agents
- [ ] Added/updated related templates or docs where appropriate

## Notes

- Automation never merges this PR. Rollback is a reviewed revert of this PR plus the
  application's documented migration/recovery procedure.
"""


def promote(runner: Runner, infra_dir: Path, version: str, run_url: str) -> str:
    """Open the promotion PR for a published chart from a k3s-infrastructure checkout.

    Returns:
        A one-line outcome: the new PR, an already-open PR, or an unchanged pin.

    Raises:
        ReleaseError: The chart is not published, first onboarding has not merged (no
            HelmRelease file), the file does not match the contract, or a promotion
            branch exists without an open PR.
    """
    source_sha, chart_digest = published_chart(runner, version)
    target = infra_dir / INFRA_HELMRELEASE_PATH
    if not target.is_file():
        raise ReleaseError(
            f"{INFRA_HELMRELEASE_PATH} does not exist in {INFRA_REPO}: first onboarding has "
            f"not merged. Chart {version} is published but NOT promoted; the reviewed "
            "first-onboarding change must pin a published version before automated "
            "promotion can succeed."
        )
    text = target.read_text(encoding="utf-8")
    updated, previous = update_helmrelease(text, version)
    if updated == text:
        return (
            f"{INFRA_HELMRELEASE_PATH} already pins {version}; no promotion PR needed"
        )

    branch = f"automation/{CHART_NAME}-chart-{version}"
    list_cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        INFRA_REPO,
        "--head",
        branch,
        "--state",
        "open",
    ]
    existing = _checked(runner, [*list_cmd, "--json", "url", "--jq", ".[].url"]).strip()
    if existing:
        return f"promotion PR already open: {existing}"
    git = ["git", "-C", str(infra_dir)]
    if _checked(runner, [*git, "ls-remote", "--heads", "origin", branch]).strip():
        raise ReleaseError(f"branch {branch} exists in {INFRA_REPO} without an open PR")

    target.write_text(updated, encoding="utf-8")
    title = f"chore({CHART_NAME}): promote {CHART_NAME} chart {version}"
    _checked(runner, [*git, "switch", "-c", branch])
    _checked(runner, [*git, "add", INFRA_HELMRELEASE_PATH])
    _checked(
        runner, [*git, "commit", "-m", title, "-m", f"Source: {APP_REPO}@{source_sha}"]
    )
    _checked(runner, [*git, "push", "origin", f"HEAD:refs/heads/{branch}"])
    body = promotion_body(version, source_sha, chart_digest, previous, run_url)
    body_file = infra_dir.parent / "promotion-body.md"
    body_file.write_text(body, encoding="utf-8")
    create_cmd = [
        "gh",
        "pr",
        "create",
        "--repo",
        INFRA_REPO,
        "--base",
        INFRA_BASE_BRANCH,
    ]
    create_cmd += ["--head", branch, "--title", title, "--body-file", str(body_file)]
    return f"opened promotion PR {_checked(runner, create_cmd).strip()}"


def _append(path: str | None, text: str) -> None:
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


def main(argv: Sequence[str] | None = None, runner: Runner = run_command) -> int:
    """Command-line entry point used by the release workflow."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    publish_cmd = commands.add_parser("publish")
    publish_cmd.add_argument("--repo", required=True)
    publish_cmd.add_argument("--trigger-sha", default="")
    promote_cmd = commands.add_parser("promote")
    promote_cmd.add_argument("--infra-dir", type=Path, required=True)
    promote_cmd.add_argument("--version", required=True)
    promote_cmd.add_argument("--run-url", required=True)
    args = parser.parse_args(argv)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    output = os.environ.get("GITHUB_OUTPUT")
    try:
        if args.command == "publish":
            published = publish(runner, args.repo, args.trigger_sha or None)
            latest = published[-1] if published else {}
            for key in ("version", "source_sha", "chart_digest"):
                _append(output, f"{key}={latest.get(key, '')}\n")
            lines = [
                f"- `{CHART_REF}:{item['version']}` (`{item['chart_digest']}`) "
                f"from `{item['source_sha']}`\n"
                for item in published
            ]
            report = "".join(lines) or "No missing chart versions to publish.\n"
            _append(summary, f"## Chart publication\n\n{report}")
            print(json.dumps(published))
        else:
            outcome = promote(runner, args.infra_dir, args.version, args.run_url)
            _append(summary, f"## Promotion\n\n{outcome}\n")
            print(outcome)
    except ReleaseError as error:
        _append(summary, f"## {args.command.capitalize()} failed\n\n{error}\n")
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
