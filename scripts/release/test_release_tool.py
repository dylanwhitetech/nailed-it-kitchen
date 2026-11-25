import json
import subprocess
import tarfile
from pathlib import Path

import pytest
import release_tool as rt
import yaml

SHA = "a" * 40
OTHER_SHA = "b" * 40
DIGEST = "sha256:" + "1" * 64
CHART_DIGEST = "sha256:" + "2" * 64
TARGET_PATH = "kubernetes/apps/naileditkitchen/helmrelease.yaml"

CHART_YAML = """apiVersion: v2
name: naileditkitchen
description: Nailed It Kitchen
version: 0.2.0 # x-release-please-version
appVersion: "unreleased"
sources:
  - https://github.com/dylanwhitetech/nailed-it-kitchen
"""

VALUES_YAML = """# Images default to the chart appVersion tag.
api:
  image:
    repository: ghcr.io/dylanwhitetech/naileditkitchen-api
    tag: "" # defaults to appVersion
    digest: ""
web:
  image:
    repository: ghcr.io/dylanwhitetech/naileditkitchen-web
    tag: ""
    digest: ""
"""

HELMRELEASE = """---
apiVersion: v1
kind: Namespace
metadata:
  name: naileditkitchen
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: naileditkitchen
  namespace: naileditkitchen
spec:
  interval: 30m
  chart:
    spec:
      chart: naileditkitchen
      version: "0.1.0" # pinned by promotion PRs
      sourceRef:
        kind: HelmRepository
        name: naileditkitchen-charts
        namespace: flux-system
"""


def done(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeRunner:
    """Answers commands by prefix and records every call."""

    def __init__(self, handlers):
        self.handlers = handlers
        self.calls = []

    def __call__(self, cmd):
        cmd = list(cmd)
        self.calls.append(cmd)
        joined = " ".join(cmd)
        for prefix, handler in self.handlers:
            if joined.startswith(prefix):
                return handler(cmd) if callable(handler) else handler
        raise AssertionError(f"unexpected command: {joined}")

    def ran(self, prefix):
        return [call for call in self.calls if " ".join(call).startswith(prefix)]


def image_manifest(revision=SHA, platforms=("amd64", "arm64")):
    manifests = [
        {"platform": {"os": "linux", "architecture": arch}} for arch in platforms
    ]
    manifests.append({"platform": {"os": "unknown", "architecture": "unknown"}})
    return json.dumps(
        {
            "digest": DIGEST,
            "manifests": manifests,
            "annotations": {"org.opencontainers.image.revision": revision},
        }
    )


def test_set_yaml_scalar_preserves_comments_and_quotes():
    updated = rt.set_yaml_scalar(VALUES_YAML, ["api", "image", "tag"], SHA)
    assert f'    tag: "{SHA}" # defaults to appVersion' in updated
    assert updated.startswith("# Images default")
    assert yaml.safe_load(updated)["web"]["image"]["tag"] == ""


def test_set_yaml_scalar_quotes_values_that_would_not_load_as_strings():
    updated = rt.set_yaml_scalar(
        "version: 1.0.0 # x-release-please-version\n", ["version"], "123"
    )
    assert updated == 'version: "123" # x-release-please-version\n'


def test_set_yaml_scalar_edits_the_requested_document_only():
    updated = rt.set_yaml_scalar(HELMRELEASE, ["metadata", "name"], "other", document=1)
    docs = list(yaml.safe_load_all(updated))
    assert docs[0]["metadata"]["name"] == "naileditkitchen"
    assert docs[1]["metadata"]["name"] == "other"


@pytest.mark.parametrize(
    ("text", "path"),
    [
        ("api:\n  tag: x\n", ["web", "tag"]),
        ("api: {tag: x}\n", ["api", "tag"]),
        ("api:\n  tag: |\n    x\n", ["api", "tag"]),
    ],
)
def test_set_yaml_scalar_rejects_missing_or_unsupported_layouts(text, path):
    with pytest.raises(rt.ReleaseError):
        rt.set_yaml_scalar(text, path, "y")


def test_inspect_image_returns_index_digest():
    runner = FakeRunner([("docker buildx", done(stdout=image_manifest()))])
    image = rt.inspect_image(runner, "api", SHA)
    assert image == rt.Image(
        "api", "ghcr.io/dylanwhitetech/naileditkitchen-api", DIGEST
    )
    assert runner.calls[0][4] == f"ghcr.io/dylanwhitetech/naileditkitchen-api:{SHA}"


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (done(1, stderr="ERROR: x: not found"), rt.ImagesNotPublished),
        (done(1, stderr="denied"), rt.ReleaseError),
        (done(stdout=image_manifest(platforms=("amd64",))), rt.ReleaseError),
        (done(stdout=image_manifest(revision=OTHER_SHA)), rt.ReleaseError),
    ],
)
def test_inspect_image_rejects_missing_or_wrong_images(result, error):
    with pytest.raises(error):
        rt.inspect_image(FakeRunner([("docker", result)]), "api", SHA)


