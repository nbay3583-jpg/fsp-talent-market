import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LevelMeter } from "./ui";

describe("LevelMeter", () => {
  it("shows Russian grade labels without changing values", () => {
    const html = renderToStaticMarkup(<LevelMeter claimed="MIDDLE" verified="SENIOR" sublevel="S1" />);
    expect(html).toContain("Джуниор");
    expect(html).toContain("Мидл");
    expect(html).toContain("Сеньор");
    expect(html).toContain("Подтверждено: Сеньор S1");
    expect(html).not.toContain("JUNIOR");
  });
});
