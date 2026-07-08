#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collector.py - SSH 批量采集服务器性能指标
服务器列表 + SSH 认证信息全部从数据库读取
"""
import os, sys, json, time, socket, hashlib, subprocess, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 配置 =====
MYSQL_HOST = "你自己的IP"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASS = "你自己的密码"
MYSQL_DB   = "server_monitor"

# 并发数
MAX_WORKERS = 50
RETRY = 2
SSH_TIMEOUT = 10

# 采集脚本
COLLECT_SCRIPT = """
cpu_idle=$(awk -v n="$(nproc)" '$1=="cpu" {print int(100-($5+0)/($2+$3+$4+$5+$6+$7+$8)*100)}' /proc/stat)
mem_total=$(awk '/MemTotal/ {printf "%.0f", $2/1024}' /proc/meminfo)
mem_avail=$(awk '/MemAvailable/ {printf "%.0f", $2/1024}' /proc/meminfo)
mem_used=$((mem_total - mem_avail))
mem_percent=$(awk "BEGIN {printf \\\"%.1f\\\", ($mem_total==0?0:$mem_used/$mem_total*100)}")
load=$(cat /proc/loadavg | awk '{print $1,$2,$3}')
ALLDISKS=$(df -B1 -x tmpfs -x devtmpfs -x squashfs -x overlay 2>/dev/null | awk 'NR>1 && $6!="" {printf "%s|%.0f|%.0f|%.1f,", $6, $3/1073741824, $2/1073741824, ($2==0?0:$3/$2*100)}')
echo "ALLDISKS_RAW:$ALLDISKS"
r1=$(awk '$1 ~ /^[svh]d[a-z]|nvme[0-9]n[0-9]|mmcblk[0-9]/ {r+=$3} END {print r}' /proc/diskstats)
w1=$(awk '$1 ~ /^[svh]d[a-z]|nvme[0-9]n[0-9]|mmcblk[0-9]/ {w+=$7} END {print w}' /proc/diskstats)
sleep 1
r2=$(awk '$1 ~ /^[svh]d[a-z]|nvme[0-9]n[0-9]|mmcblk[0-9]/ {r+=$3} END {print r}' /proc/diskstats)
w2=$(awk '$1 ~ /^[svh]d[a-z]|nvme[0-9]n[0-9]|mmcblk[0-9]/ {w+=$7} END {print w}' /proc/diskstats)
io_read=$(( (r2 - r1) * 512 ))
io_write=$(( (w2 - w1) * 512 ))
tcp_est=$(ss -t state established 2>/dev/null | tail -n +2 | wc -l || echo 0)
tcp_tw=$(ss -t state time-wait 2>/dev/null | tail -n +2 | wc -l || echo 0)
echo "CPU:$cpu_idle"
echo "MEM:$mem_total:$mem_used:$mem_percent"
echo "LOAD:$load"
echo "IO:$io_read:$io_write"
echo "TCP:$tcp_est:$tcp_tw"
"""

def log(msg):
    t = time.strftime("%H:%M:%S")
    print("[%s] %s" % (t, msg))

def parse_output(output):
    data = {}
    for line in output.strip().split("\n"):
        line = line.strip()
        if line.startswith("CPU:"):
            try: data["cpu_percent"] = float(line.split(":", 1)[1])
            except: data["cpu_percent"] = 0.0
        elif line.startswith("MEM:"):
            parts = line.split(":", 1)[1].split(":")
            if len(parts) >= 3:
                try:
                    data["mem_total_mb"] = float(parts[0])
                    data["mem_used_mb"] = float(parts[1])
                    data["mem_percent"] = float(parts[2])
                except: pass
        elif line.startswith("LOAD:"):
            parts = line.split(":", 1)[1].split()
            if len(parts) >= 3:
                try:
                    data["load_1m"] = float(parts[0])
                    data["load_5m"] = float(parts[1])
                    data["load_15m"] = float(parts[2])
                except: pass
        elif line.startswith("ALLDISKS_RAW:"):
            disks = []
            raw = line.split(":", 1)[1]
            if raw:
                parts = raw.split(",")
                for p in parts:
                    p = p.strip()
                    if not p: continue
                    fields = p.split("|")
                    if len(fields) >= 4:
                        try:
                            disks.append({"mount": fields[0], "used_gb": round(float(fields[1]), 1), "total_gb": round(float(fields[2]), 1), "percent": round(float(fields[3]), 1)})
                        except: pass
            data["disks"] = disks
        elif line.startswith("IO:"):
            parts = line.split(":", 1)[1].split(":")
            if len(parts) >= 2:
                try:
                    data["disk_read_bytes"] = float(parts[0])
                    data["disk_write_bytes"] = float(parts[1])
                except: pass
        elif line.startswith("TCP:"):
            parts = line.split(":", 1)[1].split(":")
            if len(parts) >= 2:
                try:
                    data["tcp_established"] = int(parts[0])
                    data["tcp_time_wait"] = int(parts[1])
                except: pass
    return data

def get_conn():
    import pymysql
    return pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASS, database=MYSQL_DB, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)

def init_db():
    import pymysql
    conn = pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASS, charset="utf8mb4")
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS %s CHARACTER SET utf8mb4" % MYSQL_DB)
    cur.close(); conn.close()
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            host VARCHAR(64) PRIMARY KEY,
            name VARCHAR(128) DEFAULT NULL,
            group_name VARCHAR(64) DEFAULT 'default',
            port INT DEFAULT 22,
            ssh_user VARCHAR(64) DEFAULT 'root',
            ssh_password VARCHAR(256) DEFAULT ''
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    # 兼容旧表：没有 ssh_user/ssh_password 字段时加上
    try: cur.execute("ALTER TABLE servers ADD COLUMN ssh_user VARCHAR(64) DEFAULT 'root' AFTER port")
    except: pass
    try: cur.execute("ALTER TABLE servers ADD COLUMN ssh_password VARCHAR(256) DEFAULT '' AFTER ssh_user")
    except: pass
    try: cur.execute("ALTER TABLE servers ADD COLUMN thresholds_json TEXT DEFAULT NULL AFTER ssh_password")
    except: pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            server_id VARCHAR(64) NOT NULL,
            ts DOUBLE NOT NULL,
            cpu_percent DOUBLE DEFAULT NULL,
            mem_percent DOUBLE DEFAULT NULL,
            disk_percent DOUBLE DEFAULT NULL,
            mem_total_mb DOUBLE DEFAULT NULL,
            mem_used_mb DOUBLE DEFAULT NULL,
            disk_total_gb DOUBLE DEFAULT NULL,
            disk_used_gb DOUBLE DEFAULT NULL,
            disk_read_bytes DOUBLE DEFAULT NULL,
            disk_write_bytes DOUBLE DEFAULT NULL,
            tcp_established INT DEFAULT NULL,
            tcp_time_wait INT DEFAULT NULL,
            load_1m DOUBLE DEFAULT NULL,
            load_5m DOUBLE DEFAULT NULL,
            load_15m DOUBLE DEFAULT NULL,
            disks_json TEXT DEFAULT NULL,
            UNIQUE KEY uk_server_ts (server_id, ts),
            INDEX idx_ts (ts)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit(); cur.close(); conn.close()
    log("数据库表初始化完成")

def save_metrics(server_id, data):
    conn = get_conn(); cur = conn.cursor()
    disks_json_str = json.dumps(data.get("disks", []), ensure_ascii=False)
    cur.execute("""
        INSERT INTO metrics (server_id, ts, cpu_percent, mem_percent, disk_percent, mem_total_mb, mem_used_mb, disk_total_gb, disk_used_gb, disk_read_bytes, disk_write_bytes, tcp_established, tcp_time_wait, load_1m, load_5m, load_15m, disks_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE ts=VALUES(ts)
    """, (server_id, data["ts"], data.get("cpu_percent"), data.get("mem_percent"), data.get("disk_percent"), data.get("mem_total_mb"), data.get("mem_used_mb"), data.get("disk_total_gb"), data.get("disk_used_gb"), data.get("disk_read_bytes"), data.get("disk_write_bytes"), data.get("tcp_established"), data.get("tcp_time_wait"), data.get("load_1m"), data.get("load_5m"), data.get("load_15m"), disks_json_str))
    conn.commit(); cur.close(); conn.close()

def cleanup_old_data(days=30):
    conn = get_conn(); cur = conn.cursor()
    cutoff = time.time() - days * 86400
    cur.execute("DELETE FROM metrics WHERE ts < %s", (cutoff,))
    deleted = cur.rowcount; conn.commit(); cur.close(); conn.close()
    return deleted

def ssh_exec(host, user, password, port=22, timeout=10):
    cmd = ["ssh"]
    if port and port != 22: cmd.extend(["-p", str(port)])
    if password: cmd = ["sshpass", "-p", password] + cmd
    cmd.extend(["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=%d" % timeout, "-o", "BatchMode=yes", "%s@%s" % (user, host), COLLECT_SCRIPT])
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 5)
    if result.returncode == 0:
        return result.stdout.decode("utf-8", errors="replace")
    else:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        raise Exception(err or "ssh exit code %d" % result.returncode)

def collect_one(server, retry=2):
    host = server["host"]
    port = server.get("port", 22) or 22
    user = server.get("ssh_user", "root") or "root"
    password = server.get("ssh_password", "") or ""
    name = server.get("name", host)
    for attempt in range(retry + 1):
        try:
            output = ssh_exec(host, user, password, port, SSH_TIMEOUT)
            data = parse_output(output)
            if not data: raise Exception("无法解析采集输出")
            data["ts"] = time.time()
            return host, name, data
        except Exception as e:
            if attempt < retry: time.sleep(1); continue
            return host, name, {"error": str(e)[:200], "ts": time.time()}
    return host, name, {"error": "重试耗尽", "ts": time.time()}

def collect_all():
    init_db()
    # 从数据库读取服务器列表（含 SSH 认证信息）
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT host, name, group_name, port, ssh_user, ssh_password FROM servers ORDER BY group_name, name")
    db_rows = cur.fetchall(); cur.close(); conn.close()
    if not db_rows:
        log("数据库 servers 表为空！请先在管理页面添加服务器")
        return 0, 0
    servers = []
    for r in db_rows:
        servers.append({
            "host": r["host"], "name": r.get("name") or r["host"],
            "port": r.get("port", 22) or 22,
            "ssh_user": r.get("ssh_user", "root") or "root",
            "ssh_password": r.get("ssh_password", "") or "",
        })
    total = len(servers)
    log("=" * 50)
    log("开始采集 %d 台服务器 (并发 %d)" % (total, MAX_WORKERS))
    log("=" * 50)
    results = []; errors = []; lock = threading.Lock(); done = [0]; t0 = time.time()
    def on_done(future):
        with lock:
            done[0] += 1
            host, name, data = future.result()
            if "error" in data:
                errors.append((host, name, data["error"]))
            else:
                try:
                    save_metrics(host, data)
                    results.append((host, name))
                except Exception as e:
                    errors.append((host, name, "DB: %s" % str(e)[:100]))
            sys.stdout.write("\r  进度: %d/%d  成功: %d  失败: %d" % (done[0], total, len(results), len(errors)))
            sys.stdout.flush()
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures = [executor.submit(collect_one, s, RETRY) for s in servers]
    for f in futures: f.add_done_callback(on_done)
    for f in futures: f.result()
    executor.shutdown()
    elapsed = time.time() - t0
    print()
    log("=" * 50)
    log("采集完成！耗时: %.0f秒  成功: %d  失败: %d" % (elapsed, len(results), len(errors)))
    if errors:
        print()
        log("失败列表:")
        for h, n, e in errors[:20]:
            log("  [FAIL] %s (%s): %s" % (h, n, e[:80]))
        if len(errors) > 20: log("  ... 还有 %d 个" % (len(errors) - 20))
    deleted = cleanup_old_data(30)
    if deleted: log("已清理 %d 条过期数据" % deleted)
    return len(results), len(errors)

if __name__ == "__main__":
    collect_all()

