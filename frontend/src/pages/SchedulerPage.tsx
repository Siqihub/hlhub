import { CalendarClock, RefreshCw, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DashboardStatus, SchedulePreview, ScheduleSettings } from "../types";

const labels: Record<string, string> = {
  "AutoDy-Health-Daily": "每日登录检查",
  "AutoDy-DailySpark": "每日续火发送",
  "AutoDy-Health-Weekly": "每周登录检查"
};
const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const weekdayLabels: Record<string, string> = { Monday: "周一", Tuesday: "周二", Wednesday: "周三", Thursday: "周四", Friday: "周五", Saturday: "周六", Sunday: "周日" };

export function SchedulerPage({ status, notify, onRefresh }: { status: DashboardStatus; notify: (message: string) => void; onRefresh: () => void }) {
  const [settings, setSettings] = useState<ScheduleSettings | null>(null);
  const [preview, setPreview] = useState<SchedulePreview | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { void api.config().then((config) => setSettings({
    daily_health_check_time: config.daily_health_check_time,
    daily_send_time: config.daily_send_time,
    weekly_health_check_enabled: config.weekly_health_check_enabled,
    weekly_health_check_weekday: config.weekly_health_check_weekday,
    weekly_health_check_time: config.weekly_health_check_time,
    startup_recovery_enabled: config.startup_recovery_enabled,
    recovery_deadline: config.recovery_deadline
  })); }, []);
  if (!settings) return <div className="loading">加载定时任务设置…</div>;

  const set = <K extends keyof ScheduleSettings>(key: K, value: ScheduleSettings[K]) => { setSettings({ ...settings, [key]: value }); setPreview(null); };
  const showPreview = async () => {
    try { setPreview(await api.schedulerPreview(settings)); } catch (error) { notify(error instanceof Error ? error.message : "计划设置无效"); }
  };
  const apply = async () => {
    if (!preview) return notify("请先预览本次计划变更");
    setBusy(true);
    try { await api.schedulerApply(settings); notify("设置与 Windows 定时任务已同步"); setPreview(null); onRefresh(); }
    catch (error) { notify(error instanceof Error ? error.message : "定时任务更新失败，原设置未改变"); }
    finally { setBusy(false); }
  };
  const operation = async (name: "install" | "update" | "repair" | "remove") => {
    setBusy(true);
    try { await api.schedulerOperation(name); notify(name === "remove" ? "定时任务已移除" : "定时任务操作完成"); onRefresh(); }
    catch (error) { notify(error instanceof Error ? error.message : "定时任务操作失败"); }
    finally { setBusy(false); }
  };

  return <section className="editor-page">
    <header className="page-header"><div><h1>定时任务</h1><p>计划设置保存在本地；应用前会显示旧值、新值和受影响的 Windows 任务。</p></div><div className="header-actions"><button className="action-button" disabled={busy} onClick={() => void operation("install")}><CalendarClock size={17} />安装任务</button><button className="action-button" disabled={busy} onClick={() => void operation("repair")}><ShieldCheck size={17} />修复任务</button><button className="action-button" disabled={busy} onClick={() => void operation("remove")}><Trash2 size={17} />移除任务</button></div></header>
    <div className="panel settings-form">
      <label><span>每日登录健康检查<small>只检查登录和聊天页面，不发送消息</small></span><input aria-label="每日登录健康检查" type="time" value={settings.daily_health_check_time} onChange={(event) => set("daily_health_check_time", event.target.value)} /></label>
      <label><span>每日续火发送<small>计划时间到达后执行；全局锁会阻止并发</small></span><input aria-label="每日续火发送" type="time" value={settings.daily_send_time} onChange={(event) => set("daily_send_time", event.target.value)} /></label>
      <label><span>启用每周健康检查<small>用于尽早发现需要扫码登录</small></span><input className="toggle" aria-label="启用每周健康检查" type="checkbox" checked={settings.weekly_health_check_enabled} onChange={(event) => set("weekly_health_check_enabled", event.target.checked)} /></label>
      <label><span>每周检查时间<small>选择周几和执行时间</small></span><span className="inline-settings"><select value={settings.weekly_health_check_weekday} onChange={(event) => set("weekly_health_check_weekday", event.target.value)}>{weekdays.map((day) => <option value={day} key={day}>{weekdayLabels[day]}</option>)}</select><input type="time" value={settings.weekly_health_check_time} onChange={(event) => set("weekly_health_check_time", event.target.value)} /></span></label>
      <label><span>启动后补跑错过任务<small>仅在当天恢复截止时间前，并仍保留同日去重</small></span><input className="toggle" aria-label="启动后补跑错过任务" type="checkbox" checked={settings.startup_recovery_enabled} onChange={(event) => set("startup_recovery_enabled", event.target.checked)} /></label>
      <label><span>当日恢复截止时间<small>超过该时间不会自动补跑</small></span><input type="time" value={settings.recovery_deadline} onChange={(event) => set("recovery_deadline", event.target.value)} /></label>
    </div>
    <div className="header-actions schedule-apply-actions"><button className="action-button" disabled={busy} onClick={() => void showPreview()}><RefreshCw size={17} />预览变更</button><button className="action-button primary" disabled={busy || !preview} onClick={() => void apply()}><Save size={17} />应用到 Windows 任务</button></div>
    {preview ? <section className="panel import-result"><strong>计划预览</strong><span>发送：{preview.old.daily_send_time} → {preview.new.daily_send_time}</span><span>登录检查：{preview.old.daily_health_check_time} → {preview.new.daily_health_check_time}</span><small>受影响任务：{preview.affected_tasks.map((task) => `${labels[task.name]}（${task.action === "remove" ? "移除" : "更新"}）`).join("、")}</small></section> : null}
    <div className="panel scheduler-list">
      {status.scheduler.length ? status.scheduler.map((task) => <div className="scheduler-row" key={task.name}><span className="scheduler-icon"><RefreshCw size={20} /></span><div><strong>{labels[task.name] || task.name}</strong><small>{task.name} · 已安装 / 设置待核验</small></div><span className="tag success">{task.state}</span><div className="scheduler-time"><small>下次运行</small><strong>{task.next_run ? new Date(task.next_run).toLocaleString("zh-CN") : "—"}</strong></div><div className="scheduler-time"><small>上次运行 / 结果</small><strong>{task.last_run ? new Date(task.last_run).toLocaleString("zh-CN") : "—"} / {task.last_result === 0 ? "成功" : `错误 ${task.last_result}`}</strong></div></div>) : <div className="empty-state">未安装定时任务；可先点击“安装任务”。</div>}
    </div>
  </section>;
}
