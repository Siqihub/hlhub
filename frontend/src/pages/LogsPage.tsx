import { Archive, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { LogPage } from "../types";

function localDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const taskLabels: Record<string, string> = {
  daily_send: "每日发送",
  health_check: "登录检查",
  login: "扫码登录",
  friend_scan: "好友识别",
  system: "系统"
};

export function LogsPage() {
  const today = new Date();
  const recent = new Date(today); recent.setDate(today.getDate() - 2);
  const [startDate, setStartDate] = useState(localDate(recent));
  const [endDate, setEndDate] = useState(localDate(today));
  const [level, setLevel] = useState("");
  const [taskType, setTaskType] = useState("");
  const [logs, setLogs] = useState<LogPage | null>(null);
  const [tab, setTab] = useState<"scheduler" | "application">("application");
  const load = async () => setLogs(await api.logs({ start_date: startDate, end_date: endDate, level, task_type: taskType }));
  useEffect(() => { void load(); }, []); // Initial load uses the most recent three days.

  const archive = async () => {
    if (!window.confirm(`归档 ${startDate} 之前的应用日志？日志只会移动，不会删除。`)) return;
    const result = await api.archiveLogs(startDate);
    window.alert(`已归档 ${result.archived_count} 个日志文件。`);
    await load();
  };

  return (
    <section className="editor-page">
      <header className="page-header">
        <div><h1>运行日志</h1><p>默认显示最近三天，好友名称按设置自动脱敏。</p></div>
        <div className="header-actions">
          <button className="action-button" onClick={() => void archive()}><Archive size={17} />归档旧日志</button>
          <button className="action-button" onClick={() => void load()}><RefreshCw size={17} />刷新</button>
        </div>
      </header>
      <div className="panel log-panel">
        <div className="tab-list"><button className={tab === "application" ? "active" : ""} onClick={() => setTab("application")}>应用日志</button><button className={tab === "scheduler" ? "active" : ""} onClick={() => setTab("scheduler")}>调度日志</button></div>
        {tab === "application" ? <>
          <div className="log-filters">
            <label>开始日期<input aria-label="日志开始日期" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <label>结束日期<input aria-label="日志结束日期" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
            <label>级别<select aria-label="日志级别" value={level} onChange={(event) => setLevel(event.target.value)}><option value="">全部</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select></label>
            <label>任务<select aria-label="日志任务" value={taskType} onChange={(event) => setTaskType(event.target.value)}><option value="">全部</option>{Object.entries(taskLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          </div>
          <div className="structured-logs">
            {logs?.items.length ? logs.items.map((entry, index) => <article className={`log-entry ${entry.level.toLowerCase()}`} key={`${entry.timestamp}-${index}`}>
              <div className="log-summary"><time>{entry.timestamp}</time><span className={`tag ${entry.level === "ERROR" ? "failed" : entry.level === "WARNING" ? "warning" : "success"}`}>{entry.level}</span><span>{taskLabels[entry.task_type] || "系统"}</span><strong>{entry.summary}</strong></div>
              {entry.detail ? <details><summary>查看详情</summary><pre>{entry.detail}</pre></details> : null}
            </article>) : <div className="empty-state compact">所选范围暂无日志</div>}
          </div>
        </> : <pre>{logs?.scheduler || "暂无调度日志"}</pre>}
      </div>
    </section>
  );
}
