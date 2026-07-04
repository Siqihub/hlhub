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
}

export interface AppConfig {
  targets: string[];
  retry_count: number;
  timeout_ms: number;
  headless: boolean;
}
