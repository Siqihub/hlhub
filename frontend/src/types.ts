export type FriendStatus = "success" | "failed" | "pending";

export interface Friend {
  name: string;
  status: FriendStatus;
  error?: string | null;
}

export interface HistoryRow {
  date: string;
  message: string;
  succeeded: number;
  total: number;
  failed: number;
  complete: boolean;
}

export interface SchedulerTask {
  name: string;
  state: string;
  next_run: string;
  last_run: string;
  last_result: number;
}

export interface DashboardStatus {
  today: {
    date: string;
    message: string;
    succeeded: number;
    failed: number;
    total: number;
    complete: boolean;
  };
  friends: Friend[];
  history: HistoryRow[];
  scheduler: SchedulerTask[];
  next_run: string | null;
  login: { status: string };
  message_count: number;
  issues: DashboardIssue[];
}

export interface DashboardIssue {
  id: string;
  status: "error" | "warning" | "info";
  explanation: string;
  action: string;
  action_label: string;
}

export type MessageSuffixStyle = "dash" | "bracket" | "newline" | "none";

export interface AppConfig {
  targets: string[];
  retry_count: number;
  timeout_ms: number;
  headless: boolean;
  message_suffix: {
    enabled: boolean;
    text: string;
    style: MessageSuffixStyle;
  };
  message_pack_index_url: string | null;
}

export interface MessagePack {
  id: string;
  name: string;
  description: string;
  version: string;
  count: number;
  category: string;
}

export interface PackCatalog {
  packs: MessagePack[];
  source: "remote" | "local";
  warning?: string | null;
}

export interface PackPreview {
  pack: MessagePack;
  messages: string[];
  duplicate_count: number;
  source: "remote" | "local";
  warning?: string | null;
}

export interface PackImportResult {
  added_count: number;
  duplicate_count: number;
  total_count: number;
  backup_path?: string | null;
  mode: "merge" | "replace" | "preview_only";
  source?: "remote" | "local";
  warning?: string | null;
}

export interface FriendCandidate {
  name: string;
  already_configured: boolean;
}

export interface FriendDiscovery {
  scanned_at: string | null;
  candidates: FriendCandidate[];
}
