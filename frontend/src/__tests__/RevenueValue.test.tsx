import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RevenueValue } from "../components/RevenueValue";
import { RevenueProvider } from "../context/RevenueContext";
import { apiPost } from "../lib/api";

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

const mockedApiPost = vi.mocked(apiPost);

describe("RevenueValue", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders locked by default and shows the formatted value after unlocking", async () => {
    const user = userEvent.setup();

    mockedApiPost.mockResolvedValue({
      token: "token",
      expires_at: new Date(Date.now() + 60_000).toISOString(),
    });

    render(
      <RevenueProvider>
        <RevenueValue value={1234} />
      </RevenueProvider>,
    );

    expect(screen.getByLabelText("محرمانه")).toHaveTextContent("••••");

    await user.click(screen.getByRole("button", { name: "باز کردن قفل درآمد" }));
    await user.type(screen.getByLabelText("رمز عبور"), "secret");
    await user.click(screen.getByRole("button", { name: "نمایش" }));

    expect(await screen.findByText("۱٬۲۳۴")).toBeInTheDocument();
    expect(mockedApiPost).toHaveBeenCalledWith("/revenue/unlock/", {
      password: "secret",
    });
  });
});
