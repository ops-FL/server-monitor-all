# 服务器监控 - 完整项目 🐷📱

500台服务器 CPU/内存/磁盘/IO/TCP 监控，手机微信小程序查看。

## 目录结构

```
server-monitor-all/
├── collector.py              # 采集器（SSH采集 → MySQL）
├── api_server.py             # 后端API（MySQL → HTTP接口）
├── servers.example.yaml      # 服务器列表配置模板
├── requirements.txt          # Python依赖
├── miniprogram/              # 微信小程序
│   ├── app.js / app.json     # 入口
│   └── pages/
│       ├── index/            # 首页 - 服务器列表
│       └── detail/           # 详情 - 单台服务器指标
```

## 部署步骤

### 1️⃣ 服务器上部署采集+API

```bash
# 安装依赖
pip install pymysql paramiko pyyaml rich

# 配置MySQL密码
vim collector.py      # 改 MYSQL_CONFIG 里的 password
vim api_server.py     # 改 DB_CONFIG 里的 password

# 配置服务器列表
cp servers.example.yaml servers.yaml
vim servers.yaml      # 填入你的500台服务器

# 先采集一次试试
python collector.py

# 启动 API（跑起来别关）
python api_server.py &
```

### 2️⃣ 小程序端

```bash
# 从容器复制到本地
docker cp 容器名:/home/node/.openclaw/workspace/server-monitor-all ./server-monitor-all

# 用微信开发者工具导入 miniprogram/ 目录
# 改 app.js 里的 apiBaseUrl 为你的服务器IP:8080
# 详情 → 本地设置 → 勾选"不校验合法域名"
# 预览 → 扫码 → 手机上看
```

### 3️⃣ 定时采集

```bash
crontab -e
*/5 * * * * cd /path/server-monitor-all && python collector.py
```

## 数据流

```
500台服务器
  ↓ SSH采集（每5分钟）
collector.py
  ↓ 写入
MySQL → api_server.py → HTTP接口 → 微信小程序
```

## 改密码

两个文件要改密码：
- `collector.py` → `MYSQL_CONFIG["password"]`
- `api_server.py` → `DB_CONFIG["password"]`
