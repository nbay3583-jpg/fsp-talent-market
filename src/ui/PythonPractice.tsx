import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Card, Icon } from "./ui";

const MAX_CODE = 10000;
const TIME_LIMIT_MS = 8000;
const FUNC = "second_largest";

const STARTER = `def second_largest(nums):
    """Верните второе по величине РАЗЛИЧНОЕ число из списка nums
    или None, если такого числа нет."""
    pass
`;

interface Case { name: string; args: unknown[]; expected: unknown }
const BIG = Array.from({ length: 100000 }, (_, i) => i);
const CASES: Case[] = [
  { name: "обычный список", args: [[3, 1, 4, 1, 5]], expected: 4 },
  { name: "все числа одинаковые", args: [[10, 10, 10]], expected: null },
  { name: "один элемент", args: [[7]], expected: null },
  { name: "пустой список", args: [[]], expected: null },
  { name: "отрицательные числа", args: [[-1, -5, -3]], expected: -3 },
  { name: "повторы максимума", args: [[2, 2, 3, 3]], expected: 2 },
  { name: "большой список (100 000)", args: [BIG], expected: 99998 },
];

interface CaseResult { name: string; args: unknown[]; expected: unknown; actual?: unknown; status: "passed" | "failed" | "error" | "info"; error?: string; line?: number | null; custom?: boolean }
type Outcome =
  | { kind: "tests"; results: CaseResult[]; stdout: string; truncated: boolean }
  | { kind: "load"; error: string; line: number | null; stdout: string }
  | { kind: "timeout"; reason: string }
  | { kind: "failure"; message: string };

const KW = new Set(["def", "return", "if", "elif", "else", "for", "while", "in", "not", "and", "or", "is", "None", "True", "False", "import", "from", "as", "class", "try", "except", "finally", "raise", "with", "pass", "break", "continue", "lambda", "yield", "global"]);
const BUILTIN = new Set(["len", "max", "min", "sorted", "set", "list", "dict", "range", "sum", "print", "int", "str", "float", "enumerate", "zip", "abs", "reversed", "tuple"]);

function highlight(code: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z_0-9]*)/g;
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(code))) {
    if (m.index > last) out.push(code.slice(last, m.index));
    const [tok, com, str, num, word] = m;
    let cls = "";
    if (com) cls = "tok-c"; else if (str) cls = "tok-s"; else if (num) cls = "tok-n";
    else if (word && KW.has(word)) cls = "tok-k"; else if (word && BUILTIN.has(word)) cls = "tok-b";
    out.push(cls ? <span key={i++} className={cls}>{tok}</span> : tok);
    last = m.index + tok.length;
  }
  if (last < code.length) out.push(code.slice(last));
  return out;
}

function CodeEditor({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled?: boolean }) {
  const pre = useRef<HTMLPreElement>(null);
  const sync = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (pre.current) { pre.current.scrollTop = e.currentTarget.scrollTop; pre.current.scrollLeft = e.currentTarget.scrollLeft; }
  };
  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Tab") return;
    e.preventDefault();
    const t = e.currentTarget, s = t.selectionStart;
    onChange(value.slice(0, s) + "    " + value.slice(t.selectionEnd));
    requestAnimationFrame(() => { t.selectionStart = t.selectionEnd = s + 4; });
  };
  return (
    <div className="code-editor">
      <pre ref={pre} aria-hidden="true"><code>{highlight(value)}{"\n"}</code></pre>
      <textarea aria-label="Редактор кода Python" spellCheck={false} value={value} disabled={disabled} maxLength={MAX_CODE}
        onChange={(e) => onChange(e.target.value)} onScroll={sync} onKeyDown={onKey} />
    </div>
  );
}

const show = (v: unknown): string => (v === null || v === undefined ? "None" : typeof v === "string" ? JSON.stringify(v) : Array.isArray(v) && v.length > 12 ? `[…${v.length} элементов]` : JSON.stringify(v));
const showArgs = (a: unknown[]): string => a.map(show).join(", ");

