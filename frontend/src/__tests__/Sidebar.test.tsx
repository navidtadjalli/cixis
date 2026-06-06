import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "../components/Sidebar";
import type { Category } from "../screens/OrderPanel";

const categories: Category[] = [
  { id: 1, name: "قهوه", sort_order: 1 },
  { id: 2, name: "چای", sort_order: 2 },
  { id: 3, name: "کیک", sort_order: 3 },
];

describe("Sidebar", () => {
  it("renders the category list and highlights the selected one", () => {
    render(
      <Sidebar
        categories={categories}
        selectedCategoryId={2}
        onSelectCategory={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "قهوه" })).toBeInTheDocument();
    const selected = screen.getByRole("button", { name: "چای" });
    expect(selected).toBeInTheDocument();
    expect(selected).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("button", { name: "کیک" })).toBeInTheDocument();
  });
});
