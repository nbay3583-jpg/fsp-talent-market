// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Assistant from "./Assistant";
import { setAssistantPage } from "./assistantContext";

describe("Assistant", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("opens, shows suggestions and prints the server answer", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes("suggestions")
        ? { suggestions: ["Как проходит оценка?"] }
        : { answer: "11 заданий", topic: "Как проходит оценка", related: [], matched: true }),
    })));
    render(<Assistant role="candidate" />);
    fireEvent.click(screen.getByLabelText("Открыть помощника"));
    fireEvent.click(await screen.findByText("Как проходит оценка?"));
    await waitFor(() => expect(screen.getByText("11 заданий")).toBeTruthy());
  });

  const stubOk = () => vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ suggestions: ["Общий вопрос?"] }) })));

  it("closes on Escape and returns focus to the launcher", async () => {
    stubOk();
    render(<Assistant role="candidate" />);
    const fab = screen.getByLabelText("Открыть помощника");
    fireEvent.click(fab);
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(fab);
  });

  it("offers page-specific questions for the active cabinet tab", async () => {
    stubOk();
    setAssistantPage("test");
    render(<Assistant role="candidate" />);
    fireEvent.click(screen.getByLabelText("Открыть помощника"));
    expect(await screen.findByText("Как проходит оценка?")).toBeTruthy();
    expect(screen.queryByText("Общий вопрос?")).toBeNull();
    setAssistantPage(null);
  });
});
