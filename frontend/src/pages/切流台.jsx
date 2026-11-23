import React, { useEffect, useState } from "react";
import { 取, 递 } from "../api.js";

export default function 切流台() {
  const [房列, 设房列] = useState([]);
  const [选房, 设选房] = useState("");
  const [态, 设态] = useState(null);
  const [审计, 设审计] = useState([]);
  const [开播时, 设开播时] = useState("");
  const [讯, 设讯] = useState(null);

  const 刷房 = () => 取("/直播间").then((rs) => {
    设房列(rs);
    if (!选房 && rs.length) 设选房(rs[0].房间键);
  });
  const 刷态 = () => 选房 && 取(`/切流态?房间键=${encodeURIComponent(选房)}`).then(设态).catch((e) => { 设态(null); 设讯(String(e)); });
  const 刷审计 = () => 取(`/切流审计${选房 ? `?房间键=${encodeURIComponent(选房)}` : ""}`).then(设审计);

  useEffect(() => { 刷房(); }, []);
  useEffect(() => { if (选房) { 刷态(); 刷审计(); } }, [选房]);

  const 做 = async (动作) => {
    设讯(null);
    try {
      const 体 = 动作 === "开播" ? { 房间键: 选房, 开播事件时: 开播时 } : { 房间键: 选房 };
      const r = await 递(`/${动作}`, 体);
      设讯({ 通: true, 文: `${动作}已提交：代次 ${r.切流代次}，水位 ${r.切流前水位} → ${r.切流后水位}` });
      设开播时("");
      await 刷房(); 刷态(); 刷审计();
    } catch (e) {
      设讯({ 通: false, 文: `${动作}失败闭（409）：${e.message}` });
    }
  };

  return (
    <div>
      <h1 className="题">⑥ 切流台 · 开播闭播</h1>
      <p className="述">
        全局唯一口径——<strong>重置水位</strong>：开播事务把水位重置为开播事件时，新切流代次的窗键（<code>房|e代次|窗起</code>）
        与历史窗分命名空间，已关历史窗不可被重开扫描；闭播只打状态、关尽开启窗、关闸，正式入窗一律失败闭拒收。
        切流与入流经 <code>BEGIN IMMEDIATE</code> 串行化，抢锁冲突返回 409，禁止双水位。
      </p>

      <div className="行">
        <select className="码" value={选房} onChange={(e) => 设选房(e.target.value)} style={输入样式}>
          {房列.map((r) => <option key={r.房间键} value={r.房间键}>{r.房间键}（{r.状态}）</option>)}
        </select>
        <button className="次" onClick={() => { 刷态(); 刷审计(); }}>刷新切流态</button>
      </div>

      {讯 && (
        <div className="提示条" style={{ borderColor: 讯.通 ? "var(--通)" : "var(--败)" }}>{讯.文}</div>
      )}

      {态 && (
        <div className="段">
          <div className="段题">
            切流只读接口
            <span className={`徽章 ${态.valid ? "通" : "败"}`} style={{ marginLeft: "0.6rem" }}>
              {态.valid ? "valid" : "撕裂"}
            </span>
          </div>
          <table>
            <tbody>
              <行 k="房间 / 标题" v={`${态.房间键} · ${态.标题}`} />
              <行 k="切流态（直播间状态）" v={态.切流态} />
              <行 k="入流闸" v={态.入流闸开放 ? "开放（接受正式入窗）" : "关闭（正式入窗失败闭）"} />
              <行 k="切流代次 epoch" v={态.切流代次} />
              <行 k="当前事件时水位" v={态.当前水位} 码 />
              <行 k="本代次开播事件时" v={态.开播事件时} 码 />
              <行 k="开播前水位" v={态.开播前水位 || "—（本房尚未发生过重开）"} 码 />
              <行 k="开播后水位" v={态.开播后水位 || "—"} 码 />
              <行 k="允许迟到秒" v={态.允许迟到秒} />
              <行 k="闭播后拒收数" v={态.拒收数} />
              <行 k="开启窗（须全属当前代次）" v={态.开启窗.length ? 态.开启窗.map((w) => w.窗键).join("，") : "无"} 码 />
              {态.问题.length > 0 && <行 k="一致性问题" v={态.问题.join("；")} />}
            </tbody>
          </table>

          <div className="行" style={{ marginTop: "0.8rem" }}>
            <input
              className="码" style={输入样式} placeholder="开播事件时，如 2026-11-22T20:00:00Z"
              value={开播时} onChange={(e) => 设开播时(e.target.value)}
              disabled={态.切流态 !== "已闭播"}
            />
            <button className="水" disabled={态.切流态 !== "已闭播"} onClick={() => 做("开播")}>
              开播（重置水位·代次+1）
            </button>
            <button className="次" disabled={态.切流态 !== "直播中"} onClick={() => 做("闭播")}>
              闭播（关闸·关尽窗·代次+1）
            </button>
          </div>
          <p className="讯" style={{ marginTop: "0.4rem" }}>
            仅「已闭播」可开播、仅「直播中」可闭播；非法跃迁返回 409。开播事件时留空则取处理时刻。
          </p>
        </div>
      )}

      <div className="段">
        <div className="段题">切流审计时间线（前后水位可查）</div>
        {!审计.length ? (
          <div className="空态">暂无切流记录。</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>房间</th><th>切流态</th><th>代次</th><th>开播事件时</th>
                <th>切流前水位</th><th>切流后水位</th><th>处理时</th><th>说明</th>
              </tr>
            </thead>
            <tbody>
              {审计.map((r) => (
                <tr key={r.编号}>
                  <td>{r.房间键}</td><td>{r.切流态}</td><td>{r.切流代次}</td>
                  <td className="码">{r.开播事件时}</td>
                  <td className="码">{r.切流前水位}</td><td className="码">{r.切流后水位}</td>
                  <td className="码">{r.处理时}</td><td className="讯">{r.说明}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const 输入样式 = {
  background: "var(--块)", color: "var(--字)", border: "1px solid var(--线)",
  borderRadius: 4, padding: "0.45rem 0.6rem", minWidth: 280,
};

function 行({ k, v, 码 }) {
  return (
    <tr>
      <td style={{ width: 240, color: "var(--淡)" }}>{k}</td>
      <td className={码 ? "码" : ""}>{v}</td>
    </tr>
  );
}
