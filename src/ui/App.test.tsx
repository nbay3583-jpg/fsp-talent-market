// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import App from "./App";
import { ContactBox, FitBlock, money, salaryRange, SalaryBanner, VerificationBadge } from "./ui";

function stubFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const hit = routes[url];
      if (hit === undefined) return Promise.reject(new Error("network failure"));
      return Promise.resolve({ ok: true, json: () => Promise.resolve(hit) });
    }),
  );
}

describe("App shell", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("shows the healthy status and the demo entry when the API is healthy", async () => {
    stubFetch({
      "/health": { status: "ok" },
      "/api/demo/config": { demo_mode: true, accounts: [{ key: "employer", role: "employer", label: "Демо-компания (работодатель)", fsp_id: null, note: "n" }] },
    });
    render(<App />);
    expect(await screen.findByText("Система работает")).toBeTruthy();
    expect(await screen.findByText("Демо-компания")).toBeTruthy();
  });

  it("shows an error state when the backend is unreachable", async () => {
    stubFetch({});
    render(<App />);
    expect(await screen.findByText("Система недоступна")).toBeTruthy();
    expect((await screen.findAllByRole("alert")).length).toBeGreaterThan(0);
  });

  it("says when demo mode is off", async () => {
    stubFetch({ "/health": { status: "ok" }, "/api/demo/config": { demo_mode: false, accounts: [] } });
    render(<App />);
    expect(await screen.findByText(/Демо-режим выключен/)).toBeTruthy();
  });
});

describe("product components", () => {
  afterEach(cleanup);

  it("formats the salary range with the explicit GROSS/NET type", () => {
    expect(money(220000)).toBe("220 000");
    expect(salaryRange(220000, 250000, "GROSS")).toBe("220 000–250 000 ₽ · GROSS");
    render(<SalaryBanner from={220000} to={250000} type="NET" />);
    expect(screen.getByTestId("salary").textContent).toContain("220 000–250 000 ₽");
    expect(screen.getByTestId("salary").textContent).toContain("NET");
  });

  it("labels the fit as fit to THIS need and lists why and gaps", () => {
    render(
      <FitBlock
        label="Соответствие потребности: 86%"
        fit={0.86}
        why={[{ code: "SKILL_VERIFIED", text: "api_fastapi: навык подтверждён", skill: "api_fastapi" }]}
        gaps={[{ code: "SKILL_UNVERIFIED", text: "kafka: нет данных о навыке", skill: "kafka" }]}
      />,
    );
    expect(screen.getByText(/Соответствие потребности: 86%/)).toBeTruthy();
    expect(screen.getByText(/API \/ FastAPI: навык подтверждён/)).toBeTruthy();
    expect(screen.getByText("Почему подходит")).toBeTruthy();
    expect(screen.getByText("Пробелы")).toBeTruthy();
    expect(screen.getByText(/Kafka: нет данных о навыке/)).toBeTruthy();
    expect(screen.queryByText(/Talent Score/i)).toBeNull();
  });

  it("hides contacts until they are unlocked", () => {
    const { rerender } = render(<ContactBox unlocked={false} />);
    expect(screen.getByTestId("contacts-locked")).toBeTruthy();
    expect(screen.queryByText("boris@demo.example")).toBeNull();
    rerender(<ContactBox unlocked contacts={{ full_name: "Boris P", email: "boris@demo.example", phone: null }} />);
    expect(screen.getByTestId("contacts-unlocked").textContent).toContain("boris@demo.example");
    expect(screen.getByTestId("contacts-unlocked").textContent).toContain("по согласию кандидата");
  });

  it("does not present NOT_VERIFIED as VERIFIED", () => {
    render(<VerificationBadge status="NOT_VERIFIED" />);
    expect(screen.getByText("Не подтверждено")).toBeTruthy();
    expect(screen.queryByText(/✓ Подтверждено/)).toBeNull();
  });
});
