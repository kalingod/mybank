# 仿支付宝 Demo — 本地部署与开发计划

---

## 当前执行基线（2026-05-25）

本次 demo 已从“本地 Docker 单节点”调整为 `webide_server` 实验机上的 **OBD 三节点 OceanBase CE 集群**。旧的 Docker 单节点方案只适合快速体验，不能验证高可用；当前硬件条件更适合直接验证 OceanBase 三副本。

| 角色 | 机器 | IP | Zone | 说明 |
|------|------|------|------|------|
| OBD 控制机 / OBServer | exp2 | 10.190.0.81 | zone1 | 复用已部署测试服务所在机器 |
| OBServer | exp3 | 10.190.5.111 | zone2 | 同子网，300G overlay |
| OBServer | exp5 | 10.190.5.65 | zone3 | 同子网，100G overlay |

当前连接信息：

| 项目 | 值 |
|------|-----|
| OceanBase 版本 | OceanBase CE 4.5.0.0 |
| 集群名 | alipay-ob |
| sys 租户 | `root@sys` / `<OB_SYS_PASSWORD>` |
| 业务租户 | `root@alipay_tenant` / `<ALIPAY_TENANT_PASSWORD>` |
| 业务库 | `alipay_demo` |
| MySQL 协议入口 | `10.190.0.81:2881` |
| obshell | `http://10.190.0.81:2886` |

部署文件已落在仓库：

```text
deploy/oceanbase/alipay-ob.yaml
deploy/oceanbase/init-alipay.sql
deploy/oceanbase/schema-alipay.sql
deploy/oceanbase/README.md
scripts/check-oceanbase.sh
```

容器环境限制：

- `vm.max_map_count`、`vm.overcommit_memory`、`net.core.somaxconn` 在容器内只读，只能带告警运行。
- `nofile` 已通过 `/etc/security/limits.d/99-obd-nofile.conf` 调到 65535。
- OceanBase 数据目录使用本地 overlay `/data/oceanbase`，不放在共享 OrangeFS `/home/workspace`。

---

## 旧本机硬件信息（已不作为当前部署基线）

| 组件 | 配置 |
|------|------|
| CPU | 36 核 x86_64 |
| 内存 | 94 GB（可用 ~88 GB） |
| 磁盘 | NVMe SSD 915 GB（可用 ~388 GB） |
| OS | Ubuntu 24.04.4 LTS |
| 内核 | 6.17.0-23-generic |
| IP | 192.168.0.105（内网） |
| Docker | 29.1.3 已安装 |
| JDK | OpenJDK 21.0.10 |
| Node.js | v24.13.0 |
| Python | 3.12.3 |

> 评估：该配置远超 OceanBase 学习环境需求（最低 4C/8G/50G），可以轻松跑 3 节点集群。单节点 NORMAL 模式仅需约 8G 内存，剩余资源充裕。

---

## OceanBase 简介

**OceanBase（奥星贝斯）** 是蚂蚁集团自研的企业级原生分布式数据库。

### 核心特性

| 特性 | 说明 |
|------|------|
| 单机分布式一体化 | 单机像 MySQL 一样轻量，可扩展到 1500+ 节点 |
| MySQL 兼容 | 社区版 100% 兼容 MySQL 5.7/8.0 协议 |
| 高可用 | Paxos 多副本强一致，RPO=0，RTO < 8 秒 |
| HTAP | 一套引擎同时支撑 OLTP + OLAP |
| 低成本 | LSM-Tree 存储引擎，压缩率 70%-90% |
| 多租户 | 原生资源隔离，一个集群承载多个业务 |

### 主要版本

| 版本 | 定位 |
|------|------|
| 企业版 | 金融级核心系统，兼容 Oracle，"三地五中心"容灾 |
| 社区版 | 开源免费，兼容 MySQL，适合开发者和中小企业 |
| seekdb | AI 原生混合搜索数据库，支持向量/全文/GIS 检索 |

---

## 一、OceanBase 本地部署

### 方案：Docker 单节点 NORMAL 模式

```bash
# 拉取镜像
docker pull oceanbase/oceanbase-ce

# 启动（2881=MySQL协议端口, 2886=白屏管理）
docker run -d \
  --name oceanbase-ce \
  -p 2881:2881 \
  -p 2886:2886 \
  -e MODE=NORMAL \
  -e OB_SYS_PASSWORD=<OB_SYS_PASSWORD> \
  -e OB_TENANT_PASSWORD=<ALIPAY_TENANT_PASSWORD> \
  oceanbase/oceanbase-ce

# 等待 2~5 分钟，查看是否启动成功
docker logs oceanbase-ce | tail -1
# 看到 "boot success!" 即就绪
```

