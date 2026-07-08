# 🐷 服务器监控系统 - ServerMonitorAll

> 500 台服务器 CPU / 内存 / 磁盘 / IO / TCP 监控，手机微信小程序实时查看。
>
> **SSH 批量采集 → MySQL 存储 → RESTful API → 微信小程序 + 企业微信告警**

---

## 📸 截图一览

| 首页 - 服务器列表 | 单台详情页 | 告警列表 |
|---|---|---|
| 服务器分组展示、状态一目了然 | CPU/内存/磁盘/IO/TCP 指标详情 | 实时告警、筛选和恢复通知 |

> 补截图：在你的小程序中截图后放到 `screenshots/` 目录下即可。

---

## ✨ 功能特性

- **批量 SSH 采集** — 并发 50 线程，5 分钟一轮，采集数千台无压力
- **核心指标覆盖** — CPU 使用率、内存占用、各分区磁盘、IO 读写、TCP 连接数、Load Average
- **多分区展示** — 每个挂载点的磁盘占用百分比和容量，一目了然
- **智能告警** — CPU > 80%、内存 > 80%、磁盘 > 85%、TCP > 5000、离线检测
- **告警推送** — 企业微信机器人 Webhook，支持告警收敛（冷却期 5 分钟）+ 恢复通知
- **管理后台** — 微信小程序内直接增删改查服务器，设置阈值，导入/导出
- **身份认证** — 登录 Token 鉴权
- **状态过滤** — 按"在线/离线/CPU高/内存高/磁盘高/TCP多"快速筛选
- **自动建表** — 首次运行自动创建数据库和表结构
- **数据清理** — 自动清理 30 天前的历史数据

---

## 🏗 系统架构

```
┌──────────┐    SSH(并发50)    ┌───────────┐    写入    ┌──────────┐
│  500 台   │ ◄────────────── │ collector │ ─────────► │  MySQL   │
│  服务器   │    paramiko      │  .py      │            │  Server  │
└──────────┘                  └───────────┘            │  Monitor │
                                                         └────┬─────┘
                                                              │ 查询
                                                         ┌────▼─────┐
┌──────────┐    Webhook     ┌───────────┐     HTTP     │  api_    │
│ 企业微信  │ ◄─────────── │ alerter   │ ◄─────────── │  server  │
│  机器人   │                │  .py      │    JSON      │  .py     │
└──────────┘                └───────────┘             └────▲─────┘
                                                            │ HTTP/JSON
                                                      ┌─────┴──────┐
                                                      │  微信小程序  │
                                                      │  (手机端)    │
                                                      └────────────┘
```

**三大组件：**

| 组件 | 用途 | 部署位置 |
|---|---|---|
| `collector.py` | SSH 登录每台服务器执行采集脚本，结果写入 MySQL | 内网跳板机 |
| `api_server.py` | 从 MySQL 查询最新指标，暴露 RESTful API | 内网跳板机 |
| `alerter.py` | 定期检查指标是否超阈值，推送企业微信通知 | 内网跳板机 |
| `miniprogram/` | 微信小程序，手机端查看和管理 | 微信开发者工具导入 |

---

## 🚀 快速部署

### 前置条件

- Python 3.6+
- MySQL 5.7+
- 每台被监控服务器开通 SSH（root 或普通用户）
- （可选）企业微信群机器人 Webhook

### 1. 克隆项目

