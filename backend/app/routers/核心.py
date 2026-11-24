import json
import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import 夹具目录, 连接
from app.modules import 水位继承戳 as 继
from app.services import 装载, 贯验, 目录, 切流

路由 = APIRouter(prefix="/api")


class 装载请求(BaseModel):
    批次编号: str = ""
    事件: list = Field(default_factory=list)


class 开播请求(BaseModel):
    房间键: str
    开播事件时: str = ""


class 闭播请求(BaseModel):
    房间键: str


def _失败闭(exc: Exception) -> HTTPException:
    """切流/入流并发抢锁或状态冲突 → 409 失败闭，不吞错、不双写。"""
    if 切流.是否锁冲突(exc):
        return HTTPException(409, f"切流并发冲突（写锁竞争），失败闭拒绝：{exc}")
    return HTTPException(409, str(exc))


@路由.get("/健康")
def 健康():
    return {
        "正常": True,
        "项目": "播浪",
        "骨架": "互动事件入流→事件时间水位线推进→热度窗关闭发射→迟到修正撤回→窗输出与撤回互证",
    }


@路由.get("/总览")
def 取总览():
    return 目录.总览()


@路由.get("/站规")
def 站规():
    conn = 连接()
    try:
        return {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 站规")}
    finally:
        conn.close()


@路由.get("/直播间")
def 列直播间():
    conn = 连接()
    try:
        rooms = [dict(r) for r in conn.execute("SELECT * FROM 直播间 ORDER BY 房间键")]
        for r in rooms:
            wm = conn.execute("SELECT * FROM 水位线 WHERE 房间键=?", (r["房间键"],)).fetchone()
            r["水位线"] = dict(wm) if wm else None
            z = conn.execute("SELECT * FROM 入流闸 WHERE 房间键=?", (r["房间键"],)).fetchone()
            r["入流闸"] = dict(z) if z else None
        return rooms
    finally:
        conn.close()


@路由.get("/事件")
def 列事件(命运: str = ""):
    conn = 连接()
    try:
        if 命运:
            rows = conn.execute(
                "SELECT * FROM 互动事件 WHERE 命运=? ORDER BY 事件时 DESC LIMIT 200", (命运,)
            )
        else:
            rows = conn.execute("SELECT * FROM 互动事件 ORDER BY 事件时 DESC LIMIT 200")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@路由.get("/水位线")
def 列水位线():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 水位线 ORDER BY 房间键")]
    finally:
        conn.close()


@路由.get("/热度窗")
def 列热度窗(状态: str = ""):
    conn = 连接()
    try:
        if 状态:
            rows = conn.execute(
                "SELECT * FROM 热度窗 WHERE 状态=? ORDER BY 窗起事件时 DESC", (状态,)
            )
        else:
            rows = conn.execute("SELECT * FROM 热度窗 ORDER BY 窗起事件时 DESC")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@路由.get("/撤回单")
def 列撤回():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 撤回单 ORDER BY 编号 DESC LIMIT 100")]
    finally:
        conn.close()


@路由.get("/旁路匣")
def 列旁路():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 旁路匣 ORDER BY 编号 DESC LIMIT 100")]
    finally:
        conn.close()


@路由.get("/批次")
def 列批次():
    conn = 连接()
    try:
        out = []
        for r in conn.execute("SELECT * FROM 装载批次 ORDER BY 时刻 DESC LIMIT 30"):
            d = dict(r)
            try:
                d["报告"] = json.loads(d["报告"])
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        conn.close()


@路由.post("/装载")
def 做装载(体: 装载请求):
    try:
        return 装载.装一批(体.model_dump())
    except 继.继承戳错误 as e:
        raise _失败闭(e) from e
    except sqlite3.OperationalError as e:
        if 切流.是否锁冲突(e):
            raise _失败闭(e) from e
        raise


@路由.post("/装载/夹具")
def 装夹具(名: str = "准时热度样例"):
    路径 = 夹具目录 / f"{名}.json"
    if not 路径.exists():
        raise HTTPException(404, f"夹具不存在:{名}")
    return 装载.装一批(json.loads(路径.read_text(encoding="utf-8")))


@路由.post("/贯验")
def 做贯验():
    return 贯验.跑贯验()


@路由.get("/贯验")
def 列贯验():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 窗贯验 ORDER BY 编号 DESC LIMIT 20")]
    finally:
        conn.close()


@路由.get("/切流态")
def 取切流(房间键: str):
    try:
        return 切流.取切流态(房间键)
    except 切流.切流错误 as e:
        raise HTTPException(404, str(e)) from e


@路由.get("/切流审计")
def 取切流审计(房间键: str = ""):
    return 切流.列审计(房间键)


@路由.post("/开播")
def 做开播(体: 开播请求):
    try:
        return 切流.开播(体.房间键, 体.开播事件时 or None)
    except 切流.切流错误 as e:
        raise _失败闭(e) from e
    except 继.继承戳错误 as e:
        raise _失败闭(e) from e
    except sqlite3.OperationalError as e:
        if 切流.是否锁冲突(e):
            raise _失败闭(e) from e
        raise


@路由.post("/闭播")
def 做闭播(体: 闭播请求):
    try:
        return 切流.闭播(体.房间键)
    except 切流.切流错误 as e:
        raise _失败闭(e) from e
    except 继.继承戳错误 as e:
        raise _失败闭(e) from e
    except sqlite3.OperationalError as e:
        if 切流.是否锁冲突(e):
            raise _失败闭(e) from e
        raise


@路由.get("/空桩")
def 空桩():
    from app import modules

    return modules.列表()


@路由.get("/核证/水位继承")
def 取水位继承(房间键: str | None = None):
    """水位继承核证只读接口：戳链 + 三硬约束核证 + 四闸协同快照。"""
    conn = 连接()
    try:
        return 继.查继承戳(conn, 房间键)
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

