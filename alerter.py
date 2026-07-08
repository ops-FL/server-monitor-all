#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alerter.py - 告警服务（阈值从数据库读取，支持页面配置）
支持 CPU/内存/磁盘/TCP 告警 + 离线告警 + 恢复通知
"""
import os, sys, json, time, pymysql, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

MYSQL_HOST = "你自己的IP"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PWD = "你自己的密码"
MYSQL_DB   = "server_monitor"

ALERT_COOLDOWN = 300
_last_alerts = {}
_alerted_keys = set()

DEFAULT_THRESHOLDS = { "cpu": 80, "mem": 80, "disk": 85, "tcp": 5000, "webhook": "" }

def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PWD,
        database=MYSQL_DB, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

def load_thresholds_from_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT host, thresholds_json FROM servers")
    rows = cur.fetchall()
    # 读取全局 webhook
    cur.execute("SELECT `value` FROM app_config WHERE `key` = 'webhook_url'")
    config_row = cur.fetchone()
    default_webhook = config_row["value"] if config_row else ""
    cur.close()
    conn.close()
    server_thresholds = {}
    for r in rows:
        host = r["host"]
        th_str = r.get("thresholds_json")
        th = {}
        if th_str:
            try: th = json.loads(th_str)
            except: th = {}
        has_custom = any(k in th for k in ("cpu","mem","disk","tcp"))
        if has_custom:
            st = {}
            for k in ("cpu","mem","disk","tcp"):
                if k in th and th[k] is not None: st[k] = th[k]
                else: st[k] = DEFAULT_THRESHOLDS[k] if k != "webhook" else ""
            server_thresholds[host] = st
    return default_webhook, server_thresholds

def get_latest():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT s.host, COALESCE(s.name, s.host) AS display_name, m.ts, m.cpu_percent, m.mem_percent, m.disk_percent, m.tcp_established, m.disks_json FROM servers s LEFT JOIN metrics m ON m.id = (SELECT id FROM metrics WHERE server_id = s.host ORDER BY ts DESC LIMIT 1) WHERE m.ts IS NOT NULL""")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_all_servers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT host, COALESCE(name, host) AS display_name FROM servers")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def check_and_alert():
    default_webhook, server_thresholds = load_thresholds_from_db()
    now = time.time()
    triggered = []
    webhook_msg_map = {}

    # 1. 离线检测
    online_hosts = set()
    rows = get_latest()
    for r in rows:
        if r["ts"] and now - r["ts"] <= 300:
            online_hosts.add(r["host"])

    all_servers = get_all_servers()
    for s in all_servers:
        host = s["host"]
        name = s["display_name"]
        if host not in online_hosts:
            key = "%s:离线" % host
            if now - _last_alerts.get(key, 0) >= ALERT_COOLDOWN:
                _last_alerts[key] = now
                _alerted_keys.add(key)
                mc = {"host":host,"name":name,"type":"离线","value":"","threshold":"","time":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(now)),"recovered":False}
                triggered.append(mc)
                webhook_msg_map.setdefault(default_webhook,[]).append(mc)
        else:
            key = "%s:离线" % host
            if key in _alerted_keys:
                _alerted_keys.discard(key)
                mc = {"host":host,"name":name,"type":"离线","value":"已恢复","threshold":"","time":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(now)),"recovered":True}
                triggered.append(mc)
                webhook_msg_map.setdefault(default_webhook,[]).append(mc)

    # 2. 指标告警
    for r in rows:
        host = r["host"]; name = r["display_name"]; ts = r["ts"]
        if not ts or now - ts > 300: continue
        st = server_thresholds.get(host, DEFAULT_THRESHOLDS)
        th_cpu = st.get("cpu", 80); th_mem = st.get("mem", 80)
        th_disk = st.get("disk", 85); th_tcp = st.get("tcp", 5000)
        webhook = default_webhook
        if not webhook: continue
        cpu = r["cpu_percent"] or 0; mem = r["mem_percent"] or 0; tcp = r["tcp_established"] or 0
        alerts = []
        if cpu > th_cpu: alerts.append(("CPU","%.1f%%"%cpu,"阈值 %.0f%%"%th_cpu))
        if mem > th_mem: alerts.append(("内存","%.1f%%"%mem,"阈值 %.0f%%"%th_mem))
        try: disks = json.loads(r["disks_json"]) if r.get("disks_json") else []
        except: disks = []
        if disks:
            for d in disks:
                if d.get("percent",0) > th_disk:
                    alerts.append(("磁盘","%.1f%% (%.1fGB/%.1fGB) %s"%(d["percent"],d.get("used_gb",0),d.get("total_gb",0),d.get("mount","")),"阈值 %.0f%%"%th_disk))
        else:
            dp = r["disk_percent"] or 0
            if dp > th_disk: alerts.append(("磁盘","%.1f%%"%dp,"阈值 %.0f%%"%th_disk))
        if tcp > th_tcp: alerts.append(("TCP","%d"%tcp,"阈值 %d"%th_tcp))
        current_keys = set()
        for atype,aval,ath in alerts:
            key = "%s:%s"%(host,atype); current_keys.add(key)
            if now - _last_alerts.get(key,0) < ALERT_COOLDOWN: continue
            _last_alerts[key] = now; _alerted_keys.add(key)
            mc = {"host":host,"name":name,"type":atype,"value":aval,"threshold":ath,"time":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(now)),"recovered":False}
            triggered.append(mc); webhook_msg_map.setdefault(webhook,[]).append(mc)
        for ak in list(_alerted_keys):
            ah,at = ak.split(":",1)
            if ah != host or ak in current_keys: continue
            _alerted_keys.discard(ak)
            mc = {"host":host,"name":name,"type":at,"value":"已恢复","threshold":"","time":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(now)),"recovered":True}
            triggered.append(mc); webhook_msg_map.setdefault(webhook,[]).append(mc)

    # 3. 推送
    BATCH_SIZE = 20
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs = []
        for url,msgs in webhook_msg_map.items():
            for i in range(0,len(msgs),BATCH_SIZE):
                fs.append(ex.submit(_send_wecom_bot,url,msgs[i:i+BATCH_SIZE]))
        for f in as_completed(fs):
            try: f.result()
            except Exception as e: print("[ALERT] 推送异常:",e)
    return triggered

