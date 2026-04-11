# AI Agent Context — FocusFlow V3

This file tells AI coding assistants how to work effectively with this codebase.
It is automatically read by Claude Code, Gemini CLI, Cursor, Codex, and Aider.

---

## Graphify Knowledge Graph

This repository has a Graphify knowledge graph installed.
Before answering any codebase question, query the graph first:

```
graphify query "<your question>"
```

The graph is stored at `graphify-out/graph.json` and covers:
- All Rust DSP modules (`dsp/`, `hardware/`)
- The JavaScript frontend (`dashboard_therapeutic.js`)
- The Tauri IPC bridge (`lib.rs`)

### Key nodes in the graph
- `SignalProcessor` — the stateful DSP engine orchestrator
- `tbr_to_focus` — focus metric calculation (z-score, clinically validated)
- `butter_bandpass_coefficients` — bilinear-transform Butterworth IIR filter
- `check_death_lock` — NLMS adaptive filter stability guard
- `process_chunk` — main entry point for real-time EEG processing
- `startPolling` — frontend Tauri event listener for `dsp-snapshot`

---

## Architecture Quick Reference

```
Muse 2 BLE → hardware/muse.rs → dsp/mod.rs → dsp/filters.rs
                                             → dsp/nlms.rs
                                             → dsp/artifacts.rs
                                             → dsp/features.rs
                                             → lib.rs (Tauri IPC)
                                             → dashboard_therapeutic.js
```

## Critical Invariants (do NOT break these)

1. `tbr_to_focus()` in `features.rs` — z-score is `(mean - raw) / std`.
   HIGH theta/beta ratio = LOW focus. Do not invert.

2. `butter_bandpass_coefficients()` in `filters.rs` — uses bilinear transform
   with pre-warped analog frequencies. Do not revert to Audio EQ Cookbook formula.

3. `check_death_lock()` in `nlms.rs` — counter MUST decay (÷2) when
   `chunk_frozen == 0`. Without this, the filter resets randomly after hours.

4. `process_chunk()` in `mod.rs` — PSD must be averaged across ALL 4 channels,
   not just AF7. Single-channel PSD was a known bug (fixed in v3.1).

5. `focus_metric` in `dashboard_therapeutic.js` — is already in [0.0, 0.95].
   Do NOT divide by 100.

## Test Suite

```bash
cd src-tauri && cargo test
# Expected: 34 passed; 0 failed
```

All DSP invariants above have corresponding unit tests.
