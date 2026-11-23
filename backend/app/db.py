import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

数据目录 = Path(os.environ.get("数据目录", Path(__file__).resolve().parent.parent / "data"))
夹具目录 = Path(os.environ.get("夹具目录", Path(__file__).resolve().parent.parent.parent / "fixtures"))
库路径 = 数据目录 / "播浪.db"



锁等待毫秒 = int(os.environ.get("livewave_busy_ms", "1500"))


def 连接() -> sqlite3.Connection:
    数据目录.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(库路径, timeout=锁等待毫秒 / 1000)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


@contextmanager
def 写事务():
    """切流与入流共用的串行化临界区：

    BEGIN IMMEDIATE 进入即抢保留锁，同库任一时刻只允许一个写事务。
    抢锁失败（SQLITE_BUSY）直接抛出，由路由层转 409——并发切流/入流失败闭，
    杜绝「切流半截双水位」。临界区内重新读状态做闸口判定，不依赖调用前快照。
    """
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
