import { Download, FileArchive, Upload } from "lucide-react";
import { useRef } from "react";
import { api } from "../api";

export function BackupPage({ notify }: { notify: (message: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const importFile = async (file?: File) => {
    if (!file) return;
    const result = await api.importBackup(file);
    notify(`备份已恢复：${result.targets.length} 位好友，${result.messages} 条文案`);
  };
  return (
    <section className="editor-page">
      <header className="page-header"><div><h1>备份迁移</h1><p>在不同电脑之间复制好友、文案与状态，不包含抖音登录资料。</p></div></header>
      <div className="backup-grid">
        <article className="panel backup-card"><FileArchive size={32} /><h2>导出安全备份</h2><p>生成一个 ZIP 文件，包含配置、文案和运行状态。浏览器 Cookie 与登录目录不会导出。</p><a className="action-button primary" href="/api/backup"><Download size={17} />下载备份</a></article>
        <article className="panel backup-card"><Upload size={32} /><h2>恢复备份</h2><p>导入由 AutoDy 生成的备份文件。恢复前会验证结构，当前登录状态保持不变。</p><input ref={input} type="file" accept=".zip" hidden onChange={(event) => void importFile(event.target.files?.[0])} /><button className="action-button" onClick={() => input.current?.click()}><Upload size={17} />选择备份文件</button></article>
      </div>
    </section>
  );
}
