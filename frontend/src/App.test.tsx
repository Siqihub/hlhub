import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App";

const apiMocks = vi.hoisted(() => ({
  action: vi.fn(),
  waitForAction: vi.fn(),
  checkRecovery: vi.fn().mockResolvedValue({ due: false, started: false }),
  messagePacks: vi.fn().mockResolvedValue({
    packs: [{ id: "daily", name: "日常问候", description: "自然短问候", version: "1.0.0", count: 50, category: "daily" }],
    source: "local",
    warning: null
  })
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

vi.mock("./api", () => ({
  api: {
    status: vi.fn().mockResolvedValue({
      today: { date: "2026-06-24", message: "测试文案", succeeded: 9, failed: 0, total: 9, complete: true },
      friends: [{ name: "小明", status: "success" }],
      history: [{ run_id: "run-1", date: "2026-06-24", task_type: "daily_send", trigger_source: "scheduled", success_count: 9, failed_count: 0, skipped_count: 0, total_targets: 9, retry_count: 0, final_status: "completed", end_time: "2026-06-24T07:31:00" }],
      scheduler: [],
      next_run: "2026-06-25T07:30:00",
      login: { status: "normal" },
      message_count: 60,
      issues: [],
      statistics: { last_completed_run: "2026-06-24T07:31:00", consecutive_successful_days: 7, success_rate_7d: 100, success_rate_30d: 98, retries_7d: 1, successful_today: 9, failed_today: 0, configured_friend_count: 9, enabled_friend_count: 9, local_message_count: 60, active_message_pack_count: 5, next_health_check: null, next_daily_send: "2026-06-25T07:30:00", most_recent_issue: null }
    }),
    action: apiMocks.action,
    waitForAction: apiMocks.waitForAction,
    checkRecovery: apiMocks.checkRecovery,
    messagePacks: apiMocks.messagePacks
  }
}));

test("renders the primary dashboard status", async () => {
  render(<App />);
  expect(await screen.findByText("运行总览")).toBeInTheDocument();
  expect(screen.getByText("已完成")).toBeInTheDocument();
  expect(screen.getAllByText("9/9")).toHaveLength(2);
  expect(screen.getByText("检查登录")).toBeInTheDocument();
});

test("keeps browser action buttons disabled until the action finishes", async () => {
  let finish: (value: { status: string }) => void = () => undefined;
  apiMocks.action.mockResolvedValue({ id: "job-1", action: "run", status: "running" });
  apiMocks.waitForAction.mockImplementation(
    () => new Promise((resolve) => { finish = resolve; })
  );
  render(<App />);
  const runButton = await screen.findByRole("button", { name: "立即运行" });
  fireEvent.click(runButton);

  await waitFor(() => expect(apiMocks.action).toHaveBeenCalledWith("run"));
  expect(runButton).toBeDisabled();
  expect(screen.getByRole("button", { name: "检查登录" })).toBeDisabled();

  finish({ status: "success" });
  await waitFor(() => expect(runButton).not.toBeDisabled());
});

test("opens the online message library from navigation", async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "在线文案库" }));

  expect(await screen.findByRole("heading", { name: "在线文案库" })).toBeInTheDocument();
  expect(screen.getByText("日常问候")).toBeInTheDocument();
});
