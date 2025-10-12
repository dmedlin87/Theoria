#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
START_SCRIPT="${ROOT_DIR}/start-theoria.ps1"

if [[ ! -f "${START_SCRIPT}" ]]; then
  echo "Unable to locate start-theoria.ps1 at ${START_SCRIPT}" >&2
  exit 1
fi

if command -v pwsh >/dev/null 2>&1; then
  POWERSHELL_CMD="pwsh"
elif command -v powershell >/dev/null 2>&1; then
  POWERSHELL_CMD="powershell"
else
  echo "PowerShell 7+ (pwsh) is required to run the service manager" >&2
  exit 1
fi

if [[ "${POWERSHELL_CMD}" == "powershell" ]]; then
  # Windows PowerShell needs -File and proper quoting
  exec "${POWERSHELL_CMD}" -NoProfile -ExecutionPolicy Bypass -File "${START_SCRIPT}" "$@"
else
  exec "${POWERSHELL_CMD}" -NoLogo -NoProfile -File "${START_SCRIPT}" "$@"
fi