### 三种启动模式对比

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| MINI | 最少资源启动 | 快速体验 |
| NORMAL | 使用容器全部可用资源 | **推荐用于学习开发** |
| SLIM | 快速启动，租户名固定为 test | 轻量测试 |

### 端口说明

| 端口 | 协议/用途 | 说明 |
|------|----------|------|
| 2881 | MySQL 协议 | **应用直连此端口**，无需额外部署 MySQL |
| 2886 | HTTP | obshell 白屏 Dashboard（用户管理、集群监控） |

> **不需要穿透 MySQL 的 3306 端口** — OceanBase 本身就讲 MySQL 协议，Spring Boot / Navicat / DBeaver 都可以像连 MySQL 一样连 2881。如果内网其他机器需要访问，开放 2881 即可。

### 可选：OBD 工具部署（Linux 原生）

```bash
# 下载 All-in-One 包
bash -c "$(curl -s https://obbusiness-private.oss-cn-shanghai.aliyuncs.com/download-center/opensource/oceanbase-all-in-one/installer.sh)"
source ~/oceanbase-all-in-one/bin/env.sh

# 一键 demo
obd demo
```

也可以自定义多节点配置（本机 36C/94G 完全能跑 3 节点集群学习 Paxos）。

### 连接数据库

```bash
# 进入容器
docker exec -it oceanbase-ce bash

# 连接 sys 租户（管理用）
obclient -h127.0.0.1 -P2881 -uroot@sys -p

# 连接业务租户
obclient -h127.0.0.1 -P2881 -uroot@alipay_tenant -p
```

### 初始化业务数据库

```sql
-- 创建资源单元
CREATE RESOURCE UNIT alipay_unit
  MAX_MEMORY '4G',
  MAX_DISK_SIZE '50G';

-- 创建资源池
CREATE RESOURCE POOL alipay_pool
  UNIT='alipay_unit', UNIT_NUM=1;

-- 创建 MySQL 兼容租户
CREATE TENANT IF NOT EXISTS alipay_tenant
  ZONE_LIST=('zone1'),
  RESOURCE_POOL_LIST=('alipay_pool')
  SET ob_compatibility_mode='mysql';

-- 在租户内创建业务库
CREATE DATABASE alipay_demo;
```

### 最终连接信息

| 项目 | 值 |
|------|-----|
| Host | 192.168.0.105 |
| Port | 2881 |
| 用户 | root@alipay_tenant |
| 密码 | <ALIPAY_TENANT_PASSWORD> |
| 数据库 | alipay_demo |

---

## 二、数据库表设计（核心 4 张表）

```sql
-- 用户账户表
CREATE TABLE users (
    id BIGINT NOT NULL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    balance DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 交易流水/账单表
CREATE TABLE transactions (
    id BIGINT NOT NULL PRIMARY KEY,
    from_user_id BIGINT,
    to_user_id BIGINT,
    amount DECIMAL(18,2) NOT NULL,
    type VARCHAR(32) NOT NULL COMMENT 'transfer/red_packet_send/red_packet_receive',
    remark VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_from_user (from_user_id),
    KEY idx_to_user (to_user_id),
    KEY idx_created_at (created_at)
);

-- 红包主表
CREATE TABLE red_packets (
    id BIGINT NOT NULL PRIMARY KEY,
    sender_id BIGINT NOT NULL,
    total_amount DECIMAL(18,2) NOT NULL,
    total_count INT NOT NULL,
    remaining_count INT NOT NULL,
    remaining_amount DECIMAL(18,2) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active/finished/expired',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 抢红包记录表
CREATE TABLE red_packet_grabs (
    id BIGINT NOT NULL PRIMARY KEY,
    red_packet_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_packet_id (red_packet_id),
    UNIQUE KEY uk_packet_user (red_packet_id, user_id)
);
```

> **OceanBase 关键注意点**：每张表必须有显式主键；金额字段用 DECIMAL（不用 FLOAT/DOUBLE）；`SELECT ... FOR UPDATE` 行锁保证事务安全。

---

## 三、后端：Spring Boot 3 + MyBatis-Plus

### 技术栈

| 组件 | 选型 | 版本 |
|------|------|------|
| 框架 | Spring Boot | 3.x |
| JDK | OpenJDK | 21 |
| ORM | MyBatis-Plus | 3.5.x |
| 数据库驱动 | MySQL Connector/J | 8.x（OceanBase 兼容 MySQL 协议） |
| 连接池 | HikariCP | Spring Boot 默认 |
| 构建 | Maven | 3.x |

### 项目结构

