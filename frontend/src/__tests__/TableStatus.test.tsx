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

describe("Table status badges", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("maps empty, occupied, and paid statuses to the correct label and badge tone", async () => {
    mockedApiGet.mockImplementation(async (path) => {
      if (path === "/tables/") {
        return [
          {
            id: 1,
            name: "میز خالی",
            sort_order: 1,
            active_order_id: null,
            active_order_total: null,
            status: "empty",
          },
          {
            id: 2,
            name: "میز مشغول",
            sort_order: 2,
            active_order_id: 10,
            active_order_total: 90,
            status: "occupied",
          },
          {
            id: 3,
            name: "میز پرداخت",
            sort_order: 3,
            active_order_id: 11,
            active_order_total: 120,
            status: "paid",
          },
        ];
      }

      if (path === "/day-closing/preview/") {
        return { total_sales: 210 };
      }

      throw new Error(`Unexpected path: ${path}`);
    });

    render(
      <RevenueProvider>
        <TablesScreen onOpenOrder={vi.fn()} onEventMode={vi.fn()} />
      </RevenueProvider>,
    );

    const emptyCard = (await screen.findByText("میز خالی")).closest(
      '[role="button"]',
    );
    const occupiedCard = (await screen.findByText("میز مشغول")).closest(
      '[role="button"]',
    );
    const paidCard = (await screen.findByText("میز پرداخت")).closest(
      '[role="button"]',
    );

    expect(emptyCard).not.toBeNull();
    expect(occupiedCard).not.toBeNull();
    expect(paidCard).not.toBeNull();

    const emptyBadge = within(emptyCard as HTMLElement).getByText("خالی");
    const occupiedBadge = within(occupiedCard as HTMLElement).getByText("در حال سرویس");
    const paidBadge = within(paidCard as HTMLElement).getByText("پرداخت‌شده");

    expect(emptyBadge).toHaveClass("bg-surface-2", "text-muted");
    expect(occupiedBadge).toHaveClass("bg-accent/10", "text-accent");
    expect(paidBadge).toHaveClass("bg-good/10", "text-good");
  });
});
