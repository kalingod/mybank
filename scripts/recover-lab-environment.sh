#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTROL_ALIAS="${CONTROL_ALIAS:-exp2}"
CONTROL_IP="${CONTROL_IP:-10.190.0.81}"
SSH_KEY="${SSH_KEY:-/root/.ssh/id_ed25519}"
SYNC_REPO="${SYNC_REPO:-1}"

NODE_ALIASES=(exp1 exp2 exp3 exp4 exp5 exp6)
NODE_IPS=(10.190.40.174 10.190.0.81 10.190.5.111 10.190.49.117 10.190.5.65 10.190.14.135)

echo "== ensure control key on ${CONTROL_ALIAS} =="
ssh "${CONTROL_ALIAS}" "mkdir -p /root/.ssh && chmod 700 /root/.ssh && if [ ! -s '${SSH_KEY}' ]; then ssh-keygen -t ed25519 -N '' -C mybank-monitor -f '${SSH_KEY}'; fi && cat '${SSH_KEY}.pub'"
PUB_KEY="$(ssh "${CONTROL_ALIAS}" "cat '${SSH_KEY}.pub'")"

echo "== distribute control public key to lab containers =="
for alias in "${NODE_ALIASES[@]}"; do
  printf '%s\n' "${PUB_KEY}" | ssh "${alias}" '
    set -euo pipefail
    read -r pub
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh
    touch /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
    grep -qxF "$pub" /root/.ssh/authorized_keys || printf "%s\n" "$pub" >> /root/.ssh/authorized_keys
  '
done

echo "== verify ${CONTROL_ALIAS} can reach every container by IP =="
for ip in "${NODE_IPS[@]}"; do
  ssh "${CONTROL_ALIAS}" "ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i '${SSH_KEY}' root@${ip} 'hostname; true'" >/dev/null
  echo "ok ${ip}"
done

if [ "${SYNC_REPO}" = "1" ]; then
  echo "== recover shared git repo and workspace =="
  ssh "${CONTROL_ALIAS}" "mkdir -p /home/workspace/git && if [ ! -d /home/workspace/git/mybank.git ]; then git init --bare /home/workspace/git/mybank.git; fi"
  if git -C "${ROOT}" remote get-url internal >/dev/null 2>&1; then
    git -C "${ROOT}" push internal main
  fi
  ssh "${CONTROL_ALIAS}" '
    set -euo pipefail
    if [ -d /home/workspace/mybank/.git ]; then
      cd /home/workspace/mybank
      git remote get-url internal >/dev/null 2>&1 || git remote add internal /home/workspace/git/mybank.git
      git pull internal main --ff-only
    else
      git clone /home/workspace/git/mybank.git /home/workspace/mybank
    fi
  '
fi

echo "recovery complete"
