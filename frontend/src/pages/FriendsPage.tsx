import { Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppConfig } from "../types";

export function FriendsPage({ notify }: { notify: (message: string) => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  useEffect(() => { void api.config().then(setConfig); }, []);
  if (!config) return <div className="loading">加载好友配置…</div>;

  const save = async () => {
    const names = config.targets.map((name) => name.trim()).filter(Boolean);
    if (new Set(names).size !== names.length) return notify("好友名称不能重复");
    const saved = await api.saveConfig({ ...config, targets: names });
    setConfig(saved);
    notify("好友配置已保存");
  };

  return (
    <section className="editor-page">
      <header className="page-header"><div><h1>好友管理</h1><p>名称必须与抖音聊天列表中的备注或昵称完全一致。</p></div><button className="action-button primary" onClick={save}><Save size={17} />保存修改</button></header>
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
    </section>
  );
}
