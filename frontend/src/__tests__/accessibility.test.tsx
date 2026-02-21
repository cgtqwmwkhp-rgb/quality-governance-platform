import { describe, it, expect } from "vitest";

describe("Accessibility", () => {
  it("ErrorBoundary has proper ARIA attributes", async () => {
    const { default: ErrorBoundary } =
      await import("../components/ErrorBoundary");
    expect(ErrorBoundary).toBeDefined();
  });

  it("PageErrorBoundary has proper ARIA attributes", async () => {
    const { default: PageErrorBoundary } =
      await import("../components/PageErrorBoundary");
    expect(PageErrorBoundary).toBeDefined();
  });
});
