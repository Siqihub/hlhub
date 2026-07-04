import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App";

const apiMocks = vi.hoisted(() => ({
  action: vi.fn(),
  waitForAction: vi.fn()
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
      history: [{ date: "2026-06-24", message: "测试文案", succeeded: 9, total: 9, failed: 0, complete: true }],
      scheduler: [],
      next_run: "2026-06-25T07:30:00",
      login: { status: "normal" },
      message_count: 60
    }),
    action: apiMocks.action,
    waitForAction: apiMocks.waitForAction
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
