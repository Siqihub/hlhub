import { CloudDownload, Plus, Save, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

export function MessagesPage({
  notify,
  onNavigate
}: {
  notify: (message: string) => void;
  onNavigate: (view: "packs") => void;
}) {
  const [messages, setMessages] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  useEffect(() => { void api.messages().then((data) => setMessages(data.messages)); }, []);
  const visible = useMemo(
    () => messages.map((text, index) => ({ text, index })).filter(({ text }) => text.includes(query)),
    [messages, query]
  );
  const save = async () => {
    const result = await api.saveMessages(messages);
    setMessages(result.messages);
    notify(`文案库已保存，共 ${result.messages.length} 条`);
  };
  return (
    <section className="editor-page">
      <header className="page-header"><div><h1>文案库</h1><p>每个运行日随机选取一条，本轮全部使用前不会重复。</p></div><div className="header-actions"><button className="action-button" onClick={() => onNavigate("packs")}><CloudDownload size={17} />从在线文案库导入</button><button className="action-button primary" onClick={save}><Save size={17} />保存文案库</button></div></header>
      <div className="toolbar panel">
        <label className="search-box"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索文案…" /></label>
        <span>{messages.length} 条文案</span>
        <button className="text-button" onClick={() => setMessages(["", ...messages])}><Plus size={16} />新增文案</button>
      </div>
      <div className="message-list">
        {visible.map(({ text, index }) => (
          <article className="message-row" key={index}>
            <span className="message-index">{String(index + 1).padStart(2, "0")}</span>
            <textarea value={text} rows={2} onChange={(event) => {
              const next = [...messages]; next[index] = event.target.value; setMessages(next);
            }} />
            <button className="icon-button danger" aria-label="删除文案" onClick={() => setMessages(messages.filter((_, position) => position !== index))}><Trash2 size={17} /></button>
          </article>
        ))}
      </div>
    </section>
  );
}