def _send_wecom_bot(url,alerts):
    if not url: return
    alarms = [a for a in alerts if not a.get("recovered")]
    recovers = [a for a in alerts if a.get("recovered")]
    parts = []
    if alarms:
        if len(alarms)==1:
            a=alarms[0]
            parts.append("🚨 **服务器告警**\n> 主机: %s (%s)\n> 指标: %s\n> 当前值: %s\n> %s\n> 时间: %s"%(a["name"],a["host"],a["type"],a["value"],a["threshold"],a["time"]))
        else:
            lines=["🚨 **服务器告警（%d 条）**"%len(alarms)]
            for a in alarms: lines.append("> %s (%s) - %s: %s (%s)"%(a["name"],a["host"],a["type"],a["value"],a["threshold"]))
            lines.append("> 时间: %s"%alarms[0]["time"]); parts.append("\n".join(lines))
    if recovers:
        if len(recovers)==1:
            a=recovers[0]
            parts.append("✅ **告警恢复**\n> 主机: %s (%s)\n> 指标: %s\n> 状态: 已恢复正常\n> 时间: %s"%(a["name"],a["host"],a["type"],a["time"]))
        else:
            lines=["✅ **告警恢复（%d 条）**"%len(recovers)]
            for a in recovers: lines.append("> %s (%s) - %s: 已恢复"%(a["name"],a["host"],a["type"]))
            lines.append("> 时间: %s"%recovers[0]["time"]); parts.append("\n".join(lines))
    content="\n\n".join(parts)
    payload={"msgtype":"markdown","markdown":{"content":content}}
    try:
        resp=requests.post(url,json=payload,timeout=5)
        if resp.status_code==200:
            rj=resp.json()
            if rj.get("errcode")==0: print("[WEBHOOK] ok",url[:40])
            else: print("[WEBHOOK] fail:",rj.get("errmsg"))
        else: print("[WEBHOOK] HTTP",resp.status_code)
    except Exception as e: print("[WEBHOOK] err:",e)

def run_once():
    triggered=check_and_alert()
    if triggered:
        for t in triggered:
            if t.get("recovered"): print("[RECOVER]",t["name"],t["host"],t["type"],"=已恢复")
            else: print("[ALERT]",t["name"],t["host"],t["type"],"=",t["value"],t["threshold"])
    else: print("[ALERT] 无告警")
    return triggered

def run_loop(interval=60):
    print("[ALERT] 启动，每%d秒检查"%interval)
    while True:
        try: run_once()
        except Exception as e: print("[ALERT] err:",e)
        time.sleep(interval)

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="loop": run_loop()
    else: run_once()
