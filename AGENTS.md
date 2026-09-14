# OneBoard Live Translate development guidelines

## Project identity and scope

- This repository is a minimal fork of [TheDeathDragon/LiveTranslate](https://github.com/TheDeathDragon/LiveTranslate).
- The user-facing product name is **OneBoard Live Translate**. A repository, package, application, or other machine-readable identifier may use **OneBoardLiveTranslate**.
- Keep code-level product branding centralized in `branding.py`. Update localized display strings deliberately; never perform a global replacement of `LiveTranslate`, because upstream identifiers, documentation, logger namespaces, and attribution may intentionally retain that name.
- Preserve existing internal logger namespaces unless a concrete technical requirement makes a change necessary.
- English and Vietnamese are the primary MVP languages. Prefer explicit source-language selection for English <-> Vietnamese presets and primary flows, while retaining auto-detection and every other upstream language capability.

## Branch and upstream policy

- Develop OneBoard work on `oneboard-dev` or a feature branch based on it.
- Treat `main` and `upstream/main` as read-only references while implementing OneBoard features. Never develop on them, commit OneBoard changes to them, merge OneBoard changes into them, force-update them, or push to them.
- Only update from `upstream/main` as a deliberate upstream-sync task. Keep upstream updates mergeable by avoiding broad rewrites, gratuitous renames or file moves, repository-wide formatting, and unrelated cleanup.
- Preserve third-party copyright, attribution, and license notices. Do not remove or rewrite upstream or dependency notices as part of OneBoard branding.

## Architecture boundaries

The inherited application pipeline is:

`audio_capture.py` -> `vad_processor.py` -> `asr_client.py` / `asr_worker.py` / `asr_*.py` -> `translator.py` -> subtitle UI, orchestrated by `main.py`.

- Treat inherited pipeline, model-management, installer/update, and UI behavior as upstream-owned code.
- Prefer an isolated OneBoard module, adapter, configuration layer, or preset for OneBoard-specific behavior. Use small integration points in upstream-owned files rather than spreading product conditionals through the core.
- Any OneBoard-driven change to upstream-owned core requires an explicit, recorded justification in the task notes or commit: identify why an isolated module, configuration value, preset, adapter, or feature flag is insufficient, and keep the core edit as small and general-purpose as practical.
- Do not modify ASR, VAD, audio capture, model management, or translation behavior unless the task explicitly requires it. Add focused regression coverage whenever such a change is justified.
- `config.yaml` contains checked-in base defaults; `user_settings.json` contains per-user runtime state and must remain untracked. Put shareable OneBoard defaults in version-controlled configuration or presets, and keep secrets and machine-local values out of them.
- Do not remove an upstream capability merely to simplify the OneBoard UI. Keep it available behind **Advanced**, settings, a preset, or a feature flag where possible.
- Prefer configuration and feature flags over deleting or hard-forking upstream functionality. Defaults may prioritize the English/Vietnamese MVP without narrowing the underlying engine's capabilities.

## OneBoard product experience

- Architecture: LiveTranslate upstream core plus an isolated OneBoard product layer. The primary window offers language direction, audio source, Start/Stop, status, and an upper-right settings gear. The gear opens the existing Advanced Control Panel; VAD, ASR, models, translation, benchmark, logs, subtitles, and other upstream controls remain accessible.
- English -> Vietnamese and Vietnamese -> English presets set both the source language and ASR hint explicitly (`en` or `vi`) together with the opposite target. Preserve other languages and auto-detection in Advanced.
- Show accumulated source and translation in two vertically stacked, wrapping, scrollable text regions. Update each in-progress segment in place; never append intermediate tokens as separate sentences. Keep histories ordered, bounded by configurable limits, and clearable. Follow new content by default while respecting a user reading older text. Preserve upstream transcript export.
- Keep readiness and first-run setup in OneBoard modules. Reuse existing model management. Model downloads require an explicit user action; never silently fetch multi-GB models. CPU-only performance advice must not prevent use. Setup can be reopened from Settings.
- Customer packages include a normal launcher and runtime; users must not need Git, Python, pip, a developer checkout, or command-line setup. Keep models separately manageable and preserve user settings during upgrades/uninstall. Do not install system-wide build tools without explicit authorization.
- Customer updates use configurable OneBoard release infrastructure, disabled by default until an endpoint exists. Never expose an upstream Git pull as a customer update. Centralize product version information and preserve dependency/model license notices; do not claim commercial legal clearance without verification.

## Change discipline

- Inspect the current branch and `git status` before editing. Do not modify, stage, discard, or commit unrelated user work.
- Keep each diff narrowly scoped. Avoid drive-by refactors, dependency churn, generated-file changes, or formatting outside the task.
- Never stage or commit generated files, logs, downloaded models, transcripts, caches, virtual environments, or user runtime settings. This includes `.venv/`, `models/`, `logs/`, `transcripts/`, `__pycache__/`, `.pytest_cache/`, `.pip-cache/`, `.uv-cache/`, `.tmp/`, `dist/`, `build/`, `release/`, and `user_settings.json`.
- Never use `git add -f` to bypass ignore rules for runtime or generated artifacts.
- Before every task is declared complete:
  1. Run the tests relevant to the changed behavior. Use `.venv\Scripts\python.exe -m pytest .\tests` for the full Python suite, and run that full suite for shared or core changes when practical.
  2. Run `git diff --check` and review both the unstaged and staged diffs for correctness, scope, accidental secrets, generated artifacts, and unrelated edits.
  3. Confirm the final commit contains only intended files and `git status --short` is empty. If pre-existing user changes prevent a clean worktree, preserve them and coordinate instead of committing or discarding them.
- Do not push automatically. Push only when the user explicitly requests it, and never push OneBoard feature work to `main` or `upstream/main`.
