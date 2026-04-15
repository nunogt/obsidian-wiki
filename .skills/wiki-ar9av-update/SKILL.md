---
name: wiki-ar9av-update
description: >
  Maintain the operator's fork of obsidian-wiki by fetching upstream Ar9av/obsidian-wiki,
  rebasing the fork's local patches on top, and force-with-lease pushing the result.
  Then regenerate kb-system contexts so new upstream skills propagate to every profile.
  Use this skill when the user says "update ar9av", "update the fork", "rebase on
  upstream", "pull upstream", "sync fork", or periodically (weekly) to keep the fork
  current. Replaces the retired kb-system/scripts/wiki-ar9av-update shell script.
  Triggers: /wiki-ar9av-update, "rebase our patches onto upstream", "check for new
  upstream commits".
---

# Wiki-AR9AV-Update — Safe Upstream Pull for the Fork

You are maintaining the operator's fork of `Ar9av/obsidian-wiki` by rebasing
our local patches (relative symlinks, in-vault sources exclusion, CWD-first
config ordering, `wiki-update` removal, `setup.sh` retirement) onto each
upstream pull. This skill is **fork-specific** — only run it in deployments
that carry the `nunogt/obsidian-wiki` fork (or equivalent). Stock upstream
clones have no `upstream` remote and nothing to rebase.

## Before You Start

1. Read `.env` in CWD (multi-vault contexts) or `~/.obsidian-wiki/config` (single-vault) to confirm you're in a deployment that uses the fork
2. Locate the fork: default path is `/mnt/host/shared/git/obsidian-wiki/`. If the operator has a non-standard layout, ask.
3. Locate kb-system: default `/mnt/host/shared/git/kb-system/`. If not present, warn and continue — regen step will be skipped.
4. Verify the fork has an `upstream` remote configured:
   ```bash
   git -C /mnt/host/shared/git/obsidian-wiki remote get-url upstream
   ```
   If missing, instruct the operator to add it:
   ```bash
   git -C /mnt/host/shared/git/obsidian-wiki remote add upstream https://github.com/Ar9av/obsidian-wiki.git
   ```
   and abort until they do.

## Step 1: Fetch upstream

```bash
git -C $REPO fetch upstream
```

## Step 2: Preview incoming commits

```bash
git -C $REPO log main..upstream/main --oneline
```

If output is empty:
- Report: "✓ already current with upstream/main (<short-sha>)."
- Still call `kb-contexts-regenerate` as a safety-net refresh.
- Exit.

Otherwise, enumerate the incoming commits for the operator. Also compute:
- Whether `setup.sh` changed upstream (we deleted it locally — any upstream change triggers a rebase conflict)
- Whether `.skills/*/SKILL.md` files we've patched changed upstream (wiki-ingest, wiki-query, and the SKILL.md files touched by Patch C — cross-linker, tag-taxonomy, wiki-export, wiki-lint, wiki-status, wiki-setup)
- Whether `.skills/wiki-update/` changed upstream (we deleted it locally)

Warn the operator about any of these — rebase conflict likely.

## Step 3: Confirm with operator

Before any state change:

> Rebase our fork's patches onto upstream/main and force-with-lease push?
> Incoming commits:
>   <list>
> Potential conflict paths: <list>
> [y/N]

Abort on anything other than explicit `y` / `yes`.

## Step 4: Tag a rollback point

```bash
rollback_tag="pre-update-$(date +%Y%m%d-%H%M%S)"
git -C $REPO tag -f "$rollback_tag" main
```

Report the tag to the operator — it's the escape hatch.

## Step 5: Rebase main onto upstream/main

```bash
git -C $REPO checkout main
git -C $REPO rebase upstream/main
```

