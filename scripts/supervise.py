"""Keep one web process and one retry scheduler alive in a Render instance."""
import signal
import subprocess
import time


def supervise(commands, shutdown_seconds=20):
    children = []
    stopping = False
    previous_handlers = {}

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, stop)
        for command in commands:
            children.append(subprocess.Popen(command))
        while not stopping:
            for child in children:
                code = child.poll()
                if code is not None:
                    # A scheduler stopping must not leave an apparently healthy
                    # web service silently accumulating failed deliveries.
                    return code or 1
            time.sleep(0.5)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + shutdown_seconds
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
