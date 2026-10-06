// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows Backend: ok when health response status is ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ json: () => Promise.resolve({ status: "ok" }) }),
    );
    render(<App />);
    expect(await screen.findByText("Backend: ok")).toBeTruthy();
  });

  it("shows Backend: unavailable when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failure")));
    render(<App />);
    expect(await screen.findByText("Backend: unavailable")).toBeTruthy();
  });
});
