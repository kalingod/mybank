#!/usr/bin/env bash
set -euo pipefail

ALIPAY_TENANT_PASSWORD="${ALIPAY_TENANT_PASSWORD:?Set ALIPAY_TENANT_PASSWORD to the OceanBase application tenant password}"
HOST="${HOST:-10.190.49.117}"
PORT="${PORT:-2883}"
CLUSTER_NAME="${CLUSTER_NAME:-alipay-ob}"
DATABASE="${DATABASE:-alipay_demo}"
USER_NAME="${USER_NAME:-root@alipay_tenant#${CLUSTER_NAME}}"
ACCOUNTS="${ACCOUNTS:-1000}"
CONCURRENCY_LIST="${CONCURRENCY_LIST:-1,4,8,16,32}"
QUERIES="${QUERIES:-3200}"
ITERATIONS="${ITERATIONS:-1}"
MODE="${MODE:-all}"

mysql_query() {
  MYSQL_PWD="${ALIPAY_TENANT_PASSWORD}" mysql \
    -h"${HOST}" \
    -P"${PORT}" \
    -u"${USER_NAME}" \
    -D"${DATABASE}" \
    -A \
    --connect-timeout=5 \
    "$@"
}

prepare_schema() {
  local tmp_sql
  tmp_sql="$(mktemp)"
  cat >"${tmp_sql}" <<SQL
CREATE TABLE IF NOT EXISTS loadtest_accounts (
    id BIGINT NOT NULL PRIMARY KEY,
    balance DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
);

CREATE TABLE IF NOT EXISTS loadtest_ledger (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    conn_id BIGINT NOT NULL,
    from_account BIGINT NOT NULL,
    to_account BIGINT NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_created_at (created_at),
    KEY idx_accounts (from_account, to_account)
);

TRUNCATE TABLE loadtest_accounts;
TRUNCATE TABLE loadtest_ledger;
INSERT INTO loadtest_accounts (id, balance) VALUES
SQL
  seq 1 "${ACCOUNTS}" | awk -v total="${ACCOUNTS}" '
    {
      suffix = (NR == total ? ";" : ",")
      printf("(%d, 100000.00)%s\n", $1, suffix)
    }
  ' >>"${tmp_sql}"

  cat >>"${tmp_sql}" <<SQL

DROP PROCEDURE IF EXISTS loadtest_transfer_one;
DELIMITER //
CREATE PROCEDURE loadtest_transfer_one()
BEGIN
    DECLARE src_id BIGINT;
    DECLARE dst_id BIGINT;
    DECLARE first_id BIGINT;
    DECLARE second_id BIGINT;
    DECLARE locked_balance DECIMAL(18,2);

    SET src_id = FLOOR(1 + RAND() * ${ACCOUNTS});
    SET dst_id = FLOOR(1 + RAND() * ${ACCOUNTS});
    IF dst_id = src_id THEN
        SET dst_id = IF(src_id = ${ACCOUNTS}, 1, src_id + 1);
    END IF;

    SET first_id = LEAST(src_id, dst_id);
    SET second_id = GREATEST(src_id, dst_id);

    START TRANSACTION;
    SELECT balance INTO locked_balance FROM loadtest_accounts WHERE id = first_id FOR UPDATE;
    SELECT balance INTO locked_balance FROM loadtest_accounts WHERE id = second_id FOR UPDATE;
    UPDATE loadtest_accounts SET balance = balance - 1.00 WHERE id = src_id;
    UPDATE loadtest_accounts SET balance = balance + 1.00 WHERE id = dst_id;
    INSERT INTO loadtest_ledger (conn_id, from_account, to_account, amount)
      VALUES (CONNECTION_ID(), src_id, dst_id, 1.00);
    COMMIT;
END//
DELIMITER ;
SQL

  mysql_query <"${tmp_sql}"
  rm -f "${tmp_sql}"
}

run_slap() {
  local label="$1"
  local query="$2"
  local c output avg min max qpc total tps

  IFS=',' read -r -a concurrencies <<<"${CONCURRENCY_LIST}"
  printf "%-12s %-8s %-12s %-12s %-12s %-12s\n" "workload" "clients" "queries" "avg_sec" "max_sec" "qps_or_tps"
  for c in "${concurrencies[@]}"; do
    output="$(MYSQL_PWD="${ALIPAY_TENANT_PASSWORD}" mysqlslap \
      --host="${HOST}" \
      --port="${PORT}" \
      --user="${USER_NAME}" \
      --create-schema="${DATABASE}" \
      --concurrency="${c}" \
      --iterations="${ITERATIONS}" \
      --number-of-queries="${QUERIES}" \
      --query="${query}" 2>&1)"

    avg="$(awk -F: '/Average number of seconds to run all queries/{gsub(/ seconds/, "", $2); gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' <<<"${output}")"
    min="$(awk -F: '/Minimum number of seconds to run all queries/{gsub(/ seconds/, "", $2); gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' <<<"${output}")"
    max="$(awk -F: '/Maximum number of seconds to run all queries/{gsub(/ seconds/, "", $2); gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' <<<"${output}")"
    qpc="$(awk -F: '/Average number of queries per client/{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' <<<"${output}")"
    total="$(awk -v c="${c}" -v qpc="${qpc}" 'BEGIN { printf "%.0f", c * qpc }')"
    tps="$(awk -v total="${total}" -v avg="${avg}" 'BEGIN { if (avg > 0) printf "%.2f", total / avg; else print "0.00" }')"
    printf "%-12s %-8s %-12s %-12s %-12s %-12s\n" "${label}" "${c}" "${total}" "${avg}" "${max}" "${tps}"
    if grep -Eiq 'error|failed|deadlock|timeout' <<<"${output}"; then
      echo "${output}" >&2
      return 1
    fi
  done
}

case "${MODE}" in
  prepare)
    prepare_schema
    ;;
  read)
    run_slap "point_read" "SELECT balance FROM loadtest_accounts WHERE id = FLOOR(1 + RAND() * ${ACCOUNTS})"
    ;;
  write)
    run_slap "transfer" "CALL loadtest_transfer_one()"
    mysql_query -e "SELECT COUNT(*) AS ledger_rows FROM loadtest_ledger; SELECT SUM(balance) AS total_balance FROM loadtest_accounts;"
    ;;
  all)
    prepare_schema
    run_slap "point_read" "SELECT balance FROM loadtest_accounts WHERE id = FLOOR(1 + RAND() * ${ACCOUNTS})"
    run_slap "transfer" "CALL loadtest_transfer_one()"
    mysql_query -e "SELECT COUNT(*) AS ledger_rows FROM loadtest_ledger; SELECT SUM(balance) AS total_balance FROM loadtest_accounts;"
    ;;
  *)
    echo "Unsupported MODE=${MODE}. Use prepare, read, write, or all." >&2
    exit 2
    ;;
esac
