import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../lib/api";
import { OrderReportScreen } from "../screens/OrderReportScreen";

vi.mock("../lib/api", () => ({
  apiGet: vi.fn(),
}));

const mockedApiGet = vi.mocked(apiGet);

describe("OrderReportScreen", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows paid receipts and reapplies the selected table filter", async () => {
    const user = userEvent.setup();

    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/tables/") {
        return [
          { id: 1, name: "میز ۱", sort_order: 1 },
          { id: 2, name: "میز ۲", sort_order: 2 },
        ];
      }
      if (path.startsWith("/reports/orders/")) {
        return {
          business_date: "2026-08-31",
          table_id: path.includes("table_id=2") ? 2 : null,
          orders: [
            {
              id: 19,
              order_number: 19,
              table_name: "میز ۲",
              status: "paid",
              subtotal: 480,
              paid_amount: 480,
              remaining_amount: 0,
              closed_at: "2026-08-31T20:15:00Z",
              items: [],
              payments: [],
            },
          ],
        };
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    render(<OrderReportScreen />);

    expect(await screen.findByText("گزارش سفارش‌ها")).toBeInTheDocument();
    expect(await screen.findByTestId("paid-order-19")).toHaveTextContent("میز ۲");

    await user.selectOptions(screen.getByLabelText("میز"), "2");
    await user.click(screen.getByRole("button", { name: "اعمال فیلتر" }));

    await waitFor(() => {
      expect(mockedApiGet).toHaveBeenCalledWith(
        expect.stringMatching(
          /^\/reports\/orders\/\?business_date=\d{4}-\d{2}-\d{2}&table_id=2$/,
        ),
      );
    });
  });
});
