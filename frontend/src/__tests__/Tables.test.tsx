import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RevenueProvider } from "../context/RevenueContext";
import { apiGet } from "../lib/api";
import { TablesScreen } from "../screens/TablesScreen";

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

function renderTables() {
  return render(
    <RevenueProvider>
      <TablesScreen onOpenOrder={vi.fn()} onEventMode={vi.fn()} />
    </RevenueProvider>,
  );
}

describe("TablesScreen", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders mocked table cards with status badges and occupied order total area", async () => {
    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/tables/") {
        return [
          {
            id: 1,
            name: "میز ۱",
            sort_order: 1,
            active_order_id: null,
            active_order_total: null,
            status: "empty",
          },
          {
            id: 2,
            name: "میز ۲",
            sort_order: 2,
            active_order_id: 42,
            active_order_total: 180,
            status: "occupied",
          },
          {
            id: 3,
            name: "میز ۳",
            sort_order: 3,
            active_order_id: 43,
            active_order_total: 220,
            status: "paid",
          },
        ];
      }

      if (path === "/day-closing/preview/") {
        return { total_sales: 400 };
      }

      throw new Error(`Unexpected path: ${path}`);
    });

    renderTables();

    const emptyCard = (await screen.findByText("میز ۱")).closest('[role="button"]');
    const occupiedCard = (await screen.findByText("میز ۲")).closest(
      '[role="button"]',
    );
    const paidCard = (await screen.findByText("میز ۳")).closest('[role="button"]');

    expect(emptyCard).not.toBeNull();
    expect(occupiedCard).not.toBeNull();
    expect(paidCard).not.toBeNull();
    expect(within(emptyCard as HTMLElement).getByText("خالی")).toBeInTheDocument();
    expect(within(occupiedCard as HTMLElement).getByText("در حال سرویس")).toBeInTheDocument();
    expect(within(paidCard as HTMLElement).getByText("پرداخت‌شده")).toBeInTheDocument();
    expect(within(occupiedCard as HTMLElement).getByText("مبلغ سفارش")).toBeInTheDocument();
  });
});
