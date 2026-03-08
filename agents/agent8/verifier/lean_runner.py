"""
lean_runner.py — High-level proof verification interface.

Wraps repl_client.py in the breadboard CheckRequest / CheckResult interface,
and also provides a standalone verify() function for direct use.

This module IS the implementation of the breadboard FirecrackerReplService stub.
The HTTP API in breadboard/agentic_coder_prototype/api/cli_bridge/ will work
unchanged once this is wired in as the backend.
"""

from __future__ import annotations

import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add breadboard to path so we can import its data types
_REPO_ROOT = Path(__file__).resolve().parents[1] / "breadboard"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from breadboard.lean_repl import (
    CheckRequest,
    CheckResult,
    ErrorSeverity,
    FirecrackerReplMetrics,
    FirecrackerReplService,
    LeanError,
    Sorry,
)
from repl_client import LeanReplClient, ReplError, ReplSession, ReplTimeout


# ------------------------------------------------------------------
# Parse Lean error/sorry output from CommandRepl error strings
# ------------------------------------------------------------------

def _parse_errors(error_str: Optional[str]) -> tuple[list[LeanError], list[Sorry]]:
    """
    Parse Lean error output into structured LeanError and Sorry lists.

    Lean error messages from CommandRepl look like:
      '<stdin>:2:0: error: unknown identifier 'foo''
      '<stdin>:3:4: warning: declaration uses 'sorry''

    Sorry detection: if the error contains 'sorry', we extract it as a Sorry.
    """
    errors: list[LeanError] = []
    sorries: list[Sorry] = []

    if not error_str:
        return errors, sorries

    for line in error_str.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Parse position: <stdin>:LINE:COL: SEVERITY: MESSAGE
        pos_line: Optional[int] = None
        pos_col: Optional[int] = None
        severity = ErrorSeverity.ERROR
        message = line

        if line.startswith("<stdin>:") or line.startswith("stdin>:"):
            parts = line.split(":", 4)
            if len(parts) >= 4:
                try:
                    pos_line = int(parts[1])
                    pos_col = int(parts[2])
                    sev_msg = parts[3].strip()
                    if "warning" in sev_msg:
                        severity = ErrorSeverity.WARNING
                    elif "info" in sev_msg:
                        severity = ErrorSeverity.INFO
                    message = parts[4].strip() if len(parts) > 4 else sev_msg
                except (ValueError, IndexError):
                    pass

        # Detect sorry specifically
        if "sorry" in message.lower() and "uses 'sorry'" in message.lower():
            sorries.append(Sorry(pos_line=pos_line, pos_col=pos_col, goal=None))
        else:
            errors.append(
                LeanError(
                    severity=severity,
                    message=message,
                    pos_line=pos_line,
                    pos_col=pos_col,
                )
            )

    return errors, sorries


# ------------------------------------------------------------------
# Subprocess FirecrackerReplService implementation
# ------------------------------------------------------------------

