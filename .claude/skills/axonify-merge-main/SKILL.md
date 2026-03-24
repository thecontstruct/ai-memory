---
name: axonify-merge-main
description: 'Fork workflow: sync main from upstream, then integrate into axonify/main with decision-first merge/rebase choices'
allowed-tools: Bash, Read, Grep
---

# Axonify Main Sync

Update the fork's `main` from `upstream/main`, then integrate that refreshed `main`
into `axonify/main`.

This skill is repo-local to the `ai-memory` checkout. It is not meant to be
installed into `$INSTALL_DIR`.

## Assumptions

- Run from the `ai-memory` repository root.
- `origin` points at the Axonify fork.
- `upstream` points at the canonical `Hidden-History/ai-memory` repository.
- `axonify/main` already exists locally or on `origin`.

If `upstream` does not exist, fall back to `origin/main` and skip the upstream
sync steps.

## Workflow

### 1. Preflight

```bash
git status --short --branch
git remote -v
git fetch origin
if git remote get-url upstream >/dev/null 2>&1; then
  git fetch upstream
fi
git rev-parse --verify origin/axonify/main
```

- Confirm the working tree is clean, or stash/commit intentionally.
- Confirm `origin` is the fork and `upstream` is canonical.
- Confirm `origin/axonify/main` exists before relying on this workflow.

### 2. Sync `main` First

```bash
git checkout main
git merge --ff-only upstream/main
git push origin main
```

If `git merge --ff-only upstream/main` fails:

- Use `git reset --hard upstream/main` only when local `main` has no intentional divergence.
- Otherwise use `git merge upstream/main`, resolve conflicts, verify, then push.

When `upstream` is absent:

```bash
git checkout main
git pull --ff-only origin main
```

### 3. Verify `main`

When `upstream` exists:

```bash
git log -1 --oneline main
git log -1 --oneline upstream/main
git log -1 --oneline origin/main
```

When `upstream` is absent:

```bash
git log -1 --oneline main
git log -1 --oneline origin/main
```

Treat `MAIN=main` for every command below after this verification.

### 4. Inspect Divergence

```bash
git checkout axonify/main
git fetch origin
git log --oneline main..axonify/main
git log --oneline axonify/main..main
git diff main...axonify/main --stat
```

Use the results to choose one of these paths:

- **Upstream-dominant**: upstream changes obsolete Axonify-specific work. Merge `main`, then drop or rewrite obsolete Axonify-only changes.
- **Hybrid**: merge `main` into `axonify/main`, resolve conflicts carefully, keep needed Axonify changes.
- **Axonify-dominant / replay**: rebase or replay Axonify-only commits on top of refreshed `main` when history rewrite is acceptable.

### 5. Default Path

Default to a merge:

```bash
git checkout axonify/main
git merge --no-ff main
```

Use rebase only when every commit ahead of `main` is local-only and rewriting
`axonify/main` is acceptable:

```bash
git log origin/axonify/main..axonify/main
git log main..axonify/main
git branch "backup/axonify-main-$(date +%Y%m%d-%H%M%S)"
git rebase main
git push --force-with-lease origin axonify/main
```

### 6. Resolve And Verify

- List conflicted files and resolve them deliberately.
- Run `npm test` only when `package.json` exists and defines a `test` script.
- Run `shellcheck scripts/*.sh` only when the glob matches at least one file.
- Never commit secrets or tokens.

Example guards:

```bash
if [ -f package.json ] && npm run | grep -qE '(^| )test( |$)'; then
  npm test
fi

(
  shopt -s nullglob
  scripts=(scripts/*.sh)
  if [ "${#scripts[@]}" -gt 0 ]; then
    shellcheck "${scripts[@]}"
  fi
)
```

### 7. Push

```bash
git push origin axonify/main
```

## Greenfield Only

If `axonify/main` does not already exist, create or attach it after `main` has
been synced:

```bash
git fetch origin
if git rev-parse --verify axonify/main >/dev/null 2>&1 && git rev-parse --verify origin/axonify/main >/dev/null 2>&1; then
  git checkout axonify/main
elif git rev-parse --verify origin/axonify/main >/dev/null 2>&1; then
  git checkout -b axonify/main --track origin/axonify/main
elif git rev-parse --verify axonify/main >/dev/null 2>&1; then
  git checkout axonify/main
else
  git checkout -b axonify/main main
  git push -u origin axonify/main
fi
```
