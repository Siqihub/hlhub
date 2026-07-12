import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Sidebar, type ViewName } from "./components/Sidebar";
import { BackupPage } from "./pages/BackupPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FriendsPage } from "./pages/FriendsPage";
import { LogsPage } from "./pages/LogsPage";
import { MessagesPage } from "./pages/MessagesPage";
import { MessagePacksPage } from "./pages/MessagePacksPage";
import { SchedulerPage } from "./pages/SchedulerPage";
import { SettingsPage } from "./pages/SettingsPage";
import type { DashboardStatus } from "./types";

export default function App() {
  const [view, setView] = useState<ViewName>("dashboard");
  const [status, setStatus] = useState<DashboardStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const load = useCallback(() => void api.status().then(setStatus), []);
  useEffect(() => {
    load();
    const refresh = () => { if (!document.hidden) load(); };
    const id = window.setInterval(refresh, 30000);
    document.addEventListener("visibilitychange", refresh);
    return () => { window.clearInterval(id); document.removeEventListener("visibilitychange", refresh); };
  }, [load]);
  useEffect(() => {
    void api.checkRecovery().then(async (result) => {
      if (result.started && result.job) {
        await api.waitForAction(result.job.id);
        load();
      }
    }).catch(() => undefined);
  }, [load]);
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 3200); };
  const action = async (name: string) => {
    setBusy(name);
    try {
      const job = await api.action(name);
      notify("操作已启动，可在运行日志中查看进度");
      const finished = await api.waitForAction(job.id);
      if (finished.status === "failed") {
        throw new Error(`操作失败（退出码 ${finished.exit_code ?? "未知"}）`);
      }
      notify("操作已完成");
      load();
    } catch (error) {
      notify(error instanceof Error ? error.message : "操作失败");
    } finally {
      setBusy(null);
    }
  };

  if (!status) return <div className="app-loading">正在连接 AutoDy 本地服务…</div>;
  return (
    <div className="app-shell">
      <Sidebar active={view} onChange={setView} />
      <main className="workspace">
        {view === "dashboard" && <DashboardPage status={status} busy={busy} onAction={action} onNavigate={setView} />}
        {view === "friends" && <FriendsPage notify={notify} />}
        {view === "messages" && <MessagesPage notify={notify} onNavigate={setView} />}
        {view === "packs" && <MessagePacksPage notify={notify} />}
        {view === "scheduler" && <SchedulerPage status={status} onAction={action} busy={busy} />}
        {view === "logs" && <LogsPage />}
        {view === "backup" && <BackupPage notify={notify} />}
        {view === "settings" && <SettingsPage notify={notify} />}
      </main>
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
