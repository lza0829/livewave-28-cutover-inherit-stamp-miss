from datetime import datetime, timezone

from app.db import 连接

建表 = """
CREATE TABLE IF NOT EXISTS 水位继承戳 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  房间键 TEXT NOT NULL,
  切流世代 INTEGER NOT NULL DEFAULT 0,
  切前水位 TEXT NOT NULL DEFAULT '',
  锚点事件时 TEXT NOT NULL DEFAULT '',
  继承模式 TEXT NOT NULL DEFAULT '',
  戳号 TEXT NOT NULL DEFAULT '',
  时刻 TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS 站规 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 直播间 (
  房间键 TEXT PRIMARY KEY,
  标题 TEXT NOT NULL,
  主播 TEXT NOT NULL,
  开播事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '直播中'
);
CREATE TABLE IF NOT EXISTS 互动事件 (
  事件编号 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  事件类型 TEXT NOT NULL,
  事件时 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  观众键 TEXT NOT NULL DEFAULT '',
  点赞增量 INTEGER NOT NULL DEFAULT 0,
  送礼额 INTEGER NOT NULL DEFAULT 0,
  命运 TEXT NOT NULL DEFAULT '已入流',
  窗键 TEXT NOT NULL DEFAULT '',
  批次编号 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 装载批次 (
  编号 TEXT PRIMARY KEY,
  时刻 TEXT NOT NULL,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 水位线 (
  房间键 TEXT PRIMARY KEY REFERENCES 直播间(房间键),
  事件时水位 TEXT NOT NULL,
  允许迟到秒 INTEGER NOT NULL DEFAULT 30,
  更新处理时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 热度窗 (
  窗键 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  切流代次 INTEGER NOT NULL DEFAULT 1,
  窗起事件时 TEXT NOT NULL,
  窗止事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '开启',
  点赞合计 INTEGER NOT NULL DEFAULT 0,
  送礼合计 INTEGER NOT NULL DEFAULT 0,
  事件笔数 INTEGER NOT NULL DEFAULT 0,
  关闭处理时 TEXT NOT NULL DEFAULT '',
  版本 INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS 撤回单 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  房间键 TEXT NOT NULL,
  原因 TEXT NOT NULL,
  旧点赞 INTEGER NOT NULL,
  新点赞 INTEGER NOT NULL,
  旧送礼 INTEGER NOT NULL,
  新送礼 INTEGER NOT NULL,
  处理时 TEXT NOT NULL,
  事件编号 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 旁路匣 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  原因 TEXT NOT NULL,
  载荷 TEXT NOT NULL,
  时刻 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 窗贯验 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  事件数 INTEGER NOT NULL,
  已关闭窗数 INTEGER NOT NULL,
  撤回数 INTEGER NOT NULL,
  旁路数 INTEGER NOT NULL,
  是否通过 INTEGER NOT NULL,
  说明 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 入流闸 (
  房间键 TEXT PRIMARY KEY REFERENCES 直播间(房间键),
  开放 INTEGER NOT NULL DEFAULT 1,
  切流代次 INTEGER NOT NULL DEFAULT 1,
  更新处理时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 切流审计 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  房间键 TEXT NOT NULL,
  切流态 TEXT NOT NULL,
  切流代次 INTEGER NOT NULL,
  开播事件时 TEXT NOT NULL,
  切流前水位 TEXT NOT NULL,
  切流后水位 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  结果 TEXT NOT NULL DEFAULT '已执行',
  说明 TEXT NOT NULL DEFAULT ''
);
"""


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _列名(conn, 表: str) -> set:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({表})")}


def _迁移(conn) -> None:
    """对初始快照之后的既有库做增量迁移，不重建数据。"""
    窗列 = _列名(conn, "热度窗")
    if 窗列 and "切流代次" not in 窗列:
        conn.execute("ALTER TABLE 热度窗 ADD COLUMN 切流代次 INTEGER NOT NULL DEFAULT 1")
    
    房 = [r["房间键"] for r in conn.execute("SELECT 房间键 FROM 直播间")]
    for k in 房:
        conn.execute(
            "INSERT OR IGNORE INTO 入流闸(房间键, 开放, 切流代次, 更新处理时) VALUES (?, 1, 1, ?)",
            (k, 此刻()),
        )


def 初始化库() -> None:
    conn = 连接()
    conn.executescript(建表)
    _迁移(conn)
    if conn.execute("SELECT COUNT(*) AS c FROM 站规").fetchone()["c"] == 0:
        for k, v in {
            "站名": "播浪",
            "窗长秒": "60",
            "允许迟到秒": "30",
            "水位推进策略": "事件时最大值",
            "关窗条件": "水位>=窗止即关闭发射",
            "旁路条件": "水位>=窗止+允许迟到",
            "切流水位口径": "重置：开播把水位重置为开播事件时，新代次窗键隔离历史窗；闭播关闸拒收正式入窗",
            "切流并发口径": "BEGIN IMMEDIATE 串行化，切流/入流抢锁冲突失败闭（409），禁止双水位",
            "骨架": "互动事件入流→事件时间水位线推进→热度窗关闭发射→迟到修正撤回→窗输出与撤回互证",
        }.items():
            conn.execute("INSERT INTO 站规(键, 值) VALUES (?, ?)", (k, v))
    if conn.execute("SELECT COUNT(*) AS c FROM 直播间").fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO 直播间(房间键, 标题, 主播, 开播事件时, 状态) VALUES (?,?,?,?,?)",
            ("房A", "晚间热聊", "主播小浪", "2026-11-22T12:00:00Z", "直播中"),
        )
        conn.execute(
            "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
            ("房A", "2026-11-22T12:00:00Z", 30, 此刻()),
        )
        conn.execute(
            "INSERT INTO 入流闸(房间键, 开放, 切流代次, 更新处理时) VALUES (?, 1, 1, ?)",
            ("房A", 此刻()),
        )
        
        conn.execute(
            "INSERT INTO 直播间(房间键, 标题, 主播, 开播事件时, 状态) VALUES (?,?,?,?,?)",
            ("房B", "午后小场", "主播小波", "2026-11-22T10:00:00Z", "已闭播"),
        )
        conn.execute(
            "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
            ("房B", "2026-11-22T10:30:00Z", 30, 此刻()),
        )
        conn.execute(
            "INSERT INTO 入流闸(房间键, 开放, 切流代次, 更新处理时) VALUES (?, 0, 1, ?)",
            ("房B", 此刻()),
        )
    conn.commit()
    conn.close()
