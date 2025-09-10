#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 ft_irc Test Runner - User-Friendly Edition

A simple, interactive test runner for your ft_irc project that makes testing easy!

✨ Features:
  • 🎯 Auto-detects your ircserv binary
  • 🌈 Colorful, clear output
  • 🔍 Smart file discovery
  • 🛡️  Memory leak detection with Valgrind
  • 📊 Beautiful test results
  • 🎛️  Interactive or command-line modes

🚀 Quick Start:
  Just run: python3 irc_test_runner.py
  
📚 Advanced Usage:
  python3 irc_test_runner.py --binary ./ircserv --tester v2 --valgrind

🎮 Interactive Mode (recommended for beginners):
  python3 irc_test_runner.py --interactive

Author: Enhanced for 42 students with ❤️
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

# Try to import tkinter for GUI file dialog
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

# --------------------------- Colors & UI Helpers ---------------------------

class Colors:
    """ANSI color codes for beautiful terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def colorize(text: str, color: str) -> str:
    """Add color to text if terminal supports it"""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{Colors.ENDC}"

def print_header(text: str) -> None:
    """Print a beautiful header"""
    border = "=" * (len(text) + 4)
    print(f"\n{colorize(border, Colors.CYAN)}")
    print(f"{colorize(f'  {text}  ', Colors.CYAN + Colors.BOLD)}")
    print(f"{colorize(border, Colors.CYAN)}\n")

def print_success(text: str) -> None:
    """Print success message"""
    print(f"{colorize('✅', Colors.GREEN)} {text}")

def print_error(text: str) -> None:
    """Print error message"""
    print(f"{colorize('❌', Colors.RED)} {text}")

def print_warning(text: str) -> None:
    """Print warning message"""
    print(f"{colorize('⚠️ ', Colors.YELLOW)} {text}")

def print_info(text: str) -> None:
    """Print info message"""
    print(f"{colorize('ℹ️ ', Colors.BLUE)} {text}")

def print_step(step: int, total: int, text: str) -> None:
    """Print a step in the process"""
    print(f"{colorize(f'[{step}/{total}]', Colors.BLUE)} {text}")

# --------------------------- GUI File Picker ---------------------------

def open_file_dialog(title: str = "Select ircserv binary", initial_dir: str = ".") -> str | None:
    """Open a GUI file picker dialog"""
    if not HAS_GUI:
        return None
    
    try:
        # Create a hidden root window
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Bring dialog to front
        
        # Configure dialog
        file_path = filedialog.askopenfilename(
            title=title,
            initialdir=initial_dir,
            filetypes=[
                ("Executable files", "ircserv"),
                ("All files", "*.*")
            ]
        )
        
        root.destroy()  # Clean up
        return file_path if file_path else None
        
    except Exception as e:
        print_warning(f"GUI file picker failed: {e}")
        return None

def ask_with_file_picker(prompt: str, default: str | None = None) -> str:
    """Ask for file path with optional GUI file picker"""
    if HAS_GUI:
        print(f"🎯 {prompt}")
        print(f"   📁 Click to browse files or type path manually")
        
        choice = ask("Choose method", "browse", ["browse", "type"])
        
        if choice == "browse":
            print_info("Opening file picker...")
            selected_file = open_file_dialog("Select your ircserv binary")
            if selected_file:
                print_success(f"Selected: {selected_file}")
                return selected_file
            else:
                print_warning("No file selected, falling back to manual input")
    
    # Fallback to manual input
    return ask(f"Path to {prompt.lower()}", default)

# --------------------------- Smart File Detection ---------------------------

def find_ircserv_binary() -> list[Path]:
    """Smart detection of ircserv binary in common locations"""
    possible_paths = [
        Path("./ircserv"),
        Path("../ircserv"),
        Path("./build/ircserv"),
        Path("./bin/ircserv"),
        Path("./ircserv/ircserv"),
        Path("./ft_irc/ircserv"),
    ]
    
    # Also search in current directory and subdirectories
    cwd = Path(".")
    for item in cwd.rglob("ircserv"):
        if item.is_file() and os.access(item, os.X_OK):
            possible_paths.append(item)
    
    # Remove duplicates and filter existing executable files
    found = []
    seen = set()
    for path in possible_paths:
        abs_path = path.resolve()
        if abs_path not in seen and path.exists() and os.access(path, os.X_OK):
            found.append(path)
            seen.add(abs_path)
    
    return found

def auto_detect_setup() -> dict:
    """Auto-detect the best setup for the user"""
    setup = {
        "binary": None,
        "testers": [],
        "suggestions": []
    }
    
    # Find ircserv binary
    binaries = find_ircserv_binary()
    if binaries:
        setup["binary"] = str(binaries[0])
        if len(binaries) > 1:
            setup["suggestions"].append(f"Found {len(binaries)} ircserv binaries. Using: {binaries[0]}")
    
    # Find testers
    script_dir = Path(__file__).resolve().parent
    for version, filename in [("v1", "irc_super_tester.py"), ("v2", "irc_super_tester_v2.py")]:
        if (script_dir / filename).exists():
            setup["testers"].append(version)
    
    return setup

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
            # Check if valgrind is available
            try:
                subprocess.run(["valgrind", "--version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print_error("Valgrind not found! Please install valgrind or run without --valgrind")
                raise FileNotFoundError("Valgrind not available")
            
            vg_prefix = default_valgrind_cmd()
            self.valgrind_log_file = self.outdir / f"valgrind.{int(time.time())}.log"
            vg_prefix += [f"--log-file={self.valgrind_log_file}"]

        self.server_log_file = self.outdir / "server.log"
        log = self.server_log_file.open("w", buffering=1)

        cmd = vg_prefix + server_cmd
        print_info(f"Starting server: {' '.join(shlex.quote(c) for c in cmd)}")
        
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

        print_info(f"Running {self.args.tester} tester...")
        
        # Show progress dots while running
        start_time = time.time()
        with tester_log.open("w", buffering=1) as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            
            # Simple progress indicator
            while proc.poll() is None:
                print(".", end="", flush=True)
                time.sleep(0.5)
            
            print()  # New line after dots
            elapsed = time.time() - start_time
            print_info(f"Tester completed in {elapsed:.1f} seconds")
            
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
        print_header("🚀 ft_irc Test Session Starting")
        
        port = self.args.port or find_free_port()
        print_step(1, 4, f"Using port {colorize(str(port), Colors.BOLD)}")

        # Start server
        print_step(2, 4, "Starting IRC server...")
        try:
            self.start_server(port)
        except Exception as e:
            print_error(f"Failed to start server: {e}")
            return 2
        
        print_info("Waiting for server to start listening...")
        ok = wait_for_listen(port, timeout=self.args.timeout)
        if not ok:
            self.stop_server()
            print_error(f"Server didn't start listening within {self.args.timeout} seconds")
            print_warning("Try increasing --timeout or check your server binary")
            return 2

        print_success("Server is ready!")

        # Run tester
        print_step(3, 4, f"Running {self.args.tester} tester...")
        rc = 99
        try:
            rc = self.run_tester(port)
        except Exception as e:
            print_error(f"Tester failed: {e}")
        finally:
            print_step(4, 4, "Shutting down server...")
            self.stop_server()

        # Beautiful summary
        self._print_summary(rc)
        return 0 if rc == 0 else 1
    
    def _print_summary(self, tester_rc: int) -> None:
        """Print a beautiful test summary"""
        print_header("📊 Test Results Summary")
        
        # Test status
        if tester_rc == 0:
            print_success(f"All tests passed! 🎉")
        else:
            print_error(f"Tests failed (exit code: {tester_rc})")
        
        # Log files
        print("\n📁 Log files:")
        if self.server_log_file and self.server_log_file.exists():
            size = self.server_log_file.stat().st_size
            print(f"   Server log: {colorize(str(self.server_log_file), Colors.BLUE)} ({size} bytes)")
        
        tester_log = self.outdir / 'tester.log'
        if tester_log.exists():
            size = tester_log.stat().st_size
            print(f"   Tester log: {colorize(str(tester_log), Colors.BLUE)} ({size} bytes)")

        # Valgrind summary
        vg = self.summarize_valgrind()
        if vg is not None:
            print(f"\n🔍 Memory analysis (Valgrind):")
            
            # Check for serious issues
            has_leaks = vg.get("definitely_lost", 0) > 0 or vg.get("indirectly_lost", 0) > 0
            has_errors = vg.get("errors", 0) > 0
            
            if not has_leaks and not has_errors:
                print_success("No memory leaks or errors detected! 🎯")
            else:
                if has_leaks:
                    print_error("Memory leaks detected!")
                if has_errors:
                    print_error(f"{vg.get('errors', 0)} memory errors found!")
            
            # Detailed breakdown
            print("   Detailed breakdown:")
            for k, v in vg.items():
                icon = "🔴" if k in ["definitely_lost", "indirectly_lost"] and v > 0 else "⚪"
                print(f"     {icon} {k.replace('_', ' ').title()}: {v}")
        else:
            print(f"\n🔍 Memory analysis: {colorize('Not enabled', Colors.YELLOW)} (use --valgrind to enable)")
        
        print(f"\n{colorize('💡 Tip:', Colors.YELLOW)} Check the log files for detailed information!")


# --------------------------- CLI ---------------------------

def ask(prompt: str, default: str | None = None, options: list[str] | None = None) -> str:
    """Enhanced input function with validation"""
    if options:
        options_str = "/".join(f"{colorize(opt, Colors.BOLD)}" if opt == default else opt for opt in options)
        prompt = f"{prompt} ({options_str})"
    
    suffix = f" [{colorize(default, Colors.GREEN)}]" if default is not None else ""
    
    while True:
        try:
            val = input(f"🎯 {prompt}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            if default is not None:
                print(f"\nUsing default: {default}")
                return default
            else:
                print_error("\nInput required. Exiting...")
                sys.exit(1)
        
        result = val or (default or "")
        
        if options and result not in options:
            print_error(f"Please choose one of: {', '.join(options)}")
            continue
        
        return result

def interactive_setup() -> argparse.Namespace:
    """Enhanced interactive setup with auto-detection"""
    print_header("🎮 Interactive Setup - Let's get your IRC server tested!")
    
    # Auto-detect setup
    setup = auto_detect_setup()
    
    # Show what we found
    if setup["suggestions"]:
        print("🔍 Auto-detection results:")
        for suggestion in setup["suggestions"]:
            print_info(suggestion)
        print()
    
    # Binary selection
    if setup["binary"]:
        print_success(f"Found ircserv binary: {setup['binary']}")
        use_detected = ask("Use this binary?", "y", ["y", "n"])
        if use_detected == "y":
            binary = setup["binary"]
        else:
            binary = ask_with_file_picker("your ircserv binary", "./ircserv")
    else:
        print_warning("No ircserv binary auto-detected")
        binary = ask_with_file_picker("your ircserv binary", "./ircserv")
    
    # Validate binary
    if not Path(binary).exists():
        print_error(f"Binary not found: {binary}")
        print_info("Make sure you've compiled your project first!")
        print_info("💡 Common locations: ./ircserv, ../ircserv, ./build/ircserv")
        
        # Try to suggest alternatives
        found_binaries = find_ircserv_binary()
        if found_binaries:
            print_success(f"Found these alternatives: {', '.join(str(b) for b in found_binaries)}")
            use_alt = ask("Use the first alternative?", "y", ["y", "n"])
            if use_alt == "y":
                binary = str(found_binaries[0])
            else:
                binary = ask_with_file_picker("your ircserv binary", "./ircserv")
        else:
            binary = ask_with_file_picker("your ircserv binary", "./ircserv")
            
        # Final validation
        if not Path(binary).exists():
            print_error(f"Still can't find binary: {binary}")
            print_error("Please compile your server first or provide the correct path")
            sys.exit(1)
    
    # Tester selection
    if setup["testers"]:
        available = ", ".join(setup["testers"])
        print_success(f"Available testers: {available}")
        if "v2" in setup["testers"]:
            default_tester = "v2"
        else:
            default_tester = setup["testers"][0]
    else:
        print_warning("No testers found in current directory")
        default_tester = "v2"
    
    tester = ask("Choose tester version", default_tester, ["v1", "v2"])
    
    # Other options
    password = ask("Server password", "pass")
    
    print("\n🔧 Advanced options:")
    use_vg = ask("Run with memory leak detection (Valgrind)?", "n", ["y", "n"]) == "y"
    verbose = ask("Enable verbose output?", "n", ["y", "n"]) == "y"
    
    # Output directory
    default_outdir = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    outdir = ask("Output directory for logs", default_outdir)
    
    # Port (optional)
    port_input = ask("Specific port to use (or auto-detect)", "auto")
    port = None if port_input == "auto" else int(port_input) if port_input.isdigit() else None
    
    print_header("🎯 Configuration Summary")
    print(f"📁 Binary: {colorize(binary, Colors.BLUE)}")
    print(f"🧪 Tester: {colorize(tester, Colors.BLUE)}")
    print(f"🔑 Password: {colorize(password, Colors.BLUE)}")
    print(f"🔍 Valgrind: {colorize('Yes' if use_vg else 'No', Colors.GREEN if use_vg else Colors.YELLOW)}")
    print(f"📝 Verbose: {colorize('Yes' if verbose else 'No', Colors.GREEN if verbose else Colors.YELLOW)}")
    print(f"📊 Output: {colorize(outdir, Colors.BLUE)}")
    
    confirm = ask("\nProceed with these settings?", "y", ["y", "n"])
    if confirm != "y":
        print_info("Setup cancelled by user")
        sys.exit(0)

    return argparse.Namespace(
        binary=binary,
        password=password,
        tester=tester,
        valgrind=use_vg,
        out=outdir,
        verbose=verbose,
        only=[],
        port=port,
        timeout=15.0,
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="🚀 ft_irc Test Runner - Enhanced Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Interactive mode (recommended)
  %(prog)s --interactive             # Force interactive mode
  %(prog)s --binary ./ircserv        # Quick test with auto-detection
  %(prog)s --binary ./ircserv --valgrind --tester v2  # Full test with memory check
  
For beginners: Just run '%(prog)s' and follow the prompts! 🎯
        """
    )
    p.add_argument("--binary", help="Path to your compiled ircserv binary")
    p.add_argument("--password", default="pass", help="IRC server password (default: pass)")
    p.add_argument("--tester", choices=["v1", "v2"], default="v2", help="Tester version to run (default: v2)")
    p.add_argument("--only", nargs="*", default=[], help="Run only specific named tests")
    p.add_argument("--port", type=int, help="Specific port to use (default: auto-detect)")
    p.add_argument("--timeout", type=float, default=15.0, help="Seconds to wait for server startup (default: 15)")
    p.add_argument("--valgrind", action="store_true", help="🔍 Run with memory leak detection")
    p.add_argument("--out", default=f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}", help="Output directory for logs")
    p.add_argument("--verbose", action="store_true", help="📝 Enable verbose tester output")
    p.add_argument("--interactive", action="store_true", help="🎮 Use interactive setup mode")
    return p


def main():
    print_header("🚀 ft_irc Test Runner - Enhanced Edition")
    
    ap = build_argparser()
    if len(sys.argv) == 1:
        # No flags: enter interactive mode by default
        ns = interactive_setup()
    else:
        ns = ap.parse_args()
        if ns.interactive:
            ns = interactive_setup()
        if not ns.binary:
            # Try auto-detection
            setup = auto_detect_setup()
            if setup["binary"]:
                print_success(f"Auto-detected binary: {setup['binary']}")
                ns.binary = setup["binary"]
            else:
                ap.error("--binary is required (or use --interactive for guided setup)")
    
    try:
        runner = Runner(ns)
        rc = runner.run()
        
        if rc == 0:
            print_success("🎉 All done! Check the results above.")
        else:
            print_error("❌ Some tests failed. Check the logs for details.")
        
        sys.exit(rc)
    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        print_info("💡 Tip: Make sure your ircserv is compiled and accessible")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{colorize('🛑 Interrupted by user', Colors.YELLOW)}")
        print_info("Goodbye! 👋")
        sys.exit(130)
