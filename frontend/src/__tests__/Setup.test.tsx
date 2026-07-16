import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiPost } from "../lib/api";
import { SetupScreen } from "../screens/SetupScreen";

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

async function unlock(user: ReturnType<typeof userEvent.setup>) {
  mockedApiPost.mockResolvedValueOnce({ token: "t", expires_at: "" });
  await user.type(screen.getByPlaceholderText("رمز عبور"), "1234");
  await user.click(screen.getByRole("button", { name: "ورود" }));
  await screen.findByText("ساخت میز");
}

function renderSetup() {
  const onDataChanged = vi.fn();
  render(<SetupScreen onDataChanged={onDataChanged} />);
  return { onDataChanged };
}

describe("SetupScreen", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the tools hidden until the day-closing password is accepted", async () => {
    const user = userEvent.setup();
    renderSetup();

    expect(screen.queryByText("ساخت میز")).toBeNull();

    mockedApiPost.mockRejectedValueOnce(new ApiError(401, { detail: "no" }));
    await user.type(screen.getByPlaceholderText("رمز عبور"), "wrong");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(await screen.findByText("رمز عبور نادرست است")).toBeTruthy();
    expect(screen.queryByText("ساخت میز")).toBeNull();
  });

  it("creates tables by count and reports how many were made", async () => {
    const user = userEvent.setup();
    const { onDataChanged } = renderSetup();
    await unlock(user);

    mockedApiPost.mockResolvedValueOnce({ created: 12, skipped: 0 });
    await user.type(screen.getByLabelText("تعداد میز"), "12");
    await user.click(screen.getByRole("button", { name: "ساخت میزها" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenLastCalledWith("/setup/tables/bulk/", {
        password: "1234",
        count: "12",
      });
    });
    expect(await screen.findByText("۱۲ میز ساخته شد.")).toBeTruthy();
    expect(onDataChanged).toHaveBeenCalled();
  });

  it("sends the code prefix and the inclusive range, normalizing Persian digits", async () => {
    const user = userEvent.setup();
    renderSetup();
    await unlock(user);

    mockedApiPost.mockResolvedValueOnce({ created: 3, skipped: 1 });
    await user.type(screen.getByLabelText("پیشوند"), "الف");
    await user.type(screen.getByLabelText("از شماره"), "۱");
    await user.type(screen.getByLabelText("تا شماره"), "۴");
    await user.click(screen.getByRole("button", { name: "ساخت کدها" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenLastCalledWith("/setup/event-codes/bulk/", {
        password: "1234",
        prefix: "الف",
        start: "1",
        end: "4",
      });
    });
    expect(
      await screen.findByText("۳ کد ساخته شد — ۱ مورد از قبل فعال بود."),
    ).toBeTruthy();
  });

  it("loads the bundled menu and reports what was added", async () => {
    const user = userEvent.setup();
    const { onDataChanged } = renderSetup();
    await unlock(user);

    mockedApiPost.mockResolvedValueOnce({
      categories_created: 3,
      products_created: 9,
    });
    await user.click(screen.getByRole("button", { name: "بارگذاری منو" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenLastCalledWith("/setup/menu/load/", {
        password: "1234",
      });
    });
    expect(await screen.findByText("۳ دسته‌بندی و ۹ محصول اضافه شد.")).toBeTruthy();
    expect(onDataChanged).toHaveBeenCalled();
  });

  it("wipes tables only after the confirmation is accepted", async () => {
    const user = userEvent.setup();
    renderSetup();
    await unlock(user);

    await user.click(screen.getByRole("button", { name: "پاک کردن همه میزها" }));
    // Backing out of the dialog must not touch the server.
    await user.click(screen.getByRole("button", { name: "انصراف" }));
    expect(mockedApiPost).toHaveBeenCalledTimes(1); // the unlock only

    await user.click(screen.getByRole("button", { name: "پاک کردن همه میزها" }));
    mockedApiPost.mockResolvedValueOnce({ deleted_tables: 9, deleted_orders: 0 });
    await user.click(screen.getByRole("button", { name: "بله، پاک کن" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenLastCalledWith("/setup/tables/wipe/", {
        password: "1234",
      });
    });
    expect(await screen.findByText("۹ میز حذف شد.")).toBeTruthy();
  });

  it("says when a table wipe also took unsettled orders with it", async () => {
    const user = userEvent.setup();
    renderSetup();
    await unlock(user);

    await user.click(screen.getByRole("button", { name: "پاک کردن همه میزها" }));
    mockedApiPost.mockResolvedValueOnce({ deleted_tables: 40, deleted_orders: 2 });
    await user.click(screen.getByRole("button", { name: "بله، پاک کن" }));

    expect(
      await screen.findByText("۴۰ میز حذف شد — ۲ سفارش تسویه‌نشده هم حذف شد."),
    ).toBeTruthy();
  });

  it("wipes every order and code after confirmation", async () => {
    const user = userEvent.setup();
    const { onDataChanged } = renderSetup();
    await unlock(user);

    await user.click(
      screen.getByRole("button", { name: "پاک کردن همه سفارش‌ها و کدها" }),
    );
    mockedApiPost.mockResolvedValueOnce({ deleted_orders: 153 });
    await user.click(screen.getByRole("button", { name: "بله، پاک کن" }));

    await waitFor(() => {
      expect(mockedApiPost).toHaveBeenLastCalledWith("/setup/orders/wipe/", {
        password: "1234",
      });
    });
    expect(await screen.findByText("۱۵۳ سفارش و کد حذف شد.")).toBeTruthy();
    expect(onDataChanged).toHaveBeenCalled();
  });

  it("surfaces the backend's own reason when an action fails", async () => {
    const user = userEvent.setup();
    renderSetup();
    await unlock(user);

    mockedApiPost.mockRejectedValueOnce(
      new ApiError(501, { detail: "فایل منو در این نسخه موجود نیست." }),
    );
    await user.click(screen.getByRole("button", { name: "بارگذاری منو" }));

    expect(
      await screen.findByText("فایل منو در این نسخه موجود نیست."),
    ).toBeTruthy();
  });
});
