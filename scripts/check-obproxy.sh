#!/usr/bin/env bash
set -euo pipefail

ALIPAY_TENANT_PASSWORD="${ALIPAY_TENANT_PASSWORD:?Set ALIPAY_TENANT_PASSWORD to the OceanBase application tenant password}"
CLUSTER_NAME="${CLUSTER_NAME:-alipay-ob}"
DATABASE="${DATABASE:-alipay_demo}"
USER_NAME="${USER_NAME:-root@alipay_tenant#${CLUSTER_NAME}}"
PORT="${PORT:-2883}"

if [ "$#" -gt 0 ]; then
  HOSTS=("$@")
else
  HOSTS=(10.190.49.117 10.190.14.135)
fi

for host in "${HOSTS[@]}"; do
  echo "== ${host}:${PORT} =="
  MYSQL_PWD="${ALIPAY_TENANT_PASSWORD}" mysql \
    -h"${host}" \
    -P"${PORT}" \
    -u"${USER_NAME}" \
    -D"${DATABASE}" \
    -A \
    --connect-timeout=5 \
    -e "SELECT COUNT(*) AS users FROM users; SELECT COUNT(*) AS transactions FROM transactions;"
done
