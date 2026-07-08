#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_server.py - API 服务（MySQL 版）
Python 3.6 兼容，带登录认证
"""
import os
import sys
import json
import time
import hashlib
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timedelta

def parse_disks(disks_json):
    if not disks_json:
        return []
    try:
        return json.loads(disks_json)
    except:
        return []

# ===== 配置 =====
MYSQL_HOST = "你自己的IP"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASS = "你自己的密码"
MYSQL_DB   = "server_monitor"

ACCOUNTS = {
    "admin": {"password": "admin123"},
}

API_PORT = 9098
TOKEN_EXPIRE = 86400

_active_tokens = {}


def get_conn():
    import pymysql
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        database=MYSQL_DB, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def ts_str(ts):
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts) + timedelta(hours=8)
        return dt.strftime("%H:%M:%S")
    except:
        return "N/A"


def make_token(username):
    raw = "%s_%f_%s" % (username, time.time(), "server_monitor_secret")
    token = hashlib.md5(raw.encode()).hexdigest()
    _active_tokens[token] = {"username": username, "expire": time.time() + TOKEN_EXPIRE}
    return token


def check_token(token):
    if not token or token not in _active_tokens:
        return None
    info = _active_tokens[token]
    if time.time() > info["expire"]:
        del _active_tokens[token]
        return None
    return info["username"]


class Handler(BaseHTTPRequestHandler):

    def _send(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            try:
                return json.loads(self.rfile.read(length).decode())
            except:
                return {}
        return {}

    def _check(self):
        token = self.headers.get("X-Token", "")
        user = check_token(token)
        if not user:
            self._send({"code": 401, "msg": "未登录"})
            return None
        return user

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        if path == "/api/login":
            self._handle_login()
        elif path == "/api/servers/manage":
            if not self._check(): return
            self._handle_manage()
        else:
            self._send({"code": 404, "msg": "not found"})

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")
        if not self._check():
            return
        try:
            if path == "/api/servers":
                self._handle_servers()
            elif path == "/api/servers/manage":
                self._handle_manage_list()
            elif path.startswith("/api/server/"):
                host = path.split("/")[-1]
                self._handle_detail(host)
            elif path == "/api/alerts":
                self._handle_alerts()
            elif path == "/api/stats":
                self._handle_stats()
            elif path == "/api/ping":
                self._send({"code": 200, "msg": "ok"})
            else:
                self._send({"code": 404, "msg": "not found"})
        except Exception as e:
            self._send({"code": 500, "msg": str(e)})

    def _handle_login(self):
        body = self._read_body()
        username = body.get("username", "")
        password = body.get("password", "")
        if not username or not password:
            self._send({"code": 400, "msg": "请输入账号和密码"})
            return
        acct = ACCOUNTS.get(username)
        if not acct or acct["password"] != password:
            self._send({"code": 401, "msg": "账号或密码错误"})
            return
        token = make_token(username)
        self._send({"code": 200, "msg": "登录成功", "token": token, "username": username})

    # =========================================================================
    # 管理接口（增删改阈值）
    # =========================================================================

    def _handle_manage_list(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT host, name, group_name, thresholds_json, ssh_user, ssh_password, port FROM servers ORDER BY group_name, name")
        rows = cur.fetchall()
        # 读取全局配置
        cur.execute("SELECT `value` FROM app_config WHERE `key` = 'webhook_url'")
        config_row = cur.fetchone()
        global_webhook = config_row["value"] if config_row else ""
        cur.close()
        conn.close()
        data = []
        for r in rows:
            item = {"host": r["host"], "name": r["name"] or r["host"], "group": r["group_name"] or ""}
            if r.get("thresholds_json"):
                try:
                    item["thresholds"] = json.loads(r["thresholds_json"])
                except:
                    item["thresholds"] = {}
            else:
                item["thresholds"] = {}
            item["sshUser"] = r.get("ssh_user", "root") or "root"
            item["sshPassword"] = r.get("ssh_password", "") or ""
            item["sshPort"] = r.get("port", 22) or 22
            data.append(item)
        self._send({"code": 200, "data": {"servers": data, "webhook": global_webhook}})

    def _handle_manage(self):
        body = self._read_body()
        action = body.get("action", "")
        conn = get_conn()
        cur = conn.cursor()

        if action == "add":
            host = body.get("host", "").strip()
            if not host:
                self._send({"code": 400, "msg": "IP地址不能为空"})
                cur.close(); conn.close(); return
            name = body.get("name", "").strip() or host
            group = body.get("group", "").strip()
            ssh_user = body.get("sshUser", "root").strip() or "root"
            ssh_password = body.get("sshPassword", "") or ""
            ssh_port = int(body.get("sshPort", 22) or 22)
            cur.execute("SELECT host FROM servers WHERE host = %s", (host,))
            if cur.fetchone():
                self._send({"code": 400, "msg": "该服务器已存在"})
                cur.close(); conn.close(); return
            cur.execute("INSERT INTO servers (host, name, group_name, port, ssh_user, ssh_password) VALUES (%s, %s, %s, %s, %s, %s)",
                        (host, name, group, ssh_port, ssh_user, ssh_password))
            conn.commit()
            # SSH 连通性探测
            status = self._check_ssh_alive(host, ssh_port, ssh_user, ssh_password)
            if status:
                self._send({"code": 200, "msg": "新增成功，服务器在线"})
            else:
                self._send({"code": 200, "msg": "新增成功，但服务器离线（SSH 连接失败）"})

        elif action == "update":
            host = body.get("host", "").strip()
            if not host:
                self._send({"code": 400, "msg": "参数错误"}); cur.close(); conn.close(); return
            name = body.get("name", "").strip() or host
            group = body.get("group", "").strip()
            ssh_user = body.get("sshUser", "root").strip() or "root"
            ssh_password = body.get("sshPassword", "") or ""
            ssh_port = int(body.get("sshPort", 22) or 22)
            cur.execute("UPDATE servers SET name=%s, group_name=%s, port=%s, ssh_user=%s, ssh_password=%s WHERE host=%s",
                        (name, group, ssh_port, ssh_user, ssh_password, host))
            conn.commit()
            self._send({"code": 200, "msg": "已更新"})

        elif action == "delete":
            host = body.get("host", "").strip()
            if not host:
                self._send({"code": 400, "msg": "参数错误"})
                cur.close(); conn.close(); return
            cur.execute("DELETE FROM servers WHERE host = %s", (host,))
            conn.commit()
            self._send({"code": 200, "msg": "已删除"})

        elif action == "threshold":
            host = body.get("host", "").strip()
            thresholds = body.get("thresholds", {})
            if not host:
                self._send({"code": 400, "msg": "参数错误"})
                cur.close(); conn.close(); return
            cur.execute("UPDATE servers SET thresholds_json = %s WHERE host = %s",
                        (json.dumps(thresholds, ensure_ascii=False), host))
            conn.commit()
            self._send({"code": 200, "msg": "阈值已更新"})

        elif action == "import":
            servers = body.get("servers", [])
            count = 0
            for s in servers:
                h = s.get("host", "").strip()
                if not h: continue
                n = s.get("name", "").strip() or h
                g = s.get("group", "").strip()
                su = s.get("sshUser", "root").strip() or "root"
                sp = s.get("sshPassword", "") or ""
                sport = int(s.get("sshPort", 22) or 22)
                cur.execute("SELECT host FROM servers WHERE host = %s", (h,))
                if cur.fetchone():
                    cur.execute("UPDATE servers SET name=%s, group_name=%s, port=%s, ssh_user=%s, ssh_password=%s WHERE host=%s", (n, g, sport, su, sp, h))
                else:
                    cur.execute("INSERT INTO servers (host, name, group_name, port, ssh_user, ssh_password) VALUES (%s, %s, %s, %s, %s, %s)", (h, n, g, sport, su, sp))
                count += 1
            conn.commit()
            self._send({"code": 200, "msg": "导入完成", "count": count})

        elif action == "config":
            webhook = body.get("webhook", "")
            cur.execute("INSERT INTO app_config (`key`, `value`) VALUES ('webhook_url', %s) ON DUPLICATE KEY UPDATE `value` = %s", (webhook, webhook))
            conn.commit()
            self._send({"code": 200, "msg": "配置已保存"})

        else:
            self._send({"code": 400, "msg": "未知操作"})

        cur.close()
        conn.close()

    # =========================================================================
    # 原来的接口
    # =========================================================================

    def _latest(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.host,
                   COALESCE(s.name, s.host) AS display_name,
                   COALESCE(s.group_name, 'default') AS grp,
                   m.ts, m.cpu_percent, m.mem_percent, m.disk_percent,
                   m.tcp_established, m.mem_total_mb, m.mem_used_mb,
                   m.disk_total_gb, m.disk_used_gb,
                   m.disk_read_bytes, m.disk_write_bytes,
                   m.tcp_time_wait, m.load_1m, m.disks_json
            FROM servers s
            LEFT JOIN metrics m ON m.id = (
                SELECT id FROM metrics WHERE server_id = s.host ORDER BY ts DESC LIMIT 1
            )
            ORDER BY s.group_name, s.name
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

    def _row_to_server(self, r, now):
        lag = now - (r["ts"] or now) if r["ts"] else 999
        status = "alive" if lag < 300 else "dead"
        disks = parse_disks(r.get("disks_json"))
        disk_pct = r["disk_percent"] or 0
        if disks:
            total_used = sum(d.get("used_gb", 0) or 0 for d in disks)
            total_all = sum(d.get("total_gb", 0) or 0 for d in disks)
            if total_all > 0:
                disk_pct = round(total_used / total_all * 100, 1)
        return {
            "host": r["host"], "name": r["display_name"], "status": status,
            "cpu": round(r["cpu_percent"] or 0, 1),
            "mem": round(r["mem_percent"] or 0, 1),
            "disk": disk_pct,
            "disks": disks,
            "tcp": r["tcp_established"] or 0,
            "lastUpdate": ts_str(r["ts"]),
        }

    def _row_to_detail(self, r):
        now = time.time()
        lag = now - (r["ts"] or now) if r["ts"] else 999
        status = "alive" if lag < 300 else "dead"
        disks = parse_disks(r.get("disks_json"))
        disk_pct = r["disk_percent"] or 0
        if disks:
            total_used = sum(d.get("used_gb", 0) or 0 for d in disks)
            total_all = sum(d.get("total_gb", 0) or 0 for d in disks)
            if total_all > 0:
                disk_pct = round(total_used / total_all * 100, 1)
        return {
            "host": r["host"], "name": r["display_name"], "status": status,
            "cpu": round(r["cpu_percent"] or 0, 1),
            "mem": round(r["mem_percent"] or 0, 1),
            "disk": disk_pct,
            "memUsed": round((r["mem_used_mb"] or 0) / 1024, 1),
            "memTotal": round((r["mem_total_mb"] or 0) / 1024, 1),
            "disks": disks,
            "ioRead": round((r["disk_read_bytes"] or 0) / 1048576, 2),
            "ioWrite": round((r["disk_write_bytes"] or 0) / 1048576, 2),
            "tcp": r["tcp_established"] or 0,
            "tcpTw": r["tcp_time_wait"] or 0,
            "load1": round(r["load_1m"] or 0, 2),
            "lastUpdate": ts_str(r["ts"]),
        }

    def _handle_servers(self):
        rows = self._latest()
        now = time.time()
        self._send({"code": 200, "data": [self._row_to_server(r, now) for r in rows]})

    def _handle_detail(self, host):
        for r in self._latest():
            if r["host"] == host:
                self._send({"code": 200, "data": self._row_to_detail(r)})
                return
        self._send({"code": 404, "msg": "not found"})

    def _handle_alerts(self):
        rows = self._latest()
        now = time.time()
        alerts = []
        for r in rows:
            if not r["ts"] or now - r["ts"] > 300:
                continue
            cpu = r["cpu_percent"] or 0
            mem = r["mem_percent"] or 0
            disk = r["disk_percent"] or 0
            tcp = r["tcp_established"] or 0
            if cpu > 80:
                alerts.append({"host": r["host"], "name": r["display_name"], "type": "CPU", "desc": "CPU高", "value": "%.0f%%" % cpu, "time": ts_str(r["ts"])})
            if mem > 80:
                alerts.append({"host": r["host"], "name": r["display_name"], "type": "内存", "desc": "内存高", "value": "%.0f%%" % mem, "time": ts_str(r["ts"])})
            disks = parse_disks(r.get("disks_json"))
            has_disk_alert = False
            for d in disks:
                if d.get("percent", 0) > 85:
                    alerts.append({"host": r["host"], "name": r["display_name"], "type": "磁盘", "desc": "磁盘满 (%s)" % d.get("mount", ""), "value": "%.1f%%" % d["percent"], "mount": d.get("mount", ""), "used": "%.1fGB" % d.get("used_gb", 0) if d.get("used_gb") else "", "total": "%.1fGB" % d.get("total_gb", 0) if d.get("total_gb") else "", "time": ts_str(r["ts"])})
                    has_disk_alert = True
            if not has_disk_alert and disk > 85:
                alerts.append({"host": r["host"], "name": r["display_name"], "type": "磁盘", "desc": "磁盘满", "value": "%.0f%%" % disk, "time": ts_str(r["ts"])})
            if tcp > 5000:
                alerts.append({"host": r["host"], "name": r["display_name"], "type": "TCP", "desc": "连接数过多", "value": str(tcp), "time": ts_str(r["ts"])})

        # 单独查所有服务器，找出离线（无数据或超过5分钟没数据）
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT s.host, COALESCE(s.name, s.host) AS display_name, m.ts FROM servers s LEFT JOIN metrics m ON m.id = (SELECT id FROM metrics WHERE server_id = s.host ORDER BY ts DESC LIMIT 1)")
        for s in cur.fetchall():
            host = s["host"]
            name = s["display_name"]
            ts = s["ts"]
            if not ts or now - ts > 300:
                alerts.append({"host": host, "name": name, "type": "离线", "desc": "服务器离线", "value": "", "mount": "", "used": "", "total": "", "time": ts_str(ts) if ts else "N/A"})
        cur.close()
        conn.close()

        self._send({"code": 200, "data": {
            "alerts": alerts,
            "cpuAlerts": sum(1 for a in alerts if a["type"] == "CPU"),
            "memAlerts": sum(1 for a in alerts if a["type"] == "内存"),
            "diskAlerts": sum(1 for a in alerts if a["type"] == "磁盘"),
            "tcpAlerts": sum(1 for a in alerts if a["type"] == "TCP"),
            "offlineAlerts": sum(1 for a in alerts if a["type"] == "离线"),
        }})

    def _check_ssh_alive(self, host, port, user, password):
        """SSH 连通性探测：先试端口通不通，再用 sshpass 尝试连接"""
        import socket
        # 1. 先测端口
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            result = s.connect_ex((host, port))
            s.close()
            if result != 0:
                return False
        except Exception:
            return False
        # 2. 端口通了，尝试 SSH 认证
        try:
            cmd = ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                   "-o", "ConnectTimeout=5", "-o", "BatchMode=no",
                   "-p", str(port), "%s@%s" % (user, host), "echo ok"]
            r = subprocess.run(cmd, capture_output=True, timeout=10)
            return r.returncode == 0
        except FileNotFoundError:
            # sshpass 没装，端口通了也算在线
            return True
        except Exception as e:
            print("[CHECK_SSH] %s:%d error: %s" % (host, port, e))
            return False

    def _handle_stats(self):
        rows = self._latest()
        now = time.time()
        total = len(rows)
        alive = sum(1 for r in rows if r["ts"] and now - r["ts"] < 300)
        self._send({"code": 200, "data": {
            "total": total, "alive": alive, "dead": total - alive,
            "highCpu": sum(1 for r in rows if (r["cpu_percent"] or 0) > 80),
            "highMem": sum(1 for r in rows if (r["mem_percent"] or 0) > 80),
            "highDisk": sum(1 for r in rows if (r["disk_percent"] or 0) > 85),
        }})

    def log_message(self, fmt, *args):
        print("[API] %s - %s" % (self.client_address[0], args[0]))


def main():
    print("=" * 50)
    print("API 服务: http://0.0.0.0:%d" % API_PORT)
    print("  POST /api/login           - 登录")
    print("  GET  /api/servers         - 服务器列表")
    print("  GET  /api/server/X        - 单台详情")
    print("  GET  /api/alerts          - 告警")
    print("  GET  /api/stats           - 统计")
    print("  GET  /api/servers/manage  - 管理列表")
    print("  POST /api/servers/manage  - 管理操作")
    print("    action: add/delete/threshold/import")
    print("默认账号 admin / admin123")
    print("=" * 50)

    srv = HTTPServer(("0.0.0.0", API_PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n服务停止")
        srv.close()


if __name__ == "__main__":
    main()

