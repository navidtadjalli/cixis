import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RevenueProvider } from "../context/RevenueContext";
import { apiGet, apiPost } from "../lib/api";
import { money } from "../lib/format";
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
  gross_sales: 580,
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

  it("renders a full receipt for every settled order", async () => {
    const previewWithSettled = {
      ...previewWithOpenOrders,
      settled_orders: [
        {
          id: 12,
          order_number: 12,
          table_name: "میز ۴",
          status: "paid",
          subtotal: 480,
          paid_amount: 480,
          remaining_amount: 0,
          closed_at: "2026-06-18T20:15:00Z",
          items: [
            {
              product_name: "اسپرسو",
              quantity: 2,
              unit_price: 90,
              line_total: 180,
            },
            {
              product_name: "کیک",
              quantity: 1,
              unit_price: 300,
              line_total: 300,
            },
          ],
          payments: [
            { amount: 300, method: "cash", payer_label: null },
            { amount: 180, method: "card", payer_label: "سارا" },
          ],
        },
      ],
    };

    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/day-closing/preview/") {
        return previewWithSettled;
      }
      if (path.startsWith("/resources/purchases/")) {
        return [];
      }
      if (path.startsWith("/reports/range/")) {
        return {
          from: "2026-06-18",
          to: "2026-06-18",
          orders_count: 0,
          orders_total: 0,
          items: [],
          items_quantity_total: 0,
          items_amount_total: 0,
        };
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

    const receipt = (await screen.findByTestId("settled-order-12")) as HTMLElement;

    // Every priced line is visible without any click.
    expect(receipt).toHaveTextContent("اسپرسو");
    expect(receipt).toHaveTextContent(`×${money(2)}`);
    expect(receipt).toHaveTextContent(money(90));
    expect(receipt).toHaveTextContent(money(180));
    expect(receipt).toHaveTextContent("کیک");
    expect(receipt).toHaveTextContent(money(300));

    // What had to be paid, and what covered it.
    expect(receipt).toHaveTextContent("پرداخت‌شده");
    expect(receipt).toHaveTextContent(money(480));
    expect(receipt).toHaveTextContent("نقدی");
    expect(receipt).toHaveTextContent("کارت");
    expect(receipt).toHaveTextContent("سارا");
  });

  it("refreshes the monthly table after closing so the closed row drops its button", async () => {
    const user = userEvent.setup();

    const previewNoOpenOrders = {
      ...previewWithOpenOrders,
      open_orders_count: 0,
      unresolved_orders: [],
    };

    const monthlyRow = {
      business_date: "2026-06-18",
      total_sales: 500,
      orders_count: 5,
      cash_total: 100,
      card_total: 300,
      bank_transfer_total: 100,
      purchases_total: 0,
    };

    let dayClosed = false;

    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/day-closing/preview/") {
        return previewNoOpenOrders;
      }
      if (path.startsWith("/resources/purchases/")) {
        return [];
      }
      if (path.startsWith("/reports/range/")) {
        return {
          from: "2026-06-18",
          to: "2026-06-18",
          orders_count: 0,
          orders_total: 0,
          items: [],
          items_quantity_total: 0,
          items_amount_total: 0,
        };
      }
      if (path.startsWith("/reports/monthly/")) {
        return {
          year: 2026,
          month: 6,
          total_sales: 500,
          cash_total: 100,
          card_total: 300,
          bank_transfer_total: 100,
          purchases_total: 0,
          days_count: 1,
          daily: [{ ...monthlyRow, is_closed: dayClosed }],
        };
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    mockedApiPost.mockImplementation(async (path) => {
      if (path === "/day-closing/close/") {
        // Once closed, the monthly report should report the day as closed.
        dayClosed = true;
        return { ...previewNoOpenOrders, id: 1, business_date: "2026-06-18" };
      }
      throw new Error(`Unexpected post: ${path}`);
    });

    render(
      <RevenueProvider>
        <DayClosingScreen />
      </RevenueProvider>,
    );

    await screen.findByText("پیش‌نمایش بستن روز");
    // Two "بستن روز" buttons initially: the header action + the open row's button.
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "بستن روز" })).toHaveLength(2);
    });

    // No open orders -> header button closes directly (no dialog).
    await user.click(screen.getAllByRole("button", { name: "بستن روز" })[0]);

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenCalledWith("/day-closing/close/", {
        confirm: true,
      });
    });

    // After the refresh the row is closed, leaving only the header button.
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "بستن روز" })).toHaveLength(1);
    });
  });
});
