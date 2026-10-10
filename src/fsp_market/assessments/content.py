"""Core Assessment content for Backend / Python (rubric version RUBRIC_VERSION).

Structure: Task Family -> Template (task format) -> verified Parameter Preset -> Variant.

* Everything user-facing is Russian; technical names (FastAPI, SELECT, HTTP, Docker, pytest) are kept.
* Variants are produced DETERMINISTICALLY at seed time: every generator is a pure function of
  (family code, preset index). No LLM, no runtime randomness, no user code is ever executed.
* The correct answer is not typed by hand where it can be computed: Python snippets are run with
  `exec` (our own trusted text, at seed time), SQL is run on generated data in an in-memory SQLite,
  and generators refuse to emit a variant whose correct option is not unique.
* A preset only changes the subject context / names / numbers / edge case; a family keeps one
  competency, difficulty band, rubric and scoring contract.

This is a curated MVP bank, not a calibrated item pool (no IRT, no anchor calibration).
"""

from __future__ import annotations

import contextlib
import io
import math
import random
import sqlite3
import traceback
from collections.abc import Callable
from typing import Any

RUBRIC_VERSION = "backend-core-2026.10.2"
SPECIALIZATION = {"code": "backend_python", "name": "Backend / Python"}
COMPETENCIES = [
    {"code": "python", "name": "Python"},
    {"code": "sql", "name": "SQL"},
    {"code": "api_fastapi", "name": "FastAPI"},
    {"code": "testing", "name": "Testing"},
    {"code": "docker_basics", "name": "Docker Basics"},
    {"code": "system_thinking", "name": "System Thinking"},
]
LETTERS = "ABCD"

# Time budget (seconds) for one attempt: 11 tasks per grade. Server-side `deadline_at` is derived
# from this table (see assessments/service.py).
TIME_LIMIT_SECONDS = {"JUNIOR": 15 * 60, "MIDDLE": 19 * 60, "SENIOR": 23 * 60}


# ------------------------------------------------------------------ helpers


