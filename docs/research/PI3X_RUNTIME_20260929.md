# Isolated Pi3X runtime preparation, 2026-09-29

**Checkpoint and source are ready; the new environment is not ready.** The preparation stopped at its shared 30-minute deadline while downloading dependencies. The checkpoint's exact size and SHA256 passed verification. CPU model construction could not run because installation did not finish.

The intended workflow downloads the public checkpoint directly to the remote host, creates a separate Python environment, then verifies imports plus model construction on CPU. This attempt did **not** load the checkpoint into the model, run a forward pass, allocate GPU memory, change the existing reconstruction environments, or consume a camera-optimization trial.

## Fixed sources

- [Official Pi3/Pi3X code](https://github.com/yyfz/Pi3/tree/9fa3ddb3f8d53041f8b2738df404f62223bbaa7b): commit `9fa3ddb3f8d53041f8b2738df404f62223bbaa7b`.
- [Public Pi3X checkpoint](https://huggingface.co/yyfz233/Pi3X): revision `bb1deea4d7423de5b30691739cb451a3f57dc1d5`, ungated, `model.safetensors` is 5,440,325,620 bytes.
- Expected checkpoint SHA256: `69972d6e1c4492cb4d737a84fe940e357087d81c52f5c9b7c160b49c1f41669a`.
- Required major Python versions: Torch 2.5.1, torchvision 0.20.1, NumPy 1.26.4; remaining inference dependencies come from the fixed official requirements file and their resolved versions are retained in the installer report.
- Code license: BSD-3-Clause. Model weights: CC BY-NC 4.0. Weights remain an external remote research dependency and are not added to this repository.

The official Hugging Face resolve endpoint was used only for a HEAD redirect discovery locally. The resulting signed CDN URL was placed in the remote `download_url.txt` with mode 600. Actual checkpoint bytes travel directly from the CDN to 4090-1. The helper never prints that signed URL. If it expires, obtain a new authorized redirect and resume the retained partial; do not route the file through the local workstation.

## Remote layout and process ownership

Host: `4090-1`.

Base: `/home/wqz/real2sim_capability_20260929/runtime_addons/pi3x`.

| Path under base | Meaning |
|---|---|
| `download_url.txt` | Private transport URL; never include its contents in reports |
| `model.safetensors.partial` | Resumable unverified download; retained on interruption |
| `model.safetensors` | Promoted only after exact size and SHA256 verification |
| `pi3_source.tar.gz`, `source/` | Fixed official code archive and selected inference source files |
| `venv/` | New isolated environment; no packages changed in existing environments |
| `tmp/` | Temporary installer storage under this preparation's directory |
| `wheel_partials/`, `wheel_partials/manifest.json` | Unverified same-disk hardlinks protecting downloaded wheel bytes from temporary-file cleanup |
| `launch.json` | Worker PID, Linux process start ticks, log path and helper hash |
| `preparation_budget.json` | One shared 30-minute wall-clock budget across compatibility retries |
| `prepare_*/preparation_plan.json` | Pre-execution byte budget and fixed sources |
| `prepare_*/state.json` | Phase, progress, disk availability and owned child process identity |
| `prepare_*/worker.log`, `install_dependencies.log` | Retained output and failure evidence |
| `prepare_*/install_report.json` | Planned resolved-installation report; not produced by the interrupted attempt |
| `prepare_*/cpu_construction.json` | Planned CPU model-construction verdict; not produced because dependencies were unavailable |
| `preparation_audit.json` | Independent final file/hash/package/process verification |

The first worker was launched at `2026-09-29T10:07:15Z`, PID `946801`, Linux start ticks `57581769`, with log directory `prepare_20260929T100715Z`. It completed and verified the checkpoint, then stopped because the newly created venv's old pip did not support `--report`. Its failed log is retained. A compatibility retry at `2026-09-29T10:11:15Z`, PID `972460`, start ticks `57605784`, uses `prepare_20260929T101115Z` and bootstraps pip 24.3.1 **inside the new venv only**. The shared deadline remains based on the first launch, not the retry. PID alone is not used as proof that the same process is still alive. The helper refuses duplicate live launches and creates a new retained attempt directory on an authorized restart.

## Storage and stop policy

Initial free disk was 23,051,210,752 bytes. The recorded estimate includes exact checkpoint bytes, 3,021,891,246 bytes of major binary wheels verified through PyPI metadata, an explicitly **assumed** 8 GiB allowance for environment expansion, and a 50 MiB source archive cap. This is a conservative planning allowance, not a measured installed size.

The hard disk reserve is 4 GiB. Downloads check free space before each 4 MiB chunk. Installer/model-construction subprocesses are monitored every 0.25 s and stopped if free disk drops below 5 GiB, leaving reaction headroom. Only the helper's own process group is terminated. No unrelated process, user cache or old environment is removed. The preparation has a fixed 1,800-second total budget; partial downloads and incomplete environments remain inspectable if it stops.

`--no-cache-dir` avoids a second pip download cache. Only one checkpoint is retained, with no Hugging Face cache copy. The source archive is capped and only inference code, licenses, requirements and the example entrypoint are extracted. All downloads and large outputs stay remote.

## Status and continuation

Use the checked-in `tools/prepare_pi3x_runtime.py` on the remote host:

```sh
/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python \
  /home/wqz/real2sim_capability_20260929/runtime_addons/pi3x/prepare_pi3x_runtime.py \
  status --base /home/wqz/real2sim_capability_20260929/runtime_addons/pi3x
```

`start` launches a tracked worker; `status` reads its process identity and persisted progress. `preserve` hardlinks wheel downloads from the strictly resolved owned `tmp/` directory into `wheel_partials/`, without creating a second data copy. Retained wheels stay marked unverified; their full official PyPI SHA256 must pass before reuse, and an incomplete file needs an explicitly budgeted resumable transfer. The helper also protects wheels before terminating a failing installer in subsequent executions.

A preparation marked `ready` would mean dependency versions, checkpoint bytes and CPU model construction are verified. It would not be an inference result or a geometric-quality improvement. This preparation remains `blocked`, and `start` refuses to reset the exhausted budget. A subsequent preparation phase must record its new budget explicitly while retaining this phase's records and reusable bytes.

Before any future inference, register the common six-frame evaluation protocol, freeze input hashes and preprocessing, recheck GPU availability, and save all predicted poses/points/confidences plus real runtime/memory usage. Preserve the remaining camera trials until that protocol is agreed by the research orchestration.

## Verification result

The shared deadline stopped the worker after **1800.107 seconds**. The worker PID `972460` and installer PID `972852` were independently checked absent afterward; no unattended helper remains. The limiting factor was slow dependency transfer from PyPI, not disk capacity. No timeout limit was extended.

| Final check | Result |
|---|---|
| Verified checkpoint | 5,440,325,620 bytes; SHA256 matches the fixed official value above |
| Unverified checkpoint partial | Absent: completed file had been verified and promoted |
| Fixed source | Downloaded and recorded in the source manifest |
| Retained wheel files | **9**, protected by same-device hardlinks |
| Retained wheel bytes | **2,076,526,058 bytes**, no duplicate file-data copy |
| Retained-wheel validation | Unverified; not installed from the preserved paths |
| Final free disk | 15,375,847,424 bytes, above the 4 GiB reserve |
| New environment Torch / torchvision / NumPy | Not installed; runtime **not ready** |
| CPU model construction | Not executed |
| Checkpoint model loading / forward / GPU use | None |
| Existing fresh runtime | NumPy 2.2.6 and MuJoCo 3.13.0 unchanged |
| Existing Shinka runtime | NumPy 2.2.6 unchanged; Torch remains absent |

The retained wheel set includes completed-size Torch, torchvision, NumPy, cuBLAS, CUDA runtime/NVRTC/CUPTI, and cuDNN downloads, plus the interrupted cuFFT download. File size alone is not treated as integrity verification. The manifest retains each original owned temporary path, hardlink destination, byte count, inode and unverified status. Do not discard these bytes or automatically redownload the whole dependency set in the next research phase.
