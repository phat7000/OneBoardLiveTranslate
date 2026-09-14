# OneBoard Phase 2 implementation notes

## Phase 2.3 integration justification

The upstream primary window and startup routine start capture automatically and
gate access on a legacy setup flow. A standalone widget cannot replace that entry
point. `main.py` therefore retains the existing startup as `upstream_main()` and
delegates the normal `main()` to `oneboard_app.run()`. Recognition, VAD, capture,
translation, worker and model algorithms are unchanged.

The product adapter subscribes to existing overlay Qt signals to receive committed
source segments and streaming/final translation updates. It retains the full
Control Panel, overlay, subtitle window, logging and transcript writer. ASR loading
is deferred to Start in a OneBoard subclass. Blocking stop cleanup runs outside the
GUI thread after its Qt timer is stopped in the GUI thread.

User settings remain the upstream flat settings dictionary. Presets update explicit
source/ASR/target languages; advanced selections remain available. Transcript limits
are configurable under `oneboard.history_segments` and
`oneboard.history_characters` in `config.yaml` (defaults 500 and 100,000).

## Phase 2.6 integration justification

An installed application directory is not a durable location for mutable user data:
it may be unwritable and is replaced or removed during update/uninstall. Configuration
alone cannot redirect module-level paths before user settings load. Three narrow core
integration points therefore use `oneboard_paths.data_dir()` for settings/models,
logs, and transcripts. The helper preserves the upstream repository-local paths in a
source checkout and switches only a marked customer distribution to
`%LOCALAPPDATA%\OneBoardLiveTranslate`.

## Phase 2.8 hardening justification

The inherited checked-in fallback selected a GPU FunASR model, an unrelated
translation endpoint/prompt, and a secret-shaped placeholder key. These defaults
could be used when no user settings exist, so configuration alone now aligns them
with the CPU-safe Whisper Small, explicit English-to-Vietnamese, and local Ollama
MVP path. Advanced continues to expose every inherited engine and language.

The installed settings path also made persistence failures relevant to first-run
completion. The existing writer now reports success or failure while retaining its
non-throwing behavior for upstream callers; the OneBoard wizard uses that result to
avoid claiming setup completion when the settings file was not saved.

## Public-source audit integration justification

The exposed first-run translation credential and unsafe diagnostic values existed
at their use sites and output sinks in upstream-owned `main.py`, `translator.py`,
`control_panel.py`, `model_manager.py`, `benchmark.py`, `dialogs.py`,
`log_window.py`, `asr_worker.py`, and OneBoard status/readiness adapters.
Configuration alone could not remove the shipped literal, stop existing log
calls from serializing user-provided values, or redact the independently
configured worker/UI/stderr sinks. The core edits are therefore limited to an
empty first-run API-key default, fixed non-sensitive log messages, and small
integrations with the isolated `oneboard_log_safety.py` redactor. ASR, VAD, audio
capture, translation requests, and model-management behavior are unchanged.

The OneBoard package builder now treats caches, test/fixture trees, and
PyCryptodome `SelfTest` as non-runtime content and verifies the completed stage
before archiving. This package-only guard does not modify the inherited runtime
pipeline. Vendored `funasr_nano/` source content was not changed: provenance and
the applicable FunASR MIT notice are recorded separately.