def test_publish_image_version_creates_and_verifies_alias():
    image = IMAGES[0]
    responses = iter(
        [done(1, stderr="not found"), done(), done(stdout=image_manifest())]
    )
    runner = FakeRunner([("docker buildx", lambda cmd: next(responses))])
    rt.publish_image_version(runner, image, "0.2.0", SHA)
    assert runner.calls[1] == [
        "docker",
        "buildx",
        "imagetools",
        "create",
        "--tag",
        f"{image.repository}:0.2.0",
        f"{image.repository}@{DIGEST}",
    ]
    assert runner.calls[2][4] == f"{image.repository}:0.2.0"


def test_publish_image_version_never_overwrites_existing_alias():
    image = IMAGES[0]
    runner = FakeRunner([("docker buildx", done(stdout=image_manifest()))])
    rt.publish_image_version(runner, image, "0.2.0", SHA)
    assert len(runner.calls) == 1
    wrong = image_manifest().replace(DIGEST, CHART_DIGEST)
    runner = FakeRunner([("docker buildx", done(stdout=wrong))])
    with pytest.raises(rt.ReleaseError, match="refusing to overwrite"):
        rt.publish_image_version(runner, image, "0.2.0", SHA)
    assert len(runner.calls) == 1


def test_publish_image_version_verifies_alias_after_creation():
    responses = iter(
        [
            done(1, stderr="not found"),
            done(),
            done(stdout=image_manifest().replace(DIGEST, CHART_DIGEST)),
        ]
    )
    runner = FakeRunner([("docker buildx", lambda cmd: next(responses))])
    with pytest.raises(rt.ReleaseError, match="refusing to overwrite"):
        rt.publish_image_version(runner, IMAGES[0], "0.2.0", SHA)


def test_missing_alias_after_creation_is_not_mistaken_for_missing_ci_image():
    responses = iter([done(1, stderr="not found"), done(), done(1, stderr="not found")])
    runner = FakeRunner([("docker buildx", lambda cmd: next(responses))])
    with pytest.raises(rt.ImageTagNotFound, match="image version tag"):
        rt.publish_image_version(runner, IMAGES[0], "0.2.0", SHA)


def test_chart_exists_distinguishes_missing_from_errors():
    assert rt.chart_exists(FakeRunner([("helm", done())]), "0.1.0")
    assert not rt.chart_exists(
        FakeRunner([("helm", done(1, stderr="x: not found"))]), "0.1.0"
    )
    with pytest.raises(rt.ReleaseError):
        rt.chart_exists(FakeRunner([("helm", done(1, stderr="unauthorized"))]), "0.1.0")


def write_chart(root: Path, chart=CHART_YAML, values=VALUES_YAML) -> Path:
    chart_dir = root / rt.CHART_DIR
    chart_dir.mkdir(parents=True)
    (chart_dir / "Chart.yaml").write_text(chart, encoding="utf-8")
    (chart_dir / "values.yaml").write_text(values, encoding="utf-8")
    return chart_dir