```bash
git clone https://github.com/ops-FL/server-monitor-all.git
cd server-monitor-all
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖列表：`pymysql`、`pyyaml`、`requests`

> 如果使用密码 SSH，需要额外安装 `sshpass`：
> ```bash
> # CentOS / RHEL
> yum install -y sshpass
> # Ubuntu / Debian
> apt-get install -y sshpass
> ```

### 3. 配置数据库

进入 `collector.py` 和 `api_server.py` 修改数据库连接信息：

```python
MYSQL_HOST = "127.0.0.1"   # MySQL 地址
MYSQL_PORT = 3306           # 端口
MYSQL_USER = "root"         # 用户名
MYSQL_PASS = "你的密码"      # 密码
MYSQL_DB   = "server_monitor"  # 数据库名
```

也可以手动建库（推荐首次部署时直接导入）：

```bash
mysql -uroot -p < server_monitor.sql
```

> `server_monitor.sql` 包含完整的建库建表语句，3 张表一一对应。
> 如果表已存在，`CREATE TABLE IF NOT EXISTS` 不会覆盖，放心执行。

### 4. 添加服务器

有两种方式：

**方式 A：小程序管理页面添加**

先启动 API，然后在小程序里逐台添加。

**方式 B：批量导入（推荐）**

在管理页面的"导入"功能中粘贴 CSV 格式数据：

```csv
192.168.1.101,web-01,web
192.168.1.102,db-01,db
192.168.1.103,redis-01,cache
```

格式：`IP,名称,分组`

### 5. 启动采集

```bash
python collector.py
```

首次会看到类似输出：

```
[09:00:00] ==================================================
[09:00:00] 开始采集 500 台服务器 (并发 50)
[09:00:00] ==================================================
  进度: 500/500  成功: 498  失败: 2
[09:05:32] ==================================================
[09:05:32] 采集完成！耗时: 332秒  成功: 498  失败: 2
[09:05:32] 失败列表:
[09:05:32]   [FAIL] 10.0.0.99 (old-server): ssh exit code 255
[09:05:32]   [FAIL] 10.0.0.100 (down-server): ssh_exception
[09:05:32] 已清理 0 条过期数据
```

### 6. 启动 API 服务

```bash
# 后台运行
nohup python api_server.py > api.log 2>&1 &
```

API 默认监听 `0.0.0.0:8080`，可通过修改 `api_server.py` 中的 `API_PORT` 调整。

### 7. 配置定时采集

```bash
crontab -e
```

添加（每 5 分钟采集一次）：

```cron
*/5 * * * * cd /path/to/server-monitor-all && python collector.py >> collect.log 2>&1
```

### 8. 配置告警（可选）

```bash
# 后台运行告警服务，每 60 秒检查一次
nohup python alerter.py loop > alerter.log 2>&1 &
```

在管理页面中配置：

1. 全局设置 → 企业微信 Webhook URL
2. 各服务器可单独设置告警阈值（CPU/内存/磁盘/TCP）
3. 告警有 5 分钟冷却期，避免重复推送

### 9. 微信小程序

```
1. 用微信开发者工具打开 miniprogram/ 目录
2. 修改 app.js 中的 apiBaseUrl 为你的服务器 IP:端口
3. 详情 → 本地设置 → 勾选"不校验合法域名"
4. 编译 → 预览 → 扫码 → 手机上看
```

> **小贴士：** 小程序默认登录账号 `admin` / `admin123`，可在 `api_server.py` 的 `ACCOUNTS` 字典中修改。

---

## 📂 项目结构

```
server-monitor-all/
├── README.md                       # ← 你现在在看这个
├── requirements.txt                # Python 依赖
├── collector.py                    # SSH 采集器（核心）
├── api_server.py                   # RESTful API 服务
├── alerter.py                      # 告警引擎 + 企业微信推送
├── collect.yaml                    # （旧版配置，仅供兼容参考）
├── servers.example.yaml            # （旧版配置模板）
├── schema.sql                      # 数据库完整建表语句（DDL）
├── alter_table.sql                 # 数据库迁移 SQL（旧版兼容）
├── miniprogram/                    # 微信小程序源码
│   ├── app.js                      # 小程序入口 + 全局 API 封装
│   ├── app.json                    # 页面注册
│   └── pages/
│       ├── login/                  # 登录页
│       ├── index/                  # 首页 - 服务器列表 + 状态过滤
│       ├── detail/                 # 详情页 - 单台服务器全部指标
│       ├── alerts/                 # 告警列表页
│       └── manage/                 # 管理页 - 增删改查 + 阈值设置
```

---

## 📡 API 接口文档

所有 API 基于 `http://<host>:9098`，返回 JSON 格式。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 登录，返回 Token |

