# OceanBase deployment for alipay-demo

## Current deployment

The first runnable deployment is a three-node OceanBase CE cluster managed by OBD.

| Role | SSH alias | IP | Zone | Ports |
|---|---|---:|---|---|
| OBD control node / OBServer | exp2 | 10.190.0.81 | zone1 | 2881, 2882, 2886 |
| OBServer | exp3 | 10.190.5.111 | zone2 | 2881, 2882, 2886 |
| OBServer | exp5 | 10.190.5.65 | zone3 | 2881, 2882, 2886 |

Connection:

```bash
obclient -h10.190.0.81 -P2881 -uroot@sys -p'<OB_SYS_PASSWORD>' -Doceanbase -A
obclient -h10.190.0.81 -P2881 -uroot@alipay_tenant -p'<ALIPAY_TENANT_PASSWORD>' -D alipay_demo -A
```

Application services should connect through OBProxy after it is deployed:

```bash
mysql -h10.190.49.117 -P2883 -uroot@alipay_tenant#alipay-ob -p'<ALIPAY_TENANT_PASSWORD>' -D alipay_demo -A
mysql -h10.190.14.135 -P2883 -uroot@alipay_tenant#alipay-ob -p'<ALIPAY_TENANT_PASSWORD>' -D alipay_demo -A
```

See `deploy/obproxy/README.md` for the OBProxy topology and deployment commands.

obshell dashboard:

```text
http://10.190.0.81:2886
user: root
password: <OB_SYS_PASSWORD>
```

## Deployment commands

Before deploying, copy `alipay-ob.yaml` to a local runtime file and replace
`<OB_SYS_PASSWORD>` with the real sys tenant password. Do not commit runtime
files that contain real passwords.

Run on `exp2`:

```bash
source ~/.oceanbase-all-in-one/bin/env.sh
obd cluster deploy alipay-ob -c /root/obd-alipay/alipay-ob.runtime.yaml -f
obd cluster start alipay-ob
obd cluster display alipay-ob
```

Initialize the application tenant and schema:

```bash
obclient -h10.190.0.81 -P2881 -uroot@sys -p'<OB_SYS_PASSWORD>' -Doceanbase -A < /root/obd-alipay/init-alipay.sql
sed "s/<ALIPAY_TENANT_PASSWORD>/your-password/g" /root/obd-alipay/schema-alipay.sql > /root/obd-alipay/schema-alipay.runtime.sql
obclient -h10.190.0.81 -P2881 -uroot@alipay_tenant -A < /root/obd-alipay/schema-alipay.runtime.sql
```

## Runtime notes

The webide machines are containers. Kernel settings such as `vm.max_map_count`, `vm.overcommit_memory`, and `net.core.somaxconn` are read-only in the container. OBD starts the cluster with warnings for those values.

`nofile` is a hard startup requirement. The deployment writes this file on all three nodes:

```text
/etc/security/limits.d/99-obd-nofile.conf
```

with:

```text
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
```

`iputils-ping` is also required by OBD startup checks and was installed on all three nodes.

Do not place OceanBase data files under `/home/workspace`; it is OrangeFS shared storage. The current deployment uses local overlay storage under `/data/oceanbase`.