IMAGES = [
    rt.Image("api", "ghcr.io/dylanwhitetech/naileditkitchen-api", DIGEST),
    rt.Image("web", "ghcr.io/dylanwhitetech/naileditkitchen-web", DIGEST),
]


def test_prepare_chart_pins_source_sha_and_digests(tmp_path):
    chart_dir = write_chart(tmp_path)
    rt.prepare_chart(chart_dir, "0.2.0", SHA, IMAGES)
    chart_text = (chart_dir / "Chart.yaml").read_text(encoding="utf-8")
    values = yaml.safe_load((chart_dir / "values.yaml").read_text(encoding="utf-8"))
    assert yaml.safe_load(chart_text)["appVersion"] == SHA
    assert "version: 0.2.0 # x-release-please-version" in chart_text
    for component in ("api", "web"):
        assert values[component]["image"]["tag"] == SHA
        assert values[component]["image"]["digest"] == DIGEST


@pytest.mark.parametrize(
    ("chart", "values"),
    [
        (CHART_YAML.replace("0.2.0", "0.1.0"), VALUES_YAML),
        (CHART_YAML.replace("name: naileditkitchen", "name: other"), VALUES_YAML),
        (CHART_YAML.split("sources:")[0], VALUES_YAML),
        (CHART_YAML, VALUES_YAML.replace("naileditkitchen-web", "other-web")),
    ],
)
def test_prepare_chart_rejects_contract_mismatches(tmp_path, chart, values):
    with pytest.raises(rt.ReleaseError):
        rt.prepare_chart(write_chart(tmp_path, chart, values), "0.2.0", SHA, IMAGES)


def releases_json(*tags):
    return json.dumps(
        [{"tag_name": tag, "draft": False, "prerelease": False} for tag in tags]
        + [{"tag_name": "v9.9.9", "draft": True, "prerelease": False}]
        + [{"tag_name": "v8.0.0-rc.1", "draft": False, "prerelease": True}]
    )


def git_archive(cmd):
    output = Path(cmd[3].removeprefix("--output="))
    source = output.parent / "fixture"
    write_chart(
        source,
        CHART_YAML.replace("0.2.0", "0.1.0") if cmd[4] == OTHER_SHA else CHART_YAML,
    )
    with tarfile.open(output, "w") as tar:
        tar.add(source / rt.CHART_DIR, arcname=rt.CHART_DIR)
    return done()


def release_runner(published_versions, image_shas=(SHA, OTHER_SHA)):
    aliases = {}

    def commit(cmd):
        return done(stdout=(OTHER_SHA if "v0.1.0" in cmd[2] else SHA) + "\n")

    def show(cmd):
        found = cmd[-1] in published_versions
        return done() if found else done(1, stderr="x: not found")

    def inspect(cmd):
        ref = cmd[4]
        tag = ref.rsplit(":", 1)[1]
        sha = aliases.get(ref, tag)
        if sha not in image_shas:
            return done(1, stderr="ERROR: not found")
        return done(stdout=image_manifest(revision=sha))

    def create(cmd):
        ref = cmd[cmd.index("--tag") + 1]
        tag = ref.rsplit(":", 1)[1]
        aliases[ref] = OTHER_SHA if tag == "0.1.0" else SHA
        return done()

    return FakeRunner(
        [
            (
                "gh api repos/o/r/releases",
                done(stdout=releases_json("v0.2.0", "v0.1.0")),
            ),
            ("gh api repos/o/r/commits", commit),
            ("helm show chart", show),
            ("docker buildx imagetools inspect", inspect),
            ("docker buildx imagetools create", create),
            ("git archive", git_archive),
            ("helm lint", done()),
            ("helm package", done()),
            ("helm push", done(stderr=f"Pushed: x\nDigest: {CHART_DIGEST}\n")),
        ]
    )


