#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    alias: str
    ip: str
    role: str


NODES = (
    Node("exp1", "10.190.40.174", "spare"),
    Node("exp2", "10.190.0.81", "observer"),
    Node("exp3", "10.190.5.111", "observer"),
    Node("exp4", "10.190.49.117", "obproxy"),
    Node("exp5", "10.190.5.65", "observer"),
    Node("exp6", "10.190.14.135", "obproxy"),
)


REMOTE_PROBE = r"""#!/usr/bin/env bash
set -euo pipefail

interval="${1:-2}"
alias_name="${2:-unknown}"
role="${3:-unknown}"

read_cpu() {
  awk '/^cpu / {
    total=0
    for (i=2; i<=NF; i++) total += $i
    idle=$5+$6
    printf "%.0f %.0f\n", total, idle
  }' /proc/stat
}

read_cpu_stat() {
  local file=""
  if [ -s /sys/fs/cgroup/cpu.stat ]; then
    file=/sys/fs/cgroup/cpu.stat
  elif [ -s /sys/fs/cgroup/cpu/cpu.stat ]; then
    file=/sys/fs/cgroup/cpu/cpu.stat
  fi
  if [ -n "$file" ]; then
    awk '
      $1=="nr_throttled" { throttled=$2 }
      $1=="throttled_time" { time=$2 }
      $1=="throttled_usec" { time=$2 }
      END { printf "%s %s\n", throttled+0, time+0 }
    ' "$file"
  else
    echo "0 0"
  fi
}

read_cgroup_cpu_ns() {
  if [ -s /sys/fs/cgroup/cpu.stat ]; then
    awk '$1=="usage_usec" { print $2 * 1000 }' /sys/fs/cgroup/cpu.stat
  elif [ -r /sys/fs/cgroup/cpuacct/cpuacct.usage ]; then
    cat /sys/fs/cgroup/cpuacct/cpuacct.usage
  elif [ -r /sys/fs/cgroup/cpuacct.usage ]; then
    cat /sys/fs/cgroup/cpuacct.usage
  else
    echo 0
  fi
}

read_cgroup_memory_mb() {
  if [ -r /sys/fs/cgroup/memory.current ]; then
    awk '{ printf "%.0f\n", $1 / 1024 / 1024 }' /sys/fs/cgroup/memory.current
  elif [ -r /sys/fs/cgroup/memory/memory.usage_in_bytes ]; then
    awk '{ printf "%.0f\n", $1 / 1024 / 1024 }' /sys/fs/cgroup/memory/memory.usage_in_bytes
  else
    echo 0
  fi
}

quota_cores() {
  if [ -r /sys/fs/cgroup/cpu.max ]; then
    read -r quota period < /sys/fs/cgroup/cpu.max
    if [ "$quota" = "max" ]; then
      nproc
    else
      awk -v q="$quota" -v p="$period" 'BEGIN { printf "%.2f\n", q / p }'
    fi
  elif [ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us ] && [ -r /sys/fs/cgroup/cpu/cpu.cfs_period_us ]; then
    quota="$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us)"
    period="$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)"
    if [ "$quota" -lt 0 ]; then
      nproc
    else
      awk -v q="$quota" -v p="$period" 'BEGIN { printf "%.2f\n", q / p }'
    fi
  else
    nproc
  fi
}

collect_proc() {
  for stat_file in /proc/[0-9]*/stat; do
    pid="${stat_file%/stat}"
    pid="${pid##*/}"
    comm="$(cat "/proc/${pid}/comm" 2>/dev/null || true)"
    case "$comm" in
      observer|obproxy|obshell|mysqlslap|mysql)
        stat="$(cat "$stat_file" 2>/dev/null || true)"
        [ -n "$stat" ] || continue
        set -- $stat
        jiffies=$(( ${14} + ${15} ))
        rss_pages="${24}"
        printf "%s\t%s\t%s\t%s\n" "$pid" "$comm" "$jiffies" "$rss_pages"
        ;;
    esac
  done
}

clk_tck="$(getconf CLK_TCK)"
page_kb="$(getconf PAGE_SIZE | awk '{printf "%.0f\n", $1 / 1024}')"
visible_cpus="$(nproc)"
quota="$(quota_cores)"
hostname="$(hostname)"
load1="$(awk '{print $1}' /proc/loadavg)"
cg_mem_mb="$(read_cgroup_memory_mb)"

cpu_before="$(read_cpu)"
stat_before="$(read_cpu_stat)"
cg_cpu_before="$(read_cgroup_cpu_ns)"
proc_before="$(mktemp)"
proc_after="$(mktemp)"
collect_proc > "$proc_before"
time_before="$(date +%s.%N)"
sleep "$interval"
time_after="$(date +%s.%N)"
cpu_after="$(read_cpu)"
stat_after="$(read_cpu_stat)"
cg_cpu_after="$(read_cgroup_cpu_ns)"
collect_proc > "$proc_after"

read -r total_before idle_before <<<"$cpu_before"
read -r total_after idle_after <<<"$cpu_after"
read -r throttled_before throttled_time_before <<<"$stat_before"
read -r throttled_after throttled_time_after <<<"$stat_after"

df_line="$((df -Pm /data 2>/dev/null || true) | awk 'NR==2 {gsub(/%/, "", $5); print $3, $4, $5}')"
if [ -z "$df_line" ]; then
  df_line="$((df -Pm / 2>/dev/null || true) | awk 'NR==2 {gsub(/%/, "", $5); print $3, $4, $5}')"
fi
if [ -z "$df_line" ]; then
  df_line="0 0 0"
fi

if [ -d /data/oceanbase ]; then
  oceanbase_mb="$(du -sm /data/oceanbase 2>/dev/null | awk '{print $1+0}')"
else
  oceanbase_mb=0
fi
if [ -d /data/obproxy ]; then
  obproxy_mb="$(du -sm /data/obproxy 2>/dev/null | awk '{print $1+0}')"
else
  obproxy_mb=0
fi

awk -v kind="NODE" \
  -v alias_name="$alias_name" \
  -v role="$role" \
  -v hostname="$hostname" \
  -v visible="$visible_cpus" \
  -v quota="$quota" \
  -v clk="$clk_tck" \
  -v t1="$time_before" \
  -v t2="$time_after" \
  -v tb="$total_before" \
  -v ta="$total_after" \
  -v ib="$idle_before" \
  -v ia="$idle_after" \
  -v thb="$throttled_before" \
  -v tha="$throttled_after" \
  -v thtb="$throttled_time_before" \
  -v thta="$throttled_time_after" \
  -v cgb="$cg_cpu_before" \
  -v cga="$cg_cpu_after" \
  -v mem="$cg_mem_mb" \
  -v load1="$load1" \
  -v df="$df_line" \
  -v oceanbase="$oceanbase_mb" \
  -v obproxy="$obproxy_mb" \
  'BEGIN {
    split(df, disk, " ")
    elapsed=t2-t1
    total_delta=ta-tb
    idle_delta=ia-ib
    used_delta=total_delta-idle_delta
    procstat_cores=used_delta/clk/elapsed
    procstat_pct=(total_delta > 0 ? used_delta/total_delta*100 : 0)
    cgroup_cores=(cga-cgb)/1000000000/elapsed
    cgroup_pct=(quota > 0 ? cgroup_cores/quota*100 : 0)
    printf "%s\t%s\t%s\t%s\t%d\t%.2f\t%.2f\t%.1f\t%.2f\t%.1f\t%d\t%s\t%s\t%s\t%s\t%s\t%s\n",
      kind, alias_name, role, hostname, visible, quota, cgroup_cores, cgroup_pct,
      procstat_cores, procstat_pct, tha-thb, load1,
      disk[1]+0, disk[2]+0, disk[3]+0, oceanbase+obproxy, mem
  }'

awk -v alias_name="$alias_name" -v quota="$quota" -v clk="$clk_tck" \
  -v elapsed="$(awk -v a="$time_after" -v b="$time_before" 'BEGIN {print a-b}')" \
  -v page_kb="$page_kb" '
  NR==FNR {
    key=$1 FS $2
    before[key]=$3
    next
  }
  {
    key=$1 FS $2
    if (key in before && $3 >= before[key]) {
      comm=$2
      cpu[comm]+=($3-before[key])/clk/elapsed
      rss[comm]+=$4*page_kb/1024
      count[comm]+=1
    }
  }
  END {
    for (comm in cpu) {
      quota_pct=(quota > 0 ? cpu[comm]/quota*100 : 0)
      printf "PROC\t%s\t%s\t%d\t%.2f\t%.1f\t%.0f\n", alias_name, comm, count[comm], cpu[comm], quota_pct, rss[comm]
    }
  }' "$proc_before" "$proc_after"

rm -f "$proc_before" "$proc_after"
"""


