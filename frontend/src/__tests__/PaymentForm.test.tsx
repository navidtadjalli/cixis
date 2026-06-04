import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../lib/api";
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
const mockedApiPost = vi.mocked(apiPost);

const order = {
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
  items: [],
  payments: [],
};

describe("Payment form", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("submits the selected method and amount to the payments API", async () => {
    const user = userEvent.setup();

    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/orders/7/") {
        return order;
      }

      if (path === "/categories/") {
        return [];
      }

      if (path === "/tables/") {
        return [{ id: 1, name: "میز ۱", active_order_id: 7 }];
      }

      throw new Error(`Unexpected path: ${path}`);
    });
    mockedApiPost.mockResolvedValue({
      id: 1,
      amount: 75,
      method: "card",
      payer_label: null,
      note: null,
    });

    render(<OrderPanel orderId={7} onClose={vi.fn()} />);

    await screen.findByText("سبد سفارش");
    await user.click(screen.getByRole("button", { name: "کارت" }));
    await user.type(screen.getByPlaceholderText("مبلغ (هزار تومان)"), "75");
    await user.click(screen.getByRole("button", { name: "افزودن پرداخت" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenCalledWith("/orders/7/payments/", {
        amount: 75,
        method: "card",
      });
    });
  });
});
