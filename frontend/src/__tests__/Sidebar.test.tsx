import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "../components/Sidebar";

describe("Sidebar", () => {
  it("renders exactly 3 sidebar items with the correct Persian text", () => {
    render(<Sidebar active="tables" onChange={vi.fn()} />);

    const buttons = screen.getAllByRole("button");

    expect(buttons).toHaveLength(3);
    expect(screen.getByRole("button", { name: "میزها" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "منو و محصولات" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "بستن روز" })).toBeInTheDocument();
  });
});
