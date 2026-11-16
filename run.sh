#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

MODE=""
CLI_MODE_SET=0
for arg in "$@"; do
  case "$arg" in
    --full|--completo) MODE="full"; CLI_MODE_SET=1 ;;
    --light|--ligero) MODE="light"; CLI_MODE_SET=1 ;;
    -h|--help)
      echo "Uso: ./run.sh [--full | --light]"
      echo "  --full   Instala dependencias generales y YOLO Pose (PyTorch, Ultralytics, OpenCV Headless, pesos y prueba real)."
      echo "  --light  Instala solo el núcleo general sin descargar PyTorch ni pesos YOLO."
      echo "También admite LATIRA_MODE=full|light o LATIRA_SKIP_YOLO_SETUP=1 (equivale a --light)."
      exit 0
      ;;
    *)
      echo "[ERROR] Opción desconocida: $arg (usa --full o --light)" >&2
      exit 1
      ;;
  esac
done

if [ "$CLI_MODE_SET" = "0" ] && [ "${LATIRA_SKIP_YOLO_SETUP:-0}" = "1" ]; then
  MODE="light"
fi

if [ -z "$MODE" ]; then
  case "${LATIRA_MODE:-}" in
    full|completo) MODE="full" ;;
    light|ligero|lightweight) MODE="light" ;;
    "") ;;
    *)
      echo "[ERROR] Valor inválido en LATIRA_MODE: ${LATIRA_MODE} (usa full o light)" >&2
      exit 1
      ;;
  esac
fi

if [ -z "$MODE" ]; then
  if [ -t 0 ]; then
    echo "Selecciona el modo de inicio de LÁTIRA 2.0:"
    echo "  1) Modo completo (incluye instalación y verificación real de YOLO Pose)"
    echo "  2) Modo ligero (solo núcleo de LÁTIRA, sin PyTorch ni pesos YOLO)"
    read -r -p "Opción [1/2] (predeterminado 1): " choice
    case "${choice:-1}" in
      2|light|ligero) MODE="light" ;;
      *) MODE="full" ;;
    esac
  else
    MODE="full"
  fi
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
  echo "[ERROR] Se requiere Python 3.10 o superior ejecutable." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] Node.js 20+ y npm son obligatorios." >&2
  exit 1
fi

mkdir -p data/database data/pose data/uploads/thermography models

if [ ! -x "backend/.venv/bin/python" ]; then
  echo "[INFO] Creando entorno virtual backend/.venv..."
  if ! "$PYTHON_BIN" -m venv "backend/.venv" >/dev/null 2>&1; then
    rm -rf "backend/.venv"
    if command -v curl >/dev/null 2>&1; then
      echo "[AVISO] ensurepip no está disponible; creando venv con --without-pip..."
      "$PYTHON_BIN" -m venv --without-pip "backend/.venv"
      curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/latira_get_pip.py
      "backend/.venv/bin/python" /tmp/latira_get_pip.py
      rm -f /tmp/latira_get_pip.py
    else
      echo "[ERROR] No se pudo crear backend/.venv (falta python3-venv/ensurepip)." >&2
      exit 1
    fi
  fi
fi

echo "[INFO] Instalando dependencias generales del backend..."
"backend/.venv/bin/python" -m pip install -r "backend/requirements.txt"

if [ ! -d "frontend/node_modules" ] || [ "${LATIRA_FORCE_NPM_CI:-0}" = "1" ]; then
  echo "[INFO] Instalando dependencias reproducibles del frontend (npm ci)..."
  (cd frontend && npm ci --no-audit --no-fund)
fi

if [ "$MODE" = "full" ]; then
  export LATIRA_MODE="full"
  export LATIRA_SKIP_YOLO_SETUP="0"
  "backend/.venv/bin/python" "ai/setup_yolo.py" --enable >/dev/null
  echo "[INFO] Modo completo: verificando YOLO Pose..."
  if ! "backend/.venv/bin/python" "ai/setup_yolo.py" --verify >/dev/null 2>&1; then
    echo "[INFO] YOLO Pose aún no está listo; iniciando instalación y prueba de inferencia..."
    if ! "backend/.venv/bin/python" "ai/setup_yolo.py" --install; then
      echo "" >&2
      echo "[ERROR] La preparación de YOLO Pose falló. La instalación completa NO se realizó." >&2
      if [ -t 0 ]; then
        read -r -p "¿Deseas continuar únicamente con el núcleo ligero (sin YOLO Pose)? [s/N]: " cont
        case "${cont:-n}" in
          s|S|y|Y|si|SI)
            MODE="light"
            echo "[AVISO] Continuando en modo ligero: YOLO Pose permanecerá deshabilitado/no configurado."
            ;;
          *)
            exit 1
            ;;
        esac
      elif [ "${LATIRA_ALLOW_LIGHT_FALLBACK:-0}" = "1" ]; then
        MODE="light"
        echo "[AVISO] Continuando en modo ligero por LATIRA_ALLOW_LIGHT_FALLBACK=1."
      else
        exit 1
      fi
    fi
  fi
fi

if [ "$MODE" = "full" ]; then
  echo "[OK] Modo completo verificado: YOLO Pose operativo."
  if [ -z "${YOLO_POSE_MODEL:-}" ] && [ -f "$ROOT/models/yolo11n-pose.pt" ]; then
    export YOLO_POSE_MODEL="$ROOT/models/yolo11n-pose.pt"
  fi
else
  export LATIRA_MODE="light"
  export LATIRA_SKIP_YOLO_SETUP="1"
  "backend/.venv/bin/python" "ai/setup_yolo.py" --disable >/dev/null
  echo "[INFO] Modo ligero activo: YOLO Pose deshabilitado (sin descargar ni cargar PyTorch/pesos)."
  echo "[INFO] Las rutas de inferencia /api/pose/* responderán con estado honesto 503/not_configured sin resultados ficticios."
fi

export LATIRA_ENV="${LATIRA_ENV:-demo}"
export LATIRA_DB_PATH="${LATIRA_DB_PATH:-$ROOT/data/database/latira.sqlite3}"
export POSE_STORAGE_DIR="${POSE_STORAGE_DIR:-$ROOT/data/pose}"
export POSE_HISTORY_DB="${POSE_HISTORY_DB:-$ROOT/data/pose/history.sqlite3}"
export LATIRA_THERMAL_DIR="${LATIRA_THERMAL_DIR:-$ROOT/data/uploads/thermography}"

(cd backend && ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACK_PID=$!
trap 'kill $BACK_PID 2>/dev/null || true' EXIT

cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1 --port 5173
