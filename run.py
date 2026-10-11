"""Launcher that puts ``src`` on the path, so the project runs from a checkout without installing.

    .venv\\Scripts\\python.exe run.py            # show the pet
    .venv\\Scripts\\python.exe run.py --smoke    # headless frame decode check
    .venv\\Scripts\\python.exe run.py --once     # show briefly and write evidence PNGs
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from petapp.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
