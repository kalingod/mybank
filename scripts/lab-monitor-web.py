#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import subprocess
import sys
import time
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
MONITOR_PATH = ROOT / "lab-monitor.py"


def load_monitor_module() -> Any:
    spec = importlib.util.spec_from_file_location("lab_monitor", MONITOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {MONITOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MONITOR = load_monitor_module()


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>mybank Lab Monitor</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d8dde6;
      --text: #151922;
      --muted: #667085;
      --green: #16825d;
      --amber: #a85f00;
      --red: #b42318;
      --blue: #2563eb;
      --teal: #0f766e;
      --slate: #475467;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 18px 24px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 1;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 650;
      letter-spacing: 0;
    }
    .subhead {
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(92px, 1fr));
      gap: 10px;
      min-width: min(520px, 50vw);
    }
    .summary-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      background: #fbfcfe;
    }
    .summary-label {
      color: var(--muted);
      font-size: 11px;
      white-space: nowrap;
    }
    .summary-value {
      margin-top: 2px;
      font-size: 18px;
      font-weight: 650;
    }
    main { padding: 18px 24px 28px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(260px, 1fr));
      gap: 14px;
    }
    .node {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 260px;
      display: grid;
      grid-template-rows: auto auto 1fr auto;
      gap: 12px;
    }
    .node.offline { border-color: #f0b8b2; }
    .node-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }
    .name {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0;
    }
    .meta {
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }
    .badge {
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }
    .online .badge { background: #dff8ed; color: var(--green); }
    .offline .badge { background: #fee4e2; color: var(--red); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .metric {
      min-width: 0;
      border-top: 1px solid #edf0f5;
      padding-top: 8px;
    }
    .label {
      color: var(--muted);
      font-size: 11px;
      white-space: nowrap;
    }
    .value {
      margin-top: 2px;
      font-size: 16px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }
    .bar {
      height: 7px;
      background: #edf0f5;
      border-radius: 999px;
      overflow: hidden;
      margin-top: 6px;
    }
    .fill {
      height: 100%;
      width: 0;
      background: var(--blue);
      transition: width .25s ease;
    }
    .fill.cpu { background: var(--teal); }
    .fill.disk { background: var(--blue); }
    .fill.warn { background: var(--amber); }
    .fill.bad { background: var(--red); }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 12px;
    }
    th, td {
      text-align: left;
      padding: 5px 4px;
      border-bottom: 1px solid #edf0f5;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    th { color: var(--muted); font-weight: 600; }
    .error {
      color: var(--red);
      background: #fff6f5;
      border: 1px solid #f0b8b2;
      border-radius: 8px;
      padding: 10px;
      min-height: 64px;
    }
    .footer {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 12px;
    }
    @media (max-width: 980px) {
      header { display: block; }
      .summary { margin-top: 12px; min-width: 0; grid-template-columns: repeat(2, 1fr); }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>mybank Lab Monitor</h1>
      <div class="subhead" id="scope">container cgroup scope</div>
    </div>
    <div class="summary">
      <div class="summary-item"><div class="summary-label">Online</div><div class="summary-value" id="online">-</div></div>
      <div class="summary-item"><div class="summary-label">Max CPU</div><div class="summary-value" id="maxCpu">-</div></div>
      <div class="summary-item"><div class="summary-label">Max Disk</div><div class="summary-value" id="maxDisk">-</div></div>
      <div class="summary-item"><div class="summary-label">Updated</div><div class="summary-value" id="updated">-</div></div>
    </div>
  </header>
  <main>
    <section class="grid" id="nodes"></section>
  </main>
  <script>
    const nodesEl = document.getElementById('nodes');
    const fmt = (n, d = 1) => Number.isFinite(Number(n)) ? Number(n).toFixed(d) : '-';
    const pct = n => Math.max(0, Math.min(100, Number(n) || 0));
    const fillClass = n => n >= 85 ? 'bad' : n >= 65 ? 'warn' : '';
    const htmlEscape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

    function processRows(processes) {
      if (!processes || processes.length === 0) {
        return '<table><tbody><tr><td>No tracked process</td></tr></tbody></table>';
      }
      return `<table>
        <thead><tr><th>Process</th><th>Cores</th><th>Quota%</th><th>RSS</th></tr></thead>
        <tbody>${processes.map(p => `<tr>
          <td>${htmlEscape(p.name)}</td>
          <td>${fmt(p.cores, 2)}</td>
          <td>${fmt(p.quota_pct, 1)}%</td>
          <td>${fmt(p.rss_mb, 0)}M</td>
        </tr>`).join('')}</tbody>
      </table>`;
    }

    function nodeCard(node) {
      if (!node.online) {
        return `<article class="node offline">
          <div class="node-head">
            <div><div class="name">${node.alias}</div><div class="meta">${node.ip} / ${node.role}</div></div>
            <span class="badge">offline</span>
          </div>
          <div class="error">${htmlEscape(node.error || 'No probe output')}</div>
          <div></div>
          <div class="footer"><span>container</span><span>${htmlEscape(node.hostname || '')}</span></div>
        </article>`;
      }
      const cpu = pct(node.cgroup_cpu_pct);
      const disk = pct(node.data_used_pct);
      return `<article class="node online">
        <div class="node-head">
          <div><div class="name">${node.alias}</div><div class="meta">${node.ip} / ${node.role} / ${htmlEscape(node.hostname)}</div></div>
          <span class="badge">online</span>
        </div>
        <div class="metrics">
          <div class="metric"><div class="label">Cgroup CPU</div><div class="value">${fmt(node.cgroup_cores, 2)} / ${fmt(node.quota_cores, 0)} cores</div><div class="bar"><div class="fill cpu ${fillClass(cpu)}" style="width:${cpu}%"></div></div></div>
          <div class="metric"><div class="label">CPU quota</div><div class="value">${fmt(node.cgroup_cpu_pct, 1)}%</div><div class="bar"><div class="fill cpu ${fillClass(cpu)}" style="width:${cpu}%"></div></div></div>
          <div class="metric"><div class="label">Cgroup memory</div><div class="value">${fmt(node.cgroup_mem_mb, 0)} MB</div></div>
          <div class="metric"><div class="label">Data disk</div><div class="value">${fmt(node.data_used_pct, 0)}%</div><div class="bar"><div class="fill disk ${fillClass(disk)}" style="width:${disk}%"></div></div></div>
          <div class="metric"><div class="label">Data free</div><div class="value">${fmt(node.data_free_mb / 1024, 1)} GB</div></div>
          <div class="metric"><div class="label">OB data dir</div><div class="value">${fmt(node.data_dir_mb / 1024, 1)} GB</div></div>
        </div>
        <div>${processRows(node.processes)}</div>
        <div class="footer"><span>nproc ${node.visible_cpus}</span><span>procstat ${fmt(node.procstat_cpu_pct, 1)}%</span></div>
      </article>`;
    }

    async function refresh() {
      try {
        const res = await fetch('/api/snapshot', { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        nodesEl.innerHTML = data.nodes.map(nodeCard).join('');
        document.getElementById('online').textContent = `${data.summary.online}/${data.summary.total}`;
        document.getElementById('maxCpu').textContent = `${fmt(data.summary.max_cpu_pct, 1)}%`;
        document.getElementById('maxDisk').textContent = `${fmt(data.summary.max_disk_pct, 0)}%`;
        document.getElementById('updated').textContent = new Date(data.generated_at * 1000).toLocaleTimeString();
        document.getElementById('scope').textContent = data.scope;
      } catch (err) {
        nodesEl.innerHTML = `<article class="node offline"><div class="error">${htmlEscape(err.message)}</div></article>`;
      }
    }

    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


def build_ssh_command(node: Any, args: argparse.Namespace) -> list[str]:
    probe_args = argparse.Namespace(
        interval=args.interval,
        via=args.via,
        identity=args.identity,
        direct_ip=args.direct_ip,
    )
    return MONITOR.ssh_command(node, probe_args)


def parse_node_line(parts: list[str]) -> dict[str, Any]:
    return {
        "alias": parts[1],
        "role": parts[2],
        "hostname": parts[3],
        "visible_cpus": int(float(parts[4])),
        "quota_cores": float(parts[5]),
        "cgroup_cores": float(parts[6]),
        "cgroup_cpu_pct": float(parts[7]),
        "procstat_cores": float(parts[8]),
        "procstat_cpu_pct": float(parts[9]),
        "throttle_count": int(float(parts[10])),
        "load1": float(parts[11]),
        "data_used_mb": float(parts[12]),
        "data_free_mb": float(parts[13]),
        "data_used_pct": float(parts[14]),
        "data_dir_mb": float(parts[15]),
        "cgroup_mem_mb": float(parts[16]),
        "processes": [],
        "online": True,
    }


def parse_proc_line(parts: list[str]) -> dict[str, Any]:
    return {
        "alias": parts[1],
        "name": parts[2],
        "count": int(float(parts[3])),
        "cores": float(parts[4]),
        "quota_pct": float(parts[5]),
        "rss_mb": float(parts[6]),
    }


def collect_node(node: Any, args: argparse.Namespace) -> dict[str, Any]:
    proc = subprocess.run(
        build_ssh_command(node, args),
        input=MONITOR.REMOTE_PROBE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=args.interval + args.timeout,
        check=False,
    )
    base = {
        "alias": node.alias,
        "ip": node.ip,
        "role": node.role,
        "hostname": "",
        "online": False,
        "error": "",
        "processes": [],
    }
    if proc.returncode != 0:
        base["error"] = (proc.stderr or proc.stdout or f"probe exited {proc.returncode}").strip()
        return base

    parsed = None
    processes = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if parts and parts[0] == "NODE" and len(parts) >= 17:
            parsed = parse_node_line(parts)
        elif parts and parts[0] == "PROC" and len(parts) >= 7:
            processes.append(parse_proc_line(parts))

    if parsed is None:
        base["error"] = (proc.stderr or "empty probe output").strip()
        return base

    parsed["alias"] = node.alias
    parsed["ip"] = node.ip
    parsed["role"] = node.role
    parsed["processes"] = sorted(processes, key=lambda p: (-p["cores"], p["name"]))
    return parsed


def snapshot(args: argparse.Namespace) -> dict[str, Any]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(MONITOR.NODES)) as pool:
        nodes = list(pool.map(lambda node: collect_node(node, args), MONITOR.NODES))
    online = [node for node in nodes if node.get("online")]
    return {
        "generated_at": time.time(),
        "scope": "container cgroup scope; sibling containers require host-side collection",
        "interval": args.interval,
        "nodes": nodes,
        "summary": {
            "total": len(nodes),
            "online": len(online),
            "offline": len(nodes) - len(online),
            "max_cpu_pct": max((node["cgroup_cpu_pct"] for node in online), default=0.0),
            "max_disk_pct": max((node["data_used_pct"] for node in online), default=0.0),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MybankLabMonitor/1.0"

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/api/snapshot"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/snapshot":
            args = self.server.monitor_args
            query = parse_qs(parsed.query)
            if "interval" in query:
                try:
                    args = argparse.Namespace(**vars(args))
                    args.interval = max(0.2, min(10.0, float(query["interval"][0])))
                except ValueError:
                    pass
            payload = snapshot(args)
            self.send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Web dashboard for the mybank lab containers.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--via", default="")
    parser.add_argument("--identity", default="/root/.ssh/id_ed25519")
    parser.add_argument("--direct-ip", action="store_true")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.monitor_args = args
    print(f"serving http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
