"""
LeanDojo CommandRepl subprocess client.

Spawns a persistent Lean process inside the LeanDojo mathlib4 directory,
sends JSON commands via stdin, receives JSON responses via stdout.

Protocol (from Lean4Repl.lean CommandRepl):
  Send:    {"sid": <int>, "cmd": "<lean code>"}
  Receive: {"sid": <int>, "error": <str|null>}

State IDs are monotonically increasing integers.
sid=0 is the initial empty environment.
Each successful command produces sid+1.
Commands can branch from any saved sid.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Path to the LeanDojo mathlib4 checkout with pre-built .olean files
# Windows native path (used when running from Windows Python)
_MATHLIB_WIN = Path(
    r"C:/Users/bnwboi/.cache/lean_dojo/repos"
    r"/gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
)
# WSL path (used when running from WSL Python)
_MATHLIB_WSL = Path(
    "/mnt/c/Users/bnwboi/.cache/lean_dojo/repos"
    "/gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
)
MATHLIB_DIR = _MATHLIB_WSL if _MATHLIB_WSL.exists() else _MATHLIB_WIN

# The toolchain pinned in that mathlib (leanprover/lean4:v4.10.0-rc1)
LEAN_TOOLCHAIN = "leanprover/lean4:v4.10.0-rc1"

# Lean invocation: run the CommandRepl via lake env
# lake env ensures the mathlib .olean cache is on the search path
LEAN_CMD = ["lake", "env", "lean"]  # file path appended at runtime

# Temp file written in mathlib dir to start the REPL
# Must NOT use --stdin — Lean's parser buffers stdin, conflicting with REPL's IO.getStdin
REPL_ENTRY_FILE = "/tmp/lean_repl_entry.lean"
REPL_ENTRY_CONTENT = "import Mathlib\nimport Lean4Repl\n#lean_dojo_repl\n"

# How long to wait for the REPL ready signal.
# import Mathlib from /mnt/c/ (Windows FS via 9P) takes ~100s.
STARTUP_TIMEOUT_S = 300.0

# How long to wait for a single command response
COMMAND_TIMEOUT_S = 60.0


@dataclass
class ReplResponse:
    sid: Optional[int]
    error: Optional[str]
    raw: dict = field(default_factory=dict)
    stdout_lines: list = field(default_factory=list)  # non-JSON lines printed before response

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def has_sorry(self) -> bool:
        """Lean prints sorry warnings as plain stdout lines, not in the error field."""
        for line in self.stdout_lines:
            if "sorry" in line.lower():
                return True
        return False


class ReplError(Exception):
    pass


class ReplTimeout(ReplError):
    pass


class LeanReplClient:
    """
    Persistent Lean CommandRepl subprocess.

    Usage:
        client = LeanReplClient()
        client.start()                          # boots Lean, loads mathlib (~30-60s cold)
        r = client.send(0, "import Mathlib")    # returns ReplResponse(sid=1, error=None)
        r = client.send(1, "theorem t : 1+1=2 := by decide")
        assert r.ok
        client.stop()

    Or use as context manager:
        with LeanReplClient() as client:
            r = client.send(0, "#check Nat.add_comm")
    """

    def __init__(
        self,
        mathlib_dir: Path = MATHLIB_DIR,
        startup_timeout: float = STARTUP_TIMEOUT_S,
        command_timeout: float = COMMAND_TIMEOUT_S,
    ):
        self.mathlib_dir = mathlib_dir
        self.startup_timeout = startup_timeout
        self.command_timeout = command_timeout
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._started = False
        # Reader thread feeds stdout into this queue (cross-platform: avoids select() on Windows)
        self._stdout_queue: queue.Queue[bytes] = queue.Queue()
        self._reader_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Lean subprocess and wait for the REPL to be ready."""
        if self._started:
            return

        # Write the REPL entry file (preamble processed as a file, not --stdin,
        # so Lean's parser doesn't buffer stdin before the REPL loop starts)
        Path(REPL_ENTRY_FILE).write_text(REPL_ENTRY_CONTENT)

        env = os.environ.copy()
        # Ensure WSL elan is on PATH
        home = os.path.expanduser("~")
        env["PATH"] = f"{home}/.elan/bin:" + env.get("PATH", "")

        self._proc = subprocess.Popen(
            LEAN_CMD + [REPL_ENTRY_FILE],
            cwd=str(self.mathlib_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )

        # Start background reader thread — avoids select() which doesn't work with
        # pipes on Windows. The thread does blocking reads and feeds a queue.
        self._stdout_queue = queue.Queue()
        self._reader_thread = threading.Thread(
            target=self._stdout_reader, daemon=True
        )
        self._reader_thread.start()

        # Wait for the initial ready signal: REPL> {"sid": 0, ...}
        self._wait_for_ready()
        self._started = True

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.stdin.write(b"exit\n")
                self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None
        self._started = False
        # Unblock the reader thread if it's waiting on the queue
        if self._reader_thread and self._reader_thread.is_alive():
            self._stdout_queue.put(b"")  # sentinel

    def __enter__(self) -> "LeanReplClient":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Core send/receive
    # ------------------------------------------------------------------

    def send(self, sid: int, cmd: str, timeout: Optional[float] = None) -> ReplResponse:
        """
        Send a command against the saved state `sid`.
        Returns ReplResponse with the new sid and any error.
        """
        if not self._started:
            raise ReplError("Client not started. Call start() first.")

        timeout = timeout or self.command_timeout
        # ensure_ascii=False so SMP Unicode characters (e.g. 𝒰 U+1D4B0) are
        # sent as literal UTF-8 rather than \ud835\udc30 surrogate pairs, which
        # Lean's JSON parser does not accept as valid identifier characters.
        payload = json.dumps({"sid": sid, "cmd": cmd}, ensure_ascii=False) + "\n"

        with self._lock:
            try:
                self._proc.stdin.write(payload.encode())
                self._proc.stdin.flush()
            except BrokenPipeError as e:
                raise ReplError(f"Lean process died: {e}") from e

            return self._read_response(timeout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_for_ready(self) -> None:
        """Read until we get the initial {"sid": 0} ready signal."""
        deadline = time.time() + self.startup_timeout
        buf = b""
        while time.time() < deadline:
            if self._proc.poll() is not None:
                stderr = self._proc.stderr.read().decode(errors="replace")
                raise ReplError(f"Lean process exited during startup.\nstderr:\n{stderr}")
            chunk = self._read_chunk(timeout=2.0)
            if chunk:
                buf += chunk
                # The REPL startup prints lines before the JSON; look for the JSON
                for line in buf.split(b"\n"):
                    line = line.strip()
                    if line.startswith(b"REPL> "):
                        json_part = line[len(b"REPL> "):]
                        try:
                            obj = json.loads(json_part)
                            if isinstance(obj, dict) and obj.get("sid") == 0:
                                return
                        except json.JSONDecodeError:
                            pass
        raise ReplTimeout(
            f"Lean REPL did not become ready within {self.startup_timeout}s.\n"
            f"Partial output: {buf[:500]!r}"
        )

    def _read_response(self, timeout: float) -> ReplResponse:
        """Read stdout until we get a REPL> JSON line. Collect intermediate lines."""
        deadline = time.time() + timeout
        buf = b""
        stdout_lines: list[str] = []
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise ReplError("Lean process died while waiting for response.")
            chunk = self._read_chunk(timeout=min(1.0, deadline - time.time()))
            if chunk:
                buf += chunk
                lines = buf.split(b"\n")
                # Keep last incomplete line in buf
                buf = lines[-1]
                for line in lines[:-1]:
                    decoded = line.decode(errors="replace").strip()
                    if decoded.startswith("REPL> "):
                        json_part = decoded[len("REPL> "):]
                        try:
                            obj = json.loads(json_part)
                            return ReplResponse(
                                sid=obj.get("sid"),
                                error=obj.get("error"),
                                raw=obj,
                                stdout_lines=stdout_lines,
                            )
                        except json.JSONDecodeError:
                            stdout_lines.append(decoded)
                    elif decoded:
                        stdout_lines.append(decoded)
        raise ReplTimeout(
            f"No response within {timeout}s.\nPartial: {buf[:300]!r}"
        )

    def _stdout_reader(self) -> None:
        """Background thread: reads stdout in chunks, feeds self._stdout_queue."""
        try:
            while self._proc and self._proc.poll() is None:
                chunk = os.read(self._proc.stdout.fileno(), 4096)
                if chunk:
                    self._stdout_queue.put(chunk)
                else:
                    break
        except Exception:
            pass

    def _read_chunk(self, timeout: float) -> bytes:
        """Pull a chunk from the stdout queue with timeout (cross-platform)."""
        if timeout <= 0:
            return b""
        try:
            return self._stdout_queue.get(timeout=timeout)
        except queue.Empty:
            return b""


# ------------------------------------------------------------------
# Simple session helper: keeps a base state_ref and branches from it
# ------------------------------------------------------------------

class ReplSession:
    """
    High-level session on top of LeanReplClient.
    Maintains a base_sid (e.g. after import Mathlib) and lets you
    send theorem checks that all branch from it.
    """

    def __init__(self, client: LeanReplClient):
        self.client = client
        self.base_sid: Optional[int] = None
        self._sid_counter: int = 0

    def setup(self, preamble_commands: list[str]) -> None:
        """
        Run setup commands sequentially (e.g. ["import Mathlib", "open HahnSeries"]).
        Saves the resulting sid as base_sid for all subsequent checks.
        """
        current_sid = 0
        for cmd in preamble_commands:
            r = self.client.send(current_sid, cmd, timeout=300.0)
            if not r.ok:
                raise ReplError(f"Setup command failed: {cmd!r}\nError: {r.error}")
            current_sid = r.sid
        self.base_sid = current_sid

    def check(self, cmd: str, timeout: float = 60.0) -> ReplResponse:
        """
        Check a command against base_sid (non-destructive — branches from base).
        """
        if self.base_sid is None:
            raise ReplError("Call setup() first to establish base state.")
        return self.client.send(self.base_sid, cmd, timeout=timeout)

    def check_incremental(self, cmds: list[str], timeout: float = 60.0) -> list[ReplResponse]:
        """
        Run commands sequentially, each building on the previous result.
        First command branches from base_sid.
        Returns list of responses in order.
        """
        if self.base_sid is None:
            raise ReplError("Call setup() first.")
        responses = []
        current_sid = self.base_sid
        for cmd in cmds:
            r = self.client.send(current_sid, cmd, timeout=timeout)
            responses.append(r)
            if not r.ok:
                break
            current_sid = r.sid
        return responses


# ------------------------------------------------------------------
# Pool of pre-warmed REPL workers for parallel proof checking
# ------------------------------------------------------------------

class ReplPool:
    """
    Pool of N pre-warmed LeanReplClient processes for parallel checking.

    All workers run the same preamble (default: "import Mathlib") once at
    startup and share the read-only .olean files on disk — the OS deduplicates
    those pages in RAM, so N=4 workers cost ~10-14 GB, not 4×8 GB.

    Usage:
        pool = ReplPool(size=4)
        pool.start()                          # boots N workers in parallel (~60-90s)
        results = pool.map(list_of_commands)  # checks in parallel
        pool.stop()

    Or as context manager:
        with ReplPool(size=4) as pool:
            results = pool.map(commands)
    """

    def __init__(
        self,
        size: int = 4,
        preamble: Optional[list[str]] = None,
        startup_timeout: float = STARTUP_TIMEOUT_S,
        command_timeout: float = COMMAND_TIMEOUT_S,
        start_stagger_s: float = 4.0,
    ):
        self.size = size
        # Default preamble is empty: the REPL entry file already runs `import Mathlib`
        # before the REPL loop starts, so sid=0 is already post-Mathlib.
        # Sending `import Mathlib` again causes "invalid import" errors.
        self.preamble = preamble if preamble is not None else []
        self.start_stagger_s = start_stagger_s  # seconds between worker launches to avoid lake lock
        self.startup_timeout = startup_timeout
        self.command_timeout = command_timeout
        self._sessions: list[ReplSession] = []
        # Queue holds indices of currently-idle sessions
        self._idle: queue.Queue[int] = queue.Queue()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Boot all N workers in parallel and run the preamble on each."""
        clients = [
            LeanReplClient(
                startup_timeout=self.startup_timeout,
                command_timeout=self.command_timeout,
            )
            for _ in range(self.size)
        ]
        errors: list[str] = []
        lock = threading.Lock()

        def _boot(idx: int) -> None:
            try:
                clients[idx].start()
                session = ReplSession(clients[idx])
                session.setup(self.preamble)
                with lock:
                    self._sessions.append((idx, session))
            except Exception as e:
                with lock:
                    errors.append(f"Worker {idx} failed to start: {e}")

        # Stagger launches to avoid all workers contending on `lake env`'s exclusive
        # file lock (.lake/lock). The 70s Mathlib-warm phase runs in parallel;
        # only the initial lake-env spawn is serialised by this stagger.
        threads = [threading.Thread(target=_boot, args=(i,), daemon=True) for i in range(self.size)]
        for i, t in enumerate(threads):
            if i > 0 and self.start_stagger_s > 0:
                time.sleep(self.start_stagger_s)
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise ReplError("Some workers failed to start:\n" + "\n".join(errors))

        # Sort sessions by index so the queue is ordered deterministically
        self._sessions.sort(key=lambda x: x[0])
        for idx, _ in self._sessions:
            self._idle.put(idx)

    def stop(self) -> None:
        """Terminate all worker processes."""
        for _, session in self._sessions:
            try:
                session.client.stop()
            except Exception:
                pass
        self._sessions.clear()
        # Drain the idle queue
        while not self._idle.empty():
            try:
                self._idle.get_nowait()
            except queue.Empty:
                break

    def __enter__(self) -> "ReplPool":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, cmd: str, timeout: Optional[float] = None) -> ReplResponse:
        """
        Check a single command using any idle worker.
        Blocks until a worker is available.
        """
        timeout = timeout or self.command_timeout
        idx = self._idle.get()  # blocks until a worker is free
        try:
            _, session = self._sessions[idx]
            return session.check(cmd, timeout=timeout)
        finally:
            self._idle.put(idx)

    def map(
        self,
        cmds: list[str],
        timeout: Optional[float] = None,
        max_workers: Optional[int] = None,
    ) -> list[ReplResponse]:
        """
        Check many commands in parallel.
        Returns responses in the same order as `cmds`.
        `max_workers` caps the thread pool (defaults to pool size).
        """
        timeout = timeout or self.command_timeout
        n_threads = min(max_workers or self.size, self.size, len(cmds))
        results: list[Optional[ReplResponse]] = [None] * len(cmds)

        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            future_to_idx = {
                executor.submit(self.check, cmd, timeout): i
                for i, cmd in enumerate(cmds)
            }
            for future in as_completed(future_to_idx):
                i = future_to_idx[future]
                try:
                    results[i] = future.result()
                except Exception as e:
                    # Wrap exceptions as error responses so callers get a uniform type
                    results[i] = ReplResponse(sid=None, error=str(e))

        return results  # type: ignore[return-value]