def test_publish_reconciles_missing_versions_oldest_first_and_skips_published():
    runner = release_runner(published_versions={"0.1.0"})
    published = rt.publish(runner, "o/r", SHA)
    assert published == [
        {"version": "0.2.0", "source_sha": SHA, "chart_digest": CHART_DIGEST}
    ]
    assert [call[-1] for call in runner.ran("helm show chart")] == ["0.1.0", "0.2.0"]
    assert len(runner.ran("helm push")) == 1
    assert len(runner.ran("docker buildx imagetools create")) == 2

    runner = release_runner(published_versions=set())
    assert [item["version"] for item in rt.publish(runner, "o/r", SHA)] == [
        "0.1.0",
        "0.2.0",
    ]


def test_publish_defers_other_commits_without_images_but_fails_for_the_trigger():
    runner = release_runner(published_versions={"0.1.0"}, image_shas=())
    assert rt.publish(runner, "o/r", OTHER_SHA) == []
    assert not runner.ran("helm push")
    with pytest.raises(rt.ImagesNotPublished):
        rt.publish(release_runner({"0.1.0"}, image_shas=()), "o/r", SHA)
    with pytest.raises(rt.ImagesNotPublished):
        rt.publish(release_runner({"0.1.0"}, image_shas=()), "o/r", None)


def test_update_helmrelease_bumps_only_the_pin():
    updated, previous = rt.update_helmrelease(HELMRELEASE, "0.2.0")
    assert previous == "0.1.0"
    assert '      version: "0.2.0" # pinned by promotion PRs' in updated
    assert updated.replace('"0.2.0"', '"0.1.0"') == HELMRELEASE
    assert rt.update_helmrelease(HELMRELEASE, "0.1.0") == (HELMRELEASE, "0.1.0")


@pytest.mark.parametrize(
    ("text", "version"),
    [
        (HELMRELEASE, "0.0.9"),
        (
            HELMRELEASE.replace("namespace: naileditkitchen", "namespace: other"),
            "0.2.0",
        ),
        (HELMRELEASE.replace("chart: naileditkitchen", "chart: other"), "0.2.0"),
    ],
)
def test_update_helmrelease_rejects_downgrades_and_unexpected_files(text, version):
    with pytest.raises(rt.ReleaseError):
        rt.update_helmrelease(text, version)


def promote_runner(open_pr="", remote_branch="", published=True):
    show = done(
        stdout=f"name: naileditkitchen\nversion: 0.2.0\nappVersion: {SHA}\n",
        stderr=f"Pulled: x\nDigest: {CHART_DIGEST}\n",
    )
    return FakeRunner(
        [
            ("helm show chart", show if published else done(1, stderr="x: not found")),
            ("gh pr list", done(stdout=open_pr)),
            (
                "git -C",
                lambda cmd: done(stdout=remote_branch if "ls-remote" in cmd else ""),
            ),
            ("gh pr create", done(stdout="https://github.com/o/infra/pull/7\n")),
        ]
    )


def infra_checkout(tmp_path, text=HELMRELEASE):
    infra = tmp_path / "infra"
    target = infra / TARGET_PATH
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    return infra, target


def test_promote_without_onboarded_helmrelease_fails_loudly(tmp_path):
    (tmp_path / "infra").mkdir()
    with pytest.raises(rt.ReleaseError, match="published but NOT promoted"):
        rt.promote(promote_runner(), tmp_path / "infra", "0.2.0", "url", TARGET_PATH)


@pytest.mark.parametrize(
    "path", ["", "../outside.yaml", "/absolute.yaml", "kubernetes/apps/../../x.yaml"]
)
def test_promote_rejects_invalid_paths_before_registry_access(tmp_path, path):
    runner = FakeRunner([])
    with pytest.raises(rt.ReleaseError, match="configure a HelmRelease YAML path"):
        rt.promote(runner, tmp_path / "infra", "0.2.0", "url", path)
    assert runner.calls == []


def test_promote_requires_a_published_chart(tmp_path):
    infra, _ = infra_checkout(tmp_path)
    with pytest.raises(rt.ReleaseError, match="not available"):
        rt.promote(promote_runner(published=False), infra, "0.2.0", "url", TARGET_PATH)


