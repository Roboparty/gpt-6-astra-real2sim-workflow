# Preparation, inference, geometry — separate status

As read on 2026-09-29 from repository `docs/research/STATE.json`, `docs/research/PI3X_RUNTIME_20260929.md`, and `docs/research/evidence/heartbeat_0945/pi3x_preparation_audit.json`:

| Layer | Evidence/status |
|---|---|
| Checkpoint bytes | Research audit reports SHA256 verified; this skill delivery did not rehash the 5.44 GB file |
| Dependency preparation | Shared 1800 s exhausted; 1800.107 s recorded; nine unverified wheels retained |
| Runtime imports/construction | Not ready; no successful model construction |
| Forward inference | Not run |
| Geometry accuracy | Unverified |

Source runtime: `4090-1:/home/wqz/real2sim_capability_20260929/runtime_addons/pi3x`. Do not run its `start`, install retained wheels or modify `preparation_budget.json` in this skill task. The separate existing Python at `/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python` can execute lightweight NumPy/Pillow contract checks without model preparation. It is not a Pi3X inference environment.

Before future authorized preparation, preserve original time accounting and all partial files, explicitly amend the budget, validate official wheel hashes and reuse verified bytes remotely. Before future inference, freeze frame protocol and inspect external GPU tasks. A new directory does not authorize resetting the research trial budget.
