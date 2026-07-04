import type {
  AppConfig,
  DashboardStatus,
  FriendDiscovery,
  PackCatalog,
  PackImportResult,
  PackPreview
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
  logs: () => request<{ application: string; scheduler: string }>("/api/logs"),
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
  discoveredFriends: () =>
    request<FriendDiscovery>("/api/friends/discovered"),
  importBackup: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<{ targets: string[]; messages: number }>("/api/backup/import", {
      method: "POST",
      body: data
    });
  }
};
