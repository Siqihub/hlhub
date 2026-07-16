import { AlertTriangle, ArchiveRestore, CalendarPlus2, Download, Play, ScanLine, ShieldCheck, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { ActionButton } from "../components/ActionButton";
import { StatusRail } from "../components/StatusRail";
import { api } from "../api";
import type { DashboardStatus, FailedTargetCenter, PreflightProgress, PreflightResult, ServiceIdentity, TodayPlan } from "../types";
import type { ViewName } from "../components/Sidebar";

const statusLabel = {
  success: "已发送",
  failed: "异常",
  pending: "待发送"
};

const triggerLabel = {
  scheduled: "定时",
  manual: "手动",
  startup_recovery: "错过恢复",
  retry: "补发"
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
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preflightRunning, setPreflightRunning] = useState(false);
  const [preflightProgress, setPreflightProgress] = useState<PreflightProgress | null>(null);
  const [showPreflightDetails, setShowPreflightDetails] = useState(false);
  const [plan, setPlan] = useState<TodayPlan | null>(null);
  const [failedTargets, setFailedTargets] = useState<FailedTargetCenter | null>(null);
  const [identity, setIdentity] = useState<ServiceIdentity | null>(null);
  const loadPreflight = async () => {
    const current = await api.preflightStatus();
    setPreflight(current.result); setPreflightRunning(current.running); setPreflightProgress(current.progress);
  };
  useEffect(() => { void loadPreflight(); }, []);
  const loadOperationalPanels = async () => {
    const [nextPlan, nextFailures, nextIdentity] = await Promise.all([api.todayPlan(), api.failedTargets(), api.serviceIdentity()]);
    setPlan(nextPlan); setFailedTargets(nextFailures); setIdentity(nextIdentity);
  };
  useEffect(() => { void loadOperationalPanels(); }, []);
  useEffect(() => {
    if (!preflightRunning) return;
    const timer = window.setInterval(() => { void loadPreflight(); }, 1200);
    return () => window.clearInterval(timer);
  }, [preflightRunning]);
  const startPreflight = async () => {
    await api.runPreflight();
    setPreflightRunning(true);
    setPreflightProgress({ running: true, completed_targets: 0, total_targets: 0, current_status: "checking_chat_page" });
  };
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
      <section className="stats-grid" aria-label="运行统计">
        <article className="panel stat-card"><small>今日成功</small><strong>{status.statistics.successful_today}</strong><span>失败 {status.statistics.failed_today}</span></article>
        <article className="panel stat-card"><small>连续成功</small><strong>{status.statistics.consecutive_successful_days} 天</strong><span>近 7 天 {status.statistics.success_rate_7d}%</span></article>
        <article className="panel stat-card"><small>近 30 天成功率</small><strong>{status.statistics.success_rate_30d}%</strong><span>7 天重试 {status.statistics.retries_7d} 次</span></article>
        <article className="panel stat-card"><small>本机资源</small><strong>{status.statistics.enabled_friend_count} 位好友</strong><span>{status.statistics.local_message_count} 条文案 · {status.statistics.active_message_pack_count} 个文案包</span></article>
      </section>
      <section className="panel preflight-panel">
        <div className="panel-heading"><div><h2>发送前自检</h2><small>只检查聊天页面条件；不会输入、准备或发送任何消息。</small></div><div className="inline-actions">{preflight ? <button className="text-button" onClick={() => setShowPreflightDetails(!showPreflightDetails)}>查看详情</button> : null}<button className="action-button primary" disabled={!!busy || preflightRunning} onClick={() => void startPreflight()}>{preflightRunning ? "正在检测…" : "测试全部续火目标"}</button>{preflightRunning ? <button className="action-button" onClick={() => void api.cancelPreflight()}>取消检测</button> : null}</div></div>
        <div className="preflight-summary">{preflightRunning ? <span>正在检测 {preflightProgress?.completed_targets ?? 0} / {preflightProgress?.total_targets || "…"}：正在检查聊天页面…</span> : preflight ? <><span>上次检测：{new Date(preflight.completed_at).toLocaleString("zh-CN")}</span><span>检测目标：{preflight.total_targets}</span><span>具备条件：{preflight.ready_count}</span><span>异常：{preflight.failed_count + preflight.blocked_count}</span><span>状态：{preflight.global_status}</span></> : <span>尚未检测</span>}</div>
        {showPreflightDetails && preflight ? <div className="preflight-details">{preflight.targets.map((target) => <article key={target.target_id}><strong>{target.display_name}</strong><span className={target.target_status === "ready" ? "tag success" : "tag warning"}>{target.user_message}</span><small>{target.checked_at.replace("T", " ")}</small></article>)}</div> : null}
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>今日发送计划</h2><small>仅预览当前配置和状态；不会打开浏览器、消耗文案或创建任务记录。</small></div><div className="inline-actions"><button className="text-button" onClick={() => void loadOperationalPanels()}>刷新今日计划</button><button className="text-button" onClick={() => void startPreflight()}>执行发送前自检</button><button className="text-button" onClick={() => onNavigate("logs")}>查看异常目标</button></div></div>
        {plan ? <><div className="preflight-summary"><span>主任务：{plan.main_scheduled_time}</span><span>启用：{plan.enabled_target_count}</span><span>完成：{plan.completed_count}</span><span>待执行：{plan.pending_count}</span><span>阻止：{plan.blocked_count}</span></div><div className="preflight-details">{plan.targets.map((target) => <article key={target.target_id}><strong>{target.display_name}</strong><span>{new Date(target.planned_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })} · {target.message_source} · {target.suffix}</span><small>{target.status === "blocked" ? target.blocked_reason : target.status === "success" ? "今日已完成" : target.status === "failed" ? "等待处理" : "待执行"}</small></article>)}</div></> : <div className="empty-state compact">正在生成今日计划…</div>}
      </section>
      <section className="panel issues-panel">
        <div className="panel-heading"><div><h2>今日异常目标</h2><small>{failedTargets ? `成功：${failedTargets.summary.success} · 异常：${failedTargets.summary.failed} · 结果不确定：${failedTargets.summary.uncertain} · 需要处理：${failedTargets.summary.needs_attention}` : "正在读取结构化任务状态…"}</small></div><button className="text-button" onClick={() => void loadOperationalPanels()}>刷新</button></div>
        {failedTargets?.items.length ? <div className="issue-list">{failedTargets.items.map((target) => <article className="issue-item warning" key={target.target_id}><AlertTriangle size={19} /><div><strong>{target.display_name} · {target.explanation}</strong><small>{target.reason_code} · {target.uncertain ? "结果不确定，禁止重试" : target.no_send_action_definitely_occurred ? "确认未发送" : "请查看详细原因"}</small></div>{target.safe_retry_available ? <button className="action-button" onClick={() => void api.retryFailedTarget(target.target_id).then(loadOperationalPanels)}>安全重试明确未发送目标</button> : null}</article>)}</div> : <div className="empty-state compact">今日没有需要处理的异常目标。</div>}
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>运行环境</h2><small>仅显示本机运行身份，不包含账号凭据或浏览器资料。</small></div><div className="inline-actions"><button className="text-button" disabled={!!busy} onClick={() => onAction("login")}>重新登录抖音</button><button className="text-button" disabled={!!busy} onClick={() => onAction("refresh-account-profile")}>刷新账号资料</button><button className="text-button" disabled={!!busy} onClick={() => onAction("repair-playwright")}>修复 Chromium</button><button className="text-button" disabled={!!busy} onClick={() => onAction("install-scheduler")}>重建定时任务</button></div></div>
        {identity ? <div className="preflight-summary"><span>版本：{identity.version}</span><span>提交：{identity.git_commit || "未检测"}</span><span>Python：{identity.python_executable}</span><span>前端：{identity.frontend_build_version}</span><span>登录：{status.login.status}</span></div> : <div className="empty-state compact">正在检查本机运行环境…</div>}
      </section>
      <div className="dashboard-grid">
        <section className="panel history-panel">
          <div className="panel-heading"><h2>结构化运行记录</h2><span>{status.history.length} 条记录</span></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>结束时间</th><th>来源</th><th>成功/总数</th><th>重试</th><th>状态</th></tr></thead>
              <tbody>
                {status.history.slice(0, 7).map((row) => (
                  <tr key={row.run_id}>
                    <td>{new Date(row.end_time).toLocaleString("zh-CN")}</td>
                    <td>{triggerLabel[row.trigger_source]}</td>
                    <td>{row.success_count + row.skipped_count}/{row.total_targets}</td>
                    <td>{row.retry_count}</td>
                    <td><span className={row.final_status === "completed" || row.final_status === "already_done" ? "tag success" : "tag warning"}>{row.final_status === "completed" || row.final_status === "already_done" ? "成功" : "部分失败"}</span></td>
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
