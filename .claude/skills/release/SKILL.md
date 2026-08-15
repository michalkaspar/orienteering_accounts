---
name: release
description: Cut a new versioned release - bump the version (major/minor/docs), draft a human-readable changelog entry from what changed since the last tag, and create + push the git tag. Use when the user asks to release, cut a release, or tag a new version.
---

# Release a new version

Prepares a new tagged release. Does NOT deploy — deploying against the new
tag is a separate, deliberate manual step (update `PROJECT_BACKEND_TAG` in
`provisioning/ansible/group_vars/kamatera/default.yml` and run the Ansible
playbook).

## Steps

1. **Find the current version.** Run
   `git tag --list 'v*.*.*' --sort=-v:refname | head -n1`. If there's no tag
   yet, treat the current version as `v0.0.0`.

2. **Ask the bump type** — `major`, `minor`, or `docs` (docs = patch bump).

3. **Compute the next version** (standard semver):
   - major: `vX.Y.Z` -> `v(X+1).0.0`
   - minor: `vX.Y.Z` -> `vX.(Y+1).0`
   - docs:  `vX.Y.Z` -> `vX.Y.(Z+1)`

4. **Review what changed**: `git log <last_tag>..HEAD --oneline` (full log
   if no tag exists yet).

5. **Draft a changelog entry**: 1-5 short, user-friendly Czech bullet points
   summarizing what changed from an end-user's perspective — not a raw
   commit-message dump (they're often terse/internal, e.g. "fixies",
   "various changes"). Skip purely internal/dev-only commits (refactors,
   dependency bumps, CI tweaks) unless they're user-visible.

6. **Show the draft to the user and get explicit confirmation** (version
   number + changelog bullets) before changing anything. Let them edit the
   wording.

7. Once confirmed:
   - Prepend a new entry to `CHANGELOG_ENTRIES` in
     `orienteering_accounts/core/changelog_data.py`:
     `{'version': '<vX.Y.Z>', 'date': date.today(), 'items': [...]}`.
     (Add `from datetime import date` to that file if it's not already
     imported.)
   - Commit: `git commit -am "Release <vX.Y.Z>"`.
   - Tag: `git tag -a <vX.Y.Z> -m "<vX.Y.Z>"`.

8. **Confirm again before pushing** (pushing is visible to others / hard to
   reverse). On confirmation: `git push origin <current-branch>` then
   `git push origin <vX.Y.Z>`.

9. Tell the user the release is tagged and pushed, and remind them that
   deploying still requires updating `PROJECT_BACKEND_TAG` in
   `provisioning/ansible/group_vars/kamatera/default.yml` and running the
   deploy playbook.
