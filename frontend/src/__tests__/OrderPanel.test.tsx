import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPatch } from "../lib/api";
import { OrderPanel } from "../screens/OrderPanel";

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
const mockedApiPatch = vi.mocked(apiPatch);

const baseOrder = {
  id: 7,
  order_number: "7",
  mode: "table",
  table: 1,
  table_name: "میز ۱",
  event_customer_label: null,
  status: "open",
  subtotal: 200,
  paid_amount: 0,
  remaining_amount: 200,
  items: [
    {
      id: 101,
      product: 5,
      product_name_snapshot: "لاته",
      unit_price_snapshot: 100,
      quantity: 2,
      line_total: 200,
    },
  ],
  payments: [],
};

describe("OrderPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("updates the displayed line total after incrementing and decrementing quantity", async () => {
    const user = userEvent.setup();
    let quantity = 2;

    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/orders/7/") {
        return {
          ...baseOrder,
          subtotal: quantity * 100,
          remaining_amount: quantity * 100,
          items: [
            {
              ...baseOrder.items[0],
              quantity,
              line_total: quantity * 100,
            },
          ],
        };
      }

      if (path === "/categories/") {
        return [{ id: 1, name: "نوشیدنی", sort_order: 1 }];
      }

      if (path === "/tables/") {
        return [{ id: 1, name: "میز ۱", active_order_id: 7 }];
      }

      if (path === "/products/?category=1") {
        return [];
      }

      throw new Error(`Unexpected path: ${path}`);
    });
    mockedApiPatch.mockImplementation(async (_path, body) => {
      quantity = Number((body as { quantity: number }).quantity);
      return { ...baseOrder.items[0], quantity, line_total: quantity * 100 };
    });

    render(<OrderPanel orderId={7} onClose={vi.fn()} />);

    const item = (await screen.findByText("لاته")).closest(".rounded-xl");
    expect(item).not.toBeNull();
    expect(within(item as HTMLElement).getByText("۲۰۰ هزار تومان")).toBeInTheDocument();

    await user.click(within(item as HTMLElement).getByRole("button", { name: "+" }));

    await waitFor(() => {
      expect(within(item as HTMLElement).getByText("۳۰۰ هزار تومان")).toBeInTheDocument();
    });
    expect(mockedApiPatch).toHaveBeenLastCalledWith("/order-items/101/", {
      quantity: 3,
    });

    await user.click(within(item as HTMLElement).getByRole("button", { name: "−" }));

    await waitFor(() => {
      expect(within(item as HTMLElement).getByText("۲۰۰ هزار تومان")).toBeInTheDocument();
    });
    expect(mockedApiPatch).toHaveBeenLastCalledWith("/order-items/101/", {
      quantity: 2,
    });
  });
});
