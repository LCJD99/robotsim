#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../../.." && pwd)"
LIB_PATH="${HAMI_CORE_LIB:-$ROOT_DIR/libs/libvgpu.so}"
CUDA_IMAGE="${CUDA_IMAGE:-nvidia/cuda:12.4.1-runtime-ubuntu22.04}"
CUDA_DEVICE_MEMORY_LIMIT="${CUDA_DEVICE_MEMORY_LIMIT:-1g}"
CUDA_DEVICE_SM_LIMIT="${CUDA_DEVICE_SM_LIMIT:-50}"
HAMI_SMOKE_TIMEOUT_SEC="${HAMI_SMOKE_TIMEOUT_SEC:-120}"
LIBCUDA_LOG_LEVEL="${LIBCUDA_LOG_LEVEL:-1}"
CUDA_DEVICE_MEMORY_SHARED_CACHE="${CUDA_DEVICE_MEMORY_SHARED_CACHE:-/tmp/cudevshr.$$.cache}"
GPU_CORE_UTILIZATION_POLICY="${GPU_CORE_UTILIZATION_POLICY:-DISABLE}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found in PATH" >&2
  exit 1
fi

if ! docker version >/dev/null 2>&1; then
  cat >&2 <<MSG
Docker CLI is present but daemon is unavailable.
If you are on WSL2, enable Docker Desktop WSL integration for this distro.
MSG
  exit 1
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi not found on host; GPU runtime may be unavailable" >&2
  exit 1
fi

if [[ ! -f "$LIB_PATH" ]]; then
  echo "hami-core library not found: $LIB_PATH" >&2
  echo "Run: make hami-core-prepare" >&2
  exit 1
fi

echo "[smoke] using library: $LIB_PATH"
echo "[smoke] image: $CUDA_IMAGE"
echo "[smoke] shared cache: $CUDA_DEVICE_MEMORY_SHARED_CACHE"
echo "[smoke] utilization policy: $GPU_CORE_UTILIZATION_POLICY"
echo "[smoke] timeout: ${HAMI_SMOKE_TIMEOUT_SEC}s"

docker run --rm --gpus all \
  -v "$LIB_PATH:/opt/hami/libvgpu.so:ro" \
  -e LD_PRELOAD=/opt/hami/libvgpu.so \
  -e CUDA_REDIRECT=/opt/hami/libvgpu.so \
  -e CUDA_DEVICE_MEMORY_LIMIT="$CUDA_DEVICE_MEMORY_LIMIT" \
  -e CUDA_DEVICE_SM_LIMIT="$CUDA_DEVICE_SM_LIMIT" \
  -e CUDA_DEVICE_MEMORY_SHARED_CACHE="$CUDA_DEVICE_MEMORY_SHARED_CACHE" \
  -e GPU_CORE_UTILIZATION_POLICY="$GPU_CORE_UTILIZATION_POLICY" \
  -e LIBCUDA_LOG_LEVEL="$LIBCUDA_LOG_LEVEL" \
  "$CUDA_IMAGE" \
  bash -lc 'set -euo pipefail; \
    echo "LD_PRELOAD=$LD_PRELOAD"; \
    echo "LIBCUDA_LOG_LEVEL=${LIBCUDA_LOG_LEVEL:-}"; \
    test -f "$LD_PRELOAD"; \
    mkdir -p /tmp/vgpulock; \
    rm -f /tmp/vgpulock/lock "$CUDA_DEVICE_MEMORY_SHARED_CACHE"; \
    echo "[smoke] phase-1: baseline nvidia-smi (no preload)"; \
    env -u LD_PRELOAD nvidia-smi >/tmp/nvidia-smi-baseline.log 2>&1; \
    echo "[smoke] phase-2: hami preload nvidia-smi"; \
    if ! timeout '"$HAMI_SMOKE_TIMEOUT_SEC"'s nvidia-smi >/tmp/nvidia-smi-hami.log 2>&1; then \
      rc=$?; \
      echo "[smoke] phase-2 failed with rc=$rc"; \
      echo "[smoke] baseline log:"; cat /tmp/nvidia-smi-baseline.log || true; \
      echo "[smoke] hami log (tail):"; tail -n 200 /tmp/nvidia-smi-hami.log || true; \
      exit $rc; \
    fi; \
    echo "[smoke] hami log (tail):"; tail -n 80 /tmp/nvidia-smi-hami.log'

echo "[smoke] container check passed"
