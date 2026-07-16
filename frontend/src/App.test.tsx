import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App";

const apiMocks = vi.hoisted(() => ({
  action: vi.fn(),
  waitForAction: vi.fn(),
  accountProfile: vi.fn().mockResolvedValue({
    display_name: "本人", avatar_url: "/api/account-profile/avatar?v=test", avatar_version: "test",
    is_self: true, profile_status: "verified", verification_source: "bootstrap_current_login_user",
    logged_in: true, cached: true, last_updated_at: "2026-07-15T08:00:00", refresh_running: false
  }),
  refreshAccountProfile: vi.fn(),
  checkRecovery: vi.fn().mockResolvedValue({ due: false, started: false }),
  messagePacks: vi.fn().mockResolvedValue({
    packs: [{ id: "daily", name: "日常问候", description: "自然短问候", version: "1.0.0", count: 50, category: "daily" }],
    source: "local",
    warning: null
  }),
  preflightLatest: vi.fn().mockResolvedValue({ result: { global_status: "ready", total_targets: 1, ready_count: 1, failed_count: 0, blocked_count: 0, completed_at: "2026-07-16T07:20:00", targets: [] } }),
  preflightStatus: vi.fn().mockResolvedValue({ running: false, result: { global_status: "ready", total_targets: 1, ready_count: 1, failed_count: 0, blocked_count: 0, completed_at: "2026-07-16T07:20:00", targets: [] } }),
  runPreflight: vi.fn(),
  cancelPreflight: vi.fn(),
  todayPlan: vi.fn().mockResolvedValue({ main_scheduled_time: "07:30", enabled_target_count: 0, completed_count: 0, pending_count: 0, blocked_count: 0, generated_at: "2026-07-16T07:00:00", estimated_finish: "2026-07-16T07:30", configuration_source: "current", targets: [] }),
  failedTargets: vi.fn().mockResolvedValue({ summary: { success: 0, failed: 0, uncertain: 0, needs_attention: 0 }, items: [] }),
  serviceIdentity: vi.fn().mockResolvedValue({ application: "AutoDy", version: "1.1.2", git_commit: "test", python_executable: "python.exe", package_path: "src/autody", project_path: "project", frontend_build_version: "1.1.2" })
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
    accountProfile: apiMocks.accountProfile,
    refreshAccountProfile: apiMocks.refreshAccountProfile,
    checkRecovery: apiMocks.checkRecovery,
    messagePacks: apiMocks.messagePacks,
    preflightLatest: apiMocks.preflightLatest,
    preflightStatus: apiMocks.preflightStatus,
    runPreflight: apiMocks.runPreflight,
    cancelPreflight: apiMocks.cancelPreflight,
    todayPlan: apiMocks.todayPlan,
    failedTargets: apiMocks.failedTargets,
    serviceIdentity: apiMocks.serviceIdentity
  }
}));

test("renders the primary dashboard status", async () => {
  render(<App />);
  expect(await screen.findByText("运行总览")).toBeInTheDocument();
  expect(screen.getByText("当前抖音账号")).toBeInTheDocument();
  expect(screen.getByAltText("当前账号头像")).toHaveAttribute("src", "/api/account-profile/avatar?v=test");
  expect(screen.getByText("已完成")).toBeInTheDocument();
  expect(screen.getAllByText("9/9")).toHaveLength(2);
  expect(screen.getByText("检查登录")).toBeInTheDocument();
  expect(await screen.findByText("发送前自检")).toBeInTheDocument();
  expect(await screen.findByText("具备条件：1")).toBeInTheDocument();
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

test("starts a read-only preflight from the dashboard", async () => {
  apiMocks.runPreflight.mockResolvedValue({ id: "preflight-1", action: "preflight", status: "running" });
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "测试全部续火目标" }));

  await waitFor(() => expect(apiMocks.runPreflight).toHaveBeenCalledWith());
  expect(screen.getByText(/正在检测 0/)).toBeInTheDocument();
});

test("opens the online message library from navigation", async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "在线文案库" }));

  expect(await screen.findByRole("heading", { name: "在线文案库" })).toBeInTheDocument();
  expect(screen.getByText("日常问候")).toBeInTheDocument();
});

test("shows a localized account-profile route error instead of FastAPI detail", async () => {
  apiMocks.refreshAccountProfile.mockRejectedValueOnce(new Error('{"detail":"Not Found"}'));
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "刷新当前账号资料" }));

  expect(await screen.findByText("当前账号资料接口不可用，请重启 AutoDy 管理台。"))
    .toBeInTheDocument();
  expect(screen.queryByText(/detail.*Not Found/)).not.toBeInTheDocument();
});
