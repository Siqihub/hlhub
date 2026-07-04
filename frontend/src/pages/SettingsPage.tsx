import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppConfig } from "../types";

function suffixPreview(config: AppConfig) {
  const text = config.message_suffix.text.trim();
  if (!config.message_suffix.enabled || !text) return "你好";
  if (config.message_suffix.style === "dash") return `你好 —— ${text}`;
  if (config.message_suffix.style === "bracket") return `你好【${text}】`;
  if (config.message_suffix.style === "newline") return `你好\n${text}`;
  return `你好 ${text}`;
}

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
        <label><span>启用消息后缀<small>发送时动态添加，不修改文案库原文</small></span><input className="toggle" type="checkbox" checked={config.message_suffix.enabled} onChange={(event) => setConfig({ ...config, message_suffix: { ...config.message_suffix, enabled: event.target.checked } })} /></label>
        <label><span>后缀文字<small>默认：gpt小助手</small></span><input aria-label="后缀文字" value={config.message_suffix.text} onChange={(event) => setConfig({ ...config, message_suffix: { ...config.message_suffix, text: event.target.value } })} /></label>
        <label><span>后缀样式<small>选择与正文的分隔方式</small></span><select aria-label="后缀样式" value={config.message_suffix.style} onChange={(event) => setConfig({ ...config, message_suffix: { ...config.message_suffix, style: event.target.value as AppConfig["message_suffix"]["style"] } })}><option value="dash">破折号</option><option value="bracket">方括号</option><option value="newline">换行</option><option value="none">空格</option></select></label>
        <label className="preview-setting"><span>发送预览<small>状态文件仍只记录“你好”基础文案</small></span><code>{suffixPreview(config)}</code></label>
        <label><span>GitHub 文案索引 URL<small>留空时使用内置文案包</small></span><input aria-label="GitHub 文案索引 URL" placeholder="https://raw.githubusercontent.com/.../index.json" value={config.message_pack_index_url || ""} onChange={(event) => setConfig({ ...config, message_pack_index_url: event.target.value || null })} /></label>
      </div>
    </section>
  );
}
