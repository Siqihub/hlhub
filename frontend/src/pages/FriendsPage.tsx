import { Plus, Radar, Save, Trash2, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppConfig, FriendDiscovery } from "../types";

export function FriendsPage({ notify }: { notify: (message: string) => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [discovery, setDiscovery] = useState<FriendDiscovery | null>(null);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [scanning, setScanning] = useState(false);
  useEffect(() => { void api.config().then(setConfig); }, []);
  if (!config) return <div className="loading">加载好友配置…</div>;

  const save = async () => {
    const names = config.targets.map((name) => name.trim()).filter(Boolean);
    if (new Set(names).size !== names.length) return notify("好友名称不能重复");
    const saved = await api.saveConfig({ ...config, targets: names });
    setConfig(saved);
    notify("好友配置已保存");
  };

  const scan = async () => {
    setScanning(true);
    try {
      const job = await api.scanFriends();
      const finished = await api.waitForAction(job.id);
      if (finished.status === "failed") throw new Error("好友识别失败，请查看运行日志");
      const candidates = await api.discoveredFriends();
      setDiscovery(candidates);
      setSelected(new Set());
      notify(`识别到 ${candidates.candidates.length} 个候选好友`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "好友识别失败");
    } finally {
      setScanning(false);
    }
  };

  const addSelected = () => {
    const existing = new Set(config.targets);
    const additions = [...selected].filter((name) => !existing.has(name));
    setConfig({ ...config, targets: [...config.targets, ...additions] });
    setSelected(new Set());
    notify(`已加入 ${additions.length} 位候选，请保存修改`);
  };

  return (
    <section className="editor-page">
      <header className="page-header"><div><h1>好友管理</h1><p>名称必须与抖音聊天列表中的备注或昵称完全一致。</p></div><div className="header-actions"><button className="action-button" disabled={scanning} onClick={() => void scan()}><Radar size={17} />{scanning ? "识别中…" : "自动识别好友"}</button><button className="action-button primary" onClick={save}><Save size={17} />保存修改</button></div></header>
      <div className="panel form-panel">
        <div className="panel-heading"><h2>续火目标</h2><button className="text-button" onClick={() => setConfig({ ...config, targets: [...config.targets, ""] })}><Plus size={16} />添加好友</button></div>
        <div className="friend-editor-list">
          {config.targets.map((name, index) => (
            <div className="friend-editor-row" key={`${index}-${name}`}>
              <span className="row-number">{index + 1}</span>
              <input value={name} placeholder="输入好友备注或昵称" onChange={(event) => {
                const targets = [...config.targets]; targets[index] = event.target.value; setConfig({ ...config, targets });
              }} />
              <button className="icon-button danger" aria-label={`删除 ${name}`} onClick={() => setConfig({ ...config, targets: config.targets.filter((_, position) => position !== index) })}><Trash2 size={17} /></button>
            </div>
          ))}
        </div>
      </div>
      {discovery ? <section className="panel discovery-panel"><div className="panel-heading"><h2>识别到的候选好友</h2><button className="text-button" disabled={!selected.size} onClick={addSelected}><UserPlus size={16} />添加所选好友</button></div><div className="candidate-grid">{discovery.candidates.map((candidate) => <label className={candidate.already_configured ? "candidate configured" : "candidate"} key={candidate.name}><input type="checkbox" aria-label={candidate.name} disabled={candidate.already_configured} checked={selected.has(candidate.name)} onChange={(event) => { const next = new Set(selected); if (event.target.checked) next.add(candidate.name); else next.delete(candidate.name); setSelected(next); }} /><span>{candidate.name}</span><small>{candidate.already_configured ? "已配置" : "可添加"}</small></label>)}</div></section> : null}
    </section>
  );
}
