#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-10.190.0.81}"
SYS_PASSWORD="${SYS_PASSWORD:?Set SYS_PASSWORD to the OceanBase sys tenant password}"

mysql -h"${HOST}" -P2881 -uroot@sys -p"${SYS_PASSWORD}" -Doceanbase \
  -e "SELECT SVR_IP, SVR_PORT, SQL_PORT, ZONE, STATUS FROM DBA_OB_SERVERS ORDER BY SVR_IP; SELECT TENANT_NAME, TENANT_TYPE, STATUS FROM DBA_OB_TENANTS ORDER BY TENANT_ID;"
