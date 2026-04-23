#!/usr/bin/env bash
set -euo pipefail

CGROUP_ROOT="${CGROUP_ROOT:-/sys/fs/cgroup/vee}"
CPUSET="${CPUSET:-0-7}"
CPU_MAX="${CPU_MAX:-600000 1000000}"
MEM_HIGH="${MEM_HIGH:-6G}"
MEM_MAX="${MEM_MAX:-8G}"
HAMI_CORE_LIB="${HAMI_CORE_LIB:-}"

mkdir -p "$CGROUP_ROOT"
echo "$CPUSET" > "$CGROUP_ROOT/cpuset.cpus"
echo "$CPU_MAX" > "$CGROUP_ROOT/cpu.max"
echo "$MEM_HIGH" > "$CGROUP_ROOT/memory.high"
echo "$MEM_MAX" > "$CGROUP_ROOT/memory.max"

# hami-core is a preload library (libvgpu.so), not a CLI tool.
# Validate configured library path when provided.
if [[ -n "$HAMI_CORE_LIB" && ! -f "$HAMI_CORE_LIB" ]]; then
  echo "HAMI_CORE_LIB not found: $HAMI_CORE_LIB" >&2
  exit 1
fi
