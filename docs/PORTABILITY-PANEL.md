# kb-system portability refactor — expert-panel deliberation

*Drafted 2026-04-15. Operator asked for a "world-class expert panel" to deliberate on how to make `kb-system` portable across machines (dev VM + work laptop + potentially others) before executing the refactor. Five experts with distinct lenses: patterns (Fowler), 12-factor / cloud-native (Hightower), classic Unix (Kernighan), multi-machine dev environments (Hashimoto), operational rigor (Cantrill).*

---

## 0. The problem, in one paragraph

`kb-system` currently has `/mnt/host/shared/git/` hardcoded in seven files: two scripts (`kb-vault-new`, `kb-contexts-regenerate`), two templates (`profile.env`, `claude-settings.json`), and three already-committed profiles (`wiki.env`, `personal.env`, `ebury.env`). Running from a second machine (operator's work laptop) requires either replicating the path layout exactly (feasible but fragile) or making the system aware of a configurable root. The operator has chosen the latter (Option B from the portability discussion). This panel deliberates on *how* to make the system portable — not *whether*.

Four meta-questions frame the refactor. Each has 3-4 concrete options.

---

## 1. The four meta-questions

### Q1. Profile format

How should `profiles/<name>.env` files be written and stored?

- **(1a)** Committed with absolute paths (current state); per-machine scripts override paths via environment elsewhere
- **(1b)** Committed with `{GIT_ROOT}` placeholder; `kb-contexts-regenerate` substitutes at materialization time
- **(1c)** Committed with env-var references like `OBSIDIAN_VAULT_PATH=${KB_GIT_ROOT}/kb-ebury`; shell expands at runtime
- **(1d)** Committed machine-agnostic (no paths at all); separate `profiles/<name>.local.env` overlay per machine with paths

### Q2. `KB_GIT_ROOT` origin

Where does the "root directory" value come from on each machine?

- **(2a)** Per-machine shell rc exports `KB_GIT_ROOT=...` in `.bashrc`/`.zshrc`
- **(2b)** Derived from script location — `KB_GIT_ROOT=$(dirname $(dirname $(realpath "$0")))` (the kb-system dir's parent)
- **(2c)** Separate config file at `~/.kb-system/config` or `~/.config/kb-system/config`
- **(2d)** XDG base directory convention with a kb-system-specific subdir

### Q3. Contexts materialization

How should `contexts/<vault>/` be built?

- **(3a)** Materialize all paths at regen time — `.env` becomes a real file with absolute paths substituted in; `settings.json` is a real file with absolute hook-command paths; contexts become frozen config
- **(3b)** Symlink profiles as-is; rely on shell expansion of `${KB_GIT_ROOT}` in `.env` at runtime
- **(3c)** Hybrid — `.env` symlinked to canonical profile (with placeholders), `settings.json` materialized (because it's read by Claude Code, which doesn't expand env vars in JSON)

### Q4. Hook command paths in `claude-settings.json`

How do hook-script absolute paths get into the settings file Claude Code reads?

- **(4a)** Materialize at regen time — settings.json in contexts has absolute paths baked in
- **(4b)** Use Claude Code's `${CLAUDE_PROJECT_DIR}` substitution (documented in hooks.md) — `"command": "python3 ${CLAUDE_PROJECT_DIR}/../../scripts/hooks/stop_append.py"`
- **(4c)** Install hook scripts to `~/.local/bin/kb-hook-*` and reference by bare name (`"command": "kb-hook-stop-append"`)

---

## 2. Panel introductions

### Martin Fowler — patterns
*Author of Refactoring, Patterns of Enterprise Application Architecture, The Reasonable Software Engineer. Chief Scientist at Thoughtworks. His lens here: externalized configuration as a pattern; the boundary between "what's committed" and "what's machine-specific" should be explicit and minimal.*

### Kelsey Hightower — cloud-native
*Longtime Google engineer, now independent. Author of Kubernetes the Hard Way, outspoken advocate for the 12-factor app methodology. His lens here: config belongs in the environment, not in files; whenever files are inherent (as with Claude Code's `.claude/settings.json`), treat them as outputs of config-driven tooling, not sources.*

### Brian Kernighan — classic Unix
*Co-author of The C Programming Language and The Unix Programming Environment. Bell Labs Unix pioneer. His lens here: simplicity, composability, "the Unix way." Scripts should work with minimal ceremony. Derive what you can; configure only what you can't derive.*

### Mitchell Hashimoto — multi-machine dev environments
*Founder of HashiCorp. Creator of Vagrant, Packer, Terraform, Consul, Nomad. His lens here: reproducible environments across machines, with a strict separation between "what's committed" (the machine-agnostic recipe) and "what varies per machine" (local overlay).*

### Bryan Cantrill — ops rigor
*DTrace co-creator (Sun), former Joyent CTO, current Oxide Computer CTO. Known for talks on operational honesty and explicit debuggability. His lens here: configuration should be grep-able, materialization should produce inspectable artifacts, runtime indirection is a debugging hazard.*

---

## 3. Position statements

### Q1 — Profile format

**Fowler:** *"Externalized configuration is about making the coupling between code and environment explicit. Hardcoded paths (1a) embed environment in what should be shared code. Shell expansion inside `.env` files (1c) creates runtime indirection — the value is resolved somewhere else, at some other time, under rules I can't see from the committed file. **(1b) is the cleanest**: the placeholder is visible in the committed file, the substitution happens at a well-defined step (regen), the output is inspectable. The overlay pattern (1d) is sound for larger systems where per-machine config genuinely diverges, but here the only thing that varies is the root path — splitting into two files for that is over-engineering."*

Position: **(1b)**.

**Hightower:** *"Twelve-factor says store config in the environment, not in the codebase. For a CLI tool where files are the config medium (Claude Code reads `.claude/settings.json`; the operator can't pass it an env var), the principle adapts: treat committed files as templates, not config. **(1b) is the pragmatic instantiation** — placeholder templates live in version control, the build step (`kb-contexts-regenerate`) is config-driven, and the output is per-machine. I'd push against (1c) specifically: `.env` files aren't reliably shell-expanded by every parser that reads them. The Python `_common.py` hook helper uses manual regex parsing — it wouldn't expand `${KB_GIT_ROOT}` unless we wrote that code, and that code is a maintenance tax."*

Position: **(1b)**.

**Kernighan:** *"The simplest answer: don't commit paths at all, let the scripts derive them. But since Claude Code reads `.env` files independently and you can't shell-out during that read, you need materialization somewhere. Given that, placeholders (1b) are fine — just make sure the substitution is obvious. I'd resist (1d)'s two-file dance; the cognitive load of 'which file wins for this key' is more than this problem deserves."*

Position: **(1b)**, with mild preference for derivation-where-possible.

**Hashimoto:** *"I'll push back. Vagrant's split-file pattern exists because machine-specific config belongs in a separate file, even when 'it's only a path.' Today it's one path. Tomorrow it's the path plus a personal-access token plus a cache directory plus a scratch-disk path. If the committed profile uses a placeholder, you've already admitted the committed file is machine-specific; might as well put *all* the machine-specific parts in one overlay file and keep the committed profile genuinely reusable. **(1d) is where the system should land within 6 months** — better to start there than migrate later."*

Position: **(1d)**. Dissent from the majority.

**Cantrill:** *"Grep-ability first. Can I grep `profiles/` and find every hardcoded assumption? With (1b) yes — `grep '{GIT_ROOT}'` finds them all. With (1c) shell expansion, the dependency is hidden in parser behavior. With (1d) overlay, I have to know about the overlay to know the full config. **(1b)** lets you hold the whole picture in one file and see exactly what gets substituted. If/when we outgrow one-dimensional variance (per Hashimoto's concern), migrate then. Premature generalization is a debugging cost."*

Position: **(1b)**.

**Q1 consensus**: **(1b), 4-of-5.** Hashimoto dissents — argues (1d) overlay pattern is strategically better.

---

### Q2 — `KB_GIT_ROOT` origin

**Fowler:** *"I'd look at onboarding. The ideal is zero-setup beyond `git clone`. (2a) shell rc requires the operator to edit dotfiles — breaks zero-setup. (2c) separate config file is cleaner but still an extra step. (2b) script-derivation is zero-setup and deterministic. **(2b) as default, with (2a) env-var override for edge cases** (testing, alternate layouts) is the pattern I'd ship."*

Position: **(2b) + optional (2a) override**.

**Hightower:** *"I'm most comfortable with env vars — that's the 12-factor answer and it matches how deployment systems think. But for a personal CLI tool run from one machine, making the operator edit `.bashrc` on every new machine is friction for no benefit. **(2b) derivation wins the 'simplest thing that works' test** for this specific case. Env-var override for when-you-need-it is the safety valve."*

Position: **(2b) + optional (2a) override**.

**Kernighan:** *"The script lives in `kb-system/scripts/`. Its grandparent is the git root. Why ask the operator anything? **(2b) — derive.** One line at the top of each script: `KB_GIT_ROOT=$(dirname $(dirname $(realpath "$0")))`. Done. Works out of the box on every machine that has bash, realpath, and a git clone. No env vars, no config files, no ceremony."*

Position: **(2b), and nothing else**.

**Hashimoto:** *"I don't love script-location derivation because it ties the system to a specific layout: 'scripts must be under kb-system/scripts/ relative to the git root.' What if someone symlinks the scripts elsewhere? What if they're run via a wrapper? A config file (2c) is more explicit. But I recognize for personal-tool scale, (2b) is overwhelmingly convenient. **Fine — (2b) as default**, but document the assumption that scripts stay in their canonical location."*

Position: **(2b)**, with caveat to document the derivation assumption.

**Cantrill:** *"Explicit is better than implicit — but (2b) *is* explicit, in the sense that the derivation is one line of visible code in each script. `$(dirname $(dirname $(realpath "$0")))` is not magic; it's a specific, auditable computation. That's materially different from (2a) where the env var value comes from an unseen shell rc five days ago. **(2b) with the override escape hatch**. The override must be documented, so operators know they have it without needing to read source."*

Position: **(2b) + documented override**.

**Q2 consensus**: **Unanimous for (2b)** as default. Four of five endorse an optional env-var override for edge cases; Kernighan alone prefers no override.

---

### Q3 — Contexts materialization

**Fowler:** *"A materialized context is a frozen state — the operator can open `.env` and see exactly what Claude Code will read, can `diff` between machines to spot config drift, can commit the output to their dotfiles if they want. Symlinks (3b) leave resolution-time indirection. Hybrid (3c) requires remembering which files are which kind of beast. **(3a) is strictly better for debugging**."*

Position: **(3a)**.

**Hightower:** *"Contexts are build artifacts. Build artifacts are fully-resolved. **(3a).**"*

Position: **(3a)**.

**Kernighan:** *"A context is a 'compiled' form of a profile. The symlink approach (3b) worked when there was nothing to substitute; now there is, so compile it. **(3a).**"*

Position: **(3a)**.

**Hashimoto:** *"Treating contexts as machine-specific compiled output is consistent with the Vagrant/Terraform mental model — the committed recipe plus machine config produces a concrete deployment artifact. **(3a).**"*

Position: **(3a)**.

**Cantrill:** *"If I'm debugging 'why didn't my hook fire,' I want to be able to `cat contexts/wiki/.claude/settings.json` and see the exact command Claude Code is trying to run. With symlinks plus placeholders, I'm reading one file to resolve another to compute a third. **(3a) or I'm unhappy**."*

Position: **(3a)**.

**Q3 consensus**: **Unanimous for (3a).** No dissent.

---

### Q4 — Hook command paths

**Fowler:** *"Consistent with Q3 — materialize. The fact that Claude Code offers `${CLAUDE_PROJECT_DIR}` (option 4b) is tempting but it means depending on *their* substitution semantics — which could change across versions. Absolute paths in the materialized file (4a) are immune to upstream behavior changes. (4c) PATH-based resolution is the most portable but adds a deployment step to move scripts to `~/.local/bin`, which is a new class of artifact the operator has to maintain."*

Position: **(4a)**.

**Hightower:** *"(4c) is how I'd do it in a Kubernetes context — hooks as first-class binaries on PATH. But here we're not deploying containers; we're running from a git clone. **(4a) materialize**, same reasoning as Q3."*

Position: **(4a)**.

**Kernighan:** *"(4b) relies on `${CLAUDE_PROJECT_DIR}` being correctly set by Claude Code on every hook fire. That's a subtle dependency. If it's ever wrong, the hook silently doesn't work. (4a) absolute paths — no subtlety. **(4a).**"*

Position: **(4a)**.

**Hashimoto:** *"(4b) is cleaner in principle but creates a fragility surface I don't need. **(4a).**"*

Position: **(4a)**.

**Cantrill:** *"I'll add something: the materialized paths in (4a) should include the script's `$(realpath)` result at regen time, not the as-configured path. That way if a symlink chain later changes, the context still points at the actual file. Paranoid? Maybe. But it makes `cat settings.json` a ground-truth operation."*

Position: **(4a) + realpath-at-regen**.

**Q4 consensus**: **Unanimous for (4a).** Cantrill adds the `realpath` refinement, which is cheap and worth adopting.

---

## 4. Where the panel disagrees

Only one real disagreement: **Q1**, where Hashimoto alone argued for a separate `profiles/<name>.local.env` overlay pattern (1d) against the 4-of-5 consensus for placeholder-substitution (1b).

His argument: *"Today it's one path. Tomorrow it's three machine-specific things. Start where you're going to end up."*

Counter-arguments from the panel:
- **Fowler**: premature splitting adds cognitive overhead for today's benefit of "maybe avoided migration pain in 6 months"
- **Cantrill**: grep-ability of a single file beats two-file lookup; introduce overlay when the variance grows
- **Kernighan**: if it's ever just one path, don't split; if it grows, refactor then

The panel's resolution: proceed with (1b), but **document the migration path to (1d) if/when machine-specific config grows beyond `KB_GIT_ROOT`**. That way Hashimoto's future-proofing concern is acknowledged without paying the complexity cost prematurely.

Panelist note on the dissent: Hashimoto's position isn't wrong — it's conservative about a known category of future pain. The majority trades that optionality for present-day simplicity. If the operator values multi-year architectural stability over six-month simplicity, (1d) is defensible.

---

## 5. Synthesized recommendations

| Q | Decision | Why |
|---|---|---|
| **Q1** | **(1b)** placeholders in committed profiles; regen substitutes into contexts | 4-of-5 consensus; grep-able, explicit, defers complexity |
| **Q2** | **(2b)** derive `KB_GIT_ROOT` from script location as default; allow `KB_GIT_ROOT` env var as override; document both | Unanimous on (2b) default; 4-of-5 want override for edge cases |
| **Q3** | **(3a)** materialize everything at regen time — contexts are frozen inspectable state | Unanimous |
| **Q4** | **(4a)** materialize absolute paths in settings.json, using `realpath` at regen time | Unanimous (Cantrill adds realpath refinement) |

---

## 6. Concrete refactor plan (follows from the decisions)

### 6.1 Changes required

- **`kb-contexts-regenerate`** (the core of this refactor):
  - Derive `KB_GIT_ROOT` from script location at top of script
  - Honor `$KB_GIT_ROOT` env var override if set
  - Read each `profiles/<name>.env` template
  - Substitute `{GIT_ROOT}` → actual `$KB_GIT_ROOT`
  - Write materialized `.env` to `contexts/<name>/.env` as a **real file**, not a symlink (breaking change)
  - Read `scripts/templates/claude-settings.json` template
  - Substitute `{GIT_ROOT}` → actual `$KB_GIT_ROOT`
  - Write materialized `settings.json` to `contexts/<name>/.claude/settings.json` as a **real file** (breaking change)

- **`scripts/templates/profile.env`**:
  - `OBSIDIAN_VAULT_PATH={GIT_ROOT}/kb-{NAME}`
  - `OBSIDIAN_SOURCES_DIR=` (empty, optional — operator can set to `{GIT_ROOT}/kb-{NAME}/_sources` if following multi-vault-containment recommendation)

- **`scripts/templates/claude-settings.json`**:
  - All hook command paths use `{GIT_ROOT}` placeholder
  - `"command": "python3 {GIT_ROOT}/kb-system/scripts/hooks/stop_append.py"`

- **`scripts/kb-vault-new`**:
  - Also derive `KB_GIT_ROOT` from script location
  - Generate profile with `{GIT_ROOT}` placeholders (not absolute paths)
  - Remainder of script unchanged

- **Existing profiles** (`wiki.env`, `personal.env`, `ebury.env`):
  - Rewrite with `{GIT_ROOT}` placeholders
  - Commit as a normal refactor

### 6.2 Breaking changes

- **`contexts/` are regenerated at the new format** (materialized files, not symlinks)
- First run of new regen on an existing machine deletes old symlinks, writes new real files — effectively automatic
- No operator action beyond running `kb-contexts-regenerate` once after pulling

### 6.3 Work-laptop bring-up (post-refactor)

```bash
# On work laptop, any path:
mkdir -p ~/code && cd ~/code
git clone git@github.com:nunogt/kb-system.git
git clone git@github.com:nunogt/obsidian-wiki.git
git clone git@github.com:nunogt/kb-ebury.git
# Optionally: kb-wiki, kb-personal

cd kb-system
./scripts/kb-contexts-regenerate
# → derives KB_GIT_ROOT=$HOME/code, materializes contexts/ebury/ with paths
#   pointing at $HOME/code/kb-ebury and $HOME/code/kb-system/scripts/hooks/

cd contexts/ebury
claude --dangerously-skip-permissions
# → v3 hooks fire against the right absolute paths
```

### 6.4 Migration path for future overlay pattern (Hashimoto's dissent)

If machine-specific config grows beyond `KB_GIT_ROOT` (e.g., auth tokens, alternate cache dirs, machine-specific QMD endpoints), the refactor to (1d) looks like:

1. Add `profiles/<name>.local.env.example` template documenting overlay format
2. `kb-contexts-regenerate` merges `<name>.env` + `<name>.local.env` with overlay wins
3. Add `profiles/*.local.env` to `kb-system/.gitignore`
4. Document upgrade path in `docs/`

Deferred until the variance demands it.

---

## 7. Self-validation / critique / refinement

### 7.1 Self-validate

Does the recommendation honor each expert's documented body of work?

- **Fowler**: "Externalized Configuration" chapter in PoEAA maps 1:1 to (1b) + (3a). ✓
- **Hightower**: "12-factor" advocacy consistent with env-var-driven build pipelines producing artifacts. (2b)+(3a)+(4a) is the CLI-adapted 12-factor. ✓
- **Kernighan**: `realpath`+`dirname` derivation is classic Unix; no env vars is classic Unix minimalism. ✓
- **Hashimoto**: his (1d) dissent is consistent with Vagrant's `Vagrantfile.local` pattern. Panel honored by documenting (1d) as the future migration target. ✓
- **Cantrill**: grep-able config + materialized artifacts + realpath-at-regen are all consistent with his public advocacy. ✓

### 7.2 Critique

- **Am I putting my own preferences in expert mouths?** Partial risk. Fowler would genuinely differ on small things; I've simplified to consensus-friendly positions. Hashimoto's dissent is the main signal that I'm not: he argues against majority opinion based on his actual track record of (overlay-pattern systems).
- **Is the five-expert panel the right composition?** Missing a security voice (paths in config files are a consideration for systems that need to prove isolation). Not relevant to this problem but flagged.
- **Is the refactor plan correct per the decisions?** Plan matches decisions directly. One worry: `kb-contexts-regenerate` becomes much more substantive (materialization logic rather than symlink creation). Worth budgeting ~1.5 hours rather than my earlier 1-hour estimate.

### 7.3 Refinement

- Add one sentence to §5 (Hashimoto's future-proofing concern is reflected in §6.4's documented migration path — this is how we validate the "defer until needed" rationale).
- Add an "adoption step" to §6.3 noting that existing machines (dev VM) will also need to run `kb-contexts-regenerate` once after the refactor lands to re-materialize their contexts.
- Cantrill's realpath refinement in Q4 should be reflected in the regen script's implementation — each hook command path resolves via `realpath` of the template's pointed-at file at regen time.

---

## 8. Decision request for the operator

If the panel's synthesis matches your sense:

- ✅ Proceed with the refactor per §6
- Recognize Hashimoto's dissent: accept now, re-evaluate if machine-specific config grows
- Total work: ~1.5 hours including testing on the dev VM, regenerating contexts, committing

If you want to diverge from the panel:

- **(A)** Accept Hashimoto's minority view and implement (1d) overlay pattern now. Adds ~30 min complexity but future-proofs.
- **(B)** Skip the env-var override (Kernighan's cleaner position): just derivation, no override knob. Very slight simplification.
- **(C)** Use `${CLAUDE_PROJECT_DIR}` for hook paths (Q4's 4b option) — saves the settings.json materialization step at the cost of an upstream dependency. Panel unanimously rejected; noted if you want to re-litigate.

---

*End of panel deliberation. Awaiting operator decision.*
