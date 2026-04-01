import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StepShell } from "./StepShell";

describe("StepShell", () => {
  it("renders children inside the card", () => {
    render(<StepShell step={0}><p>child content</p></StepShell>);
    expect(screen.getByText("child content")).toBeTruthy();
  });

  it("shows correct progress badge text", () => {
    render(<StepShell step={2}><span /></StepShell>);
    expect(screen.getByText("3 of 7")).toBeTruthy();
    expect(screen.getByText("Review")).toBeTruthy();
  });

  it("Previous button fires onBack when defined", async () => {
    const onBack = vi.fn();
    render(<StepShell step={1} onBack={onBack}><span /></StepShell>);
    await userEvent.click(screen.getByText("Previous"));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("does not render Previous button when onBack is undefined", () => {
    render(<StepShell step={1}><span /></StepShell>);
    expect(screen.queryByText("Previous")).toBeNull();
  });

  it("Continue button fires onNext when defined", async () => {
    const onNext = vi.fn();
    render(<StepShell step={0} onNext={onNext}><span /></StepShell>);
    await userEvent.click(screen.getByText("Continue"));
    expect(onNext).toHaveBeenCalledOnce();
  });

  it("does not render Next button when onNext is undefined", () => {
    render(<StepShell step={6}><span /></StepShell>);
    expect(screen.queryByText("Continue")).toBeNull();
  });

  it("Next button is disabled when loading=true", async () => {
    const onNext = vi.fn();
    render(<StepShell step={0} onNext={onNext} loading><span /></StepShell>);
    const btn = screen.getByText("Loading…");
    expect((btn as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(btn);
    expect(onNext).not.toHaveBeenCalled();
  });
});
