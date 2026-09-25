# Dependencies and project references

## Three-room showcase credits

- **ArtVIP — X-Humanoid**: VITBERGET and BRUKSVARA reference assets appear in the final comparison section of `docs/showcase/media/overview.mp4`. The [official dataset card](https://huggingface.co/datasets/X-Humanoid/ArtVIP/blob/d22f209/README.md) declares Apache-2.0 (checked 2026-09-25). The video imports geometry into Blender and adds neutral lighting and kinematic replay; it does not run the original PhysX simulation. The BRUKSVARA reference is the brown variant. Reference geometry is not included in this Git repository. [Apache-2.0 text](licenses/Apache-2.0.txt).
- **Poly Haven**: `oak_veneer_01` and `dirty_carpet` source textures, recorded as CC0 in the source case's material provenance. [Oak veneer](https://polyhaven.com/a/oak_veneer_01), [dirty carpet](https://polyhaven.com/a/dirty_carpet), [licence](https://polyhaven.com/license). Textures were carried forward from an earlier scene package; this project does not claim authorship of them.
- The bedding pattern was generated in the source task. Original photographs and composed preview media use the separate [media terms](MEDIA_NOTICE.md).

## Runtime and references

The MIT licence in this repository covers project-authored source code, text documentation, and machine-readable metadata. Example media is covered separately by [MEDIA_NOTICE.md](MEDIA_NOTICE.md).

Runtime dependencies are not redistributed as part of this Git repository and retain their own licences. Consult the exact installed version's notices, including transitive dependencies, when distributing an environment or container:

- [Blender](https://www.blender.org/about/license/)
- [MuJoCo](https://github.com/google-deepmind/mujoco)
- [NumPy](https://github.com/numpy/numpy)
- [SciPy](https://github.com/scipy/scipy)
- [OpenCV](https://github.com/opencv/opencv)
- [Pillow](https://github.com/python-pillow/Pillow)
- [FFmpeg](https://ffmpeg.org/legal.html)

This is a dependency/source index, not a completed legal audit of every optional environment. Model access, third-party model weights, catalogue photographs, downloaded CAD assets, and online services require their own applicable permissions and terms.

The projects linked in [INTEGRATIONS.md](docs/INTEGRATIONS.md), including HKU Real2Sim_GPT6_ASTRA and Real2Gym, are research references and potential integration directions. Their code, weights, and case assets have not been vendored into this repository. No affiliation or endorsement is implied.
