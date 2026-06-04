import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RevenueProvider } from "../context/RevenueContext";
import { apiGet, apiPost } from "../lib/api";
import { DayClosingScreen } from "../screens/DayClosingScreen";

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
const mockedApiPost = vi.mocked(apiPost);

const previewWithOpenOrders = {
  total_sales: 500,
  cash_total: 100,
  card_total: 300,
  bank_transfer_total: 100,
  orders_count: 5,
  closed_orders_count: 4,
  open_orders_count: 1,
  table_usage_count: 3,
  purchases_total: 40,
  resource_suggestions: [],
  unresolved_orders: [
    {
      id: 7,
      order_number: "7",
      table_name: "میز ۱",
      status: "open",
      remaining_amount: 80,
    },
  ],
};

describe("DayClosingScreen", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a confirmation dialog before calling close when open orders exist", async () => {
    const user = userEvent.setup();

    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/day-closing/preview/") {
        return previewWithOpenOrders;
      }

      if (path.startsWith("/resources/purchases/")) {
        return [];
      }

      if (path.startsWith("/reports/monthly/")) {
        return {
          year: 2026,
          month: 6,
          total_sales: 0,
          cash_total: 0,
          card_total: 0,
          bank_transfer_total: 0,
          purchases_total: 0,
          days_count: 0,
          daily: [],
        };
      }

      throw new Error(`Unexpected path: ${path}`);
    });

    render(
      <RevenueProvider>
        <DayClosingScreen />
      </RevenueProvider>,
    );

    await screen.findByText("پیش‌نمایش بستن روز");
    await user.click(screen.getByRole("button", { name: "بستن روز" }));

    expect(await screen.findByRole("dialog")).toHaveTextContent(
      "بستن روز با سفارش باز",
    );
    expect(mockedApiPost).not.toHaveBeenCalledWith("/day-closing/close/", {
      confirm: true,
    });

    await user.click(screen.getByRole("button", { name: "تایید و بستن روز" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenCalledWith("/day-closing/close/", {
        confirm: true,
      });
    });
  });
});
