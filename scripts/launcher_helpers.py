#!/usr/bin/env python3
"""Support utilities for the Theoria PowerShell launcher."""
from __future__ import annotations

import argparse
import base64
import http.server
import json
import shutil
import subprocess
import sys
import textwrap
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
except Exception:  # pragma: no cover - lazily imported only when needed
    x509 = None  # type: ignore
    rsa = None  # type: ignore


RUNTIME_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "Python",
        "commands": ["python", "python3", "py"],
        "args": ["--version"],
        "category": "local",
        "guidance": "Install Python 3.11 or newer from https://python.org/downloads/",
        "installers": [
            {"tool": "winget", "args": ["install", "--id", "Python.Python.3.11", "-e"], "display": "winget install --id Python.Python.3.11 -e"},
            {"tool": "choco", "args": ["install", "python", "-y"], "display": "choco install python -y"},
            {"tool": "brew", "args": ["install", "python@3.11"], "display": "brew install python@3.11"},
        ],
    },
    {
        "name": "Node.js",
        "commands": ["node"],
        "args": ["--version"],
        "category": "local",
        "guidance": "Install Node.js 18+ from https://nodejs.org/en/download",
        "installers": [
            {"tool": "winget", "args": ["install", "--id", "OpenJS.NodeJS.LTS", "-e"], "display": "winget install --id OpenJS.NodeJS.LTS -e"},
            {"tool": "choco", "args": ["install", "nodejs-lts", "-y"], "display": "choco install nodejs-lts -y"},
            {"tool": "brew", "args": ["install", "node@18"], "display": "brew install node@18"},
        ],
    },
    {
        "name": "npm",
        "commands": ["npm"],
        "args": ["--version"],
        "category": "local",
        "guidance": "npm ships with Node.js. Install Node.js to obtain npm.",
        "installers": [],
    },
    {
        "name": "Docker",
        "commands": ["docker"],
        "args": ["--version"],
        "category": "container",
        "guidance": "Install Docker Desktop from https://www.docker.com/products/docker-desktop/",
        "installers": [
            {"tool": "winget", "args": ["install", "--id", "Docker.DockerDesktop", "-e"], "display": "winget install --id Docker.DockerDesktop -e"},
            {"tool": "choco", "args": ["install", "docker-desktop", "-y"], "display": "choco install docker-desktop -y"},
            {"tool": "brew", "args": ["install", "--cask", "docker"], "display": "brew install --cask docker"},
        ],
    },
]


def detect_runtime(runtime: Dict[str, Any]) -> Dict[str, Any]:
    present = False
    version: Optional[str] = None
    resolved_command: Optional[str] = None

    commands: Iterable[str] = runtime.get("commands", [])
    args: List[str] = runtime.get("args", [])

    for candidate in commands:
        executable = shutil.which(candidate)
        if not executable:
            continue

        cmd = [executable]
        cmd.extend(args or [])
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        except Exception:
            continue

        if completed.returncode == 0:
            output = completed.stdout.strip() or completed.stderr.strip()
            first_line = output.splitlines()[0] if output else ""
            version = first_line or None
            present = True
            resolved_command = executable
            break

    return {
        "name": runtime["name"],
        "present": present,
        "version": version,
        "command": resolved_command,
        "category": runtime.get("category", "local"),
        "guidance": runtime.get("guidance"),
        "installers": runtime.get("installers", []),
    }


def detect_docker_compose() -> Dict[str, Any]:
    candidates = [
        ("docker", ["compose", "version"]),
        ("docker-compose", ["version"]),
    ]

    for base, extra_args in candidates:
        executable = shutil.which(base)
        if not executable:
            continue
        cmd = [executable, *extra_args]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        except Exception:
            continue
        if completed.returncode == 0:
            output = completed.stdout.strip() or completed.stderr.strip()
            first_line = output.splitlines()[0] if output else ""
            return {
                "name": "Docker Compose",
                "present": True,
                "version": first_line or None,
                "command": " ".join(cmd),
                "category": "container",
                "guidance": "Install Docker Compose (included with Docker Desktop).",
                "installers": [
                    {"tool": "winget", "args": ["install", "--id", "Docker.DockerDesktop", "-e"], "display": "winget install --id Docker.DockerDesktop -e"},
                    {"tool": "choco", "args": ["install", "docker-desktop", "-y"], "display": "choco install docker-desktop -y"},
                    {"tool": "brew", "args": ["install", "--cask", "docker"], "display": "brew install --cask docker"},
                ],
            }

    return {
        "name": "Docker Compose",
        "present": False,
        "version": None,
        "command": None,
        "category": "container",
        "guidance": "Install Docker Desktop to use docker compose fallback.",
        "installers": [
            {"tool": "winget", "args": ["install", "--id", "Docker.DockerDesktop", "-e"], "display": "winget install --id Docker.DockerDesktop -e"},
            {"tool": "choco", "args": ["install", "docker-desktop", "-y"], "display": "choco install docker-desktop -y"},
            {"tool": "brew", "args": ["install", "--cask", "docker"], "display": "brew install --cask docker"},
        ],
    }


def command_check(project_root: Path) -> Dict[str, Any]:
    runtimes = [detect_runtime(defn) for defn in RUNTIME_DEFINITIONS]
    runtimes.append(detect_docker_compose())
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "project_root": str(project_root),
        "runtimes": runtimes,
    }
    return result


