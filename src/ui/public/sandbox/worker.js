// Runs INSIDE a dedicated Web Worker created by runner.js (sandboxed iframe, opaque origin).
// Has no DOM, no web storage, no parent memory: only the Python runtime and the task data.
let py = null;
const MAX_OUT = 20000;
const HARNESS = `
import json, sys, traceback
def _line(tb):
    n = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == "<ваш код>":
            n = tb.tb_lineno
        tb = tb.tb_next
    return n
def _main():
    ns = {"__name__": "__main__"}
    try:
        exec(compile(USER_CODE, "<ваш код>", "exec"), ns)
    except BaseException as e:
        return {"phase": "load", "error": type(e).__name__ + ": " + str(e), "line": _line(e.__traceback__)}
    fn = ns.get(FUNC)
    if not callable(fn):
        return {"phase": "load", "error": "Функция " + FUNC + " не найдена: определите её через def " + FUNC + "(...)", "line": None}
    out = []
    for c in json.loads(CASES_JSON):
        item = {"name": c["name"], "args": c["args"], "expected": c.get("expected"), "custom": bool(c.get("custom"))}
        try:
            got = fn(*json.loads(json.dumps(c["args"])))
            try:
                got = json.loads(json.dumps(got))
            except Exception:
                got = repr(got)
            item["actual"] = got
            item["status"] = "info" if c.get("custom") else ("passed" if got == c.get("expected") else "failed")
        except BaseException as e:
            item["status"] = "error"
            item["error"] = type(e).__name__ + ": " + str(e)
            item["line"] = _line(e.__traceback__)
        out.append(item)
    return {"phase": "tests", "results": out}
RESULT = json.dumps(_main(), ensure_ascii=False)
`;

self.onmessage = async (e) => {
  const m = e.data;
  try {
    if (m.type === "init") {
      importScripts(m.base + "pyodide/pyodide.js");
      py = await loadPyodide({ indexURL: m.base + "pyodide/" });
      self.postMessage({ type: "ready" });
    } else if (m.type === "run") {
      let out = "", truncated = false;
      const sink = (s) => { if (out.length < MAX_OUT) out += s + "\n"; else truncated = true; };
      py.setStdout({ batched: sink });
      py.setStderr({ batched: sink });
      py.globals.set("USER_CODE", m.code);
      py.globals.set("FUNC", m.func);
      py.globals.set("CASES_JSON", JSON.stringify(m.cases));
      py.runPython(HARNESS);
      const result = JSON.parse(py.globals.get("RESULT"));
      self.postMessage({ type: "result", id: m.id, result, stdout: out.slice(0, MAX_OUT), truncated });
    }
  } catch (err) {
    self.postMessage({ type: "failure", id: m.id, message: String(err && err.message ? err.message : err) });
  }
};
