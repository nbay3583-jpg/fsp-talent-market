import { describe, expect, it } from "vitest";
import { answeredOf } from "./Candidate";

describe("answeredOf (assessment answers)", () => {
  it("treats numeric 0 and the string '0' as answered", () => {
    expect(answeredOf(0)).toBe(true);
    expect(answeredOf("0")).toBe(true);
    expect(answeredOf("-0,5")).toBe(true);
  });
  it("treats missing, blank and empty selections as unanswered", () => {
    expect(answeredOf(undefined)).toBe(false);
    expect(answeredOf(null)).toBe(false);
    expect(answeredOf("")).toBe(false);
    expect(answeredOf("  ")).toBe(false);
    expect(answeredOf([])).toBe(false);
    expect(answeredOf(["A"])).toBe(true);
  });
});
