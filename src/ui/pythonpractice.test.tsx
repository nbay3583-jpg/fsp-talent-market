import runnerSrc from "./public/sandbox/runner.js?raw";
import workerSrc from "./public/sandbox/worker.js?raw";
import componentSrc from "./PythonPractice.tsx?raw";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import PythonPractice from "./PythonPractice";

describe("Практика Python: изоляция", () => {
  const html = renderToStaticMarkup(<PythonPractice />);
  it("код выполняется в iframe без allow-same-origin и без отправки на сервер", () => {
    expect(html).toContain('sandbox="allow-scripts"');
    expect(html).not.toContain("allow-same-origin");
    expect(html).toContain("не является независимой сертификацией");
    expect(html).toContain("Запустить код");
  });
  it("страница-песочница не читает хранилище и токены приложения", () => {
    const runner = runnerSrc + workerSrc;
    for (const bad of ["localStorage", "sessionStorage", "document.cookie", "fsp.session", "/api/"]) expect(runner).not.toContain(bad);
  });
  it("исходник компонента не вызывает API сервера с кодом", () => {
    expect(componentSrc).not.toMatch(/api\(|fetch\(/);
  });
});
