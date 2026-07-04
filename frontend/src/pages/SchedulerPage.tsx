import { CalendarClock, RefreshCw, Trash2 } from "lucide-react";
import type { DashboardStatus } from "../types";

const labels: Record<string, string> = {
  "AutoDy-Health-Daily": "每日登录检查",
  "AutoDy-DailySpark": "每日续火发送",
  "AutoDy-Health-Weekly": "每周登录检查"
};

export function SchedulerPage({
  status,
  onAction,
  busy
}: {
  status: DashboardStatus;
  onAction: (action: string) => void;
  busy: string | null;
}) {
  return (
    <section className="editor-page">
      <header className="page-header"><div><h1>定时任务</h1><p>Windows 本地任务计划，错过时间后会尽快补跑。</p></div><div className="header-actions"><button className="action-button primary" disabled={!!busy} onClick={() => onAction("install-scheduler")}><CalendarClock size={17} />安装 / 更新</button><button className="action-button" disabled={!!busy} onClick={() => onAction("remove-scheduler")}><Trash2 size={17} />移除任务</button></div></header>
      <div className="panel scheduler-list">
        {status.scheduler.length ? status.scheduler.map((task) => (
          <div className="scheduler-row" key={task.name}>
            <span className="scheduler-icon"><RefreshCw size={20} /></span>
            <div><strong>{labels[task.name] || task.name}</strong><small>{task.name}</small></div>
            <span className="tag success">{task.state}</span>
            <div className="scheduler-time"><small>下次运行</small><strong>{task.next_run ? new Date(task.next_run).toLocaleString("zh-CN") : "—"}</strong></div>
            <div className="scheduler-time"><small>上次结果</small><strong>{task.last_result === 0 ? "成功" : `错误 ${task.last_result}`}</strong></div>
          </div>
        )) : <div className="empty-state">尚未安装定时任务</div>}
      </div>
    </section>
  );
}
