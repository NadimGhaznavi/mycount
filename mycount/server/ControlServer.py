"""Serve MyCount Control independently of the visitor collector."""

import argparse
from http.server import ThreadingHTTPServer
import signal

from mycount.constants.DControl import DControl
from mycount.server.ControlHandler import ControlHandler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DControl.HOST)
    parser.add_argument("--port", type=int, default=DControl.PORT)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535.")

    def stop(signum, frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        with ThreadingHTTPServer((args.host, args.port), ControlHandler) as server:
            print(f"MyCount Control: http://{args.host}:{server.server_port}/", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    main()
