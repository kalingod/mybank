# Lightweight lab monitoring

This lab runs inside containers, so monitoring must keep two scopes separate:

- Container scope: the current container's cgroup quota, CPU usage, memory usage, processes, and `/data` filesystem.
- Host scope: the physical host and sibling containers on the same physical machine.

`scripts/lab-monitor.py` reports container-scope data. It does not claim to report physical-host totals.

## Run

From the Mac worktree:

```bash
python3 scripts/lab-monitor.py --via exp2 --interval 2 --samples 5
```

From exp2:

```bash
cd /home/workspace/mybank
python3 scripts/lab-monitor.py --direct-ip --interval 2 --samples 5
```

Key columns:

| Column | Meaning |
|---|---|
| `quota` | cgroup CPU quota in cores |
| `nproc` | CPU IDs visible inside the container; do not treat this as available quota |
| `cg_cores` | CPU cores used by this container during the sample interval |
| `cg%` | `cg_cores / quota` |
| `procstat_cores` | `/proc/stat` comparison view; useful as a sanity check, not the authoritative container usage |
| `cg_mem_mb` | current cgroup memory usage |

## Can one container read other containers?

A normal Docker container cannot reliably read CPU and memory usage for sibling containers on the same physical host. It can usually read its own cgroup files, such as:

```text
/sys/fs/cgroup/cpu.max
/sys/fs/cgroup/cpu.stat
/sys/fs/cgroup/cpuacct/cpuacct.usage
/sys/fs/cgroup/memory.current
/sys/fs/cgroup/memory/memory.usage_in_bytes
```

To monitor sibling containers, run the collector on the physical host or run a dedicated monitoring container with explicit host mounts:

```text
/sys/fs/cgroup
/proc
/var/run/docker.sock
```

Mounting `docker.sock` is powerful and should be treated as host-root-equivalent access. For a long-lived setup, prefer a host-side agent or a purpose-built collector such as cAdvisor plus node-level metrics.

## Current lab finding

The webide containers expose many visible CPUs through `nproc`, but the cgroup quota is 16 cores:

```text
cpu.cfs_quota_us=1600000
cpu.cfs_period_us=100000
quota=16 cores
```

OceanBase itself is also configured with `cpu_count=8`, and the current `alipay_tenant` resource unit has `MAX_CPU=2`. These are separate from Docker-visible CPU count and must be considered when interpreting TPS and CPU graphs.
