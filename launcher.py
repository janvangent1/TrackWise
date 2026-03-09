"""
TrackWise Web — Desktop Launcher (Windows)

A Python tkinter GUI to start/stop the web server locally,
open the browser, and view server logs in real time.

Usage:
    python launcher.py

Requirements: tkinter (built-in), subprocess, threading
"""

from __future__ import annotations

import os
import platform
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
ROOT = Path(__file__).parent
BACKEND_DIR = ROOT / "web" / "backend"
VENV_DIR = ROOT / "web" / ".venv"

if platform.system() == "Windows":
    PYTHON_EXE = VENV_DIR / "Scripts" / "python.exe"
    UVICORN_EXE = VENV_DIR / "Scripts" / "uvicorn.exe"
else:
    PYTHON_EXE = VENV_DIR / "bin" / "python"
    UVICORN_EXE = VENV_DIR / "bin" / "uvicorn"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


# ──────────────────────────────────────────────
# Launcher App
# ──────────────────────────────────────────────

class TrackWiseLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TrackWise Launcher")
        self.resizable(True, True)
        self.geometry("700x520")
        self.minsize(560, 400)

        self._server_proc: subprocess.Popen | None = None
        self._log_queue: queue.Queue = queue.Queue()
        self._running = False

        self._configure_style()
        self._build_ui()
        self._start_log_drain()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Style ──────────────────────────────────
    def _configure_style(self):
        style = ttk.Style(self)
        available = style.theme_names()
        if "clam" in available:
            style.theme_use("clam")
        style.configure("TButton", padding=6)
        style.configure("Start.TButton",  background="#27ae60", foreground="white", font=("Segoe UI", 10, "bold"))
        style.configure("Stop.TButton",   background="#e74c3c", foreground="white", font=("Segoe UI", 10, "bold"))
        style.configure("Open.TButton",   background="#4a90e2", foreground="white", font=("Segoe UI", 10, "bold"))
        style.configure("Install.TButton",background="#f39c12", foreground="white", font=("Segoe UI",  9))

    # ── UI ────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#1a1d23", height=56)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🗺️ TrackWise Web Launcher", bg="#1a1d23", fg="#4a90e2",
                 font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, padx=16, pady=10)
        self._status_lbl = tk.Label(hdr, text="● Stopped", bg="#1a1d23", fg="#e74c3c",
                                    font=("Segoe UI", 10))
        self._status_lbl.pack(side=tk.RIGHT, padx=16)

        # Config row
        cfg_frame = ttk.LabelFrame(self, text="Server Configuration", padding=8)
        cfg_frame.pack(fill=tk.X, padx=12, pady=(8, 0))

        ttk.Label(cfg_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self._host_var = tk.StringVar(value=DEFAULT_HOST)
        ttk.Entry(cfg_frame, textvariable=self._host_var, width=18).grid(row=0, column=1, padx=(0, 16))

        ttk.Label(cfg_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=(0, 4))
        self._port_var = tk.StringVar(value=str(DEFAULT_PORT))
        ttk.Entry(cfg_frame, textvariable=self._port_var, width=8).grid(row=0, column=3, padx=(0, 16))

        self._reload_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg_frame, text="Auto-reload (dev)", variable=self._reload_var).grid(
            row=0, column=4, padx=(0, 8))

        # Action buttons
        btn_frame = tk.Frame(self, bg=self.cget("bg"))
        btn_frame.pack(fill=tk.X, padx=12, pady=8)

        self._start_btn = ttk.Button(btn_frame, text="▶  Start Server",
                                     style="Start.TButton", command=self._start_server)
        self._start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._stop_btn = ttk.Button(btn_frame, text="■  Stop Server",
                                    style="Stop.TButton", command=self._stop_server, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._browser_btn = ttk.Button(btn_frame, text="🌐  Open Browser",
                                       style="Open.TButton", command=self._open_browser, state=tk.DISABLED)
        self._browser_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._install_btn = ttk.Button(btn_frame, text="📦  Install Dependencies",
                                       style="Install.TButton", command=self._install_deps)
        self._install_btn.pack(side=tk.RIGHT)

        # Log area
        log_frame = ttk.LabelFrame(self, text="Server Log", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self._log_text = tk.Text(
            log_frame, wrap=tk.WORD, state=tk.DISABLED,
            bg="#0d1117", fg="#c9d1d9", font=("Consolas", 10),
            insertbackground="white", relief=tk.FLAT, bd=0,
        )
        self._log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._log_text.configure(yscrollcommand=scrollbar.set)

        # Tag colours for log
        self._log_text.tag_configure("info",  foreground="#58a6ff")
        self._log_text.tag_configure("ok",    foreground="#3fb950")
        self._log_text.tag_configure("warn",  foreground="#d29922")
        self._log_text.tag_configure("error", foreground="#f85149")
        self._log_text.tag_configure("dim",   foreground="#6e7681")

        # Status bar
        self._sb = tk.Label(self, text="Ready. Click Start Server to launch TrackWise Web.",
                            anchor=tk.W, bg="#161b22", fg="#8b949e", font=("Segoe UI", 9))
        self._sb.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Logging ───────────────────────────────
    def _append_log(self, text: str, tag: str = ""):
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, text + "\n", tag or ())
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _start_log_drain(self):
        """Poll the log queue and write to text widget."""
        try:
            while True:
                msg, tag = self._log_queue.get_nowait()
                self._append_log(msg, tag)
        except queue.Empty:
            pass
        self.after(100, self._start_log_drain)

    def _log(self, msg: str, tag: str = ""):
        self._log_queue.put((msg, tag))

    # ── Server management ─────────────────────
    def _get_python(self) -> str:
        """Return Python executable to use — venv first, then system."""
        if PYTHON_EXE.exists():
            return str(PYTHON_EXE)
        return sys.executable

    def _get_uvicorn_cmd(self) -> list[str]:
        host = self._host_var.get().strip() or DEFAULT_HOST
        port = self._port_var.get().strip() or str(DEFAULT_PORT)
        python = self._get_python()
        cmd = [python, "-m", "uvicorn", "app:app",
               "--host", host, "--port", port]
        if self._reload_var.get():
            cmd.append("--reload")
        return cmd

    def _start_server(self):
        if self._running:
            return
        self._log("─" * 60, "dim")
        self._log("Starting TrackWise Web server…", "info")

        # Check backend exists
        if not BACKEND_DIR.exists():
            self._log(f"ERROR: Backend directory not found: {BACKEND_DIR}", "error")
            messagebox.showerror("Not Found",
                f"Backend directory not found:\n{BACKEND_DIR}\n\nPlease ensure web/backend/ exists.")
            return

        cmd = self._get_uvicorn_cmd()
        self._log(f"Command: {' '.join(cmd)}", "dim")

        try:
            self._server_proc = subprocess.Popen(
                cmd,
                cwd=str(BACKEND_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as e:
            self._log(f"ERROR: Could not start server — {e}", "error")
            self._log("Run '📦 Install Dependencies' to set up the virtual environment.", "warn")
            return

        self._running = True
        self._update_ui_state()
        self._set_status("● Starting…", "#f39c12")

        # Stream logs from subprocess in a thread
        threading.Thread(target=self._stream_server_output, daemon=True).start()
        # Poll until server is ready
        port = int(self._port_var.get().strip() or DEFAULT_PORT)
        threading.Thread(target=self._wait_for_server, args=(port,), daemon=True).start()

    def _stream_server_output(self):
        proc = self._server_proc
        if not proc or not proc.stdout:
            return
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            tag = "dim"
            low = line.lower()
            if "error" in low or "traceback" in low or "exception" in low:
                tag = "error"
            elif "warning" in low:
                tag = "warn"
            elif "started" in low or "running" in low or "uvicorn" in low:
                tag = "ok"
            elif "info" in low:
                tag = "info"
            self._log(line, tag)

        # Process exited
        rc = proc.wait()
        self._log(f"Server process exited (code {rc})", "warn" if rc != 0 else "dim")
        self._running = False
        self.after(0, self._update_ui_state)
        self.after(0, lambda: self._set_status("● Stopped", "#e74c3c"))

    def _wait_for_server(self, port: int):
        """Poll until uvicorn is accepting connections, then update UI."""
        import socket
        host = self._host_var.get().strip() or "127.0.0.1"
        listen_host = "127.0.0.1" if host == "0.0.0.0" else host
        for _ in range(30):  # up to 15 seconds
            try:
                with socket.create_connection((listen_host, port), timeout=0.5):
                    self.after(0, lambda: self._set_status("● Running", "#27ae60"))
                    self.after(0, self._update_ui_state)
                    self._log(f"Server ready at http://{listen_host}:{port}", "ok")
                    return
            except OSError:
                time.sleep(0.5)
        self._log("Server did not respond in time — check log for errors", "warn")

    def _stop_server(self):
        if not self._running or not self._server_proc:
            return
        self._log("Stopping server…", "warn")
        try:
            self._server_proc.terminate()
            self._server_proc.wait(timeout=5)
        except Exception:
            try:
                self._server_proc.kill()
            except Exception:
                pass
        self._running = False
        self._server_proc = None
        self._update_ui_state()
        self._set_status("● Stopped", "#e74c3c")
        self._log("Server stopped.", "dim")

    def _open_browser(self):
        host = self._host_var.get().strip() or "127.0.0.1"
        port = self._port_var.get().strip() or str(DEFAULT_PORT)
        view_host = "127.0.0.1" if host == "0.0.0.0" else host
        url = f"http://{view_host}:{port}"
        self._log(f"Opening browser: {url}", "info")
        webbrowser.open(url)

    # ── Dependency installation ───────────────
    def _install_deps(self):
        req_file = ROOT / "web" / "requirements.txt"
        if not req_file.exists():
            messagebox.showerror("Not Found", f"requirements.txt not found:\n{req_file}")
            return

        answer = messagebox.askyesno(
            "Install Dependencies",
            f"This will create a virtual environment in:\n{VENV_DIR}\n\n"
            f"and install packages from:\n{req_file}\n\nContinue?"
        )
        if not answer:
            return

        self._log("─" * 60, "dim")
        self._log("Installing dependencies…", "info")

        def run_install():
            python = sys.executable
            # Create venv
            self._log(f"Creating venv at {VENV_DIR}…", "dim")
            result = subprocess.run(
                [python, "-m", "venv", str(VENV_DIR)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                self._log(f"venv creation failed:\n{result.stderr}", "error")
                return

            # Install packages
            pip = str(PYTHON_EXE if PYTHON_EXE.exists() else Path(str(VENV_DIR) + "/Scripts/pip.exe"))
            self._log("Running pip install…", "dim")
            proc = subprocess.Popen(
                [str(PYTHON_EXE if PYTHON_EXE.exists() else sys.executable),
                 "-m", "pip", "install", "-r", str(req_file)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                self._log(line.rstrip(), "dim")
            proc.wait()
            if proc.returncode == 0:
                self._log("✅ Dependencies installed successfully!", "ok")
            else:
                self._log("❌ Installation failed — check log above.", "error")

        threading.Thread(target=run_install, daemon=True).start()

    # ── UI helpers ────────────────────────────
    def _update_ui_state(self):
        if self._running:
            self._start_btn.configure(state=tk.DISABLED)
            self._stop_btn.configure(state=tk.NORMAL)
            self._browser_btn.configure(state=tk.NORMAL)
            self._sb.configure(
                text=f"Server running on http://{self._host_var.get()}:{self._port_var.get()}"
            )
        else:
            self._start_btn.configure(state=tk.NORMAL)
            self._stop_btn.configure(state=tk.DISABLED)
            self._browser_btn.configure(state=tk.DISABLED)
            self._sb.configure(text="Server stopped. Press Start Server to launch.")

    def _set_status(self, text: str, color: str):
        self._status_lbl.configure(text=text, fg=color)

    def _on_close(self):
        if self._running:
            if messagebox.askyesno("Quit", "Server is running. Stop it and quit?"):
                self._stop_server()
            else:
                return
        self.destroy()


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    app = TrackWiseLauncher()
    app.mainloop()
