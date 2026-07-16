import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../lib/api";
import { EventScreen } from "../screens/EventScreen";

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

const order = (id: number, label: string) => ({
  id,
  mode: "event",
  event_customer_label: label,
  subtotal: 0,
  status: "open",
});

async function renderEvents() {
  mockedApiGet.mockResolvedValue([
    order(1, "الف۱"),
    order(2, "الف۱۲"),
    order(3, "ب۲۰"),
  ]);
  render(<EventScreen onOpenOrder={vi.fn()} onBack={vi.fn()} />);
  await screen.findByText("الف۱");
}

describe("EventScreen search", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("matches anywhere in the code, not just at the start", async () => {
    const user = userEvent.setup();
    await renderEvents();

    await user.type(screen.getByRole("searchbox"), "۱۲");

    await waitFor(() => {
      expect(screen.queryByText("الف۱")).toBeNull();
    });
    // Would have found nothing back when the filter was startsWith.
    expect(screen.getByText("الف۱۲")).toBeTruthy();
    expect(screen.queryByText("ب۲۰")).toBeNull();
  });

  it("still matches from the start", async () => {
    const user = userEvent.setup();
    await renderEvents();

    await user.type(screen.getByRole("searchbox"), "الف");

    await waitFor(() => {
      expect(screen.queryByText("ب۲۰")).toBeNull();
    });
    expect(screen.getByText("الف۱")).toBeTruthy();
    expect(screen.getByText("الف۱۲")).toBeTruthy();
  });

  it("matches Persian codes typed with ASCII digits", async () => {
    const user = userEvent.setup();
    await renderEvents();

    await user.type(screen.getByRole("searchbox"), "12");

    await waitFor(() => {
      expect(screen.queryByText("الف۱")).toBeNull();
    });
    expect(screen.getByText("الف۱۲")).toBeTruthy();
  });
});
