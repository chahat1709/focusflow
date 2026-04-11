# Graph Report - C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3  (2026-04-11)

## Corpus Check
- 40 files · ~56,215 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3140 nodes · 7996 edges · 26 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `copy()` - 189 edges
2. `set()` - 106 edges
3. `We` - 76 edges
4. `js()` - 71 edges
5. `map()` - 63 edges
6. `an()` - 61 edges
7. `me` - 57 edges
8. `push()` - 56 edges
9. `ns()` - 55 edges
10. `be()` - 55 edges

## Surprising Connections (you probably didn't know these)
- `pi()` --calls--> `n()`  [EXTRACTED]
  C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\chart.min.js → C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\chart.min.js  _Bridges community 0 → community 9_
- `tn` --calls--> `u()`  [EXTRACTED]
  C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\chart.min.js → C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\chart.min.js  _Bridges community 0 → community 13_
- `gi()` --calls--> `ae()`  [EXTRACTED]
  C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\three.min.js → C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\three.min.js  _Bridges community 4 → community 7_
- `setFromCartesianCoords()` --calls--> `ae()`  [EXTRACTED]
  C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\three.min.js → C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\three.min.js  _Bridges community 4 → community 2_
- `setX()` --calls--> `de()`  [EXTRACTED]
  C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\three.min.js → C:\Users\chaha\OneDrive\Pictures\Predator\muse 2 phase 1 - Copy (2)\FocusFlow_V3\public\assets\libs\three.min.js  _Bridges community 7 → community 2_

## Communities

### Community 0 - "chart.min.js / js() / an()"
Cohesion: 0.01
Nodes (235): a(), aa(), addBox(), Ae(), afterDatasetsUpdate(), afterDraw(), afterEvent(), afterUpdate() (+227 more)

### Community 1 - "tailwind.js / map() / push()"
Cohesion: 0.01
Nodes (539): $2(), $3(), A_(), A3(), a5(), Aa(), Ab(), ad() (+531 more)

### Community 2 - "three.min.js / .push() / toJSON()"
Cohesion: 0.01
Nodes (163): ac, _activateAction(), _addInactiveAction(), _addInactiveBinding(), As(), au, bc(), bi (+155 more)

### Community 3 - "copy() / set() / be()"
Cohesion: 0.01
Nodes (61): $a(), aa(), Ao, ba(), be(), bo, Ca(), ch (+53 more)

### Community 4 - "We / me / .max()"
Cohesion: 0.01
Nodes (53): add(), ae(), applyMatrix4(), at(), clampPoint(), closestPointToPoint(), closestPointToPointParameter(), containsPoint() (+45 more)

### Community 5 - "Fu / tu / connect()"
Cohesion: 0.04
Nodes (13): connect(), disconnect(), Fu, getInput(), getOutput(), _lendControlInterpolant(), removeFilter(), setFilter() (+5 more)

### Community 6 - "ke / ._onChangeCallback() / Pn"
Cohesion: 0.04
Nodes (8): ah, Ar(), er(), getParameter(), ke, Pn, Wa(), Xa()

### Community 7 - "Mi / de() / oo"
Cohesion: 0.05
Nodes (11): de(), gi(), Mi, oo, pl(), setW(), setXY(), setXYZW() (+3 more)

### Community 8 - "dashboard_therapeutic.js / showAlert() / processServerData()"
Cohesion: 0.07
Nodes (40): closeSessionModal(), createClass(), createCollege(), createStudent(), dbSearch(), deleteClass(), deleteCollege(), deleteSession() (+32 more)

### Community 9 - "zt() / bt / Cs"
Cohesion: 0.07
Nodes (16): Bi(), bt, Cs, gt(), jt(), kt(), mt(), pi() (+8 more)

### Community 10 - "ci / .getHex() / .setHSL()"
Cohesion: 0.06
Nodes (6): ci, io, le(), li(), no, oe()

### Community 11 - "MuseConnector / OpenBCIConnector / sync.rs"
Cohesion: 0.07
Nodes (13): MuseConnector, parse_eeg_packet(), parse_uuid(), test_muse_connector_metadata(), test_parse_eeg_packet_length(), test_parse_eeg_packet_too_short(), OpenBCIConnector, SyncConfig (+5 more)

### Community 12 - "features.rs / sleep_pipeline.rs / SleepPipeline"
Cohesion: 0.12
Nodes (18): compute_tbr(), find_iaf(), tbr_to_focus(), test_find_iaf_detects_10hz_peak(), test_focus_baseline_gives_quarter_focus(), test_focus_decreases_when_tbr_is_high(), test_focus_metric_range(), test_tbr_invalidated_by_emg() (+10 more)

### Community 13 - "tn / ._each() / ._get()"
Cohesion: 0.16
Nodes (2): addElements(), tn

### Community 14 - "Hr / ._fromTexture() / .fromScene()"
Cohesion: 0.18
Nodes (6): Hr, jr(), kr(), qr(), wr(), xr

### Community 15 - "bh / .getValueSize() / .getInterpolation()"
Cohesion: 0.13
Nodes (3): bh, mh(), rh

### Community 16 - "mod.rs / BaselineState / .observe()"
Cohesion: 0.11
Nodes (13): BandPowers, BaselineState, BrainChunk, Channel, ConnectionStatus, DspSnapshot, EpochRecord, FrequencyBands (+5 more)

### Community 17 - "artifacts.rs / detect_blinks() / imu_motion_mask()"
Cohesion: 0.18
Nodes (12): BlinkDetectorState, BlinkZone, detect_blinks(), detect_emg(), EmgResult, imu_motion_mask(), sorted_median(), std_dev() (+4 more)

### Community 18 - "filters.rs / IirFilter / .new()"
Cohesion: 0.22
Nodes (12): bandpass_filter(), butter_bandpass_coefficients(), demean(), dual_notch(), IirFilter, make_bandpass_pair(), notch_filter_iir(), test_demean() (+4 more)

### Community 19 - "ScreenTracker / .new() / screen_tracker.rs"
Cohesion: 0.3
Nodes (5): AppFocusSummary, ScreenActivity, ScreenTracker, test_summarize_groups_by_app(), test_tracker_starts_and_stops()

### Community 20 - "nlms.rs / check_death_lock() / .new()"
Cohesion: 0.28
Nodes (11): check_death_lock(), generate_ref_matrix(), nlms_adaptive_kernel(), NlmsResult, NlmsState, test_death_lock_counter_returns_to_zero_after_sustained_clean_signal(), test_death_lock_decays_on_clean_data(), test_death_lock_does_not_trigger_below_threshold() (+3 more)

### Community 21 - "lib.rs / AppState / connect_muse()"
Cohesion: 0.18
Nodes (3): AppState, DspConfig, SystemStatus

### Community 22 - "build.rs / main()"
Cohesion: 1.0
Nodes (0): 

### Community 23 - "main.rs / main()"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "vite.config.ts"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "schema.rs"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **20 isolated node(s):** `eo`, `wh`, `AppState`, `SystemStatus`, `DspConfig` (+15 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `build.rs / main()`** (2 nodes): `build.rs`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `main.rs / main()`** (2 nodes): `main.rs`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `vite.config.ts`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `schema.rs`** (1 nodes): `schema.rs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `copy()` connect `Community 3` to `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 10`, `Community 14`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `We` connect `Community 4` to `Community 2`, `Community 3`, `Community 6`, `Community 7`, `Community 10`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `me` connect `Community 4` to `Community 10`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **What connects `eo`, `wh`, `AppState` to the rest of the system?**
  _20 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.01 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.01 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.01 - nodes in this community are weakly interconnected._