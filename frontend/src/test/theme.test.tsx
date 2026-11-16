import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeToggle } from "@/components/theme-toggle";
import { themeInitializer } from "@/lib/theme";

let systemChange: () => void;
beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  vi.stubGlobal("matchMedia", vi.fn(() => ({
    matches: false,
    addEventListener: (_: string, handler: () => void) => { systemChange = handler; },
    removeEventListener: vi.fn(),
  })));
});

describe("appearance preference", () => {
  it("applies the device preference before paint and honors a saved override", () => {
    new Function(themeInitializer)();
    expect(document.documentElement.dataset.theme).toBe("light");
    localStorage.setItem("fantasy-advisor-theme", "dark");
    new Function(themeInitializer)();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("toggles, persists, and labels the next available mode", () => {
    document.documentElement.dataset.theme = "dark";
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("fantasy-advisor-theme")).toBe("light");
    expect(screen.getByRole("button", { name: "Switch to dark mode" })).toBeInTheDocument();
    act(() => systemChange());
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("works when browser storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    new Function(themeInitializer)();
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
