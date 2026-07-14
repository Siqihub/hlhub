export type FriendStatus = "success" | "failed" | "pending";

export interface Friend {
  name: string;
  status: FriendStatus;
  error?: string | null;
}

export interface HistoryRow {
  run_id: string;
  date: string;
  task_type: string;
  trigger_source: "scheduled" | "manual" | "startup_recovery" | "retry";
  success_count: number;
  failed_count: number;
  skipped_count: number;
  total_targets: number;
  retry_count: number;
  final_status: string;
  end_time: string;
}

export interface SchedulerTask {
  name: string;
  state: string;
  next_run: string;
  last_run: string;
  last_result: number;
}

export interface ScheduleSettings {
  daily_health_check_time: string;
  daily_send_time: string;
  weekly_health_check_enabled: boolean;
  weekly_health_check_weekday: string;
  weekly_health_check_time: string;
  startup_recovery_enabled: boolean;
  recovery_deadline: string;
}

export interface SchedulePreview {
  old: ScheduleSettings;
  new: ScheduleSettings;
  affected_tasks: { name: string; action: "update" | "remove" }[];
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
  statistics: {
    last_completed_run: string | null;
    consecutive_successful_days: number;
    success_rate_7d: number;
    success_rate_30d: number;
    retries_7d: number;
    successful_today: number;
    failed_today: number;
    configured_friend_count: number;
    enabled_friend_count: number;
    local_message_count: number;
    active_message_pack_count: number;
    next_health_check: string | null;
    next_daily_send: string | null;
    most_recent_issue: string | null;
    log_summary: {
      active_errors: number;
      warnings_24h: number;
      successful_tasks_7d: number;
      last_health_check: string | null;
      last_send: string | null;
      last_error_time: string | null;
    };
  };
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
  daily_send_time: string;
  daily_health_check_time: string;
  weekly_health_check_enabled: boolean;
  weekly_health_check_weekday: string;
  weekly_health_check_time: string;
  startup_recovery_enabled: boolean;
  recovery_deadline: string;
  min_delay_seconds: number;
  max_delay_seconds: number;
  page_load_timeout_ms: number;
  friend_search_timeout_ms: number;
  confirmation_timeout_ms: number;
  friend_order: "configured" | "randomized";
  message_selection: "one_for_all" | "per_friend";
  completion_notifications_enabled: boolean;
  log_retention_days: number;
  mask_log_friend_names: boolean;
}

export interface LogEntry {
  timestamp: string;
  date: string;
  level: "INFO" | "WARNING" | "ERROR";
  task_type: string;
  summary: string;
  detail: string;
  source: string;
  status: "active" | "resolved" | "historical";
  fingerprint: string;
  occurrences: number;
}

export interface LogPage {
  items: LogEntry[];
  total: number;
  page: number;
  page_size: number;
  start_date: string;
  end_date: string;
  scheduler: string;
}

export interface BackupPreview {
  package_version: number;
  autody_version: string | null;
  categories: string[];
  friend_count: number;
  message_count: number;
  schedule_changes: Record<string, { old: unknown; new: unknown }>;
  suffix_change: boolean;
  conflicts: string[];
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
  candidate_id: string;
  display_name: string;
  avatar_url: string;
  avatar_status: "cached" | "missing";
  discovered_at: string;
  match_status: "configured" | "unconfigured" | "ambiguous";
  configured_target_id: string | null;
  configured_enabled: boolean | null;
}

export interface FriendDiscovery {
  scanned_at: string | null;
  candidates: FriendCandidate[];
}

export interface ConfiguredFriend {
  id: string | null;
  display_name: string;
  enabled: boolean;
  note: string;
  avatar_url: string;
  avatar_status: "cached" | "missing";
  today_status: "success" | "failed" | "pending";
  last_success_date: string | null;
}
