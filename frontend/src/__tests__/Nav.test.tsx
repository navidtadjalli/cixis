import { describe, expect, it } from "vitest";
import { navItems } from "../components/Sidebar";

// Tests run with the default brand (cixis). The nav must expose the CiXiS staff
// tabs and the owner tab, and hide the Majaz-only guest-codes tab.
describe("brand-gated navItems (cixis build)", () => {
  const ids = navItems.map((item) => item.id);

  it("includes the shared tabs and the owner tab", () => {
    expect(ids).toContain("tables");
    expect(ids).toContain("closing");
    expect(ids).toContain("orders-report");
    expect(ids).toContain("owner");
  });

  it("places the orders report immediately to the right of day closing", () => {
    expect(ids.indexOf("orders-report")).toBe(ids.indexOf("closing") - 1);
  });

  it("includes the CiXiS attendance tabs", () => {
    expect(ids).toContain("attendance-entry");
    expect(ids).toContain("attendance-report");
  });

  it("hides the Majaz guest-codes tab", () => {
    expect(ids).not.toContain("guest-codes");
  });

  it("drops the old standalone setup/settings entries", () => {
    expect(ids).not.toContain("setup");
    expect(ids).not.toContain("settings");
  });
});
