// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Assistant from "./Assistant";

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
});