def output_prereq_report(report: Dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        json.dump(report, sys.stdout)
        return

    lines = ["Runtime prerequisite report"]
    for runtime in report["runtimes"]:
        status = "OK" if runtime["present"] else "MISSING"
        version = runtime.get("version") or "(unknown)"
        lines.append(f" - {runtime['name']}: {status} [{version}]")
    sys.stdout.write("\n".join(lines))


def check_prereqs(args: argparse.Namespace) -> None:
    report = command_check(args.project_root)
    output_prereq_report(report, args.format)


def ensure_crypto_available() -> None:
    if x509 is None or rsa is None:
        raise RuntimeError(
            "The 'cryptography' package is required to generate certificates. Install dependencies with 'pip install -r requirements-dev.txt'."
        )


def generate_certificate(args: argparse.Namespace) -> None:
    ensure_crypto_available()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, args.common_name or "Theoria Local"),
    ])

    alt_names = ["localhost", "127.0.0.1"]
    if args.additional_san:
        alt_names.extend(args.additional_san)

    entries = []
    for name in sorted({n.strip() for n in alt_names if n.strip()}):
        try:
            entries.append(x509.IPAddress(ipaddress_from_text(name)))
        except ValueError:
            entries.append(x509.DNSName(name))

    san = x509.SubjectAlternativeName(entries)

    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=730))
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_basename = f"theoria-{args.profile}-dev"
    cert_path = output_dir / f"{cert_basename}.crt.pem"
    key_path = output_dir / f"{cert_basename}.key.pem"

    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    json.dump({"cert_path": str(cert_path), "key_path": str(key_path)}, sys.stdout)


def ipaddress_from_text(value: str):  # pragma: no cover - helper for dynamic import
    from ipaddress import ip_address

    return ip_address(value)


def record_telemetry(args: argparse.Namespace) -> None:
    log_dir = Path(args.project_root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "telemetry.jsonl"

    metadata: Dict[str, Any]
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            try:
                decoded = base64.b64decode(args.metadata)
                metadata = json.loads(decoded.decode("utf-8"))
            except Exception:
                metadata = {"raw": args.metadata}
    else:
        metadata = {}

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": args.event,
        "profile": args.profile,
        "metadata": metadata,
    }

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def load_telemetry_entries(log_path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not log_path.exists():
        return entries

    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def render_dashboard(entries: List[Dict[str, Any]]) -> str:
    total = len(entries)
    by_event: Dict[str, int] = {}
    by_profile: Dict[str, int] = {}
    last_event = "N/A"

    for entry in entries:
        by_event[entry.get("event", "unknown")] = by_event.get(entry.get("event", "unknown"), 0) + 1
        by_profile[entry.get("profile", "unknown")] = by_profile.get(entry.get("profile", "unknown"), 0) + 1
        last_event = entry.get("timestamp", last_event)

    def build_list(data: Dict[str, int]) -> str:
        if not data:
            return "<li>No data yet</li>"
        return "".join(f"<li><strong>{key}</strong>: {value}</li>" for key, value in sorted(data.items()))

    html = f"""
    <html>
      <head>
        <title>Theoria Launcher Telemetry</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }}
          h1 {{ color: #38bdf8; }}
          section {{ margin-bottom: 2rem; padding: 1rem; background: #1e293b; border-radius: 8px; }}
          ul {{ list-style: none; padding-left: 0; }}
          li {{ margin-bottom: 0.5rem; }}
          .metric {{ font-size: 1.4rem; margin-bottom: 1rem; }}
        </style>
      </head>
      <body>
        <h1>Theoria Launcher Telemetry</h1>
        <section>
          <div class="metric">Total events recorded: <strong>{total}</strong></div>
          <div>Last event: <strong>{last_event}</strong></div>
        </section>
        <section>
          <h2>Events</h2>
          <ul>{build_list(by_event)}</ul>
        </section>
        <section>
          <h2>Profiles</h2>
          <ul>{build_list(by_profile)}</ul>
        </section>
      </body>
    </html>
    """
    return textwrap.dedent(html)


class TelemetryHandler(http.server.BaseHTTPRequestHandler):
    log_path: Path

    def do_GET(self) -> None:  # noqa: N802
        entries = load_telemetry_entries(self.log_path)
        html = render_dashboard(entries)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: D401
        """Suppress default request logging."""
        return


def run_dashboard(args: argparse.Namespace) -> None:
    log_path = Path(args.project_root) / "logs" / "telemetry.jsonl"
    handler_cls = type("TelemetryHandler", (TelemetryHandler,), {"log_path": log_path})
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler_cls)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Telemetry dashboard available at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        thread.join()
    except KeyboardInterrupt:
        print("Stopping dashboard...")
        server.shutdown()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helpers for the Theoria launcher")
    parser.add_argument("--project-root", default=Path.cwd(), type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check-prereqs", help="Check runtime prerequisites")
    check_parser.add_argument("--format", choices={"json", "text"}, default="json")
    check_parser.set_defaults(func=check_prereqs)

    cert_parser = subparsers.add_parser("generate-cert", help="Generate self-signed development certificates")
    cert_parser.add_argument("--profile", default="dev")
    cert_parser.add_argument("--output-dir", required=True)
    cert_parser.add_argument("--common-name", default="Theoria Local")
    cert_parser.add_argument("--additional-san", nargs="*")
    cert_parser.set_defaults(func=generate_certificate)

    telemetry_parser = subparsers.add_parser("record-telemetry", help="Append launcher telemetry event")
    telemetry_parser.add_argument("--event", required=True)
    telemetry_parser.add_argument("--profile", required=True)
    telemetry_parser.add_argument("--metadata")
    telemetry_parser.set_defaults(func=record_telemetry)

    dashboard_parser = subparsers.add_parser("dashboard", help="Serve a lightweight telemetry dashboard")
    dashboard_parser.add_argument("--host", default="127.0.0.1")
    dashboard_parser.add_argument("--port", default=8765, type=int)
    dashboard_parser.set_defaults(func=run_dashboard)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.project_root = Path(args.project_root)
    args.func(args)


if __name__ == "__main__":
    main()
