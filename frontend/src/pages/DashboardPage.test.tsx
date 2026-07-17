import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DashboardPage } from "./DashboardPage";

const apiMocks = vi.hoisted(() => ({
  preflightStatus: vi.fn(), runPreflight: vi.fn(), cancelPreflight: vi.fn(),
  todayPlan: vi.fn(), failedTargets: vi.fn(), serviceIdentity: vi.fn(), retryFailedTarget: vi.fn()
}));
vi.mock("../api", () => ({ api: apiMocks }));

const status = { today: { date: "2026-07-16", message: "", succeeded: 0, failed: 1, total: 1, complete: false }, friends: [], history: [], scheduler: [], next_run: null, login: { status: "success" }, message_count: 2, issues: [], statistics: { last_completed_run: null, successful_today: 0, failed_today: 1, consecutive_successful_days: 0, success_rate_7d: 0, success_rate_30d: 0, retries_7d: 0, enabled_friend_count: 1, local_message_count: 2, active_message_pack_count: 1, configured_friend_count: 1, next_health_check: null, next_daily_send: null, most_recent_issue: null, log_summary: { active_errors: 0, warnings_24h: 0, successful_tasks_7d: 0, last_health_check: null, last_send: null, last_error_time: null } } };

beforeEach(() => {
  apiMocks.preflightStatus.mockResolvedValue({ running: false, progress: null, result: null });
  apiMocks.todayPlan.mockResolvedValue({ main_scheduled_time: "07:30", enabled_target_count: 1, completed_count: 0, pending_count: 1, blocked_count: 0, generated_at: "2026-07-16T07:00:00", estimated_finish: "2026-07-16T07:30", configuration_source: "current", targets: [{ target_id: "t1", display_name: "测试目标", planned_at: "2026-07-16T07:30", message_source: "全局本地文案库", suffix: "全局后缀", status: "pending", blocked_reason: null }] });
  apiMocks.failedTargets.mockResolvedValue({ summary: { success: 0, failed: 1, uncertain: 1, needs_attention: 1 }, items: [{ target_id: "t1", display_name: "测试目标", explanation: "发送结果不确定，为避免重复发送，已禁止自动重试。", reason_code: "confirmation_failed_uncertain", uncertain: true, safe_retry_available: false }] });
  apiMocks.serviceIdentity.mockResolvedValue({ application: "AutoDy", version: "1.0.0", git_commit: "abc123", python_executable: "python.exe", package_path: "src/autody", project_path: "project", frontend_build_version: "1.0.0" });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

test("does not render a preflight card or request preflight status on the normal dashboard", async () => {
  render(<DashboardPage status={status} busy={null} onAction={vi.fn()} onNavigate={vi.fn()} />);

  expect(await screen.findByRole("heading", { name: "运行总览" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "发送前自检" })).not.toBeInTheDocument();
  expect(apiMocks.preflightStatus).not.toHaveBeenCalled();
});

test("keeps Test Center panels out of the normal dashboard", async () => {
  render(<DashboardPage status={status} busy={null} onAction={vi.fn()} onNavigate={vi.fn()} />);

  await screen.findByRole("heading", { name: "运行总览" });
  expect(screen.queryByRole("heading", { name: "今日发送计划" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "今日异常目标" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "运行环境" })).not.toBeInTheDocument();
  expect(apiMocks.todayPlan).not.toHaveBeenCalled();
  expect(apiMocks.failedTargets).not.toHaveBeenCalled();
  expect(apiMocks.serviceIdentity).not.toHaveBeenCalled();
});
