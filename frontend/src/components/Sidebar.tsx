import {
  ArchiveRestore,
  CloudDownload,
  Clock3,
  FileText,
  Flame,
  LayoutDashboard,
  ScrollText,
  Settings,
  Users
} from "lucide-react";

export type ViewName =
  | "dashboard"
  | "friends"
  | "messages"
  | "packs"
  | "scheduler"
  | "logs"
  | "backup"
  | "settings";

const navigation = [
  ["dashboard", "总览", LayoutDashboard],
  ["friends", "好友管理", Users],
  ["messages", "文案库", FileText],
  ["packs", "在线文案库", CloudDownload],
  ["scheduler", "定时任务", Clock3],
  ["logs", "运行日志", ScrollText],
  ["backup", "备份迁移", ArchiveRestore],
  ["settings", "设置", Settings]
] as const;

export function Sidebar({
  active,
  onChange
}: {
  active: ViewName;
  onChange: (view: ViewName) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark"><Flame size={24} fill="currentColor" /></span>
        <span>AutoDy 续火助手</span>
      </div>
      <nav aria-label="主导航">
        {navigation.map(([value, label, Icon]) => (
          <button
            className={active === value ? "nav-item active" : "nav-item"}
            key={value}
            onClick={() => onChange(value)}
          >
            <Icon size={20} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="service-dot" />
        <span>本地服务运行中</span>
        <small>数据仅保存在此电脑</small>
      </div>
    </aside>
  );
}