If the rebase reports conflicts:
- Do NOT attempt to auto-resolve them
- Report each conflict file to the operator with a brief description of our local patch for that file
- Tell the operator to resolve in `$REPO`, then either `git rebase --continue` or `git rebase --abort`
- Provide the rollback command: `cd $REPO && git rebase --abort && git reset --hard $rollback_tag`
- Exit the skill; don't proceed to push

## Step 6: Force-with-lease push to the fork

```bash
git -C $REPO push --force-with-lease origin main
```

`--force-with-lease` refuses the push if `origin/main` has commits we don't know about. Safe default. If it fails, it means something pushed to the fork between our fetch and push — investigate before force-pushing.

## Step 7: Regenerate kb-system contexts

```bash
if [ -x "$KB_SYSTEM/scripts/kb-contexts-regenerate" ]; then
  "$KB_SYSTEM/scripts/kb-contexts-regenerate"
fi
```

This catches any new upstream skills (they get symlinked into every context) and prunes symlinks for skills that upstream removed.

## Step 8: Next-step reminder

Tell the operator:

> ✓ fork synced with upstream ($new_sha). Our local patches replayed cleanly on top.
>
> Recommended next: run `/wiki-lint` from inside each vault context to catch
> any schema migrations (ar9av's "lint-is-the-migration" principle).
>
>   cd /mnt/host/shared/git/kb-system/contexts/<profile> && claude --dangerously-skip-permissions
>   > lint the wiki and commit
>
> Rollback (if anything breaks post-push):
>   cd $REPO && git reset --hard $rollback_tag && git push --force-with-lease origin main
>   cd $KB_SYSTEM && scripts/kb-contexts-regenerate

## Rollback details

The operator can undo a completed update any time:

```bash
git -C $REPO reset --hard pre-update-<timestamp>
git -C $REPO push --force-with-lease origin main
cd $KB_SYSTEM && scripts/kb-contexts-regenerate
```

If mid-rebase (conflict not resolved):
```bash
git -C $REPO rebase --abort
# Then optionally: git -C $REPO reset --hard pre-update-<timestamp>
```

## Suggested cadence

**Weekly**, or on a GitHub notification highlighting a meaningful upstream
change. `Ar9av/obsidian-wiki` typically commits a few times per week — low
burden.

## What this skill won't do

- Run unattended — every invocation has a y/N confirm gate before any state change
- Auto-resolve rebase conflicts — our patches are small and surgical; on the
  rare conflict, human judgment is needed
- Create the `upstream` remote if missing — tells the operator the exact
  `git remote add` command instead
- Push without `--force-with-lease` — never plain `--force`
- Run on a non-fork deployment (no `upstream` remote) — warns and aborts

## Invocation examples

From any context directory (CWD doesn't matter for this skill — it operates
on the fork, not the vault):

```
cd /mnt/host/shared/git/kb-system/contexts/wiki
claude --dangerously-skip-permissions
> /wiki-ar9av-update
```

Or for scripted/cron invocation:

```bash
cd /mnt/host/shared/git/kb-system/contexts/wiki
claude --print --dangerously-skip-permissions "/wiki-ar9av-update"
```

(Note: in scripted mode, the y/N confirm gate still applies — the skill
will abort if running non-interactively without input. For fully-automated
upstream pulls, the operator would need to either add a `--yes` mode to
this skill or script around it with `yes y | claude --print ...`.)

## Relation to the retired shell script

This skill supersedes `kb-system/scripts/wiki-ar9av-update`, which was a
bash script doing the same flow. The shell script was deleted as part of
the 2026-04-15 legacy cleanup (see `kb-system/docs/LEGACY-CLEANUP-PROPOSAL.md`
Patch G).

Rationale for the migration: the script's logic is a sequence of `git`
calls, a y/N prompt, and a subprocess invocation — all of which a Claude
session can do. Making it a skill puts the maintenance logic in the same
place as the code it maintains (the fork's `.skills/`), and enables
richer interaction (summarizing incoming commits, warning about specific
conflict risks with context on our patches) that a bash script couldn't
do as naturally.
