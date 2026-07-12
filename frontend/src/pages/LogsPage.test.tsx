import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { LogsPage } from "./LogsPage";

vi.mock("../api", () => ({
  api: {
    logs: vi.fn().mockResolvedValue({
      items: [{ timestamp: "2026-07-13 08:00:00", date: "2026-07-13", level: "ERROR", task_type: "daily_send", summary: "发送失败：好友#1234", detail: "Traceback detail", source: "autody-2026-07-13.log" }],
      total: 1, page: 1, page_size: 50, start_date: "2026-07-11", end_date: "2026-07-13", scheduler: ""
    }),
    archiveLogs: vi.fn()
  }
}));

afterEach(cleanup);

test("shows masked summaries and keeps traceback details collapsed", async () => {
  render(<LogsPage />);

  expect(await screen.findByText("发送失败：好友#1234")).toBeInTheDocument();
  expect(screen.getByText("查看详情")).toBeInTheDocument();
  expect(screen.getByLabelText("日志开始日期")).toBeInTheDocument();
  expect(screen.queryByText("小明")).not.toBeInTheDocument();
});
