"""Helper process for the cross-process guard test: hold the pipe and pump the event loop."""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402
from petapp.instance import InstanceGuard  # noqa: E402

app = QApplication(sys.argv[:1])
guard = InstanceGuard(sys.argv[1])
acquired = guard.acquire()
seen = []
if guard.server is not None:
    guard.server.newConnection.connect(lambda: seen.append(1))
print("ACQUIRED" if acquired else "DENIED", flush=True)

deadline = time.time() + float(sys.argv[2])
while time.time() < deadline:
    app.processEvents()
    time.sleep(0.02)
print(f"DONE connections={len(seen)}", flush=True)
guard.close()