def ssh_command(node: Node, args: argparse.Namespace) -> list[str]:
    if args.via:
        return [
            "ssh",
            "-T",
            args.via,
            "ssh",
            "-T",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            args.identity,
            f"root@{node.ip}",
            "bash",
            "-s",
            "--",
            str(args.interval),
            node.alias,
            node.role,
        ]
    if args.direct_ip:
        return [
            "ssh",
            "-T",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            args.identity,
            f"root@{node.ip}",
            "bash",
            "-s",
            "--",
            str(args.interval),
            node.alias,
            node.role,
        ]
    return [
        "ssh",
        "-T",
        node.alias,
        "bash",
        "-s",
        "--",
        str(args.interval),
        node.alias,
        node.role,
    ]


def probe(node: Node, args: argparse.Namespace) -> tuple[str, str, str]:
    proc = subprocess.run(
        ssh_command(node, args),
        input=REMOTE_PROBE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=args.interval + args.timeout,
        check=False,
    )
    return node.alias, proc.stdout, proc.stderr


def print_sample(args: argparse.Namespace) -> None:
    rows: list[list[str]] = []
    procs: list[list[str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(NODES)) as pool:
        futures = [pool.submit(probe, node, args) for node in NODES]
        for fut in concurrent.futures.as_completed(futures):
            alias, stdout, stderr = fut.result()
            if stderr.strip():
                print(f"[warn] {alias}: {stderr.strip()}", file=sys.stderr)
            for line in stdout.splitlines():
                parts = line.split("\t")
                if not parts:
                    continue
                if parts[0] == "NODE" and len(parts) >= 17:
                    rows.append(parts)
                elif parts[0] == "PROC" and len(parts) >= 7:
                    procs.append(parts)

    rows.sort(key=lambda r: r[1])
    procs.sort(key=lambda r: (r[1], r[2]))

    print(
        "scope=container-cgroup; procstat columns are comparison-only and may reflect the visible CPU set."
    )
    print(
        "node role     quota nproc cg_cores  cg% procstat_cores procstat% throttle data_used data_free data% data_dir_mb cg_mem_mb"
    )
    for r in rows:
        print(
            f"{r[1]:<4} {r[2]:<8} {r[5]:>5} {r[4]:>5} {r[6]:>8} {r[7]:>5} "
            f"{r[8]:>14} {r[9]:>9} {r[10]:>8} {int(float(r[12])):>9}M "
            f"{int(float(r[13])):>8}M {int(float(r[14])):>5}% "
            f"{int(float(r[15])):>10}M {int(float(r[16])):>9}M"
        )

    if procs:
        print()
        print("node process   count cores quota% rss_mb")
        for p in procs:
            print(f"{p[1]:<4} {p[2]:<9} {p[3]:>5} {p[4]:>5} {p[5]:>6} {p[6]:>6}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quota-aware lightweight monitor for the mybank OceanBase lab."
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Sample interval in seconds.")
    parser.add_argument("--samples", type=int, default=1, help="Number of samples to print.")
    parser.add_argument(
        "--via",
        default="",
        help="SSH through this host first, then connect to lab node IPs as root.",
    )
    parser.add_argument(
        "--identity",
        default="/root/.ssh/id_ed25519",
        help="SSH identity path used on --via host.",
    )
    parser.add_argument(
        "--direct-ip",
        action="store_true",
        help="Connect directly to root@node-ip instead of using local SSH aliases.",
    )
    parser.add_argument("--timeout", type=float, default=8.0, help="Extra SSH timeout seconds.")
    args = parser.parse_args()

    for i in range(args.samples):
        if args.samples > 1:
            print(f"sample {i + 1}/{args.samples}")
        print_sample(args)
        if i + 1 < args.samples:
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
