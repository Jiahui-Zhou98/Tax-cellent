import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepSidebar } from "./StepSidebar";

describe("StepSidebar", () => {
  it("renders all 7 step labels on desktop (md+)", () => {
    render(<StepSidebar current={0} />);
    const labels = ["Upload", "Context", "Review", "Validate", "Settings", "Analysis", "Report"];
    for (const label of labels) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it("sets aria-current=step only on the active step", () => {
    render(<StepSidebar current={3} />);
    const currentItems = screen
      .getAllByRole("generic")
      .filter((el) => el.getAttribute("aria-current") === "step");
    expect(currentItems).toHaveLength(1);
    expect(currentItems[0].getAttribute("aria-label")).toContain("current");
  });

  it("marks completed steps with aria-label containing 'completed'", () => {
    render(<StepSidebar current={2} />);
    // Steps 0 and 1 are completed
    const completedItems = screen
      .getAllByRole("generic")
      .filter((el) => el.getAttribute("aria-label")?.includes("completed"));
    expect(completedItems.length).toBeGreaterThanOrEqual(2);
  });

  it("does not mark pending steps as current or completed", () => {
    render(<StepSidebar current={1} />);
    // Step 3 onwards are pending
    const step4Label = screen.getByLabelText(/Step 4: Validate$/);
    expect(step4Label.getAttribute("aria-current")).toBeNull();
    expect(step4Label.getAttribute("aria-label")).not.toContain("completed");
  });

  it("active step shows 'Step N of 7' sub-label", () => {
    render(<StepSidebar current={4} />);
    expect(screen.getByText("Step 5 of 7")).toBeTruthy();
  });
});
