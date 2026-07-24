import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../lib/api";
import { AttendanceEntryScreen } from "../screens/AttendanceEntryScreen";

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

describe("AttendanceEntryScreen", () => {
  afterEach(() => vi.clearAllMocks());

  it("adds a fractional quantity to the personnel bill", async () => {
    mockedApiGet.mockImplementation(
      ((path: string) => {
        if (path === "/employees/") {
          return Promise.resolve([{ id: 1, name: "سعید" }]);
        }
        if (path === "/categories/") {
          return Promise.resolve([{ id: 2, name: "قهوه" }]);
        }
        if (path === "/products/?category=2") {
          return Promise.resolve([
            { id: 3, name: "اسپرسو", price: 50, is_available: true },
          ]);
        }
        return Promise.resolve([]);
      }) as typeof apiGet,
    );
    mockedApiPost.mockImplementation(
      ((path: string) => {
        if (path === "/revenue/unlock/") {
          return Promise.resolve({ token: "t", expires_at: "" });
        }
        return Promise.resolve({});
      }) as typeof apiPost,
    );

    const user = userEvent.setup();
    render(<AttendanceEntryScreen />);

    expect(
      screen.getByText(/فیش پرسنل، رمز عبور بستن روز را وارد کنید/),
    ).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("رمز عبور"), "1234");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(
      await screen.findByText("فیش پرسنل (شیفت ۹ تا ۱۷)"),
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("شیفت"), "evening");
    expect(
      await screen.findByText("فیش پرسنل (شیفت ۱۶ تا ۲۴)"),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(mockedApiGet).toHaveBeenCalledWith(
        expect.stringMatching(
          /^\/staff-consumption\/\?date=\d{4}-\d{2}-\d{2}&shift=evening$/,
        ),
      );
    });
    await user.selectOptions(screen.getByLabelText("پرسنل"), "1");
    await user.selectOptions(screen.getByLabelText("دسته‌بندی"), "2");
    await screen.findByRole("option", { name: "اسپرسو" });
    await user.selectOptions(screen.getByLabelText("محصول"), "3");
    const quantityInput = screen.getByLabelText("تعداد");
    expect(quantityInput).toHaveValue("1");
    expect(quantityInput).toHaveAttribute("dir", "ltr");
    await user.type(quantityInput, "0.5");
    expect(quantityInput).toHaveValue("0.5");
    await user.click(screen.getByRole("button", { name: "افزودن به فیش" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenCalledWith("/staff-consumption/", {
        employee: 1,
        product: 3,
        quantity: 0.5,
        business_date: expect.any(String),
        shift: "evening",
      });
    });
  });
});
