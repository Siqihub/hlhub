import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { FriendsPage } from "./FriendsPage";

const apiMocks = vi.hoisted(() => ({
  config: vi.fn(),
  friends: vi.fn(),
  discoveredFriends: vi.fn(),
  scanFriends: vi.fn(),
  refreshFriendAvatars: vi.fn(),
  waitForAction: vi.fn(),
  addDiscoveredFriends: vi.fn(),
  friendBatch: vi.fn(),
  saveConfig: vi.fn()
}));

vi.mock("../api", () => ({ api: apiMocks }));

const config = {
  targets: ["小明"], retry_count: 3, timeout_ms: 30000, headless: true,
  message_suffix: { enabled: true, text: "gpt小助手", style: "dash" as const },
  message_pack_index_url: null,
  daily_send_time: "07:30", daily_health_check_time: "07:20", weekly_health_check_enabled: true,
  weekly_health_check_weekday: "Sunday", weekly_health_check_time: "20:00",
  startup_recovery_enabled: true, recovery_deadline: "23:59", min_delay_seconds: 1,
  max_delay_seconds: 3, page_load_timeout_ms: 30000, friend_search_timeout_ms: 30000,
  confirmation_timeout_ms: 12000, friend_order: "configured" as const,
  message_selection: "one_for_all" as const, completion_notifications_enabled: true,
  log_retention_days: 30, mask_log_friend_names: true
};

const discovered = {
  scanned_at: "2026-07-04T12:30:00",
  candidates: [
    {
      candidate_id: "friend-xiaoming", display_name: "小明", avatar_url: "/api/avatars/friend-xiaoming",
      avatar_status: "cached" as const, discovered_at: "2026-07-04T12:30:00", match_status: "configured" as const,
      configured_target_id: "friend-xiaoming", configured_enabled: true
    },
    {
      candidate_id: "candidate-new", display_name: "新朋友", avatar_url: "/api/avatars/candidate-new",
      avatar_status: "cached" as const, discovered_at: "2026-07-04T12:30:00", match_status: "unconfigured" as const,
      configured_target_id: null, configured_enabled: null
    }
  ]
};

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.config.mockResolvedValue(config);
  apiMocks.friends.mockResolvedValue({
    friends: [{
      id: "friend-xiaoming", display_name: "小明", enabled: true,
      avatar_url: "/api/avatars/friend-xiaoming", avatar_status: "cached",
      today_status: "success", last_success_date: "2026-07-04", note: ""
    }]
  });
  apiMocks.discoveredFriends.mockResolvedValue(discovered);
  apiMocks.scanFriends.mockResolvedValue({ id: "scan-1", action: "scan-friends", status: "running" });
  apiMocks.refreshFriendAvatars.mockResolvedValue({ id: "avatar-1", action: "refresh-friend-avatars", status: "running" });
  apiMocks.waitForAction.mockResolvedValue({ id: "scan-1", action: "scan-friends", status: "success" });
  apiMocks.addDiscoveredFriends.mockResolvedValue({ added: 1, skipped: 0 });
  apiMocks.friendBatch.mockResolvedValue({ affected: 1 });
  apiMocks.saveConfig.mockResolvedValue(config);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("shows local avatars, supports selecting a discovered friend, and removes standalone transfer controls", async () => {
  render(<FriendsPage notify={vi.fn()} />);

  expect((await screen.findAllByAltText("小明 的头像"))[0]).toHaveAttribute("loading", "lazy");
  expect(screen.getByText(/今日已完成/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /导入好友|导出 CSV|导出 JSON/ })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "扫描好友" }));
  const candidate = await screen.findByRole("checkbox", { name: "选择 新朋友" });
  fireEvent.click(candidate);
  fireEvent.click(screen.getByRole("button", { name: "添加所选好友" }));

  await waitFor(() => expect(apiMocks.addDiscoveredFriends).toHaveBeenCalledWith(["candidate-new"]));
  expect(screen.getByAltText("新朋友 的头像")).toHaveAttribute("loading", "lazy");
});


test("starts the avatar-only scan without a send action", async () => {
  render(<FriendsPage notify={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "扫描并更新头像" }));

  await waitFor(() => expect(apiMocks.refreshFriendAvatars).toHaveBeenCalledTimes(1));
  expect(apiMocks.scanFriends).not.toHaveBeenCalled();
});
