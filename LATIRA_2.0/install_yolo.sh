#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --skip-deps) EXTRA_ARGS+=("--skip-deps") ;;
    -h|--help)
      echo "Uso: ./install_yolo.sh [--skip-deps]"
      echo "  --skip-deps  Omite pip install de PyTorch/Ultralytics y solo descarga/verifica pesos YOLO."
      exit 0
      ;;
    *)
      echo "[ERROR] Opción desconocida: $arg (usa --skip-deps o --help)" >&2
      exit 1
      ;;
  esac
done

if [ "${LATIRA_SKIP_YOLO_SETUP:-0}" = "1" ]; then
  echo "[INFO] LATIRA_SKIP_YOLO_SETUP=1 está activo: preparación de YOLO Pose deshabilitada."
  echo "[INFO] Para instalar YOLO Pose ejecuta LATIRA_SKIP_YOLO_SETUP=0 ./install_yolo.sh"
  exit 1
fi

PYTHON_BIN=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      PYTHON_BIN="$cand"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "[ERROR] Python 3.10+ is required to install YOLO Pose." >&2
  exit 1
fi

if [ ! -x "backend/.venv/bin/python" ]; then
  echo "[INFO] Creating virtual environment in backend/.venv..."
  if ! "$PYTHON_BIN" -m venv "backend/.venv" >/dev/null 2>&1; then
    rm -rf "backend/.venv"
    if command -v curl >/dev/null 2>&1; then
      "$PYTHON_BIN" -m venv --without-pip "backend/.venv"
      curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/latira_get_pip.py
      "backend/.venv/bin/python" /tmp/latira_get_pip.py
      rm -f /tmp/latira_get_pip.py
    else
      echo "[ERROR] Failed to create backend/.venv (missing ensurepip)." >&2
      exit 1
    fi
  fi
fi

echo "[INFO] Ensuring base backend dependencies..."
"backend/.venv/bin/python" -m pip install -r "backend/requirements.txt"

echo "[INFO] Installing CPU PyTorch, Ultralytics, OpenCV Headless, and verifying yolo11n-pose.pt..."
if ! "backend/.venv/bin/python" "ai/setup_yolo.py" --install "${EXTRA_ARGS[@]}"; then
  echo "[ERROR] YOLO Pose installation or inference verification failed." >&2
  echo "[INFO] Core LATIRA 2.0 can still run in lightweight mode via: ./run.sh --light" >&2
  exit 1
fi

echo "[OK] YOLO Pose installed, weights verified, and real inference passed."
