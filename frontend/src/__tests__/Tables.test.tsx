import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TablesScreen, type Table } from "../screens/TablesScreen";

const tables: Table[] = [
  {
    id: 1,
    name: "میز ۱",
    sort_order: 1,
    active_order_id: null,
    active_order_total: null,
    active_order_created_at: null,
    status: "empty",
  },
  {
    id: 2,
    name: "میز ۲",
    sort_order: 2,
    active_order_id: 42,
    active_order_total: 180,
    active_order_created_at: "2026-06-06T14:30:00",
    status: "occupied",
  },
];

function renderTables() {
  return render(
    <TablesScreen
      tables={tables}
      isLoading={false}
      loadError={null}
      refresh={vi.fn()}
      onOpenOrder={vi.fn()}
      onEventMode={vi.fn()}
    />,
  );
}

describe("TablesScreen", () => {
  it("draws tables with an order as circles showing time + total, free tables as plain cards", async () => {
    renderTables();

    const emptyCard = (await screen.findByText("میز ۱")).closest(
      '[data-testid="table-card"]',
    ) as HTMLElement;
    const occupiedCard = (await screen.findByText("میز ۲")).closest(
      '[data-testid="table-card"]',
    ) as HTMLElement;

    expect(emptyCard).not.toBeNull();
    expect(occupiedCard).not.toBeNull();

    // Free table: plain rectangular card, no order total / time.
    expect(emptyCard.className).not.toContain("rounded-full");

    // Occupied table: circular, shows the order total and creation clock time.
    expect(occupiedCard.className).toContain("rounded-full");
    expect(within(occupiedCard).getByText("۱۴:۳۰")).toBeInTheDocument();
  });
});