export default function PythonPractice() {
  const [code, setCode] = useState(STARTER);
  const [custom, setCustom] = useState("");
  const [state, setState] = useState<"loading" | "ready" | "running" | "error">("loading");
  const [envErr, setEnvErr] = useState("");
  const [out, setOut] = useState<Outcome | null>(null);
  const [epoch, setEpoch] = useState(0);  // changing it destroys the sandbox iframe (hard kill)
  const frame = useRef<HTMLIFrameElement>(null);
  const runId = useRef(0);
  const watchdog = useRef<number | undefined>(undefined);

  const killSandbox = useCallback(() => { window.clearTimeout(watchdog.current); setEpoch((e) => e + 1); setState("loading"); }, []);

  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.source !== frame.current?.contentWindow) return;  // only our sandbox may talk to us
      const m = e.data ?? {};
      if (m.type === "status") {
        if (m.state === "error") { setState("error"); setEnvErr(String(m.message ?? "")); } else setState(m.state);
      } else if (m.id === runId.current) {
        window.clearTimeout(watchdog.current);
        if (m.type === "result") {
          const r = m.result;
          setOut(r.phase === "load" ? { kind: "load", error: r.error, line: r.line, stdout: m.stdout }
            : { kind: "tests", results: r.results, stdout: m.stdout, truncated: m.truncated });
          setState("ready");
        } else if (m.type === "timeout") { setOut({ kind: "timeout", reason: m.reason }); setState("loading"); }
        else if (m.type === "failure") { setOut({ kind: "failure", message: m.message }); setState("ready"); }
      }
    };
    window.addEventListener("message", onMsg);
    return () => { window.removeEventListener("message", onMsg); window.clearTimeout(watchdog.current); };
  }, []);

  const run = () => {
    if (state !== "ready" || code.length > MAX_CODE) return;
    const cases: unknown[] = [...CASES];
    if (custom.trim()) {
      try {
        const parsed = JSON.parse(custom);
        if (!Array.isArray(parsed)) throw new Error("not a list");
        cases.push({ name: "ваш ввод", args: [parsed], expected: null, custom: true });
      } catch { setOut({ kind: "failure", message: "Своё входное значение должно быть JSON-списком, например [3, 1, 4]." }); return; }
    }
    const id = ++runId.current;
    setOut(null); setState("running");
    frame.current?.contentWindow?.postMessage({ type: "run", id, code, func: FUNC, cases, timeoutMs: TIME_LIMIT_MS }, "*");
    // fallback: if the sandbox itself is frozen, destroy it from here
    window.clearTimeout(watchdog.current);
    watchdog.current = window.setTimeout(() => { setOut({ kind: "timeout", reason: "time" }); killSandbox(); }, TIME_LIMIT_MS + 15000);
  };
  const stop = () => {
    window.clearTimeout(watchdog.current);
    frame.current?.contentWindow?.postMessage({ type: "kill" }, "*");
    runId.current++;
    setOut({ kind: "timeout", reason: "user" });
    killSandbox();  // belt and braces: the whole iframe is replaced
  };

  const tests = out?.kind === "tests" ? out.results.filter((r) => !r.custom) : [];
  const passed = tests.filter((r) => r.status === "passed").length;
  const customRes = out?.kind === "tests" ? out.results.find((r) => r.custom) : undefined;
  const statusText = useMemo(() => ({ loading: "Загрузка среды Python…", ready: "Среда готова", running: "Выполняется…", error: "Среда недоступна" }[state]), [state]);

  return (
    <div className="stack">
      <Card title="Практика Python: второе по величине число" aside={<Badge tone="muted">самопроверка, не сертификат</Badge>}>
        <p style={{ marginTop: 0 }}>
          Напишите функцию <code>second_largest(nums)</code>: она принимает список целых чисел и возвращает <b>второе по величине различное число</b>.
          Если такого числа нет (пустой список, один элемент, все числа одинаковые), верните <code>None</code>.
        </p>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Код выполняется только в вашем браузере, в изолированной среде без доступа к вашему аккаунту. На сервер он не отправляется,
          результат не сохраняется, не влияет на грейд и не является независимой сертификацией.
        </p>
      </Card>

      <Card title="Редактор" aside={<span className={`env-state ${state}`} role="status">{statusText}</span>}>
        <CodeEditor value={code} onChange={setCode} disabled={state === "running"} />
        <div className="code-meta muted">{code.length} / {MAX_CODE} символов · лимит времени {TIME_LIMIT_MS / 1000} с · вывод ограничен 20 000 символов</div>
        <label className="custom-input">
          <span>Своё входное значение (необязательно, JSON-список)</span>
          <input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="[3, 1, 4, 1, 5]" inputMode="text" />
        </label>
        <div className="row" style={{ marginTop: 12, gap: 10, flexWrap: "wrap" }}>
          <button className="primary" onClick={run} disabled={state !== "ready" || code.length > MAX_CODE}><Icon name="bolt" size={15} />Запустить код</button>
          <button onClick={stop} disabled={state !== "running"}>Остановить</button>
          <button onClick={() => { setCode(STARTER); setOut(null); }} disabled={state === "running"}>Сбросить код</button>
        </div>
        {state === "error" && <p className="warn" role="alert">Не удалось загрузить среду Python: {envErr || "неизвестная ошибка"}. Обновите страницу.</p>}
        <iframe key={epoch} ref={frame} title="Изолированная среда Python" src="/sandbox/runner.html" sandbox="allow-scripts"
          style={{ display: "none" }} aria-hidden="true" />
      </Card>

      <Card title="Результат">
        {!out && <p className="muted" style={{ margin: 0 }}>Нажмите «Запустить код»: выполнится ваша функция и {CASES.length} автоматических проверок.</p>}
        {out?.kind === "timeout" && (
          <p className="warn" role="alert">
            {out.reason === "user" ? "Выполнение остановлено вами." : `Превышен лимит времени ${TIME_LIMIT_MS / 1000} с — выполнение принудительно завершено.`}
            {out.reason !== "user" && " Проверьте, нет ли бесконечного цикла или слишком медленного алгоритма."} Среда перезапускается.
          </p>)}
        {out?.kind === "failure" && <p className="warn" role="alert">{out.message}</p>}
        {out?.kind === "load" && (
          <div role="alert">
            <p className="warn" style={{ margin: 0 }}>Код не удалось выполнить{out.line ? ` (строка ${out.line})` : ""}: <code>{out.error}</code></p>
            {out.stdout && <pre className="code-out">{out.stdout}</pre>}
          </div>)}
        {out?.kind === "tests" && (
          <>
            <p className={passed === tests.length ? "ok" : "warn"} style={{ margin: "0 0 10px", fontWeight: 600 }}>
              {passed === tests.length ? "Все проверки пройдены" : `Пройдено ${passed} из ${tests.length}`}
            </p>
            <p className="muted" style={{ margin: "0 0 10px", fontSize: 13 }}>
              {passed === tests.length
                ? "Отлично: ваша реализация учла все граничные случаи. Это самопроверка в браузере — на грейд она не влияет."
                : "Посмотрите на непройденные проверки: чаще всего ошибка в повторяющихся значениях, пустом списке или отрицательных числах."}
            </p>
            <ul className="test-list">
              {tests.map((r, i) => (
                <li key={i} className={`t-${r.status}`}>
                  <span className="t-mark" aria-hidden="true">{r.status === "passed" ? "✓" : "✗"}</span>
                  <div>
                    <b>{r.name}</b> — {r.status === "passed" ? "пройдена" : r.status === "failed" ? "не пройдена" : "ошибка выполнения"}
                    <small>Вход: <code>{showArgs(r.args)}</code> · ожидалось: <code>{show(r.expected)}</code>
                      {r.status !== "error" && <> · получено: <code>{show(r.actual)}</code></>}</small>
                    {r.status === "error" && <small className="warn">{r.error}{r.line ? ` (строка ${r.line})` : ""}</small>}
                  </div>
                </li>))}
            </ul>
            {customRes && (
              <p style={{ margin: "10px 0 0" }}>Ваш ввод <code>{showArgs(customRes.args)}</code> →{" "}
                {customRes.status === "error" ? <span className="warn">{customRes.error}</span> : <code>{show(customRes.actual)}</code>}</p>)}
            {out.stdout && (<><h4>Вывод программы</h4><pre className="code-out">{out.stdout}{out.truncated ? "\n… вывод обрезан" : ""}</pre></>)}
          </>)}
      </Card>
    </div>
  );
}
