import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../lib/api";
import { GuestCodesScreen } from "../screens/GuestCodesScreen";

vi.mock("../lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    body: unknown;
    constructor(status: number, body: unknown) {
      super("API error");
      this.status = status;
      this.body = body;
    }
  },
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  apiPatch: vi.fn(),
  apiPost: vi.fn(),
}));

const mockedApiGet = vi.mocked(apiGet);

describe("GuestCodesScreen", () => {
  afterEach(() => vi.clearAllMocks());

  it("sums guests, gender split and paid entries across the codes", async () => {
    mockedApiGet.mockResolvedValueOnce([
      {
        id: 1,
        code: "الف1",
        guest_name: "مهمان",
        guest_count: 3,
        men_count: 2,
        women_count: 1,
        paid_entry: true,
      },
      {
        id: 2,
        code: "الف2",
        guest_name: "",
        guest_count: 2,
        men_count: 1,
        women_count: 1,
        paid_entry: false,
      },
    ]);

    render(<GuestCodesScreen />);

    await waitFor(() => expect(screen.getByText("۲ کد")).toBeInTheDocument());
    expect(screen.getByText("مهمان‌ها: ۵")).toBeInTheDocument();
    expect(screen.getByText("مرد: ۳")).toBeInTheDocument();
    expect(screen.getByText("زن: ۲")).toBeInTheDocument();
    expect(screen.getByText("پرداخت‌شده: ۱")).toBeInTheDocument();
    expect(screen.getByText("الف1")).toBeInTheDocument();
    expect(screen.getByText("الف2")).toBeInTheDocument();
  });
});
