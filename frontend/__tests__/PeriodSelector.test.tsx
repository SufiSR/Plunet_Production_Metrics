/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { PeriodSelector } from "@/app/components/header/PeriodSelector";
import { useUIStore } from "@/lib/store";

describe("PeriodSelector", () => {
  beforeEach(() => {
    useUIStore.setState({ period: "30d" });
  });

  it("renders all dashboard period controls", () => {
    render(<PeriodSelector />);

    expect(screen.getByRole("button", { name: "Last 30 Days" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quarterly" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yearly" })).toBeInTheDocument();
  });

  it("updates the active dashboard period", async () => {
    render(<PeriodSelector />);

    await userEvent.click(screen.getByRole("button", { name: "Yearly" }));

    expect(useUIStore.getState().period).toBe("yearly");
    expect(screen.getByRole("button", { name: "Yearly" })).toHaveAttribute("aria-pressed", "true");
  });
});