```
alipay-demo/
├── pom.xml
├── src/main/java/com/alipay/demo/
│   ├── AlipayDemoApplication.java
│   ├── controller/
│   │   ├── UserController.java          # 用户注册、查询
│   │   ├── TransferController.java      # 转账
│   │   ├── RedPacketController.java     # 发红包、抢红包
│   │   └── BillController.java          # 账单流水查询
│   ├── service/
│   │   ├── UserService.java
│   │   ├── TransferService.java         # 事务内扣款+加款
│   │   ├── RedPacketService.java        # 并发安全的抢红包
│   │   └── BillService.java
│   ├── entity/
│   │   ├── User.java
│   │   ├── Transaction.java
│   │   ├── RedPacket.java
│   │   └── RedPacketGrab.java
│   └── mapper/
│       ├── UserMapper.java
│       ├── TransactionMapper.java
│       ├── RedPacketMapper.java
│       └── RedPacketGrabMapper.java
└── src/main/resources/
    └── application.yml
```

### application.yml 数据源配置

```yaml
spring:
  datasource:
    url: jdbc:mysql://192.168.0.105:2881/alipay_demo?useSSL=false&serverTimezone=Asia/Shanghai
    username: root@alipay_tenant
    password: <ALIPAY_TENANT_PASSWORD>
    driver-class-name: com.mysql.cj.jdbc.Driver
```

### REST API 设计

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /api/users | 用户列表 |
| POST | /api/users | 注册用户（初始余额 10000 元） |
| POST | /api/transfer | 转账 `{fromId, toId, amount, remark}` |
| POST | /api/red-packet/send | 发红包 `{senderId, totalAmount, count}` |
| POST | /api/red-packet/grab/{id} | 抢红包 `{userId}` |
| GET | /api/red-packet/{id} | 红包详情（含抢红包记录） |
| GET | /api/red-packets | 红包列表 |
| GET | /api/bills/{userId} | 账单查询 `?start=&end=` |

### 核心业务逻辑

**转账 — @Transactional 保证 ACID：**

```java
@Transactional
public void transfer(Long fromId, Long toId, BigDecimal amount, String remark) {
    User from = userMapper.selectByIdForUpdate(fromId);  // 行锁
    User to   = userMapper.selectByIdForUpdate(toId);    // 行锁

    if (from.getBalance().compareTo(amount) < 0) {
        throw new BusinessException("余额不足");
    }

    from.setBalance(from.getBalance().subtract(amount));
    to.setBalance(to.getBalance().add(amount));
    userMapper.updateById(from);
    userMapper.updateById(to);

    // 两条流水
    transactionMapper.insert(new Transaction(fromId, toId, amount, "transfer", remark));
}
```

**红包算法 — 二倍均值法（微信同款）：**

```
每次抢到的金额 = (0.01, 剩余金额/剩余个数 × 2) 之间的随机数
```

特点：金额随机但不失公平，最后一个人可能拿到较大的剩余金额，但平均期望一致。

**抢红包 — SELECT FOR UPDATE 防超抢：**

```java
@Transactional
public BigDecimal grab(Long packetId, Long userId) {
    // 悲观锁锁住红包行
    RedPacket packet = redPacketMapper.selectByIdForUpdate(packetId);

    if (packet.getRemainingCount() <= 0) {
        throw new BusinessException("红包已被抢完");
    }
    if (grabMapper.exists(packetId, userId)) {
        throw new BusinessException("你已经抢过了");
    }

    // 二倍均值算法计算本次金额
    BigDecimal amount = calcAmount(packet);

    // 更新红包剩余
    packet.setRemainingCount(packet.getRemainingCount() - 1);
    packet.setRemainingAmount(packet.getRemainingAmount().subtract(amount));
    if (packet.getRemainingCount() == 0) {
        packet.setStatus("finished");
    }
    redPacketMapper.updateById(packet);

    // 写入抢红包记录
    grabMapper.insert(new RedPacketGrab(packetId, userId, amount));

    // 增加用户余额
    userMapper.addBalance(userId, amount);

    return amount;
}
```

---

## 四、前端：React + Vite + Ant Design

### 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 框架 | React 18 | |
| 构建 | Vite | 快速的开发服务器 |
| UI 库 | Ant Design 5 | 蚂蚁集团出品，风格契合支付宝场景 |
| HTTP | axios | |
| 路由 | React Router 6 | |

### 目录结构

```
alipay-demo/frontend/
├── package.json
├── vite.config.js                # proxy /api → localhost:8080
├── index.html
├── src/
│   ├── main.jsx
│   ├── App.jsx                   # 路由 + 布局
│   ├── api/
│   │   └── index.js              # axios 实例，baseURL /api
│   └── pages/
│       ├── Home.jsx              # 用户列表 + 余额总览
│       ├── Transfer.jsx          # 转账页面
│       ├── RedPacket.jsx         # 发红包 + 红包列表
│       └── Bills.jsx             # 账单查询（按时间筛选）
```

