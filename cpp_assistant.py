import subprocess
import threading
import sys
from typing import Optional, Callable


class CppAssistant:
    def __init__(
        self,
        binary_path: str = "./assistant",
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.binary_path = binary_path
        self.on_log = on_log or (lambda line: sys.stderr.write("Jarvis: " + line))
        self.proc: Optional[subprocess.Popen] = None
        self._stdout_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.proc is not None:
            return

        self.proc = subprocess.Popen(
            [self.binary_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def reader() -> None:
            assert self.proc is not None
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self.on_log(line)
            self.on_log("Jarvis \n")

        self._stdout_thread = threading.Thread(target=reader, daemon=True)
        self._stdout_thread.start()

    def send_chunk(self, text: str) -> None:
        if not text or self.proc is None or self.proc.stdin is None:
            return
        try:
            self.proc.stdin.write(text.replace("\n", " ") + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            self.on_log("BrokenPipeError while writing to Jarvis\n")

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except Exception:
            pass
        self.proc = None
