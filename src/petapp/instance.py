"""Single-instance guard that doubles as the control channel for acceptance capture.

Ownership is a named mutex (see ``petapp.win32.acquire_named_mutex``); the ``QLocalServer`` under the
same name is only the command channel, and it must be inside a live Qt event loop to accept, so it is
owned by the running app rather than a probe process.
"""

from __future__ import annotations

import os
import sys

SERVER_NAME = "DesktopPetSakiko"
MUTEX_PREFIX = "Local\\"


class InstanceGuard:
    def __init__(self, name: str = SERVER_NAME):
        self.name = name
        self.server = None
        self.mutex = 0
        self._handler = None

    def acquire(self) -> bool:
        """True when this process is the one that should keep running.

        The mutex decides, because nothing about the pipe does: ``listen()`` succeeds for every
        process, and a pipe left by a killed instance still accepts connections while answering
        none. The kernel drops the mutex with the process, so the next launch is never blocked by a
        corpse, and any stale pipe registration under our name is cleared before we re-listen.
        """
        from PySide6.QtNetwork import QLocalServer

        from petapp import win32

        debug = os.environ.get("DESKTOPPET_GUARD_DEBUG") == "1"
        verdict, handle = win32.acquire_named_mutex(MUTEX_PREFIX + self.name)
        if verdict == "taken":
            if debug:
                print(f"GUARD pid={os.getpid()} mutex held elsewhere; not primary", flush=True)
            return False
        if verdict == "error" and debug:
            print(f"GUARD pid={os.getpid()} CreateMutexW failed; proceeding without it", flush=True)
        self.mutex = handle

        QLocalServer.removeServer(self.name)
        probe = QLocalServer()
        if not probe.listen(self.name):
            if debug:
                print(f"GUARD pid={os.getpid()} primary but no channel: {probe.errorString()!r}",
                      flush=True)
            return True          # keep the pet; just no command channel
        self.server = probe
        self.server.newConnection.connect(self._on_connection)
        if debug:
            print(f"GUARD pid={os.getpid()} owns {self.name}", flush=True)
        return True

    def attach(self, handler) -> None:
        self._handler = handler

    def _on_connection(self) -> None:
        debug = os.environ.get("DESKTOPPET_GUARD_DEBUG") == "1"
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            if debug:
                print(f"CHANNEL pid={os.getpid()} accepted a command connection", flush=True)
            conn.readyRead.connect(lambda c=conn: self._read(c))
            conn.disconnected.connect(conn.deleteLater)

    def _read(self, conn) -> None:
        data = bytes(conn.readAll().data()).decode("utf-8", "replace").strip()
        reply = self._handler(data) if self._handler else ""
        if os.environ.get("DESKTOPPET_GUARD_DEBUG") == "1":
            print(f"CHANNEL pid={os.getpid()} cmd={data!r} handler={bool(self._handler)} "
                  f"reply_len={len(str(reply))}", flush=True)
        if reply:
            conn.write(str(reply).encode("utf-8"))
            conn.waitForBytesWritten(500)
        conn.disconnectFromServer()

    def close(self) -> None:
        if self.server is not None:
            self.server.close()
            self.server = None


def send_command(name: str, command: str, timeout_ms: int = 3000) -> str:
    """Client side, used by tools/accept_shots.py against the running pet."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtNetwork import QLocalSocket
    app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    sock = QLocalSocket()
    try:
        sock.connectToServer(name)
        if not sock.waitForConnected(timeout_ms):
            return ""
        sock.write(command.encode("utf-8"))
        sock.waitForBytesWritten(timeout_ms)
        sock.waitForReadyRead(timeout_ms)
        reply = bytes(sock.readAll().data()).decode("utf-8", "replace")
    finally:
        sock.disconnectFromServer()
        if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            sock.waitForDisconnected(1000)
        sock.deleteLater()
        app.processEvents()
    return reply
