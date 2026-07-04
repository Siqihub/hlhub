import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";

export function LogsPage() {
  const [logs, setLogs] = useState({ application: "", scheduler: "" });
  const [tab, setTab] = useState<"scheduler" | "application">("scheduler");
  const load = () => void api.logs().then(setLogs);
  useEffect(load, []);
  return (
    <section className="editor-page">
      <header className="page-header"><div><h1>运行日志</h1><p>查看调度器和发送程序的最近输出。</p></div><button className="action-button" onClick={load}><RefreshCw size={17} />刷新</button></header>
      <div className="panel log-panel">
        <div className="tab-list"><button className={tab === "scheduler" ? "active" : ""} onClick={() => setTab("scheduler")}>调度日志</button><button className={tab === "application" ? "active" : ""} onClick={() => setTab("application")}>应用日志</button></div>
        <pre>{logs[tab] || "暂无日志"}</pre>
      </div>
    </section>
  );
}
