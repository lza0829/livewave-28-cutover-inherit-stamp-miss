from app.db import 连接
from app.seed import 此刻
from app.services import 时间


def 跑贯验() -> dict:
    """窗输出与撤回互证：已关闭窗的点赞/送礼须等于窗内事件合计；撤回后版本与末次撤回一致。"""
    conn = 连接()
    try:
        问题 = []
        事件数 = conn.execute("SELECT COUNT(*) FROM 互动事件").fetchone()[0]
        已关闭 = conn.execute("SELECT * FROM 热度窗 WHERE 状态='已关闭'").fetchall()
        撤回数 = conn.execute("SELECT COUNT(*) FROM 撤回单").fetchone()[0]
        旁路数 = conn.execute("SELECT COUNT(*) FROM 旁路匣").fetchone()[0]

        for 窗 in 已关闭:
            agg = conn.execute(
                """SELECT COALESCE(SUM(点赞增量),0) AS 赞, COALESCE(SUM(送礼额),0) AS 送, COUNT(*) AS n
                   FROM 互动事件 WHERE 窗键=? AND 命运='已入窗'""",
                (窗["窗键"],),
            ).fetchone()
            if agg["赞"] != 窗["点赞合计"] or agg["送"] != 窗["送礼合计"]:
                问题.append(
                    f"窗{窗['窗键']}合计不符: 窗表赞{窗['点赞合计']}/送{窗['送礼合计']} vs 事件赞{agg['赞']}/送{agg['送']}"
                )
            if agg["n"] != 窗["事件笔数"]:
                问题.append(f"窗{窗['窗键']}笔数不符: 窗表{窗['事件笔数']} vs 事件{agg['n']}")

            末撤 = conn.execute(
                "SELECT * FROM 撤回单 WHERE 窗键=? ORDER BY 编号 DESC LIMIT 1",
                (窗["窗键"],),
            ).fetchone()
            if 末撤 and (末撤["新点赞"] != 窗["点赞合计"] or 末撤["新送礼"] != 窗["送礼合计"]):
                问题.append(f"窗{窗['窗键']}末次撤回与窗表不一致")

        
        脏旁路 = conn.execute(
            "SELECT COUNT(*) FROM 互动事件 WHERE 命运='已旁路' AND 窗键!=''"
        ).fetchone()[0]
        if 脏旁路:
            问题.append(f"旁路事件仍挂窗键:{脏旁路}")

        
        
        for r in conn.execute(
            "SELECT 房间键, MAX(处理时) AS t FROM 切流审计 WHERE 切流态='已闭播' GROUP BY 房间键"
        ).fetchall():
            房态 = conn.execute("SELECT 状态 FROM 直播间 WHERE 房间键=?", (r["房间键"],)).fetchone()
            更晚开播 = conn.execute(
                "SELECT COUNT(*) AS c FROM 切流审计 WHERE 房间键=? AND 切流态='直播中' AND 处理时>?",
                (r["房间键"], r["t"]),
            ).fetchone()["c"]
            if 房态 and 房态["状态"] == "已闭播" and not 更晚开播:
                脏 = conn.execute(
                    "SELECT COUNT(*) AS c FROM 互动事件 WHERE 房间键=? AND 命运='已入窗' AND 处理时>?",
                    (r["房间键"], r["t"]),
                ).fetchone()["c"]
                if 脏:
                    问题.append(f"房{r['房间键']}闭播后仍有{脏}笔正式入窗")
        
        for 房 in conn.execute("SELECT 房间键, 状态 FROM 直播间").fetchall():
            闸 = conn.execute("SELECT * FROM 入流闸 WHERE 房间键=?", (房["房间键"],)).fetchone()
            开 = conn.execute(
                "SELECT COUNT(*) AS c FROM 热度窗 WHERE 房间键=? AND 状态='开启'", (房["房间键"],)
            ).fetchone()["c"]
            if 房["状态"] == "已闭播" and 开:
                问题.append(f"房{房['房间键']}已闭播仍有{开}个开启窗")
            if 闸:
                串 = conn.execute(
                    "SELECT COUNT(*) AS c FROM 热度窗 WHERE 房间键=? AND 状态='开启' AND 切流代次<>?",
                    (房["房间键"], 闸["切流代次"]),
                ).fetchone()["c"]
                if 串:
                    问题.append(f"房{房['房间键']}有{串}个跨代次开启窗")
        
        for 房 in conn.execute("SELECT * FROM 直播间 WHERE 状态='直播中'").fetchall():
            w = conn.execute("SELECT 事件时水位 FROM 水位线 WHERE 房间键=?", (房["房间键"],)).fetchone()
            if w and 时间.解析(w["事件时水位"]) < 时间.解析(房["开播事件时"]):
                问题.append(f"房{房['房间键']}水位{w['事件时水位']}低于开播事件时{房['开播事件时']}")

        # 水位继承戳协同：切流成功不得继承戳空（每条切流审计须有同世代戳）
        for a in conn.execute("SELECT 房间键, 切流代次, 切流态 FROM 切流审计").fetchall():
            戳 = conn.execute(
                "SELECT 1 FROM 水位继承戳 WHERE 房间键=? AND 切流世代=?",
                (a["房间键"], a["切流代次"]),
            ).fetchone()
            if not 戳:
                问题.append(
                    f"房{a['房间键']}切流e{a['切流代次']}({a['切流态']})无同票继承戳——切流成功继承戳空"
                )

        通过 = 1 if not 问题 else 0
        说明 = "窗输出与事件/撤回互证通过" if 通过 else "；".join(问题)[:800]
        conn.execute(
            """INSERT INTO 窗贯验(时刻,事件数,已关闭窗数,撤回数,旁路数,是否通过,说明)
               VALUES (?,?,?,?,?,?,?)""",
            (此刻(), 事件数, len(已关闭), 撤回数, 旁路数, 通过, 说明),
        )
        conn.commit()
        return {
            "是否通过": bool(通过),
            "事件数": 事件数,
            "已关闭窗数": len(已关闭),
            "撤回数": 撤回数,
            "旁路数": 旁路数,
            "说明": 说明,
            "问题": 问题,
        }
    finally:
        conn.close()

def _alias_payload(payload: dict) -> dict:
    out = dict(payload or {})
    if "窗键" in out and "window_key" not in out:
        out["window_key"] = out.get("窗键")
    if "房间键" in out and "room_key" not in out:
        out["room_key"] = out.get("房间键")
    if "事件编号" in out and "event_id" not in out:
        out["event_id"] = out.get("事件编号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows(rows: list) -> list:
    return [_alias_payload(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_28(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "livewave", "nn": "28"}
    if extra:
        data.update(extra)
    return data

