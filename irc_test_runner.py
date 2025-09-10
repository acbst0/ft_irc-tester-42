#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ft_irc Test Runner UI (no‑root, 42‑friendly)

What this does (quick):
  • Lets users point to their compiled ./ircserv binary (no sudo needed)
  • Starts the server on a free high port with a chosen password
  • Runs ONE of your two testers (v1 or v2)
  • Captures logs (server + tester) into a run directory
  • (Optional) Runs server under valgrind and parses leak summary; warns if leaks

Usage (non‑interactive):
  python3 irc_test_runner.py \
      --binary ./ircserv \
      --password pass \
      --tester v2 \
      --valgrind \
      --timeout 20 \
      --out runs/latest

Or just run without flags for a tiny interactive prompt:
  python3 irc_test_runner.py

Notes:
  • Assumes python3 is available and your testers are placed next to this file
    as `irc_super_tester.py` (v1) and `irc_super_tester_v2.py` (v2).
  • Uses only unprivileged ports and standard user permissions.
  • Valgrind section mirrors the common flags used in 42 defenses.

Author: for Ahmet & 42 peers
"""
from __future__ import annotations
import argparse
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# --------------------------- Helpers ---------------------------

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_listen(port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def default_valgrind_cmd() -> list[str]:
    """Valgrind flags commonly used in ft_irc defenses."""
    return [
        "valgrind",
        "-s",
        "--trace-children=no",
        "--leak-check=full",
        "--show-leak-kinds=all",
        "--track-origins=yes",
        "--track-fds=yes",
        "--error-limit=no",
        # log filename will be appended at runtime with PID interpolation
    ]


def parse_valgrind_log(text: str) -> dict:
    """Extract a tiny summary from valgrind output text."""
    # Look for the standard leak summary lines
    def get(pattern: str) -> int | None:
        m = re.search(pattern, text)
        return int(m.group(1)) if m else None

    return {
        "definitely_lost": get(r"definitely lost: *([0-9,]+) bytes") or 0,
        "indirectly_lost": get(r"indirectly lost: *([0-9,]+) bytes") or 0,
        "possibly_lost": get(r"possibly lost: *([0-9,]+) bytes") or 0,
        "still_reachable": get(r"still reachable: *([0-9,]+) bytes") or 0,
        "open_fds": get(r"Open file descriptor.*: *([0-9]+)") or 0,
        "errors": get(r"ERROR SUMMARY: *([0-9,]+) errors") or 0,
    }


# --------------------------- Core runner ---------------------------

class Runner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.outdir = Path(args.out)
        ensure_dir(self.outdir)
        self.server_proc: subprocess.Popen | None = None
        self.server_log_file: Path | None = None
        self.valgrind_log_file: Path | None = None

    # --- server lifecycle ---
    def start_server(self, port: int) -> None:
        password = self.args.password
        bin_path = Path(self.args.binary).resolve()
        if not bin_path.exists():
            raise FileNotFoundError(f"Binary not found: {bin_path}")

        server_cmd = [str(bin_path), str(port), password]
        env = os.environ.copy()
        env["FT_IRC_PORT"] = str(port)
        env["FT_IRC_PASS"] = password

        vg_prefix = []
        if self.args.valgrind:
            vg_prefix = default_valgrind_cmd()
            # unique per‑run pid will be set by valgrind; but we can pre‑choose a file
            self.valgrind_log_file = self.outdir / f"valgrind.{int(time.time())}.log"
            vg_prefix += [f"--log-file={self.valgrind_log_file}"]

        self.server_log_file = self.outdir / "server.log"
        log = self.server_log_file.open("w", buffering=1)

        cmd = vg_prefix + server_cmd
        print(f"[runner] starting server: {' '.join(shlex.quote(c) for c in cmd)}")
        self.server_proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            preexec_fn=os.setsid  # so we can kill the whole group
        )

    def stop_server(self) -> None:
        if not self.server_proc:
            return
        try:
            # send SIGINT to the whole group for graceful shutdown
            os.killpg(os.getpgid(self.server_proc.pid), signal.SIGINT)
            try:
                self.server_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.server_proc.pid), signal.SIGKILL)
                self.server_proc.wait(timeout=2)
        except Exception:
            pass
        finally:
            self.server_proc = None

    # --- testers ---
    def tester_path(self) -> Path:
        here = Path(__file__).resolve().parent
        if self.args.tester == "v1":
            path = here / "irc_super_tester.py"
        else:
            path = here / "irc_super_tester_v2.py"
        if not path.exists():
            raise FileNotFoundError(f"Tester not found: {path}")
        return path

    def run_tester(self, port: int) -> int:
        tester = self.tester_path()
        tester_log = self.outdir / "tester.log"
        cmd = [
            sys.executable, str(tester),
            "--host", "127.0.0.1",
            "--port", str(port),
            "--password", self.args.password,
        ]
        if self.args.verbose:
            cmd.append("--verbose")
        if self.args.only:
            cmd += ["--only", *self.args.only]

        print(f"[runner] running tester: {' '.join(shlex.quote(c) for c in cmd)}")
        with tester_log.open("w", buffering=1) as log:
            proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
            return proc.returncode

    # --- valgrind summary ---
    def summarize_valgrind(self) -> dict | None:
        if not self.args.valgrind:
            return None
        lf = self.valgrind_log_file
        if lf and lf.exists():
            txt = lf.read_text(errors="ignore")
            return parse_valgrind_log(txt)
        # If log file unknown, try to find vg.*.log under outdir
        for p in sorted(self.outdir.glob("valgrind*.log")):
            txt = p.read_text(errors="ignore")
            return parse_valgrind_log(txt)
        return None

    # --- orchestrate ---
    def run(self) -> int:
        port = self.args.port or find_free_port()
        print(f"[runner] using port {port}")

        # Start server
        self.start_server(port)
        ok = wait_for_listen(port, timeout=self.args.timeout)
        if not ok:
            self.stop_server()
            print("[runner] ERROR: server didn't start listening in time")
            return 2

        # Run tester
        rc = 99
        try:
            rc = self.run_tester(port)
        finally:
            self.stop_server()

        # Summaries
        tester_ok = (rc == 0)
        print(f"\n[summary] tester status: {'PASS' if tester_ok else 'FAIL'} (rc={rc})")
        if self.server_log_file:
            print(f"[summary] server log: {self.server_log_file}")
        print(f"[summary] tester log: {self.outdir / 'tester.log'}")

        vg = self.summarize_valgrind()
        if vg is not None:
            print("[summary] valgrind:")
            for k, v in vg.items():
                print(f"  - {k.replace('_', ' ')}: {v}")
            if vg.get("definitely_lost", 0) > 0 or vg.get("indirectly_lost", 0) > 0:
                print("[summary] WARNING: memory leaks detected!")
            if vg.get("open_fds", 0) > 0:
                print("[summary] NOTE: open file descriptors reported by valgrind")
        else:
            print("[summary] valgrind: (not enabled)")

        return 0 if tester_ok else 1


# --------------------------- CLI ---------------------------

def ask(prompt: str, default: str | None = None) -> str:
    sfx = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{sfx}: ").strip()
    return val or (default or "")


def interactive_defaults() -> argparse.Namespace:
    print("\n== ft_irc Test Runner (interactive) ==\n")
    binary = ask("Path to your compiled server binary", "./ircserv")
    password = ask("Server password (PASS)", "pass")
    tester = ask("Choose tester (v1 or v2)", "v2")
    use_vg = ask("Run under valgrind? (y/N)", "N").lower().startswith("y")
    outdir = ask("Output directory for logs", f"runs/{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    verbose = ask("Verbose tester output? (y/N)", "N").lower().startswith("y")
    port = ask("Port (enter for auto)", "").strip()

    ns = argparse.Namespace(
        binary=binary,
        password=password,
        tester=tester if tester in {"v1", "v2"} else "v2",
        valgrind=use_vg,
        out=outdir,
        verbose=verbose,
        only=[],
        port=int(port) if port.isdigit() else None,
        timeout=15.0,
    )
    return ns


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ft_irc Test Runner UI (no‑root)")
    p.add_argument("--binary", help="Path to ./ircserv (compiled)")
    p.add_argument("--password", default="pass", help="IRC PASS password")
    p.add_argument("--tester", choices=["v1", "v2"], default="v2", help="Which tester to run")
    p.add_argument("--only", nargs="*", default=[], help="Tester: run only these named tests")
    p.add_argument("--port", type=int, help="Port to use (default: auto)")
    p.add_argument("--timeout", type=float, default=15.0, help="Seconds to wait for server to listen")
    p.add_argument("--valgrind", action="store_true", help="Run server under valgrind and parse leaks")
    p.add_argument("--out", default=f"runs/{datetime.now().strftime('%Y%m%d_%H%M%S')}", help="Directory for logs")
    p.add_argument("--verbose", action="store_true", help="Tester: verbose output")
    p.add_argument("--interactive", action="store_true", help="Use interactive prompts")
    return p


def main():
    ap = build_argparser()
    if len(sys.argv) == 1:
        # No flags: enter interactive mode by default
        ns = interactive_defaults()
    else:
        ns = ap.parse_args()
        if ns.interactive:
            ns = interactive_defaults()
        if not ns.binary:
            ap.error("--binary is required (or use --interactive)")
    runner = Runner(ns)
    rc = runner.run()
    sys.exit(rc)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[runner] interrupted by user")