### Vite 代理配置

```js
// vite.config.js
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8080'
    }
  }
})
```

### 页面功能

| 路由 | 页面 | 核心交互 |
|------|------|---------|
| `/` | 首页 | 用户列表 + 余额展示 + 快捷操作入口 |
| `/transfer` | 转账 | 选择付款方/收款方 + 金额 + 备注 → 提交 |
| `/red-packet` | 红包 | 发红包表单 + 活跃红包列表 + 点击抢红包 |
| `/bills/:userId` | 账单 | 按时间范围筛选收入/支出流水 |

---

## 五、网络与端口规划

```
┌──────────────────────────────────────────────────┐
│                    本机 (192.168.0.105)            │
│                                                   │
│  ┌──────────────┐   ┌──────────────────┐         │
│  │ OceanBase CE │   │  Spring Boot API │         │
│  │  Docker 容器  │   │  (JDK 21)       │         │
│  │              │   │                  │         │
│  │ :2881  ◄────┼───┤  jdbc:mysql://   │         │
│  │ (MySQL协议)  │   │  192.168.0.105   │         │
│  │              │   │  :2881/alipay    │         │
│  │ :2886 (Web)  │   │                  │         │
│  └──────────────┘   │  :8080 (REST)   │         │
│                      └──────┬───────────┘         │
│                             │                     │
│  ┌──────────────────────────┘                    │
│  │  ┌──────────────────┐                         │
│  │  │ React Dev Server │                         │
│  │  │ (Vite)           │                         │
│  │  │                  │                         │
│  │  │ :5173  ──────────┤  浏览器访问              │
│  │  │ proxy /api→8080  │                         │
│  │  └──────────────────┘                         │
│                                                   │
│  内网其他机器可通过 192.168.0.105:2881 直连 OB    │
└──────────────────────────────────────────────────┘
```

### 端口汇总

| 服务 | 端口 | 对外 | 用途 |
|------|------|------|------|
| OceanBase MySQL 协议 | 2881 | 内网 | 应用 + 工具连接 |
| obshell Dashboard | 2886 | 内网 | Web 管理界面 |
| Spring Boot | 8080 | 本机 | REST API |
| React Dev Server | 5173 | 本机 | 前端开发 |

---

## 六、部署步骤总览

### Step 1：部署 OceanBase

```bash
docker pull oceanbase/oceanbase-ce
docker run -d --name oceanbase-ce \
  -p 2881:2881 -p 2886:2886 \
  -e MODE=NORMAL \
  -e OB_SYS_PASSWORD=<OB_SYS_PASSWORD> \
  -e OB_TENANT_PASSWORD=<ALIPAY_TENANT_PASSWORD> \
  oceanbase/oceanbase-ce

# 等待启动（2~5分钟）
docker logs -f oceanbase-ce
# 看到 "boot success!" 即就绪
```

### Step 2：初始化数据库

```bash
docker exec -it oceanbase-ce obclient -h127.0.0.1 -P2881 -uroot@sys -p<OB_SYS_PASSWORD>
```

执行创建租户和库的 SQL（见第一章）。

### Step 3：创建 Spring Boot 后端项目

使用 Spring Initializr 或手写 pom.xml，数据源配连 2881，逐模块实现 API。

### Step 4：创建 React 前端项目

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install antd axios react-router-dom
```

### Step 5：验证

1. 注册 5 个测试用户 → 转账 → 查余额 → 查账单，确认金额正确
2. 发 100 元/10 个红包 → 多人抢 → 确认红包总额 = 100 元
3. 并发抢红包测试（模拟 20 人同时抢同一红包，验证无超抢）

### 学习 OceanBase 特性的验证 SQL

```sql
-- 查看租户资源使用
SELECT * FROM oceanbase.GV$OB_UNITS;

-- 查看 SQL 审计
SELECT * FROM oceanbase.GV$OB_SQL_AUDIT
WHERE tenant_name = 'alipay_tenant' LIMIT 20;

-- 体验在线 DDL（ALTER TABLE 不阻塞读写）
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
```

---

## 七、可扩展方向（学完基础后）

| 方向 | 涉及技术点 |
|------|-----------|
| 3 节点集群 + Paxos | OBD 部署多节点，观察 leader 选举、故障切换 |
| OBProxy 路由 | 读写分离、连接池、故障自动切换 |
| 压测对比 | JMeter + TPC-C benchmark，对比 MySQL |
| 备份恢复 | 物理备份 + PITR 时间点恢复 |
| 监控告警 | OBAgent + Prometheus + Grafana |
| OceanBase seekdb | AI 场景：向量检索 + 全文搜索 |
