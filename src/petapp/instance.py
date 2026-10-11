"""Single-instance guard that doubles as the control channel for acceptance capture.

The spike showed the server must be inside a live Qt event loop for a second process to be
accepted, so this is a QLocalServer owned by the running app rather than a mutex.
"""

from __future__ import annotations

import sys

SERVER_NAME = "DesktopPetSakiko"


class InstanceGuard:
    def __init__(self, name: str = SERVER_NAME):
        self.name = name
        self.server = None
        self._handler = None

    def acquire(self) -> bool:
        """True when this process is the one that should keep running.

        A named pipe left behind by a killed instance makes ``listen()`` fail while no live
        primary answers. Recovery matters: without a re-listen the pet runs but the control
        channel is dead for its whole lifetime.
        """
        from PySide6.QtNetwork import QLocalServer, QLocalSocket

        probe = QLocalServer()
        if not probe.listen(self.name):
            sock = QLocalSocket()
            sock.connectToServer(self.name)
            live_primary = sock.waitForConnected(500)
            sock.abort()
            sock.deleteLater()
            if live_primary:
                return False
            QLocalServer.removeServer(self.name)
            probe.close()
            probe = QLocalServer()
            if not probe.listen(self.name):
                return True          # keep the pet; just no command channel
            self.server = probe
        else:
            self.server = probe
        self.server.newConnection.connect(self._on_connection)
        return True

    def attach(self, handler) -> None:
        self._handler = handler

    def _on_connection(self) -> None:
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._read(c))
            conn.disconnected.connect(conn.deleteLater)

    def _read(self, conn) -> None:
        data = bytes(conn.readAll().data()).decode("utf-8", "replace").strip()
        reply = self._handler(data) if self._handler else ""
        if reply:
            conn.write(str(reply).encode("utf-8"))
            conn.waitForBytesWritten(500)
        conn.disconnectFromServer()

    def close(self) -> None:
        if self.server is not None:
            self.server.close()


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
