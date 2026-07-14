import { Plus, Radar, RefreshCw, Save, Trash2, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppConfig, ConfiguredFriend, FriendDiscovery } from "../types";

function FriendAvatar({ name, url }: { name: string; url?: string }) {
  const initial = name.trim().slice(0, 1) || "?";
  if (!url) return <span className="friend-avatar avatar-fallback" aria-label={`${name} 的默认头像`}>{initial}</span>;
  return <img className="friend-avatar" src={url} alt={`${name} 的头像`} loading="lazy" />;
}

function todayLabel(status: ConfiguredFriend["today_status"] | undefined) {
  if (status === "success") return "今日已完成";
  if (status === "failed") return "今日失败";
  return "今日待执行";
}

function candidateLabel(status: FriendDiscovery["candidates"][number]["match_status"], enabled: boolean | null) {
  if (status === "ambiguous") return "可能重名，未自动关联";
  if (status === "configured") return enabled ? "已配置 · 已启用" : "已配置 · 已停用";
  return "未配置";
}

export function FriendsPage({ notify }: { notify: (message: string) => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [friends, setFriends] = useState<ConfiguredFriend[]>([]);
  const [discovery, setDiscovery] = useState<FriendDiscovery | null>(null);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [batchSelected, setBatchSelected] = useState<Set<string>>(() => new Set());
  const [busyAction, setBusyAction] = useState<"scan" | "avatar" | null>(null);

  const load = async () => {
    try {
      const [nextConfig, nextFriends, nextDiscovery] = await Promise.all([
        api.config(), api.friends(), api.discoveredFriends()
      ]);
      setConfig(nextConfig);
      setFriends(nextFriends.friends);
      setDiscovery(nextDiscovery.scanned_at ? nextDiscovery : null);
    } catch (error) {
      notify(error instanceof Error ? error.message : "好友配置加载失败");
    }
  };

  useEffect(() => { void load(); }, []);
  if (!config) return <div className="loading">加载好友配置…</div>;

  const friendByName = new Map(friends.map((friend) => [friend.display_name, friend]));

  const save = async () => {
    const names = config.targets.map((name) => name.trim()).filter(Boolean);
    if (new Set(names).size !== names.length) return notify("好友名称不能重复");
    try {
      const saved = await api.saveConfig({ ...config, targets: names });
      setConfig(saved);
      setFriends((await api.friends()).friends);
      notify("好友配置已保存");
    } catch (error) {
      notify(error instanceof Error ? error.message : "好友配置保存失败");
    }
  };

  const scan = async () => {
    setBusyAction("scan");
    try {
      const job = await api.scanFriends();
      const finished = await api.waitForAction(job.id);
      if (finished.status === "failed") throw new Error("好友识别失败，请查看运行日志");
      await load();
      setSelected(new Set());
      notify("好友识别完成，候选列表已更新");
    } catch (error) {
      notify(error instanceof Error ? error.message : "好友识别失败");
    } finally {
      setBusyAction(null);
    }
  };

  const refreshAvatars = async () => {
    setBusyAction("avatar");
    try {
      const job = await api.refreshFriendAvatars();
      const finished = await api.waitForAction(job.id);
      if (finished.status === "failed") throw new Error("头像更新失败，请查看运行日志");
      await load();
      notify("头像扫描完成，未修改好友名称或续火目标");
    } catch (error) {
      notify(error instanceof Error ? error.message : "头像更新失败");
    } finally {
      setBusyAction(null);
    }
  };

  const addSelected = async () => {
    if (!selected.size) return;
    try {
      const result = await api.addDiscoveredFriends([...selected]);
      await load();
      setSelected(new Set());
      notify(`已添加 ${result.added} 位候选${result.skipped ? `，跳过 ${result.skipped} 位` : ""}`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "添加候选好友失败");
    }
  };

  const batch = async (action: "enable" | "disable" | "delete") => {
    if (!batchSelected.size) return notify("请先勾选好友");
    if (action === "delete" && !window.confirm(`删除所选 ${batchSelected.size} 位好友？`)) return;
    try {
      const result = await api.friendBatch([...batchSelected], action);
      await load();
      setBatchSelected(new Set());
      notify(`已处理 ${result.affected} 位好友`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "批量操作失败");
    }
  };

  return (
    <section className="editor-page">
      <header className="page-header">
        <div><h1>好友管理</h1><p>扫描仅读取当前聊天列表并缓存本地缩略头像；不会上传头像，也不会自动修改昵称。</p></div>
        <div className="header-actions">
          <button className="action-button" disabled={busyAction !== null} onClick={() => void scan()}><Radar size={17} />{busyAction === "scan" ? "扫描中…" : "扫描好友"}</button>
          <button className="action-button" disabled={busyAction !== null} onClick={() => void refreshAvatars()}><RefreshCw size={17} />{busyAction === "avatar" ? "更新中…" : "扫描并更新头像"}</button>
          <button className="action-button primary" onClick={() => void save()}><Save size={17} />保存修改</button>
        </div>
      </header>

      <div className="panel form-panel">
        <div className="panel-heading"><h2>续火目标</h2><span className="inline-actions"><button className="text-button" onClick={() => void batch("enable")}>批量启用</button><button className="text-button" onClick={() => void batch("disable")}>批量停用</button><button className="text-button" onClick={() => void batch("delete")}>批量删除</button><button className="text-button" onClick={() => setConfig({ ...config, targets: [...config.targets, ""] })}><Plus size={16} />添加好友</button></span></div>
        <div className="friend-editor-list">
          {config.targets.map((name, index) => {
            const friend = friendByName.get(name);
            return <div className="friend-editor-row" key={`${index}-${name}`}>
              <input className="row-check" aria-label={`选择 ${name}`} type="checkbox" checked={batchSelected.has(name)} onChange={(event) => { const next = new Set(batchSelected); if (event.target.checked) next.add(name); else next.delete(name); setBatchSelected(next); }} />
              <FriendAvatar name={name} url={friend?.avatar_url} />
              <span className="row-number">{index + 1}</span>
              <div className="friend-editor-copy">
                <input value={name} placeholder="输入好友备注或昵称" onChange={(event) => { const targets = [...config.targets]; targets[index] = event.target.value; setConfig({ ...config, targets }); }} />
                <small>{friend ? `${friend.enabled ? "已启用" : "已停用"} · ${todayLabel(friend.today_status)}${friend.last_success_date ? ` · 最近成功 ${friend.last_success_date}` : ""}` : "未扫描头像 · 今日待执行"}</small>
              </div>
              <button className="icon-button danger" aria-label={`删除 ${name}`} onClick={() => setConfig({ ...config, targets: config.targets.filter((_, position) => position !== index) })}><Trash2 size={17} /></button>
            </div>;
          })}
        </div>
      </div>

      {discovery ? <section className="panel discovery-panel">
        <div className="panel-heading"><h2>识别到的候选好友</h2><button className="text-button" disabled={!selected.size} onClick={() => void addSelected()}><UserPlus size={16} />添加所选好友</button></div>
        <div className="candidate-grid">{discovery.candidates.map((candidate) => {
          const selectable = candidate.match_status === "unconfigured";
          return <label className={selectable ? "candidate" : "candidate configured"} key={candidate.candidate_id}>
            <input type="checkbox" aria-label={`选择 ${candidate.display_name}`} disabled={!selectable} checked={selected.has(candidate.candidate_id)} onChange={(event) => { const next = new Set(selected); if (event.target.checked) next.add(candidate.candidate_id); else next.delete(candidate.candidate_id); setSelected(next); }} />
            <FriendAvatar name={candidate.display_name} url={candidate.avatar_url} />
            <span>{candidate.display_name}</span><small>{candidateLabel(candidate.match_status, candidate.configured_enabled)}</small>
          </label>;
        })}</div>
      </section> : null}
    </section>
  );
}
