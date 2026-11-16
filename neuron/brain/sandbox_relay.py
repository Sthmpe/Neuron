"""Runs INSIDE the sandbox next to a web app. The sandbox has no network at all, so the app's
port cannot be reached from outside. This relay listens on a Unix socket in a folder shared
with the brain and passes each connection on to the app's port inside the sandbox.

    python3 /neuron_relay.py <socket path> <port> -- <command that starts the app>
"""
import os
import socket
import subprocess
import sys
import threading
import time


def pump(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()


def serve(sock_path, port):
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(sock_path)
    srv.listen(64)
    while True:
        conn, _ = srv.accept()
        try:
            for _ in range(100):                      # the app may still be starting
                try:
                    up = socket.create_connection(("127.0.0.1", port), timeout=5)
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                conn.close()
                continue
        except Exception:
            conn.close()
            continue
        up.settimeout(None)
        threading.Thread(target=pump, args=(conn, up), daemon=True).start()
        threading.Thread(target=pump, args=(up, conn), daemon=True).start()


def main():
    sock_path, port = sys.argv[1], int(sys.argv[2])
    cmd = sys.argv[sys.argv.index("--") + 1:]
    child = subprocess.Popen(cmd, env={**os.environ, "PORT": str(port)})
    threading.Thread(target=serve, args=(sock_path, port), daemon=True).start()
    os._exit(child.wait() & 0xFF)


if __name__ == "__main__":
    main()
