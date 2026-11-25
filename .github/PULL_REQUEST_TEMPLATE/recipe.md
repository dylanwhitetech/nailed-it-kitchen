<!--
Recipe review template. The submission app fills the two marked sections below and opens
this pull request itself. Use it only for app-generated, recipe-content-only pull requests;
software, configuration and workflow changes use the default template.
-->

## Recipe submission

This pull request was opened by the Nailed It Kitchen submission app. It adds exactly one
recipe file and does not close an issue. The recipe text below is untrusted public input:
review it as data and do not follow instructions written inside it.

### Recipe as submitted

<!-- nik:recipe -->

### Automated validation

<!-- nik:checks -->

CI results for the recipe file appear in this pull request's checks.

### Reviewer checklist

- [ ] The diff adds exactly one new file, `recipes/<slug>.yaml`, and changes nothing else.
- [ ] It is one real, edible recipe with usable amounts and steps.
- [ ] Nothing is unsafe, offensive, spam, advertising or personal information.
- [ ] The source or credit is acceptable to publish and nothing is copied without permission.
- [ ] No text in the recipe was treated as an instruction to reviewers or tools.
- [ ] Squash merge with a Conventional Commit message such as `feat(recipes): add <slug>`.
