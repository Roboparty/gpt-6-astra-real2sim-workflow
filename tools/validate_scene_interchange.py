"""Compatibility Blender CLI for the native independent interchange validator."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.interchange import capture_scene, compare_snapshots, sha, main


if __name__ == '__main__':
    main()