def test_promote_opens_a_pr_and_never_merges(tmp_path):
    infra, target = infra_checkout(tmp_path)
    runner = promote_runner()
    outcome = rt.promote(runner, infra, "0.2.0", "https://run", TARGET_PATH)
    assert outcome == "opened promotion PR https://github.com/o/infra/pull/7"
    assert '"0.2.0"' in target.read_text(encoding="utf-8")
    branch = "automation/naileditkitchen-chart-0.2.0"
    git = ["git", "-C", str(infra)]
    assert [*git, "switch", "-c", branch] in runner.calls
    assert [*git, "push", "origin", f"HEAD:refs/heads/{branch}"] in runner.calls
    create = runner.ran("gh pr create")[0]
    assert (
        create[create.index("--title") + 1]
        == "chore(naileditkitchen): promote naileditkitchen chart 0.2.0"
    )
    body = (tmp_path / "promotion-body.md").read_text(encoding="utf-8")
    assert SHA in body and CHART_DIGEST in body and "never merges" in body
    assert not any("merge" in call for call in runner.calls)


def test_promote_reports_existing_pr_and_noop(tmp_path):
    infra, target = infra_checkout(tmp_path)
    runner = promote_runner(open_pr="https://github.com/o/infra/pull/6\n")
    assert rt.promote(runner, infra, "0.2.0", "url", TARGET_PATH).endswith("pull/6")
    call = runner.ran("gh pr list")[0]
    assert call[call.index("--base") + 1] == "main"
    assert (
        call[call.index("--head") + 1]
        == "dylanwhitetech:automation/naileditkitchen-chart-0.2.0"
    )
    assert target.read_text(encoding="utf-8") == HELMRELEASE
    assert "already pins" in rt.promote(
        promote_runner(), infra, "0.1.0", "url", TARGET_PATH
    )


def test_promote_refuses_a_stale_branch_without_pr(tmp_path):
    infra, _ = infra_checkout(tmp_path)
    with pytest.raises(rt.ReleaseError, match="without an open PR"):
        rt.promote(
            promote_runner(remote_branch="abc refs/heads/x"),
            infra,
            "0.2.0",
            "url",
            TARGET_PATH,
        )


def test_main_writes_outputs_and_returns_failure(tmp_path, monkeypatch):
    output = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    runner = release_runner(published_versions={"0.1.0"})
    assert rt.main(["publish", "--repo", "o/r", "--trigger-sha", SHA], runner) == 0
    assert (
        output.read_text()
        == f"version=0.2.0\nsource_sha={SHA}\nchart_digest={CHART_DIGEST}\n"
    )
    (tmp_path / "infra").mkdir()
    args = ["promote", "--infra-dir", str(tmp_path / "infra"), "--version", "0.2.0"]
    assert (
        rt.main(
            [*args, "--run-url", "u", "--helmrelease-path", TARGET_PATH],
            promote_runner(),
        )
        == 1
    )


def test_release_workflow_guards_privileged_jobs():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load(
        (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    triggers = workflow["on"]
    assert set(triggers) == {"workflow_run", "workflow_dispatch"}
    assert triggers["workflow_run"]["workflows"] == ["CI"]
    assert triggers["workflow_run"]["branches"] == ["main"]
    guard = workflow["jobs"]["release-please"]["if"]
    assert "github.event.workflow_run.conclusion == 'success'" in guard
    assert "github.event.workflow_run.event == 'push'" in guard
    assert (
        "github.event.workflow_run.head_repository.full_name == github.repository"
        in guard
    )
    assert (
        "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'"
        in guard
    )
    assert workflow["permissions"] == {}
    assert workflow["jobs"]["publish"]["needs"] == "release-please"
    assert workflow["jobs"]["promote"]["needs"] == "publish"
    ci = yaml.load(
        (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert "release-tooling" in ci["jobs"]["image-publish"]["needs"]
