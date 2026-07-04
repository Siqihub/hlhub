import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppConfig } from "../types";

export function SettingsPage({ notify }: { notify: (message: string) => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  useEffect(() => { void api.config().then(setConfig); }, []);
  if (!config) return <div className="loading">加载设置…</div>;
  const save = async () => {
    setConfig(await api.saveConfig(config));
    notify("运行设置已保存");
  };
  return (
    <section className="editor-page">
      <header className="page-header"><div><h1>设置</h1><p>控制重试、超时和浏览器运行方式。</p></div><button className="action-button primary" onClick={save}><Save size={17} />保存设置</button></header>
      <div className="panel settings-form">
        <label><span>失败重试次数<small>单个好友失败后的最大尝试次数</small></span><input type="number" min={1} max={5} value={config.retry_count} onChange={(event) => setConfig({ ...config, retry_count: Number(event.target.value) })} /></label>
        <label><span>页面超时（毫秒）<small>网络较慢时可以适当增加</small></span><input type="number" min={5000} max={120000} step={5000} value={config.timeout_ms} onChange={(event) => setConfig({ ...config, timeout_ms: Number(event.target.value) })} /></label>
        <label><span>后台无窗口运行<small>关闭后可以看到自动化浏览器</small></span><input className="toggle" type="checkbox" checked={config.headless} onChange={(event) => setConfig({ ...config, headless: event.target.checked })} /></label>
      </div>
    </section>
  );
}
