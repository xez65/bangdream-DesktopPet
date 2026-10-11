"""PyInstaller entry point. Kept separate so the analysis sees ``petapp`` as a normal package."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from petapp.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
