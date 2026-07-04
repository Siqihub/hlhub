import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { FriendsPage } from "./FriendsPage";

vi.mock("../api", () => ({
  api: {
    config: vi.fn().mockResolvedValue({
      targets: ["小明"], retry_count: 3, timeout_ms: 30000, headless: true,
      message_suffix: { enabled: true, text: "gpt小助手", style: "dash" },
      message_pack_index_url: null
    }),
    saveConfig: vi.fn(),
    scanFriends: vi.fn().mockResolvedValue({ id: "scan-1", action: "scan-friends", status: "running" }),
    waitForAction: vi.fn().mockResolvedValue({ id: "scan-1", action: "scan-friends", status: "success" }),
    discoveredFriends: vi.fn().mockResolvedValue({
      scanned_at: "2026-07-04T12:30:00",
      candidates: [
        { name: "小明", already_configured: true },
        { name: "新朋友", already_configured: false }
      ]
    })
  }
}));

afterEach(cleanup);

test("scans candidates and adds only selected names to the editor", async () => {
  render(<FriendsPage notify={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "自动识别好友" }));

  const candidate = await screen.findByRole("checkbox", { name: "新朋友" });
  fireEvent.click(candidate);
  fireEvent.click(screen.getByRole("button", { name: "添加所选好友" }));

  await waitFor(() => expect(screen.getByDisplayValue("新朋友")).toBeInTheDocument());
  expect(screen.getAllByDisplayValue("小明")).toHaveLength(1);
});