请求体：`{"username": "admin", "password": "admin123"}`

之后所有 API 需要在 Header 中携带：`X-Token: <token>`

### 服务器

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/servers` | 所有服务器最新指标（含状态） |
| GET  | `/api/server/<host>` | 单台服务器详细指标 |
| GET  | `/api/stats` | 概览统计（总/在线/离线/高CPU/高内存/高磁盘） |

### 告警

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/alerts` | 当前告警列表（含统计摘要） |

### 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/servers/manage` | 管理列表（含 SSH 配置、阈值） |
| POST | `/api/servers/manage` | 管理操作（增删改） |

POST action 支持：
- `add` — 新增服务器
- `update` — 更新服务器信息
- `delete` — 删除服务器
- `threshold` — 设置告警阈值
- `import` — 批量导入
- `config` — 全局配置（webhook）

### 返回格式

```json
{
  "code": 200,
  "msg": "ok",
  "data": { ... }
}
```

---

## 📊 采集指标说明

| 指标 | 来源 | 说明 |
|------|------|------|
| CPU | `/proc/stat` | 通过 `/proc/stat` 计算 CPU 使用率 |
| 内存 | `/proc/meminfo` | MemTotal / MemAvailable |
| 磁盘 | `df -B1` | 每个分区的总量、已用、使用率 |
| IO | `/proc/diskstats` | 每秒读写字节数（间隔 1 秒采样） |
| TCP | `ss -t` | ESTABLISHED 和 TIME_WAIT 连接数 |
| Load | `/proc/loadavg` | 1/5/15 分钟负载 |

---

## ⚙️ 配置详解

### 数据库配置

修改 `collector.py` 和 `api_server.py` 顶部 `MYSQL_*` 常量。

### 账号配置

修改 `api_server.py` 中的 `ACCOUNTS` 字典：

```python
ACCOUNTS = {
    "admin": {"password": "admin123"},
    "ops":   {"password": "ops@2024"},
    "dev":   {"password": "dev@2024"},
}
```

### 并发与超时

修改 `collector.py` 顶部：

```python
MAX_WORKERS = 50    # 并发 SSH 连接数
RETRY = 2            # 采集失败重试次数
SSH_TIMEOUT = 10     # SSH 连接超时（秒）
```

### 告警阈值

在管理页面中可对每台服务器单独设置阈值，优先级高于全局默认值。

---

## 🔧 常见问题

### Q: 大量机器 SSH 连接失败怎么办？
- 检查 SSH 端口和用户名密码是否正确
- 检查跳板机到目标服务器的网络连通性
- 降低 `MAX_WORKERS` 并发数，避免网络拥塞
- 启用密钥认证替代密码，去掉 `sshpass` 依赖

### Q: 采集性能如何？
- 50 并发下，500 台服务器约 5-6 分钟完成一轮
- 如果服务器数量更大，可以调整并发数
- 注意跳板机自身资源（CPU/内存/网络）不要打满

### Q: API 服务稳定吗？
- `api_server.py` 基于 Python 内置 `http.server`，单进程单线程
- 适合 1-5 人同时使用的场景
- 如需更高并发，建议用 Flask/FastAPI 封装，或前面加 Nginx 反向代理

### Q: 告警风暴怎么避免？
- 内置 5 分钟冷却期，同一台服务器同一种告警不会重复推送
- 告警恢复后有恢复通知，避免人为忽略
- 支持企业微信机器人精准推送

---

## 📝 License

MIT License

---

## 🌟 贡献

欢迎提 Issue 和 PR！

如果你觉得这个项目有帮助，请给个 ⭐️，谢谢！🐷
