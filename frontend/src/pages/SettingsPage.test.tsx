import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";

vi.mock("../api", () => ({
  api: {
    config: vi.fn().mockResolvedValue({
      targets: [], retry_count: 3, timeout_ms: 30000, headless: true,
      message_suffix: { enabled: true, text: "gpt小助手", style: "dash" },
      message_pack_index_url: null
    }),
    saveConfig: vi.fn()
  }
}));

afterEach(cleanup);

test("shows a live suffix preview for every style", async () => {
  render(<SettingsPage notify={vi.fn()} />);
  expect(await screen.findByText("你好 —— gpt小助手")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("后缀样式"), { target: { value: "bracket" } });

  expect(screen.getByText("你好【gpt小助手】")).toBeInTheDocument();
});
