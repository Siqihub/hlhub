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
import type { AccountProfile } from "../types";

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
  onChange,
  account,
  onRefreshAccount
}: {
  active: ViewName;
  onChange: (view: ViewName) => void;
  account: AccountProfile | null;
  onRefreshAccount: () => void;
}) {
  const verified = account?.profile_status === "verified" && account.is_self;
  return (
    <aside className="sidebar">
      <div className="account-identity">
        {verified && account.avatar_url ? <img className="account-avatar" src={account.avatar_url} alt="当前账号头像" /> : <span className="brand-mark"><Flame size={24} fill="currentColor" /></span>}
        <div className="account-copy">
          <strong>{verified ? account.display_name : "未识别当前账号"}</strong>
          <small>{verified ? (account.logged_in ? "当前抖音账号" : "上次登录账号") : "AutoDy 续火助手"}</small>
          {verified ? <em>AutoDy 续火助手</em> : null}
        </div>
      </div>
      <button className="account-refresh" onClick={onRefreshAccount} disabled={Boolean(account?.refresh_running)}>刷新当前账号资料</button>
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
