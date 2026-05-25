# OBProxy deployment for alipay-demo

## Current deployment

OBProxy is deployed as a standalone OBD cluster named `mybank-obproxy`.

| Role | SSH alias | IP | Ports |
|---|---|---:|---|
| OBProxy | exp4 | 10.190.49.117 | 2883, 2884, 2885 |
| OBProxy | exp6 | 10.190.14.135 | 2883, 2884, 2885 |

Application traffic should use OBProxy instead of hardcoding a single OBServer.

```bash
mysql -h10.190.49.117 -P2883 -uroot@alipay_tenant#alipay-ob -p'<ALIPAY_TENANT_PASSWORD>' -D alipay_demo -A
mysql -h10.190.14.135 -P2883 -uroot@alipay_tenant#alipay-ob -p'<ALIPAY_TENANT_PASSWORD>' -D alipay_demo -A
```

## Deployment commands

Run on `exp2`, the OBD control node. Copy `obproxy.yaml` to a runtime file and replace passwords there. Do not commit runtime files.

```bash
cp deploy/obproxy/obproxy.yaml /root/obd-alipay/obproxy.runtime.yaml
chmod 600 /root/obd-alipay/obproxy.runtime.yaml
```

Create the `proxyro` account in the sys tenant before starting OBProxy:

```sql
CREATE USER IF NOT EXISTS proxyro IDENTIFIED BY '<OB_PROXYRO_PASSWORD>';
GRANT SELECT ON oceanbase.* TO proxyro;
```

Deploy and start:

```bash
obd cluster deploy mybank-obproxy -c /root/obd-alipay/obproxy.runtime.yaml -f
obd cluster start mybank-obproxy
obd cluster display mybank-obproxy
```

## Verification

From the repo root:

```bash
ALIPAY_TENANT_PASSWORD='<ALIPAY_TENANT_PASSWORD>' scripts/check-obproxy.sh
```

Current smoke verification performed on 2026-05-25:

- `10.190.49.117:2883` and `10.190.14.135:2883` both connected to `alipay_tenant`.
- A write through exp4 OBProxy was read back through exp6 OBProxy.

## Runtime notes

`obproxy_sys_password` is for `root@proxysys`. `observer_sys_password` must match the sys tenant `proxyro` password.

OBProxy state is under `/data/obproxy` on exp4 and exp6. Keep it off `/home/workspace`, which is shared OrangeFS.