def run_py(code: str) -> str:
    """Run OUR OWN task snippet and return its stdout (seed-time only, never user input)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<task>", "exec"), {"__name__": "__task__"})  # noqa: S102
    return buf.getvalue().strip()


def run_py_safe(code: str) -> str:
    try:
        return run_py(code)
    except Exception as exc:  # noqa: BLE001 - a mutant may legitimately crash: its outcome is a distractor
        return type(exc).__name__


def failing_line(code: str) -> tuple[str, int]:
    """(exception name, line number inside <task>) of the first uncaught error in `code`."""
    try:
        run_py(code)
    except Exception as exc:  # noqa: BLE001 - any task error is data here
        frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<task>"]
        if frames:
            return type(exc).__name__, frames[-1].lineno
    raise AssertionError("snippet did not fail")


def make_options(rng: random.Random, correct: str, wrongs: list[str]) -> tuple[dict[str, str], str]:
    uniq: list[str] = []
    for w in wrongs:
        if w != correct and w not in uniq:
            uniq.append(w)
    if len(uniq) < 3:
        raise ValueError(f"not enough distinct distractors for {correct!r}: {uniq}")
    chosen = uniq[:3] if len(uniq) == 3 else rng.sample(uniq, 3)
    items = [correct, *chosen]
    rng.shuffle(items)
    options = {LETTERS[i]: items[i] for i in range(4)}
    return options, LETTERS[items.index(correct)]


def pad_numeric(correct: str, extra: list[str]) -> list[str]:
    """Numeric neighbours as last-resort distractors."""
    out = list(extra)
    try:
        n = int(correct)
        out += [str(n + 1), str(n - 1), str(n + 2), str(n * 2)]
    except ValueError:
        out += [correct.lower(), correct.upper(), correct.title(), correct[::-1], "ошибка выполнения"]
    return out


def pad_lines(correct: str, wrongs: list[str]) -> list[str]:
    """Plausible wrong traces: the same events in another order / with one step missing."""
    parts = correct.split(", ")
    extra = [", ".join(reversed(parts)), ", ".join(parts[1:]), ", ".join(parts[:-1]),
             ", ".join(parts[:1] + parts[:1] + parts[1:])]
    return [w for w in [*wrongs, *extra] if w and w != correct]


def choice(
    rng: random.Random, correct: str, wrongs: list[str], dimension: str, **placeholders: Any
) -> dict[str, Any]:
    options, key = make_options(rng, correct, wrongs)
    return {"options": options, "correct": key, "dimension": dimension, **placeholders}


def _sqlite(setup: list[str], query: str) -> list[tuple]:
    conn = sqlite3.connect(":memory:")
    try:
        for stmt in setup:
            conn.execute(stmt)
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def _table_text(header: list[str], rows: list[tuple]) -> str:
    widths = [max(len(str(x)) for x in [h, *[r[i] for r in rows]]) for i, h in enumerate(header)]
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*header), "-+-".join("-" * w for w in widths)]
    lines += [fmt.format(*[str(c) for c in r]) for r in rows]
    return "\n".join(lines)


# ------------------------------------------------------------------ JUNIOR


def j_python_output(rng: random.Random, i: int) -> dict[str, Any]:
    kind = ("arith", "slice", "string", "cond")[i % 4]
    v1, v2 = rng.sample(["total", "count", "value", "acc", "n", "step"], 2)
    if kind == "arith":
        a, b, c = rng.randint(17, 60), rng.randint(2, 6), rng.randint(2, 9)
        code = f"{v1} = {a}\n{v2} = {v1} // {b}\nprint({v2} % {c})"
        mutants = [
            f"{v1} = {a}\n{v2} = {v1} / {b}\nprint({v2} % {c})",
            f"{v1} = {a}\n{v2} = {v1} % {b}\nprint({v2} // {c})",
            f"{v1} = {a}\n{v2} = {v1} // {c}\nprint({v2} % {b})",
        ]
        dim = "арифметика"
    elif kind == "slice":
        xs = rng.sample(range(2, 60), 6)
        s, e = rng.randint(1, 2), rng.randint(3, 5)
        code = f"items = {xs}\nprint(items[{s}:{e}])"
        mutants = [
            f"items = {xs}\nprint(items[{s}:{e + 1}])",
            f"items = {xs}\nprint(items[{s - 1}:{e}])",
            f"items = {xs}\nprint(items[{e}:])",
        ]
        dim = "срезы и списки"
    elif kind == "string":
        w1, w2 = rng.sample(["fast", "api", "docker", "query", "token", "cache", "queue"], 2)
        code = f's = "{w1} {w2}"\nprint(s.split()[1].upper())'
        mutants = [
            f's = "{w1} {w2}"\nprint(s.split()[0].upper())',
            f's = "{w1} {w2}"\nprint(s.split()[1].title())',
            f's = "{w1} {w2}"\nprint(s.upper())',
        ]
        dim = "строки"
    else:
        x, t = rng.randint(3, 20), rng.randint(3, 20)
        body = '    print("больше")\nelif x == {t}:\n    print("равно")\nelse:\n    print("меньше")'
        code = f"x = {x}\nif x > {t}:\n" + body.format(t=t)
        mutants = [
            f"x = {x}\nif x >= {t}:\n" + body.format(t=t),
            f"x = {x + 7}\nif x > {t}:\n" + body.format(t=t),
            f"x = {t}\nif x > {t}:\n" + body.format(t=t),
            f"x = {max(1, t - 2)}\nif x > {t}:\n" + body.format(t=t),
        ]
        dim = "условия"
    correct = run_py(code)
    wrongs = pad_numeric(correct, [run_py_safe(m) for m in mutants])
    if kind == "cond":
        wrongs = [w for w in ["больше", "равно", "меньше", "ошибка выполнения"] if w != correct]
    return choice(rng, correct, wrongs, dim, snippet=code)


_J_BUG_TEMPLATES = ("name", "types", "index")


def j_python_bug(rng: random.Random, i: int) -> dict[str, Any]:
    kind = _J_BUG_TEMPLATES[i % 3]
    fn, p, acc, it = rng.choice(
        [("total_price", "prices", "total", "p"), ("sum_scores", "scores", "result", "s"),
         ("count_bytes", "chunks", "size", "c"), ("add_all", "numbers", "acc", "x")]
    )
    xs = [rng.randint(1, 9) for _ in range(3)]
    if kind == "name":
        lines = [f"def {fn}({p}):", f"    {acc} = 0", f"    for {it} in {p}:",
                 f"        {acc} += {it}", f"    return {acc}s", "", f"print({fn}({xs}))"]
    elif kind == "types":
        lines = [f"def {fn}({p}):", f"    {acc} = 0", f"    for {it} in {p}:",
                 f"        {acc} += {it}", f'    return "Итого: " + {acc}', "", f"print({fn}({xs}))"]
    else:
        lines = [f"def {fn}({p}):", f"    {acc} = 0", f"    for k in range(len({p}) + 1):",
                 f"        {acc} += {p}[k]", f"    return {acc}", "", f"print({fn}({xs}))"]
    code = "\n".join(lines)
    err, line_no = failing_line(code)
    numbered = "\n".join(f"{n}: {t}" for n, t in enumerate(lines, 1))
    candidates = [n for n in range(1, len(lines) + 1) if lines[n - 1].strip() and n != line_no]
    wrongs = [f"Строка {n}" for n in candidates]
    return choice(
        rng, f"Строка {line_no}", wrongs, "поиск ошибки", snippet=numbered, error=err
    )


_TABLES = [
    ("users", "возраст", "age", "город", "city", ["Москва", "Казань", "Самара"]),
    ("orders", "сумма", "amount", "статус", "status", ["paid", "new", "canceled"]),
    ("tickets", "приоритет", "priority", "состояние", "state", ["open", "closed", "waiting"]),
    ("payments", "сумма", "sum", "тип", "kind", ["card", "cash", "sbp"]),
]


def j_sql_select(rng: random.Random, i: int) -> dict[str, Any]:
    t, num_ru, num, txt_ru, txt, values = _TABLES[i % len(_TABLES)]
    thr, val = rng.choice([10, 18, 25, 100, 500, 1000]), rng.choice(values)
    where = f"{num} > {thr} AND {txt} = '{val}'"
    correct = f"SELECT * FROM {t} WHERE {where}"
    wrongs = [
        f"SELECT * FROM {t} WHERE {num} > {thr} OR {txt} = '{val}'",
        f"SELECT * FROM {t} WHERE {num} < {thr} AND {txt} = '{val}'",
        f"SELECT * FROM {t} WHERE {num} > {thr} AND {txt} != '{val}'",
        f"SELECT * FROM {t} WHERE {num} = {thr} AND {txt} = '{val}'",
    ]
    setup = [f"CREATE TABLE {t}(id INTEGER, {num} INTEGER, {txt} TEXT)"]
    for q in [correct, *wrongs]:  # every option must at least be valid SQL
        _sqlite(setup, q)
    return choice(
        rng, correct, wrongs, "условия выборки",
        table=t, num_ru=num_ru, num=num, thr=thr, txt_ru=txt_ru, txt=txt, val=val,
    )


def j_sql_count(rng: random.Random, i: int) -> dict[str, Any]:
    t, _num_ru, num, _txt_ru, txt, values = _TABLES[(i + 1) % len(_TABLES)]
    rows = [(n, rng.choice([5, 12, 20, 45, 80, 120, 300]), rng.choice(values)) for n in range(1, 9)]
    thr, val = rng.choice([10, 20, 50]), values[0]
    kind = i % 3
    agg = ["COUNT(*)", f"SUM({num})", f"COUNT(DISTINCT {txt})"][kind]
    where = f"{txt} = '{val}'" if kind != 2 else f"{num} >= {thr}"
    query = f"SELECT {agg} FROM {t} WHERE {where}"
    setup = [f"CREATE TABLE {t}(id INTEGER, {num} INTEGER, {txt} TEXT)"]
    setup += [f"INSERT INTO {t} VALUES ({a}, {b}, '{c}')" for a, b, c in rows]
    answer = _sqlite(setup, query)[0][0] or 0
    return {
        "type": "numeric", "correct": answer, "tolerance": 0, "dimension": "агрегаты",
        "options": None, "query": query, "table": t,
        "data": _table_text(["id", num, txt], rows),
    }


_HTTP = [
    ("POST", "{r}", "клиент отправил корректное тело, ресурс создан", "201 Created"),
    ("GET", "{r}/{id}", "ресурса с таким id нет", "404 Not Found"),
    ("DELETE", "{r}/{id}", "ресурс удалён, тело ответа пустое", "204 No Content"),
    ("GET", "{r}", "запрос без токена к защищённому эндпоинту", "401 Unauthorized"),
    ("POST", "{r}", "тело запроса не прошло валидацию Pydantic в FastAPI", "422 Unprocessable Entity"),
    ("GET", "{r}/{id}", "пользователь авторизован, но не имеет прав на этот ресурс", "403 Forbidden"),
    ("GET", "{r}", "список успешно возвращён", "200 OK"),
]
_RESOURCES = ["orders", "users", "invoices", "tickets", "products", "reports"]


def j_api_status(rng: random.Random, i: int) -> dict[str, Any]:
    method, path, situation, code = _HTTP[i % len(_HTTP)]
    res = _RESOURCES[(i * 5 + rng.randint(0, 2)) % len(_RESOURCES)]
    endpoint = f"{method} /" + path.format(r=res, id="42")
    wrongs = [c for _, _, _, c in _HTTP if c != code]
    return choice(rng, code, wrongs, "коды ответа HTTP", endpoint=endpoint, situation=situation)


def j_testing_outcome(rng: random.Random, i: int) -> dict[str, Any]:
    fn = rng.choice(["add", "plus", "merge_sum"])
    a, b = rng.randint(2, 30), rng.randint(2, 30)
    kind = i % 4
    func = f"def {fn}(x, y):\n    return x + y"
    if kind == 0:
        test = f"assert {fn}({a}, {b}) == {a + b}"
    elif kind == 1:
        test = f"assert {fn}({a}, {b}) == {a + b + rng.randint(1, 3)}"
    elif kind == 2:
        test = f'assert {fn}({a}, "{b}") == {a + b}'
    else:
        test = f"assert {fn}x({a}, {b}) == {a + b}"
    probe = f"{func}\ntry:\n    {test}\nexcept Exception as e:\n    print(type(e).__name__)\nelse:\n    print('OK')"
    outcome = run_py(probe)
    names = {
        "OK": "Тест пройдёт",
        "AssertionError": "Тест упадёт с AssertionError",
        "TypeError": "Тест упадёт с TypeError",
        "NameError": "Тест упадёт с NameError",
    }
    correct = names[outcome]
    return choice(
        rng, correct, [v for v in names.values() if v != correct], "чтение теста",
        func=func, test=test,
    )


_DOCKER_INSTR = {
    "FROM": "Задаёт базовый образ, на основе которого строится новый образ",
    "RUN": "Выполняет команду при сборке образа и сохраняет результат в новом слое",
    "CMD": "Задаёт команду по умолчанию, которая запускается при старте контейнера",
    "COPY": "Копирует файлы из контекста сборки в файловую систему образа",
    "EXPOSE": "Документирует порт приложения в контейнере (сам по себе не публикует порт на хосте)",
    "WORKDIR": "Задаёт рабочую директорию для следующих инструкций и для запуска контейнера",
    "ENV": "Задаёт переменную окружения, доступную при сборке и в запущенном контейнере",
}


def j_docker_instruction(rng: random.Random, i: int) -> dict[str, Any]:
    instr = list(_DOCKER_INSTR)[i % len(_DOCKER_INSTR)]
    wrongs = [v for k, v in _DOCKER_INSTR.items() if k != instr]
    return choice(rng, _DOCKER_INSTR[instr], wrongs, "инструкции Dockerfile", instr=instr)


_SYS_TERMS = {
    "индекс в базе данных": "Ускоряет поиск и фильтрацию строк за счёт дополнительной структуры данных",
    "кэш": "Хранит результат дорогой операции, чтобы не вычислять его повторно при тех же запросах",
    "очередь сообщений": "Позволяет передать работу другому процессу и обработать её асинхронно, вне запроса",
    "транзакция": "Объединяет несколько операций так, что они применяются целиком или не применяются вовсе",
    "балансировщик нагрузки": "Распределяет входящие запросы между несколькими экземплярами сервиса",
    "миграция схемы БД": "Версионированное и повторяемое изменение структуры базы данных",
    "healthcheck": "Позволяет внешней системе проверить, что сервис жив и готов принимать запросы",
}


def j_system_term(rng: random.Random, i: int) -> dict[str, Any]:
    term = list(_SYS_TERMS)[i % len(_SYS_TERMS)]
    wrongs = [v for k, v in _SYS_TERMS.items() if k != term]
    return choice(rng, _SYS_TERMS[term], wrongs, "базовые понятия", term=term)


# ------------------------------------------------------------------ MIDDLE


def m_python_output(rng: random.Random, i: int) -> dict[str, Any]:
    kind = ("default", "alias", "closure", "counter")[i % 4]
    if kind == "default":
        fn = rng.choice(["collect", "push_item", "register"])
        x1, x2 = rng.sample(range(1, 90), 2)
        code = (f"def {fn}(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n\n"
                f"{fn}({x1})\nprint({fn}({x2}))")
        mutants = [code.replace("bucket=[]", "bucket=None").replace(
            "    bucket.append(item)", "    bucket = bucket or []\n    bucket.append(item)"),
            code.replace(f"print({fn}({x2}))", f"print(len({fn}({x2})))"),
            code.replace(f"{fn}({x1})\n", "")]
        dim = "изменяемые аргументы"
    elif kind == "alias":
        a, b = rng.sample(["xs", "data", "rows", "queue"], 2)
        n = [rng.randint(1, 9) for _ in range(3)]
        code = (f"{a} = {n}\n{b} = {a}\n{b}.append(0)\nc = {a}[:]\nc.append(1)\n"
                f"print(len({a}), len(c))")
        mutants = [code.replace(f"{b} = {a}\n", f"{b} = {a}[:]\n"),
                   code.replace("c = " + a + "[:]", "c = " + a),
                   code.replace(f"{b}.append(0)\n", "")]
        dim = "ссылки и копии"
    elif kind == "closure":
        k, m = rng.randint(3, 5), rng.randint(2, 6)
        code = f"funcs = []\nfor i in range({k}):\n    funcs.append(lambda: i * {m})\nprint([f() for f in funcs])"
        mutants = [code.replace("lambda: i", "lambda i=i: i"),
                   code.replace("print([f() for f in funcs])", "print(len(funcs))"),
                   code.replace(f"range({k})", f"range({k - 1})")]
        dim = "замыкания"
    else:
        ws = rng.sample(["api", "db", "cache", "queue", "auth", "cron"], 3)
        code = (f's = "{ws[0]} {ws[1]} {ws[0]} {ws[2]} {ws[0]} {ws[1]}"\ncounts = {{}}\n'
                f"for w in s.split():\n    counts[w] = counts.get(w, 0) + 1\n"
                f'print(counts["{ws[0]}"], len(counts))')
        mutants = [code.replace('counts.get(w, 0) + 1', '1'),
                   code.replace(f'counts["{ws[0]}"]', f'counts["{ws[1]}"]'),
                   code.replace("len(counts)", "len(s.split())")]
        dim = "словари и итерация"
    correct = run_py(code)
    wrongs = [run_py_safe(m) for m in mutants]
    if len(set(wrongs) - {correct}) < 3:
        wrongs += pad_numeric(correct, [])
    return choice(rng, correct, wrongs, dim, snippet=code)


def m_python_exceptions(rng: random.Random, i: int) -> dict[str, Any]:
    kind = i % 3
    fn = rng.choice(["job", "step", "handler"])
    if kind == 0:
        exc = ["ValueError", "KeyError", "TypeError"][(i // 3) % 3]
        code = (f"def {fn}():\n    try:\n        print('try')\n        raise {exc}('x')\n"
                "    except KeyError:\n        print('key')\n    except ValueError:\n        print('value')\n"
                "    else:\n        print('else')\n    finally:\n        print('finally')\n\n"
                f"try:\n    {fn}()\nexcept Exception as e:\n    print(type(e).__name__)")
        mutants = [code.replace(f"raise {exc}('x')", "pass"),
                   code.replace("    finally:\n        print('finally')\n", ""),
                   code.replace("    else:\n        print('else')\n", "")]
    elif kind == 1:
        a, b = rng.sample(["ok", "done", "saved", "sent"], 2)
        code = (f"def {fn}():\n    try:\n        return '{a}'\n    finally:\n        print('{b}')\n\n"
                f"print({fn}())")
        mutants = [code.replace("        return '" + a + "'", "        pass"),
                   code.replace("print('" + b + "')", "return '" + b + "'"),
                   code.replace("    finally:", "    except Exception:")]
    else:
        n = rng.randint(2, 4)
        code = (f"def {fn}(n):\n    for i in range(n):\n        try:\n            if i == 1:\n"
                "                continue\n            print(i)\n        finally:\n            print('f')\n\n"
                f"{fn}({n})")
        mutants = [code.replace("continue", "break"), code.replace("i == 1", "i == 0"),
                   code.replace("        finally:\n            print('f')\n", "        finally:\n            pass\n")]
    fmt = lambda s: s.replace("\n", ", ")
    correct = fmt(run_py(code))
    wrongs = pad_lines(correct, [fmt(run_py_safe(m)) for m in mutants])
    return choice(rng, correct, wrongs, "порядок выполнения", snippet=code)


def m_sql_join_numeric(rng: random.Random, i: int) -> dict[str, Any]:
    names = rng.sample(["Анна", "Борис", "Вера", "Глеб", "Дарья"], 4)
    customers = [(n + 1, nm) for n, nm in enumerate(names)]
    orders = [(k + 1, rng.randint(1, 3), rng.choice([40, 90, 150, 220, 310])) for k in range(7)]
    kind = i % 3
    setup = ["CREATE TABLE customers(id INTEGER, name TEXT)",
             "CREATE TABLE orders(id INTEGER, customer_id INTEGER, amount INTEGER)"]
    setup += [f"INSERT INTO customers VALUES ({a}, '{b}')" for a, b in customers]
    setup += [f"INSERT INTO orders VALUES ({a}, {b}, {c})" for a, b, c in orders]
    if kind == 0:
        query = ("SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o "
                 "ON o.customer_id = c.id GROUP BY c.name")
        ask = "Сколько строк вернёт запрос?"
    elif kind == 1:
        query = ("SELECT c.name, COUNT(o.id) FROM customers c LEFT JOIN orders o "
                 "ON o.customer_id = c.id GROUP BY c.name")
        ask = "Сколько строк вернёт запрос?"
    else:
        t = rng.choice([100, 200, 300])
        query = ("SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.id "
                 f"GROUP BY c.name HAVING SUM(o.amount) > {t}")
        ask = "Сколько строк вернёт запрос?"
    answer = len(_sqlite(setup, query))
    return {
        "type": "numeric", "correct": answer, "tolerance": 0, "dimension": "соединения и группировка",
        "options": None, "query": query, "ask": ask,
        "customers": _table_text(["id", "name"], customers),
        "orders": _table_text(["id", "customer_id", "amount"], orders),
    }


def m_sql_having(rng: random.Random, i: int) -> dict[str, Any]:
    for attempt in range(40):
        t = rng.choice([100, 200, 300, 400])
        rows = [(k + 1, rng.randint(1, 4), rng.choice([40, 90, 150, 220])) for k in range(9)]
        setup = ["CREATE TABLE orders(id INTEGER, customer_id INTEGER, amount INTEGER)"]
        setup += [f"INSERT INTO orders VALUES ({a}, {b}, {c})" for a, b, c in rows]
        correct = (f"SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id "
                   f"HAVING SUM(amount) > {t}")
        wrongs = [
            f"SELECT customer_id, SUM(amount) FROM orders WHERE SUM(amount) > {t} GROUP BY customer_id",
            f"SELECT customer_id, SUM(amount) FROM orders WHERE amount > {t} GROUP BY customer_id",
            f"SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id HAVING COUNT(*) > {t // 100}",
            f"SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id ORDER BY SUM(amount) > {t}",
        ]
        good = set(_sqlite(setup, correct))
        distinct = 0
        for w in wrongs:
            try:
                same = set(_sqlite(setup, w)) == good
            except sqlite3.Error:
                same = False
            distinct += not same
        if distinct == len(wrongs) and good:
            return choice(rng, correct, wrongs, "агрегаты и HAVING", t=t)
    raise RuntimeError("could not build a unique HAVING task")


_FACTS = {
    "FastAPI": [
        (True, "Тело запроса, описанное Pydantic-моделью, валидируется автоматически, при ошибке возвращается 422"),
        (True, "Зависимости объявляются через `Depends` и могут переиспользоваться между эндпоинтами"),
        (True, "`response_model` ограничивает набор полей, которые попадут в ответ"),
        (True, "Схема OpenAPI по умолчанию доступна по пути `/openapi.json`"),
        (True, "Эндпоинт, объявленный через `def`, выполняется в пуле потоков, а не блокирует event loop"),
        (True, "`HTTPException(status_code=404)` приводит к ответу с кодом 404"),
        (True, "Параметры пути объявляются в фигурных скобках в строке пути и в аргументах функции"),
        (False, "FastAPI не работает без Django ORM"),
        (False, "Ошибка валидации тела запроса возвращается клиенту с кодом 200"),
        (False, "Валидация входных данных в FastAPI выполняется только на стороне клиента"),
        (False, "Query-параметр нельзя сделать необязательным"),
        (False, "`async def` эндпоинт всегда выполняется в отдельном процессе"),
        (False, "Документация `/docs` появляется только после ручной установки Swagger UI"),
    ]
}
_FACTS_SENIOR = [
    (True, "`PUT` по спецификации HTTP идемпотентен: повторный одинаковый запрос не меняет результат"),
    (True, "Ключ идемпотентности позволяет безопасно повторить `POST` оплаты после сетевой ошибки"),
    (True, "Курсорная пагинация устойчивее к вставкам новых строк, чем пагинация по смещению (offset)"),
    (True, "Код 401 означает отсутствие или недействительность аутентификации, 403 — отказ в правах"),
    (True, "Код 429 используется для ограничения частоты запросов (rate limiting)"),
    (True, "Заголовок `ETag` вместе с `If-None-Match` позволяет вернуть 304 без тела"),
    (True, "`PATCH` предназначен для частичного изменения ресурса"),
    (False, "`GET`-запрос допустимо использовать для изменения состояния, это не нарушает семантику HTTP"),
    (False, "Автоматически повторять любой `POST` после таймаута всегда безопасно"),
    (False, "Код 403 следует возвращать, когда токен просрочен"),
    (False, "Пагинация по смещению (offset) всегда быстрее курсорной на больших таблицах"),
    (False, "Заголовок `ETag` нужен только для шифрования ответа"),
    (False, "Код 200 с описанием ошибки в теле — рекомендуемый способ сообщать о сбое сервера"),
]


def _fact_task(rng: random.Random, bank: list[tuple[bool, str]], dimension: str) -> dict[str, Any]:
    true_n = rng.choice([2, 3])
    trues = rng.sample([t for ok, t in bank if ok], true_n)
    falses = rng.sample([t for ok, t in bank if not ok], 5 - true_n)
    items = [(True, t) for t in trues] + [(False, t) for t in falses]
    rng.shuffle(items)
    letters = "ABCDE"
    options = {letters[k]: text for k, (_, text) in enumerate(items)}
    correct = [letters[k] for k, (ok, _) in enumerate(items) if ok]
    return {"type": "set", "options": options, "correct": correct, "dimension": dimension}


def m_api_statements(rng: random.Random, i: int) -> dict[str, Any]:
    return _fact_task(rng, _FACTS["FastAPI"], "основы FastAPI")


def m_testing_edge(rng: random.Random, i: int) -> dict[str, Any]:
    kind = i % 4
    if kind == 0:
        size = rng.choice([5, 10, 20])
        ref = f"def pages(total):\n    return -(-total // {size})"
        bug = f"def pages(total):\n    return total // {size}"
        inputs = [size * 2, size * 5, size * 3 + rng.randint(1, size - 1), size * 8]
        what = f"количество страниц при размере страницы {size}"
    elif kind == 1:
        age = rng.choice([16, 18, 21])
        ref = f"def allowed(age):\n    return age >= {age}"
        bug = f"def allowed(age):\n    return age > {age}"
        inputs = [age - 6, age + 12, age, age + 30]
        what = f"допуск при возрасте не менее {age}"
    elif kind == 2:
        limit = rng.choice([1000, 3000, 5000])
        ref = f"def free_shipping(total):\n    return total >= {limit}"
        bug = f"def free_shipping(total):\n    return total > {limit}"
        inputs = [limit // 2, limit * 2, limit, limit + 1500]
        what = f"бесплатная доставка от {limit}"
    else:
        ref = "def mean(xs):\n    return sum(xs) / len(xs) if xs else 0.0"
        bug = "def mean(xs):\n    return sum(xs) / len(xs)"
        inputs = [[1, 2, 3], [10], [4, 6, 8, 10], []]
        what = "среднее значение списка (для пустого списка ожидается 0.0)"
    name = ref.split("(")[0].split()[-1]

    def out(src: str, x: Any) -> str:
        return run_py_safe(f"{src}\nprint({name}({x!r}))")

    differing = [x for x in inputs if out(ref, x) != out(bug, x)]
    assert len(differing) == 1, (kind, inputs, differing)
    correct = repr(differing[0])
    wrongs = [repr(x) for x in inputs if x != differing[0]]
    return choice(rng, correct, wrongs, "граничные значения", what=what, code=bug, ref=ref)


def m_docker_compose(rng: random.Random, i: int) -> dict[str, Any]:
    kind = i % 3
    svc = rng.choice(["api", "web", "worker", "backend"])
    db = rng.choice(["db", "postgres", "database"])
    if kind == 0:
        host, cont = rng.choice([(8080, 8000), (9000, 80), (8081, 3000), (5433, 5432)])
        correct = f"localhost:{host}"
        wrongs = [f"localhost:{cont}", f"{svc}:{host}", f"{svc}:{cont}"]
        return choice(rng, correct, wrongs, "порты и сети compose", kind="port",
                      svc=svc, host=host, cont=cont, db=db)
    if kind == 1:
        port = rng.choice([5432, 3306, 6379])
        correct = f"{db}:{port}"
        wrongs = [f"localhost:{port}", f"127.0.0.1:{port}", f"{svc}:{port}"]
        return choice(rng, correct, wrongs, "порты и сети compose", kind="dns",
                      svc=svc, host=0, cont=port, db=db)
    correct = "Данные останутся в именованном томе (volume) и будут доступны после повторного запуска"
    wrongs = [
        "Данные будут удалены вместе с контейнером, потому что том удаляется всегда",
        "Данные сохранятся только в слое образа и пропадут при пересборке",
        "Данные попадут в `.dockerignore` и не будут сохранены",
    ]
    return choice(rng, correct, wrongs, "тома и данные", kind="volume",
                  svc=svc, host=0, cont=0, db=db)


_SYSTEM_MIDDLE = [
    ("Список заказов с клиентами работает медленно: на каждый заказ выполняется отдельный запрос за клиентом (N+1)",
     "Загрузить связанные данные одним запросом (JOIN / eager loading)"),
    ("Один и тот же редко меняющийся справочник запрашивается из БД тысячи раз в минуту",
     "Закэшировать результат с разумным временем жизни (TTL)"),
    ("Формирование отчёта занимает 40 секунд и блокирует HTTP-запрос пользователя",
     "Вынести генерацию в фоновую задачу и отдавать пользователю статус/результат позже"),
    ("Запросы с фильтром по `email` в таблице из десятков миллионов строк выполняются секундами",
     "Добавить индекс по полю `email`"),
    ("Два запроса одновременно списывают остаток товара, из-за чего остаток уходит в минус",
     "Выполнять списание в транзакции с блокировкой строки или условным обновлением"),
    ("Внешний платёжный сервис иногда отвечает ошибкой 503 на единичные запросы",
     "Повторять запрос ограниченное число раз с нарастающей паузой и таймаутом"),
]


def m_system_scenarios(rng: random.Random, i: int) -> dict[str, Any]:
    scenario, answer = _SYSTEM_MIDDLE[i % len(_SYSTEM_MIDDLE)]
    wrongs = [a for _, a in _SYSTEM_MIDDLE if a != answer]
    return choice(rng, answer, wrongs, "выбор решения", scenario=scenario)


# ------------------------------------------------------------------ SENIOR


def s_python_semantics(rng: random.Random, i: int) -> dict[str, Any]:
    kind = i % 4
    if kind == 0:
        n = rng.randint(3, 6)
        code = (f"def gen():\n    for i in range({n}):\n        yield i * 2\n\n"
                "g = gen()\nnext(g)\nnext(g)\nprint(sum(g))")
        mutants = [code.replace("next(g)\nnext(g)\n", ""), code.replace("sum(g)", "len(list(g))"),
                   code.replace("next(g)\nnext(g)\n", "next(g)\n")]
        dim = "генераторы"
    elif kind == 1:
        a, b = rng.sample(["A", "B", "C", "D"], 2)
        code = (f"def deco(tag):\n    def wrap(f):\n        def inner():\n            return '{{}}({{}})'.format(tag, f())\n"
                "        return inner\n    return wrap\n\n"
                f"@deco('{a}')\n@deco('{b}')\ndef base():\n    return 'x'\n\nprint(base())")
        mutants = [code.replace(f"@deco('{a}')\n@deco('{b}')", f"@deco('{b}')\n@deco('{a}')"),
                   code.replace("@deco('" + a + "')\n", ""), code.replace("@deco('" + b + "')\n", "")]
        dim = "декораторы"
    elif kind == 2:
        step = rng.randint(2, 5)
        code = (f"def counter():\n    n = 0\n    def inc():\n        nonlocal n\n        n += {step}\n        return n\n"
                "    return inc\n\nc1, c2 = counter(), counter()\nc1()\nc1()\nprint(c1(), c2())")
        mutants = [code.replace("c1()\nc1()\n", "c1()\n"), code.replace("print(c1(), c2())", "print(c2(), c1())"),
                   code.replace("c1, c2 = counter(), counter()", "c1 = c2 = counter()")]
        dim = "замыкания"
    else:
        k = rng.randint(3, 4)
        code = ("from functools import lru_cache\ncalls = []\n\n@lru_cache(maxsize=None)\n"
                "def sq(x):\n    calls.append(x)\n    return x * x\n\nfor v in [1, 2, 1, 3, 2, 1]:\n    sq(v)\nprint(len(calls), sq.cache_info().hits)")
        mutants = [code.replace("@lru_cache(maxsize=None)\n", ""),
                   code.replace("[1, 2, 1, 3, 2, 1]", f"[1, 2, 3, {k}, 1, 2]"),
                   code.replace("maxsize=None", "maxsize=1")]
        dim = "кэширование функций"
    correct = run_py(code)
    wrongs = [run_py_safe(m) for m in mutants]
    if len(set(wrongs) - {correct}) < 3:
        wrongs += pad_numeric(correct, [])
    return choice(rng, correct, wrongs, dim, snippet=code)


def s_python_context(rng: random.Random, i: int) -> dict[str, Any]:
    kind = i % 3
    tag = rng.choice(["conn", "lock", "tx"])
    if kind == 0:
        code = (f"class R:\n    def __enter__(self):\n        print('open')\n        return self\n"
                "    def __exit__(self, *a):\n        print('close')\n        return False\n\n"
                f"try:\n    with R():\n        print('{tag}')\n        raise ValueError\n"
                "except ValueError:\n    print('caught')")
        mutants = [code.replace("        raise ValueError\n", ""),
                   code.replace("return False", "return True"),
                   code.replace("print('close')", "print('closed')")]
    elif kind == 1:
        inner, outer = rng.choice([("KeyError", "ValueError"), ("OSError", "RuntimeError"),
                                   ("IndexError", "LookupError"), ("TypeError", "ValueError")])
        code = (f"def f():\n    try:\n        raise {inner}('a')\n    except {inner} as e:\n"
                f"        raise {outer}('b') from e\n    finally:\n        print('{tag}')\n\n"
                f"try:\n    f()\nexcept {outer} as e:\n    print(type(e.__cause__).__name__)")
        mutants = [code.replace(f"raise {outer}('b') from e", f"raise {outer}('b')"),
                   code.replace(f"    finally:\n        print('{tag}')\n", ""),
                   code.replace("e.__cause__", "e")]
    else:
        n = rng.randint(2, 4)
        code = ("def f(n):\n    out = []\n    try:\n        for i in range(n):\n            if i == 2:\n"
                "                raise RuntimeError\n            out.append(i)\n    except RuntimeError:\n"
                "        out.append('x')\n    finally:\n        out.append('f')\n    return out\n\n"
                f"print(f({n}))")
        mutants = [code.replace("i == 2", "i == 9"), code.replace("out.append('x')", "pass"),
                   code.replace("    finally:\n        out.append('f')\n", "")]
    fmt = lambda s: s.replace("\n", ", ")
    correct = fmt(run_py(code))
    wrongs = pad_lines(correct, [fmt(run_py_safe(m)) for m in mutants])
    return choice(rng, correct, wrongs, "потоки управления", snippet=code)


def s_sql_window(rng: random.Random, i: int) -> dict[str, Any]:
    teams = rng.sample(["backend", "data", "mobile", "infra"], 2)
    rows = []
    for k in range(7):
        rows.append((k + 1, rng.choice(teams), rng.choice([100, 120, 150, 150, 180, 200])))
    kind = i % 2
    target = rng.choice(rows)[0]
    if kind == 0:
        expr = "RANK() OVER (PARTITION BY team ORDER BY salary DESC)"
        ask = "Какое значение столбца `pos` у строки с id = {t}?"
    else:
        expr = "SUM(salary) OVER (PARTITION BY team ORDER BY id)"
        ask = "Какое значение столбца `pos` у строки с id = {t}?"
    setup = ["CREATE TABLE staff(id INTEGER, team TEXT, salary INTEGER)"]
    setup += [f"INSERT INTO staff VALUES ({a}, '{b}', {c})" for a, b, c in rows]
    query = f"SELECT id, {expr} AS pos FROM staff"
    answer = dict(_sqlite(setup, query))[target]
    return {
        "type": "numeric", "correct": answer, "tolerance": 0, "dimension": "оконные функции",
        "options": None, "query": query, "ask": ask.format(t=target),
        "data": _table_text(["id", "team", "salary"], rows),
    }


def s_sql_index(rng: random.Random, i: int) -> dict[str, Any]:
    cols = rng.sample(["status", "customer_id", "created_at", "region", "category"], 3)
    a, b, c = cols
    if i % 2 == 0:
        where, order = f"{a} = ? AND {b} > ?", ""
        correct, wrongs = f"({a}, {b})", [f"({b}, {a})", f"({b})", f"({c}, {a}, {b})"]
    else:
        where, order = f"{a} = ?", f" ORDER BY {b}"
        correct, wrongs = f"({a}, {b})", [f"({b}, {a})", f"({b})", f"({c}, {b})"]
    query = f"SELECT * FROM events WHERE {where}{order}"
    return choice(rng, correct, wrongs, "индексы", query=query)


def s_api_statements(rng: random.Random, i: int) -> dict[str, Any]:
    return _fact_task(rng, _FACTS_SENIOR, "проектирование API")


_TESTING_SENIOR = [
    ("Тест проходит локально, но периодически падает в CI: он зависит от текущего времени",
     "Передавать часы как зависимость или фиксировать время в тесте"),
    ("Тесты проходят по отдельности, но падают при запуске всем набором, потому что делят состояние БД",
     "Изолировать состояние: отдельная транзакция с откатом или чистая БД на тест"),
    ("Набор тестов идёт 20 минут, потому что каждый тест обращается к внешнему HTTP-сервису",
     "Заменить внешний сервис тестовым двойником и отдельно держать малое число контрактных проверок"),
    ("Тест проверяет, что внутренний приватный метод был вызван, и ломается при любом рефакторинге",
     "Проверять наблюдаемое поведение и результат, а не детали реализации"),
    ("Баг в проде воспроизводится редко и только при конкурентных запросах; модульные тесты зелёные",
     "Добавить тест на гонку (конкурентный сценарий) и исправить синхронизацию"),
    ("Тест генерирует случайные данные и иногда падает, а причину воспроизвести не удаётся",
     "Фиксировать seed и сохранять его при падении, чтобы воспроизвести сбой"),
]


def s_testing_diagnosis(rng: random.Random, i: int) -> dict[str, Any]:
    scenario, answer = _TESTING_SENIOR[i % len(_TESTING_SENIOR)]
    wrongs = [a for _, a in _TESTING_SENIOR if a != answer]
    return choice(rng, answer, wrongs, "диагностика тестов", scenario=scenario)


def s_docker_cache(rng: random.Random, i: int) -> dict[str, Any]:
    deps = rng.choice(["requirements.txt", "poetry.lock", "pyproject.toml"])
    pkg = rng.choice(["app", "src", "service"])
    steps = [
        ("FROM python:3.12-slim", None),
        ("WORKDIR /app", None),
        (f"COPY {deps} .", deps),
        ("RUN pip install -r requirements.txt", None),
        (f"COPY {pkg}/ ./{pkg}/", pkg),
        ("RUN python -m compileall .", None),
        (f'CMD ["python", "-m", "{pkg}"]', None),
    ]
    changed = rng.choice([deps, pkg, pkg, deps][i % 4: i % 4 + 1] or [pkg])
    first = next(k for k, (_, src) in enumerate(steps) if src == changed)
    answer = len(steps) - first
    dockerfile = "\n".join(s for s, _ in steps)
    return {
        "type": "numeric", "correct": answer, "tolerance": 0, "dimension": "кэш слоёв",
        "options": None, "dockerfile": dockerfile, "changed": changed,
    }


_SYSTEM_SENIOR = [
    ("Сервис обработки заказов публикует событие в брокер после записи в БД; при сбое между двумя шагами события теряются",
     "Паттерн transactional outbox: писать событие в БД в той же транзакции и отправлять отдельным процессом"),
    ("Зависимый сервис деградировал; наши запросы к нему накапливаются и исчерпывают пул потоков",
     "Ограничить таймауты и включить circuit breaker, чтобы быстро отказывать, пока сервис не восстановится"),
    ("Повторная доставка сообщения из очереди приводит к двойному списанию денег",
     "Сделать обработчик идемпотентным (ключ дедупликации) и фиксировать обработанные сообщения"),
    ("Резкий пик трафика ложится на базу данных, хотя 90% запросов — чтение одних и тех же данных",
     "Добавить кэш на чтение и/или реплики для чтения, ограничив нагрузку на основную БД"),
    ("Миграция добавляет NOT NULL-колонку в огромную таблицу, а приложение должно работать без простоя",
     "Выполнять в несколько совместимых шагов: добавить nullable-колонку, заполнить пакетами, затем ужесточить"),
]


def s_system_scenarios(rng: random.Random, i: int) -> dict[str, Any]:
    if i % 3 == 2:
        cap, util = rng.choice([(120, 70), (200, 60), (150, 80), (90, 50)])
        peak = rng.choice([900, 1500, 2400, 3100])
        answer = math.ceil(peak / (cap * util / 100))
        return {
            "type": "numeric", "correct": answer, "tolerance": 0, "dimension": "оценка ёмкости",
            "options": None,
            "scenario": (
                f"Пиковая нагрузка составляет {peak} запросов/с. Один экземпляр сервиса выдерживает "
                f"{cap} запросов/с, но загрузку планируют держать не выше {util}% от этого значения. "
                "Сколько экземпляров нужно как минимум? Введите одно число."
            ),
        }
    scenario, answer = _SYSTEM_SENIOR[(i - i // 3) % len(_SYSTEM_SENIOR)]
    wrongs = [a for _, a in _SYSTEM_SENIOR if a != answer]
    return choice(
        rng, answer, wrongs, "надёжность",
        scenario=f"{scenario}\n\nКакое решение наиболее уместно?",
    )


# ------------------------------------------------------------------ extra families (2026.10.2)
# Added to widen coverage: 11 tasks per grade instead of 8, same generator contract as above.


def j_python_types(rng: random.Random, i: int) -> dict[str, Any]:
    a, b = rng.randint(2, 9), rng.randint(2, 5)
    w = rng.choice(["abc", "data", "fsp", "key"])
    pool = [
        (f"{a * b} / {b}", "float"), (f"{a * b} // {b}", "int"), (f"'{w}' * {b}", "str"),
        (f"[{a}, {b}] + [{a}]", "list"), (f"({a},)", "tuple"), (f"{{'{w}': {a}}}", "dict"),
        (f"{{{a}, {b}, {a}}}", "set"), (f"{a} > {b}", "bool"), (f"len('{w}')", "int"),
        (f"'{w}'.split('a')", "list"), (f"{a} == {a}.0", "bool"), (f"round({a} / {b}, 1)", "float"),
    ]
    expr, answer = pool[i % len(pool)]
    code = f"x = {expr}\nprint(type(x).__name__)"
    correct = run_py(code)
    assert correct == answer
    wrongs = [t for t in ["int", "float", "str", "bool", "list", "tuple", "dict", "set"] if t != correct]
    return choice(rng, correct, wrongs, "типы данных", snippet=code)


def j_sql_order(rng: random.Random, i: int) -> dict[str, Any]:
    t, _nr, num, _tr, txt, values = _TABLES[(i + 2) % len(_TABLES)]
    nums = rng.sample([5, 12, 20, 45, 80, 120, 300, 450], 6)
    rows = [(n, v, rng.choice(values)) for n, v in enumerate(nums, 1)]
    k = i % 3
    order, off = [("DESC", 0), ("ASC", 0), ("DESC", 2)][k]
    query = f"SELECT {num} FROM {t} ORDER BY {num} {order} LIMIT 1 OFFSET {off}"
    setup = [f"CREATE TABLE {t}(id INTEGER, {num} INTEGER, {txt} TEXT)"]
    setup += [f"INSERT INTO {t} VALUES ({a}, {b}, '{c}')" for a, b, c in rows]
    answer = _sqlite(setup, query)[0][0]
    return {"type": "numeric", "correct": answer, "tolerance": 0, "dimension": "сортировка и LIMIT",
            "options": None, "query": query, "table": t,
            "data": _table_text(["id", num, txt], rows)}


_METHODS = [
    ("получить карточку {res} по идентификатору", "GET"),
    ("создать новый элемент в коллекции {res}", "POST"),
    ("полностью заменить существующий элемент {res}", "PUT"),
    ("изменить одно поле существующего элемента {res}", "PATCH"),
    ("удалить элемент {res}", "DELETE"),
    ("получить список {res} с фильтром в query-параметрах", "GET"),
    ("отправить форму заявки, после которой будет создан новый элемент {res}", "POST"),
    ("обновить только статус элемента {res}, не трогая остальные поля", "PATCH"),
]


def j_http_method(rng: random.Random, i: int) -> dict[str, Any]:
    action, answer = _METHODS[i % len(_METHODS)]
    res = rng.choice(_RESOURCES)
    wrongs = [m for m in ["GET", "POST", "PUT", "PATCH", "DELETE"] if m != answer]
    return choice(rng, answer, wrongs, "методы HTTP", res=res, action=action.format(res=res))


def m_python_comprehension(rng: random.Random, i: int) -> dict[str, Any]:
    kind = i % 5
    xs = rng.sample(range(2, 15), 5)
    ws = rng.sample(["python", "api", "sql", "docker", "git", "test"], 4)
    if kind == 0:
        code = f"xs = {xs}\nprint(sorted(xs, key=lambda v: v % 5)[:3])"
        mutants = [code.replace("v % 5", "v"), code.replace("[:3]", "[-3:]"),
                   code.replace("sorted(", "sorted(reverse=True, iterable=").replace(", key", ", key", 1)]
        mutants[2] = code.replace("key=lambda v: v % 5", "key=lambda v: -v")
    elif kind == 1:
        code = f"ws = {ws}\nd = {{w: len(w) for w in ws if len(w) > 3}}\nprint(len(d), sum(d.values()))"
        mutants = [code.replace("> 3", ">= 3"), code.replace("> 3", "> 4"),
                   code.replace("sum(d.values())", "sum(d)")]
    elif kind == 2:
        code = (f"a = {xs[:3]}\nb = {xs[2:]}\nprint(sorted(set(a) & set(b)), "
                "len(set(a) | set(b)))")
        mutants = [code.replace("&", "|"), code.replace("|", "&"),
                   code.replace("a = ", "a = [0] + ")]
    elif kind == 3:
        code = (f"ws = {ws}\nprint(', '.join(f'{{i}}:{{w[0]}}' for i, w in enumerate(ws, 1)))")
        mutants = [code.replace("enumerate(ws, 1)", "enumerate(ws)"), code.replace("w[0]", "w[-1]"),
                   code.replace("enumerate(ws, 1)", "enumerate(ws[::-1], 1)")]
    else:
        code = (f"xs = {xs}\nys = [x for x in xs if x % 2 == 0]\nit = iter(ys)\nnext(it, None)\n"
                "print(list(it), len(ys))")
        mutants = [code.replace("next(it, None)\n", ""), code.replace("x % 2 == 0", "x % 2 == 1"),
                   code.replace("print(list(it), len(ys))", "print(list(it), len(xs))")]
    correct = run_py(code)
    wrongs = [run_py_safe(m) for m in mutants]
    if len(set(wrongs) - {correct}) < 3:
        wrongs += [correct.replace("[", "[0, ", 1) if "[" in correct else correct + "0",
                   correct[::-1], "ошибка выполнения"]
    return choice(rng, correct, wrongs, "коллекции и генераторы", snippet=code)


def m_sql_left_join(rng: random.Random, i: int) -> dict[str, Any]:
    names = rng.sample(["Анна", "Борис", "Вера", "Глеб", "Дарья", "Егор"], 5)
    customers = [(n + 1, nm) for n, nm in enumerate(names)]
    orders = [(k + 1, rng.choice([1, 2, 3, 3, 1]), rng.choice([40, 90, 150, 220])) for k in range(6)]
    kind = i % 3
    if kind == 1:
        orders[-1] = (orders[-1][0], None, orders[-1][2])  # the NOT IN / NULL trap
    setup = ["CREATE TABLE customers(id INTEGER, name TEXT)",
             "CREATE TABLE orders(id INTEGER, customer_id INTEGER, amount INTEGER)"]
    setup += [f"INSERT INTO customers VALUES ({a}, '{b}')" for a, b in customers]
    setup += [f"INSERT INTO orders VALUES ({a}, {'NULL' if b is None else b}, {c})" for a, b, c in orders]
    if kind == 0:
        query = ("SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
                 "WHERE o.id IS NULL")
    elif kind == 1:
        query = "SELECT name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)"
    else:
        query = "SELECT COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id"
    rows = _sqlite(setup, query)
    answer = rows[0][0] if kind == 2 else len(rows)
    ask = "Какое число вернёт запрос?" if kind == 2 else "Сколько строк вернёт запрос?"
    return {"type": "numeric", "correct": answer, "tolerance": 0, "dimension": "соединения и NULL",
            "options": None, "query": query, "ask": ask,
            "customers": _table_text(["id", "name"], customers),
            "orders": _table_text(["id", "customer_id", "amount"],
                                  [(a, "NULL" if b is None else b, c) for a, b, c in orders])}


_FACTS["HTTP"] = [
    (True, "Идемпотентный метод при повторе того же запроса оставляет сервер в том же состоянии (например, `PUT`, `DELETE`)"),
    (True, "Токен в заголовке `Authorization` не попадает в URL и поэтому реже оседает в логах прокси"),
    (True, "Пароли в БД хранят в виде соленого хэша медленной функции (bcrypt, argon2), а не открытым текстом"),
    (True, "CORS ограничивает доступ из браузера к чужому источнику, но не защищает API от прямых запросов"),
    (True, "Все запросы с параметрами в SQL нужно передавать как параметры запроса, а не склеивать строкой"),
    (True, "Ответ 401 означает, что клиент не аутентифицирован, 403 — что прав недостаточно"),
    (False, "Метод `POST` по определению идемпотентен"),
    (False, "Хэш пароля с короткой функцией (MD5) — достаточная защита, если добавить пароль в начало строки"),
    (False, "Если API доступно только из браузера, проверку прав на сервере можно не делать"),
    (False, "Код 500 разумно возвращать при неверном формате входных данных от клиента"),
    (False, "JWT нельзя подделать, поэтому срок его действия указывать необязательно"),
    (False, "HTTPS нужен только для запросов с паролем, остальные можно отправлять по HTTP"),
]


def m_api_http_security(rng: random.Random, i: int) -> dict[str, Any]:
    return _fact_task(rng, _FACTS["HTTP"], "HTTP и безопасность API")


def s_python_classes(rng: random.Random, i: int) -> dict[str, Any]:
    kind = i % 5
    a, b = rng.sample(["A", "B", "C", "D"], 2)
    n = rng.randint(2, 5)
    if kind == 0:
        code = (f"class Base:\n    def hi(self):\n        return 'base'\n\nclass {a}(Base):\n"
                "    def hi(self):\n        return 'a>' + super().hi()\n\n"
                f"class {b}(Base):\n    def hi(self):\n        return 'b>' + super().hi()\n\n"
                f"class Z({a}, {b}):\n    pass\n\nprint(Z().hi())")
        mutants = [code.replace(f"Z({a}, {b})", f"Z({b}, {a})"),
                   code.replace("'a>' + super().hi()", "'a>'"), code.replace("'b>' + super().hi()", "'b>'")]
    elif kind == 1:
        code = (f"class Box:\n    items = []\n    def __init__(self, v):\n        self.items.append(v)\n\n"
                f"Box({n})\nBox({n + 1})\nprint(len(Box.items))")
        mutants = [code.replace("self.items.append(v)", "self.items = [v]"),
                   code.replace("    items = []\n", "").replace("def __init__(self, v):\n",
                   "def __init__(self, v):\n        self.items = []\n"), code.replace("len(Box.items)", "Box.items[0]")]
    elif kind == 2:
        code = (f"class Temp:\n    def __init__(self):\n        self._c = {n * 10}\n    @property\n"
                "    def f(self):\n        return self._c * 9 // 5 + 32\n\nt = Temp()\nt._c += 10\nprint(t.f)")
        mutants = [code.replace("t._c += 10\n", ""), code.replace("+ 32", "+ 30"),
                   code.replace("t._c += 10", "t._c -= 10")]
    elif kind == 3:
        code = (f"class Job:\n    def __init__(self, name):\n        self.name = name\n"
                "    def __repr__(self):\n        return 'Job(' + self.name + ')'\n\n"
                f"jobs = [Job('x'), Job('y{n}')]\nprint(jobs, str(jobs[0]))")
        mutants = [code.replace("    def __repr__", "    def __str__"),
                   code.replace("print(jobs, str(jobs[0]))", "print(jobs[0], jobs[1])"),
                   code.replace("print(jobs, str(jobs[0]))", "print(str(jobs))")]
    else:
        code = (f"class Money:\n    def __init__(self, v):\n        self.v = v\n    def __eq__(self, o):\n"
                "        return self.v == o.v\n    def __hash__(self):\n        return hash(self.v)\n\n"
                f"s = {{Money({n}), Money({n})}}\nprint(len(s), Money({n}) == Money({n}))")
        mutants = [code.replace("    def __hash__(self):\n        return hash(self.v)\n", ""),
                   code.replace("return hash(self.v)", "return id(self)"),
                   code.replace("Money(" + str(n) + ") == Money(" + str(n) + ")", "Money(" + str(n) + ") is Money(" + str(n) + ")")]
    correct = run_py(code)
    wrongs = [run_py_safe(m) for m in mutants]
    if len(set(wrongs) - {correct}) < 3:
        wrongs += pad_numeric(correct, []) + ["ошибка выполнения"]
    return choice(rng, correct, wrongs, "объектная модель Python", snippet=code)


def s_sql_cte(rng: random.Random, i: int) -> dict[str, Any]:
    teams = rng.sample(["backend", "data", "mobile", "infra", "qa"], 3)
    rows = [(k + 1, rng.choice(teams), rng.choice([90, 110, 130, 150, 180, 210])) for k in range(8)]
    setup = ["CREATE TABLE staff(id INTEGER, team TEXT, salary INTEGER)"]
    setup += [f"INSERT INTO staff VALUES ({a}, '{b}', {c})" for a, b, c in rows]
    kind = i % 3
    if kind == 0:
        target = rng.randint(2, 8)
        query = "SELECT id, salary - LAG(salary) OVER (ORDER BY id) AS pos FROM staff"
        answer = dict(_sqlite(setup, query))[target]
        ask = f"Какое значение столбца `pos` у строки с id = {target}?"
    elif kind == 1:
        query = ("WITH t AS (SELECT team, AVG(salary) AS a FROM staff GROUP BY team) "
                 "SELECT team FROM t WHERE a > (SELECT AVG(salary) FROM staff)")
        answer = len(_sqlite(setup, query))
        ask = "Сколько строк вернёт запрос?"
    else:
        query = ("SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY team "
                 "ORDER BY salary DESC, id) AS rn FROM staff) WHERE rn = 1")
        answer = len(_sqlite(setup, query))
        ask = "Сколько строк вернёт запрос?"
    return {"type": "numeric", "correct": answer, "tolerance": 0, "dimension": "CTE и подзапросы",
            "options": None, "query": query, "ask": ask,
            "data": _table_text(["id", "team", "salary"], rows)}


_SYSTEM_SENIOR_TRADEOFFS = [
    ("Обработчик платежа может быть вызван повторно брокером сообщений (at-least-once), и клиента нельзя списать дважды",
     "Сделать обработку идемпотентной: ключ операции + проверка/уникальное ограничение перед списанием"),
    ("Нужно атомарно сохранить заказ и отправить событие в брокер; сервис иногда падает между этими шагами",
     "Записывать событие в таблицу outbox в той же транзакции и публиковать из неё отдельным процессом"),
    ("Миграция добавляет NOT NULL столбец в таблицу на сотни миллионов строк без простоя сервиса",
     "Добавить столбец как nullable, заполнить пакетами в фоне, затем добавить ограничение"),
    ("При истечении TTL популярного ключа кэша тысячи запросов одновременно идут в БД и перегружают её",
     "Использовать блокировку перегенерации/«single flight» и случайный разброс TTL"),
    ("Консьюмер не успевает за потоком сообщений, очередь растёт, память приложения исчерпывается",
     "Ограничить размер очереди и применить backpressure: замедлять источник или отбрасывать/откладывать нагрузку"),
    ("Чтение с реплики БД иногда возвращает данные, которых ещё нет после только что выполненной записи",
     "Читать критичные после записи данные с primary либо учитывать лаг реплики (read-your-writes)"),
    ("Сторонний сервис деградировал, и наши запросы к нему висят до таймаута, занимая все воркеры",
     "Ввести короткие таймауты и circuit breaker, чтобы быстро отказывать и не исчерпывать воркеры"),
    ("Нужно безопасно выкатить изменение формата ответа API, которым пользуются мобильные клиенты старых версий",
     "Сохранять обратную совместимость: добавлять поля, версионировать API, удалять старое после миграции клиентов"),
]


def s_system_tradeoffs(rng: random.Random, i: int) -> dict[str, Any]:
    scenario, answer = _SYSTEM_SENIOR_TRADEOFFS[i % len(_SYSTEM_SENIOR_TRADEOFFS)]
    wrongs = [a for _, a in _SYSTEM_SENIOR_TRADEOFFS if a != answer]
    return choice(rng, answer, wrongs, "компромиссы проектирования", scenario=scenario)


_ST_METHOD = "Эндпоинт `/{res}`: нужно {action}. Какой HTTP-метод подходит лучше всего?"


# ------------------------------------------------------------------ catalogue
# structure strings only use {placeholders}; the learner sees them verbatim.

Template = dict[str, Any]


def _tpl(code: str, fmt: str, structure: str, gen: Callable, presets: int, dims: list[str]) -> Template:
    return {"code": code, "task_format": fmt, "structure": structure, "gen": gen,
            "presets": presets, "dimensions": dims}


_ST_OUTPUT = "Что выведет программа?\n\n{snippet}"
_ST_BUG = ("В коде ниже при запуске происходит ошибка ({error}). "
           "В какой строке она возникает?\n\n{snippet}")
_ST_SQL_FILTER = ("Дана таблица `{table}` со столбцами `id`, `{num}` ({num_ru}) и `{txt}` ({txt_ru}). "
                  "Какой запрос выбирает все строки, где {num_ru} больше {thr} И {txt_ru} равно '{val}'?")
_ST_SQL_COUNT = "Дана таблица `{table}`:\n\n{data}\n\nЧто вернёт запрос?\n\n{query}\n\nВведите одно число."
_ST_HTTP = ("Эндпоинт `{endpoint}`. Ситуация: {situation}. "
            "Какой HTTP-статус должен вернуть сервер?")
_ST_TEST = "Прочитайте тест и определите его результат.\n\n{func}\n\n{test}"
_ST_DOCKER_INSTR = "Для чего служит инструкция `{instr}` в Dockerfile?"
_ST_SYSTEM_TERM = "Для чего нужен(-а) {term}?"
_ST_SQL_JOIN = ("Таблицы:\n\ncustomers\n{customers}\n\norders\n{orders}\n\nЗапрос:\n{query}\n\n"
                "{ask} Введите одно число.")
_ST_HAVING = ("Таблица `orders(id, customer_id, amount)`. Нужны клиенты, у которых суммарная сумма "
              "заказов больше {t}, и эта сумма. Какой запрос корректен?")
_ST_FASTAPI = "Выберите ВСЕ верные утверждения."
_ST_EDGE = ("Дана функция ({what}). В ней есть ошибка на границе. Какой входной набор данных "
            "выявит ошибку, если сравнить с ожидаемой реализацией?\n\n{code}")
_ST_COMPOSE = ("{lead}")
_ST_SCENARIO = "{scenario}\n\nКакое решение здесь наиболее уместно?"
_ST_WINDOW = "Дана таблица `staff`:\n\n{data}\n\nЗапрос:\n{query}\n\n{ask} Введите одно число."
_ST_INDEX = "Запрос:\n{query}\n\nКакой составной индекс по таблице `events` лучше всего подходит?"
_ST_CACHE = ("Сборка образа с кэшем слоёв. Dockerfile:\n\n{dockerfile}\n\n"
             "Изменился только файл/каталог `{changed}`. Сколько инструкций (считая первую "
             "изменившуюся и все последующие) будет выполнено заново, а не взято из кэша?"
             " Введите одно число.")
_ST_SYSTEM_SENIOR = "{scenario}"

_ST_COMPOSE_VARIANTS = {
    "port": ("В `docker-compose.yml` сервис `{svc}` слушает порт {cont} внутри контейнера и "
             'опубликован как `ports: ["{host}:{cont}"]`. По какому адресу к нему можно обратиться с '
             "хоста?"),
    "dns": ("Сервисы `{svc}` и `{db}` находятся в одной сети docker compose; БД слушает порт {cont}. "
            "По какому адресу сервис `{svc}` должен подключаться к БД?"),
    "volume": ("В compose сервис `{db}` использует именованный том (`volumes: [dbdata:/var/lib/data]`). "
               "Выполнена команда `docker compose down` (без флага `-v`), затем `docker compose up`. "
               "Что произойдёт с данными?"),
}

FAMILIES: list[dict[str, Any]] = []


def _family(grade: str, short: str, competency: str, band: int, templates: list[Template]) -> None:
    dims = []
    for t in templates:
        dims += [d for d in t["dimensions"] if d not in dims]
    FAMILIES.append({
        "code": f"core.{grade.lower()}.{short}",
        "grade": grade,
        "competency": competency,
        "band": band,
        "templates": templates,
        "rubric": [{"dimension": d, "weight": round(1 / len(dims), 6)} for d in dims],
    })


def _build() -> None:
    p = "core"
    _family("JUNIOR", "python_read", "python", 1, [
        _tpl(f"{p}.j.py_out", "CODE_READING", _ST_OUTPUT, j_python_output, 8,
             ["арифметика", "срезы и списки", "строки", "условия"])])
    _family("JUNIOR", "python_bug", "python", 1, [
        _tpl(f"{p}.j.py_bug", "BUG_HUNT", _ST_BUG, j_python_bug, 6, ["поиск ошибки"])])
    _family("JUNIOR", "sql_select", "sql", 1, [
        _tpl(f"{p}.j.sql_sel", "SQL_REASONING", _ST_SQL_FILTER, j_sql_select, 8, ["условия выборки"])])
    _family("JUNIOR", "sql_count", "sql", 1, [
        _tpl(f"{p}.j.sql_cnt", "NUMERIC_ANSWER", _ST_SQL_COUNT, j_sql_count, 6, ["агрегаты"])])
    _family("JUNIOR", "api_status", "api_fastapi", 1, [
        _tpl(f"{p}.j.api", "API_REASONING", _ST_HTTP, j_api_status, 7, ["коды ответа HTTP"])])
    _family("JUNIOR", "testing_read", "testing", 1, [
        _tpl(f"{p}.j.test", "CODE_READING", _ST_TEST, j_testing_outcome, 8, ["чтение теста"])])
    _family("JUNIOR", "docker_instr", "docker_basics", 1, [
        _tpl(f"{p}.j.docker", "DETERMINISTIC_QUESTION", _ST_DOCKER_INSTR, j_docker_instruction, 7,
             ["инструкции Dockerfile"])])
    _family("JUNIOR", "system_terms", "system_thinking", 1, [
        _tpl(f"{p}.j.sys", "DETERMINISTIC_QUESTION", _ST_SYSTEM_TERM, j_system_term, 7,
             ["базовые понятия"])])

    _family("JUNIOR", "python_types", "python", 1, [
        _tpl(f"{p}.j.py_types", "CODE_READING", _ST_OUTPUT, j_python_types, 8, ["типы данных"])])
    _family("JUNIOR", "sql_order", "sql", 1, [
        _tpl(f"{p}.j.sql_ord", "NUMERIC_ANSWER", _ST_SQL_COUNT, j_sql_order, 6,
             ["сортировка и LIMIT"])])
    _family("JUNIOR", "http_method", "api_fastapi", 1, [
        _tpl(f"{p}.j.method", "API_REASONING", _ST_METHOD, j_http_method, 8, ["методы HTTP"])])

    _family("MIDDLE", "python_semantics", "python", 2, [
        _tpl(f"{p}.m.py_sem", "CODE_READING", _ST_OUTPUT, m_python_output, 8,
             ["изменяемые аргументы", "ссылки и копии", "замыкания", "словари и итерация"])])
    _family("MIDDLE", "python_exceptions", "python", 2, [
        _tpl(f"{p}.m.py_exc", "CODE_READING", _ST_OUTPUT, m_python_exceptions, 6,
             ["порядок выполнения"])])
    _family("MIDDLE", "sql_join", "sql", 2, [
        _tpl(f"{p}.m.sql_join", "NUMERIC_ANSWER", _ST_SQL_JOIN, m_sql_join_numeric, 6,
             ["соединения и группировка"])])
    _family("MIDDLE", "sql_having", "sql", 2, [
        _tpl(f"{p}.m.sql_hav", "SQL_REASONING", _ST_HAVING, m_sql_having, 6, ["агрегаты и HAVING"])])
    _family("MIDDLE", "api_fastapi", "api_fastapi", 2, [
        _tpl(f"{p}.m.api", "MULTI_SELECT", _ST_FASTAPI, m_api_statements, 8, ["основы FastAPI"])])
    _family("MIDDLE", "testing_edge", "testing", 2, [
        _tpl(f"{p}.m.test", "BUG_HUNT", _ST_EDGE, m_testing_edge, 8, ["граничные значения"])])
    _family("MIDDLE", "docker_compose", "docker_basics", 2, [
        _tpl(f"{p}.m.docker", "DETERMINISTIC_QUESTION", _ST_COMPOSE, m_docker_compose, 6,
             ["порты и сети compose", "тома и данные"])])
    _family("MIDDLE", "system_choice", "system_thinking", 2, [
        _tpl(f"{p}.m.sys", "ARCHITECTURE_CASE", _ST_SCENARIO, m_system_scenarios, 6,
             ["выбор решения"])])

    _family("MIDDLE", "python_collections", "python", 2, [
        _tpl(f"{p}.m.py_col", "CODE_READING", _ST_OUTPUT, m_python_comprehension, 10,
             ["коллекции и генераторы"])])
    _family("MIDDLE", "sql_left_join", "sql", 2, [
        _tpl(f"{p}.m.sql_left", "NUMERIC_ANSWER", _ST_SQL_JOIN, m_sql_left_join, 6,
             ["соединения и NULL"])])
    _family("MIDDLE", "api_http_security", "api_fastapi", 2, [
        _tpl(f"{p}.m.api_sec", "MULTI_SELECT", _ST_FASTAPI, m_api_http_security, 8,
             ["HTTP и безопасность API"])])

    _family("SENIOR", "python_semantics", "python", 3, [
        _tpl(f"{p}.s.py_sem", "CODE_READING", _ST_OUTPUT, s_python_semantics, 8,
             ["генераторы", "декораторы", "замыкания", "кэширование функций"])])
    _family("SENIOR", "python_flow", "python", 3, [
        _tpl(f"{p}.s.py_flow", "CODE_READING", _ST_OUTPUT, s_python_context, 6,
             ["потоки управления"])])
    _family("SENIOR", "sql_window", "sql", 3, [
        _tpl(f"{p}.s.sql_win", "NUMERIC_ANSWER", _ST_WINDOW, s_sql_window, 6, ["оконные функции"])])
    _family("SENIOR", "sql_index", "sql", 3, [
        _tpl(f"{p}.s.sql_idx", "SQL_REASONING", _ST_INDEX, s_sql_index, 6, ["индексы"])])
    _family("SENIOR", "api_design", "api_fastapi", 3, [
        _tpl(f"{p}.s.api", "MULTI_SELECT", _ST_FASTAPI, s_api_statements, 8, ["проектирование API"])])
    _family("SENIOR", "testing_diag", "testing", 3, [
        _tpl(f"{p}.s.test", "ARCHITECTURE_CASE", _ST_SCENARIO, s_testing_diagnosis, 6,
             ["диагностика тестов"])])
    _family("SENIOR", "docker_cache", "docker_basics", 3, [
        _tpl(f"{p}.s.docker", "NUMERIC_ANSWER", _ST_CACHE, s_docker_cache, 6, ["кэш слоёв"])])
    _family("SENIOR", "system_reliability", "system_thinking", 3, [
        _tpl(f"{p}.s.sys", "ARCHITECTURE_CASE", _ST_SYSTEM_SENIOR, s_system_scenarios, 6,
             ["надёжность", "оценка ёмкости"])])
    _family("SENIOR", "python_classes", "python", 3, [
        _tpl(f"{p}.s.py_cls", "CODE_READING", _ST_OUTPUT, s_python_classes, 10,
             ["объектная модель Python"])])
    _family("SENIOR", "sql_cte", "sql", 3, [
        _tpl(f"{p}.s.sql_cte", "NUMERIC_ANSWER", _ST_WINDOW, s_sql_cte, 6, ["CTE и подзапросы"])])
    _family("SENIOR", "system_tradeoffs", "system_thinking", 3, [
        _tpl(f"{p}.s.sys_trade", "ARCHITECTURE_CASE", _ST_SCENARIO, s_system_tradeoffs, 8,
             ["компромиссы проектирования"])])


_build()


def _lead_for_compose(fields: dict[str, Any]) -> dict[str, Any]:
    fields = dict(fields)
    fields["lead"] = _ST_COMPOSE_VARIANTS[fields["kind"]].format(**fields)
    return fields


def generate_presets(template: Template, family_code: str) -> list[dict[str, Any]]:
    """Deterministic parameter presets for a template (seed = family code + preset index)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index in range(template["presets"]):
        for attempt in range(60):  # a preset must differ from its siblings in what the learner sees
            rng = random.Random(f"{RUBRIC_VERSION}|{template['code']}|{index}|{attempt}")
            fields = template["gen"](rng, index)
            if template["code"].endswith(".m.docker"):
                fields = _lead_for_compose(fields)
            shown = {k: v for k, v in fields.items()
                     if k not in ("options", "correct", "dimension", "type", "tolerance")}
            fingerprint = template["structure"].format(**shown) + repr(fields.get("options"))
            if fingerprint not in seen:
                seen.add(fingerprint)
                out.append(fields)
                break
        else:
            raise RuntimeError(f"{template['code']}: preset {index} is a duplicate of a sibling")
    return out
