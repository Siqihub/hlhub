import { AlertTriangle, ArchiveRestore, CalendarPlus2, Download, Play, ScanLine, ShieldCheck, Wrench } from "lucide-react";
import { ActionButton } from "../components/ActionButton";
import { StatusRail } from "../components/StatusRail";
import type { DashboardStatus } from "../types";
import type { ViewName } from "../components/Sidebar";

const statusLabel = {
  success: "已发送",
  failed: "异常",
  pending: "待发送"
};

export function DashboardPage({
  status,
  busy,
  onAction,
  onNavigate
}: {
  status: DashboardStatus;
  busy: string | null;
  onAction: (action: string) => void;
  onNavigate: (view: ViewName) => void;
}) {
  const handleIssue = (action: string) => {
    if (["friends", "messages", "packs", "scheduler", "logs", "backup", "settings"].includes(action)) {
      onNavigate(action as ViewName);
    } else {
      onAction(action);
    }
  };
  return (
    <>
      <header className="page-header">
        <div><h1>运行总览</h1><p>查看今日续火状态和本机自动化健康情况。</p></div>
        <div className="header-actions">
          <ActionButton disabled={!!busy} icon={<ShieldCheck size={17} />} onClick={() => onAction("health-check")}>检查登录</ActionButton>
          <ActionButton disabled={!!busy} primary icon={<Play size={17} fill="currentColor" />} onClick={() => onAction("run")}>立即运行</ActionButton>
          <ActionButton disabled={!!busy} icon={<ScanLine size={17} />} onClick={() => onAction("login")}>扫码登录</ActionButton>
          <ActionButton disabled={!!busy} icon={<Wrench size={17} />} onClick={() => onAction("repair-playwright")}>修复运行时</ActionButton>
        </div>
      </header>
      <StatusRail status={status} />
      <div className="dashboard-grid">
        <section className="panel history-panel">
          <div className="panel-heading"><h2>最近运行</h2><span>{status.history.length} 条记录</span></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>日期</th><th>文案预览</th><th>成功/发送</th><th>状态</th></tr></thead>
              <tbody>
                {status.history.slice(0, 7).map((row) => (
                  <tr key={row.date}>
                    <td>{row.date}</td>
                    <td className="message-preview">{row.message || "尚未运行"}</td>
                    <td>{row.succeeded}/{row.total}</td>
                    <td><span className={row.complete ? "tag success" : "tag warning"}>{row.complete ? "成功" : "部分成功"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <aside className="panel quick-panel">
          <div className="panel-heading"><h2>快捷操作</h2></div>
          <button onClick={() => { window.location.href = "/api/backup"; }}><Download className="blue-text" /><span><strong>导出配置</strong><small>生成可迁移的安全备份</small></span></button>
          <button onClick={() => onNavigate("backup")}><ArchiveRestore className="green-text" /><span><strong>导入备份</strong><small>从备份恢复好友和文案</small></span></button>
          <button onClick={() => onNavigate("scheduler")}><CalendarPlus2 className="purple-text" /><span><strong>安装定时任务</strong><small>管理 07:20 与 07:30 任务</small></span></button>
        </aside>
      </div>
      <section className="panel issues-panel">
        <div className="panel-heading"><h2>需要处理</h2><span>{status.issues.length ? `${status.issues.length} 项` : "当前无异常"}</span></div>
        {status.issues.length ? <div className="issue-list">{status.issues.map((issue) => <article className={`issue-item ${issue.status}`} key={issue.id}><AlertTriangle size={19} /><div><strong>{issue.explanation}</strong><small>{issue.id}</small></div><button className="action-button" disabled={!!busy} onClick={() => handleIssue(issue.action)}>{issue.action_label}</button></article>)}</div> : <div className="empty-state compact">运行状态正常，暂无需要处理的事项。</div>}
      </section>
      <section className="panel friends-panel">
        <div className="panel-heading"><h2>好友状态</h2><span>共 {status.friends.length} 位</span></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>好友名称</th><th>状态</th><th>今日发送</th><th>异常信息</th></tr></thead>
            <tbody>
              {status.friends.map((friend) => (
                <tr key={friend.name}>
                  <td><span className="avatar">{friend.name.slice(0, 1)}</span>{friend.name}</td>
                  <td><span className={`tag ${friend.status}`}>{statusLabel[friend.status]}</span></td>
                  <td>{friend.status === "success" ? "已发送" : "未完成"}</td>
                  <td className="muted">{friend.error || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
