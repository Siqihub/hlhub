import type {
  AppConfig,
  AccountProfile,
  BackupPreview,
  ConfiguredFriend,
  DashboardStatus,
  FriendDiscovery,
  LogPage,
  PackCatalog,
  PackImportResult,
  PackPreview,
  SchedulePreview,
  ScheduleSettings
} from "./types";

type ActionJob = {
  id: string;
  action: string;
  status: "running" | "success" | "failed";
  exit_code?: number | null;
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `请求失败 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<DashboardStatus>("/api/status"),
  accountProfile: () => request<AccountProfile>("/api/account-profile"),
  refreshAccountProfile: () => request<AccountProfile & { job?: ActionJob }>("/api/account-profile/refresh", { method: "POST" }),
  config: () => request<AppConfig>("/api/config"),
  saveConfig: (config: AppConfig) =>
    request<AppConfig>("/api/config", { method: "PUT", body: JSON.stringify(config) }),
  messages: () => request<{ messages: string[] }>("/api/messages"),
  saveMessages: (messages: string[]) =>
    request<{ messages: string[] }>("/api/messages", {
      method: "PUT",
      body: JSON.stringify({ messages })
    }),
  messagePacks: () => request<PackCatalog>("/api/message-packs"),
  previewMessagePack: (id: string) =>
    request<PackPreview>(`/api/message-packs/${encodeURIComponent(id)}`),
  importMessagePack: (id: string, mode: "merge" | "replace" | "preview_only") =>
    request<PackImportResult>(`/api/message-packs/${encodeURIComponent(id)}/import`, {
      method: "POST",
      body: JSON.stringify({ mode })
    }),
  logs: (filters?: { start_date?: string; end_date?: string; level?: string; task_type?: string; status?: string }) => {
    const query = new URLSearchParams();
    Object.entries(filters || {}).forEach(([key, value]) => { if (value) query.set(key, value); });
    return request<LogPage>(`/api/logs${query.size ? `?${query}` : ""}`);
  },
  archiveLogs: (before: string) =>
    request<{ archived_count: number; archive_dir: string }>(`/api/logs/archive?before=${encodeURIComponent(before)}`, { method: "POST" }),
  archiveHistoricalLogs: () => request<{ archived_count: number; archive_dir: string }>("/api/logs/archive-historical", { method: "POST" }),
  openLogFolder: () => request<{ opened: boolean }>("/api/logs/open-folder", { method: "POST" }),
  schedulerPreview: (settings: ScheduleSettings) => request<SchedulePreview>("/api/scheduler/preview", { method: "POST", body: JSON.stringify(settings) }),
  schedulerApply: (settings: ScheduleSettings) => request<{ config: AppConfig }>("/api/scheduler/apply", { method: "POST", body: JSON.stringify(settings) }),
  schedulerOperation: (operation: "install" | "update" | "repair" | "remove") => request<{ message: string }>(`/api/scheduler/${operation}`, { method: "POST" }),
  checkRecovery: () =>
    request<{ due: boolean; started: boolean; job?: ActionJob }>("/api/recovery/check", { method: "POST" }),
  action: (name: string) =>
    request<ActionJob>(`/api/actions/${name}`, {
      method: "POST"
    }),
  waitForAction: async (id: string) => {
    for (let attempt = 0; attempt < 1200; attempt += 1) {
      const job = await request<ActionJob>(`/api/actions/${id}`);
      if (job.status !== "running") return job;
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    throw new Error("操作等待超时，请查看运行日志");
  },
  scanFriends: () =>
    request<ActionJob>("/api/friends/scan", { method: "POST" }),
  refreshFriendAvatars: () =>
    request<ActionJob>("/api/friends/refresh-avatars", { method: "POST" }),
  discoveredFriends: () =>
    request<FriendDiscovery>("/api/friends/discovered"),
  friends: () => request<{ friends: ConfiguredFriend[] }>("/api/friends"),
  addCandidateToTargets: (candidateId: string) =>
    request<{ created: boolean; target: { target_id: string; display_name: string; enabled: boolean } }>(`/api/friends/${encodeURIComponent(candidateId)}/add-to-targets`, {
      method: "POST"
    }),
  addDiscoveredFriends: (candidateIds: string[]) =>
    request<{ added: number; skipped: number }>("/api/friends/discovered/batch", {
      method: "POST",
      body: JSON.stringify({ candidate_ids: candidateIds })
    }),
  importBackup: (file: File, mode: "merge" | "replace" = "merge") => {
    const data = new FormData();
    data.append("file", file);
    return request<{ targets: string[]; messages: number }>(`/api/backup/import?mode=${mode}`, {
      method: "POST",
      body: data
    });
  },
  previewBackup: (file: File) => {
    const data = new FormData(); data.append("file", file);
    return request<BackupPreview>("/api/backup/preview", { method: "POST", body: data });
  },
  exportBackup: async (categories: string[]) => {
    const response = await fetch("/api/backup/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ categories }) });
    if (!response.ok) throw new Error(await response.text());
    return response.blob();
  },
  friendBatch: (targetIds: string[], action: "enable" | "disable" | "delete") => request<{ affected: number }>("/api/friends/batch", { method: "PATCH", body: JSON.stringify({ target_ids: targetIds, action }) }),
  previewMessageImport: (file: File) => upload<{ total_entries: number; valid_entries: number; exact_duplicates: number; empty_entries: number; overly_long_entries: number; entries_with_links: number }>("/api/messages/import/preview", file),
  importMessages: (file: File, mode: "merge" | "replace") => upload<{ imported: number; duplicated: number; total: number }>(`/api/messages/import?mode=${mode}`, file),
  deduplicateMessages: () => request<{ removed: number }>("/api/messages/deduplicate", { method: "POST" })
};

function upload<T>(url: string, file: File): Promise<T> {
  const data = new FormData();
  data.append("file", file);
  return request<T>(url, { method: "POST", body: data });
}