class SubprocessReplService(FirecrackerReplService):
    """
    Implements FirecrackerReplService using a persistent LeanDojo REPL subprocess.

    This replaces the Firecracker VM layer with a local subprocess.
    The API contract (CheckRequest → CheckResult + metrics) is identical.

    state_ref here is an integer string representing the saved REPL sid.
    """

    def __init__(self):
        self._client: Optional[LeanReplClient] = None
        self._base_sid: Optional[int] = None
        self._started = False

    def start(self) -> None:
        """Start the Lean subprocess and run import Mathlib once."""
        if self._started:
            return
        print("Starting Lean subprocess (Mathlib loads from entry file — ~100s on /mnt/c/)...")
        t0 = time.time()
        self._client = LeanReplClient()
        self._client.start()  # blocks until REPL> {"sid":0} received — Mathlib already loaded

        # sid=0 from the REPL is already post-Mathlib (import Mathlib is in the entry file)
        self._base_sid = 0
        elapsed = time.time() - t0
        print(f"Lean ready. Mathlib loaded in {elapsed:.1f}s. base_sid={self._base_sid}")
        self._started = True

    def stop(self) -> None:
        if self._client:
            self._client.stop()
            self._client = None
        self._started = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ------------------------------------------------------------------
    # FirecrackerReplService interface
    # ------------------------------------------------------------------

    def submit_request_with_metrics(
        self, request: CheckRequest
    ) -> tuple[CheckResult, list[FirecrackerReplMetrics]]:
        if not self._started:
            self.start()

        t_restore = time.time()
        # "restore" = resolve which sid to branch from
        start_sid = self._resolve_state_ref(request.state_ref)
        restore_ms = (time.time() - t_restore) * 1000

        t_repl = time.time()
        result = self._run_commands(
            request=request,
            start_sid=start_sid,
        )
        repl_ms = (time.time() - t_repl) * 1000

        metrics = [FirecrackerReplMetrics(repl_ms=repl_ms, restore_ms=restore_ms)]
        return result, metrics

    def submit_batch_requests(
        self, requests: list[CheckRequest]
    ) -> tuple[list[CheckResult], list[list[FirecrackerReplMetrics]]]:
        if not self._started:
            self.start()

        results = []
        metrics_rows = []
        for req in requests:
            result, metrics = self.submit_request_with_metrics(req)
            results.append(result)
            metrics_rows.append(metrics)
        return results, metrics_rows

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_state_ref(self, state_ref: Optional[str]) -> int:
        """Map a state_ref string to a REPL sid integer."""
        if state_ref is None:
            return self._base_sid or 0
        try:
            sid = int(state_ref)
            return sid
        except (ValueError, TypeError):
            # Fall back to base
            return self._base_sid or 0

    def _run_commands(self, request: CheckRequest, start_sid: int) -> CheckResult:
        request_id = str(uuid.uuid4())
        all_errors: list[LeanError] = []
        all_sorries: list[Sorry] = []
        messages: list[str] = []
        current_sid = start_sid
        new_state_ref: Optional[str] = None
        success = True

        timeout = request.timeout_s or 60.0

        for cmd in request.commands:
            try:
                r = self._client.send(current_sid, cmd, timeout=timeout)
            except ReplTimeout:
                all_errors.append(
                    LeanError(
                        severity=ErrorSeverity.ERROR,
                        message=f"Timeout after {timeout}s checking: {cmd[:80]}",
                    )
                )
                success = False
                break
            except ReplError as e:
                all_errors.append(
                    LeanError(severity=ErrorSeverity.ERROR, message=str(e))
                )
                success = False
                break

            if r.error:
                errs, sorries = _parse_errors(r.error)
                all_errors.extend(errs)
                all_sorries.extend(sorries)
                # Hard errors stop execution
                if errs:
                    success = False
                    break
                # Sorries mark proof as incomplete
                if sorries:
                    success = False
            else:
                # Sorry can appear as a plain stdout warning (not in error field)
                if r.has_sorry:
                    all_sorries.append(Sorry(pos_line=None, pos_col=None, goal=None))
                    success = False
                else:
                    messages.append(f"ok: {cmd[:60]}")

            if r.sid is not None:
                current_sid = r.sid

        if success and request.want_state:
            new_state_ref = str(current_sid)

        return CheckResult(
            request_id=request_id,
            success=success,
            messages=messages,
            errors=all_errors,
            sorries=all_sorries,
            new_state_ref=new_state_ref,
        )


# ------------------------------------------------------------------
# Standalone convenience function
# ------------------------------------------------------------------

_default_service: Optional[SubprocessReplService] = None


def get_service() -> SubprocessReplService:
    """Get or create the global service instance."""
    global _default_service
    if _default_service is None:
        _default_service = SubprocessReplService()
    return _default_service


def verify(
    proof_text: str,
    *,
    statement: Optional[str] = None,
    state_ref: Optional[str] = None,
    timeout_s: float = 60.0,
    want_state: bool = False,
) -> CheckResult:
    """
    Verify a Lean proof. Starts the service on first call (loads Mathlib once).

    Args:
        proof_text:  The full proof body, e.g. "by\n  simp\n  ring"
                     OR a complete theorem declaration.
        statement:   Optional theorem statement to prepend.
                     If provided, combined as: statement + "\n" + proof_text
        state_ref:   Optional REPL state to branch from (default: post-import-Mathlib).
        timeout_s:   Per-command timeout in seconds.
        want_state:  If True, return new_state_ref for incremental use.

    Returns:
        CheckResult with success, errors, sorries, new_state_ref.

    Example:
        result = verify("theorem t : 1 + 1 = 2 := by decide")
        assert result.success

        result = verify(
            statement="theorem C_ne_zero {r : R} (h : r ≠ 0) : (C r : HahnSeries Γ R) ≠ 0",
            proof_text="by\\n  contrapose! h\\n  rw [← C_zero] at h\\n  exact C_injective h"
        )
    """
    svc = get_service()
    if not svc._started:
        svc.start()

    if statement:
        combined = f"{statement} :=\n{proof_text}"
    else:
        combined = proof_text

    req = CheckRequest(
        commands=[combined],
        state_ref=state_ref,
        timeout_s=timeout_s,
        want_state=want_state,
    )
    result, _ = svc.submit_request_with_metrics(req)
    return result


def verify_with_preamble(
    preamble: list[str],
    theorem: str,
    *,
    timeout_s: float = 60.0,
) -> CheckResult:
    """
    Verify a theorem that needs additional setup beyond import Mathlib.

    Args:
        preamble:  Commands to run after import Mathlib, e.g.
                   ["open HahnSeries", "variable {Γ : Type*} {R : Type*}"]
        theorem:   The full theorem declaration + proof.

    Returns:
        CheckResult
    """
    svc = get_service()
    if not svc._started:
        svc.start()

    commands = preamble + [theorem]
    req = CheckRequest(
        commands=commands,
        state_ref=None,
        timeout_s=timeout_s,
    )
    result, _ = svc.submit_request_with_metrics(req)
    return result
