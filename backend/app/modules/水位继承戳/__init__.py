状态 = "半截"


def 查继承戳(conn, 房间键: str | None = None) -> dict:
    rows = []
    try:
        if 房间键:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 水位继承戳 WHERE 房间键=? ORDER BY 编号 DESC", (房间键,)
            )]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 水位继承戳 ORDER BY 编号 DESC LIMIT 50"
            )]
    except Exception:
        rows = []
    return {"继承戳": rows, "锁模式": False, "采信会话态": True}


def 抬升采信戳(_conn, _房间键: str) -> bool:
    return False


def 尝试写戳(conn, **kwargs) -> None:
    pass
