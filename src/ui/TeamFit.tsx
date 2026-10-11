import { useCallback, useEffect, useState } from "react";
import { api, type Session } from "./api";
import type { Catalog, Need, PublicCandidate, Reason } from "./types";
import { Badge, Card, COMPETENCY_RU, CompanyMark, Empty, ErrorBox, FORMAT_RU, GRADE_RU, gradeLine, Icon, InviteBadge, Loading, money, skillName } from "./ui";

interface Axis { key: string; label: string; low: string; high: string }
interface Questions { axes: Axis[]; note: string; career_goals: Record<string, string> }
interface Rec {
  need_id: number; title: string; company: string; target_grade: string; salary_from: number; salary_to: number;
  salary_type: string; work_formats?: string[]; fit_state?: "ready" | "insufficient_data";
  mutual_fit: number | null; requirement_fit: number | null; reverse_fit: number | null; why: Reason[]; gaps: Reason[];
}
interface RecResponse { items: Rec[]; assessed: boolean; next_action: "take_assessment" | "fill_preferences" | null }
const NEXT_RU = {
  take_assessment: "Пройдите оценку компетенций (вкладка «Основная оценка») — без неё соответствие требованиям не рассчитывается.",
  fill_preferences: "Укажите интересы, карьерную цель или заполните анкету предпочтений — тогда появится оценка ваших ожиданий.",
};
interface Team {
  manager: Record<string, number> | null; source: string; profile: Record<string, number> | null;
  employees: { responses: number; aggregate: Record<string, number> | null; note: string | null };
}

const pct = (x: number | null | undefined) => (x === null || x === undefined ? "Недостаточно данных" : `${Math.round(x * 100)}%`);
/** Технические коды навыков в текстах причин заменяем русскими названиями. */
const CODE_RE = new RegExp(`\\b(${Object.keys(COMPETENCY_RU).join("|")})\\b`, "g");
const ruText = (t: string) => t.replace(CODE_RE, (c) => COMPETENCY_RU[c] ?? c);

function Reasons({ why, gaps }: { why: Reason[]; gaps: Reason[] }) {
  if (!why.length && !gaps.length) return <p className="muted">Подробных причин пока нет: недостаточно данных.</p>;
  return (
    <details>
      <summary>Почему так и пробелы ({why.length + gaps.length})</summary>
      <div className="rec-columns">
        <div className="why-col"><h5>Почему подходит</h5>{why.length ? <ul>{why.map((r, i) => <li key={i}>{ruText(r.text)}</li>)}</ul> : <span className="muted">Нет подтверждённых оснований</span>}</div>
        <div className="gap-col"><h5>Пробелы</h5>{gaps.length ? <ul>{gaps.map((r, i) => <li key={i}>{ruText(r.text)}</li>)}</ul> : <span className="muted">Пробелов не обнаружено</span>}</div>
      </div>
    </details>
  );
}

function Meter({ label, value, na }: { label: string; value: number | null; na?: string }) {
  if (value === null) return <div className="rec-meter na"><b>{na ?? "Недостаточно данных"}</b><span>{label}</span></div>;
  return (
    <div className="rec-meter"><b>{Math.round(value * 100)}%</b><span>{label}</span>
      <div className="progress thin" aria-hidden="true"><span style={{ width: `${Math.round(value * 100)}%` }} /></div></div>
  );
}

/** Подписи шкалы 1–5 строятся из полюсов вопроса: 1 и 5 — крайние варианты, 3 — «по ситуации». */
const scaleLabels = (low: string, high: string) => [low, `Скорее: ${low}`, "По ситуации / одинаково", `Скорее: ${high}`, high];

/** Анкета предпочтений: пять подписанных вариантов на вопрос; неотвеченный вопрос не считается нейтральным. */
export function WorkStyleForm({ q, value, onSave, label }: { q: Questions; value: Record<string, number> | null; onSave: (a: Record<string, number>) => Promise<void>; label: string }) {
  const [a, setA] = useState<Record<string, number>>(value ?? {});
  const [msg, setMsg] = useState("");
  const answered = Object.keys(a).length;
  const setAxis = (k: string, v: number | null) => {
    setMsg("");
    const n = { ...a };
    if (v === null) delete n[k]; else n[k] = v;
    setA(n);
  };
  return (
    <div>
      <p className="muted">{q.note}</p>
      {q.axes.map((x) => (
        <fieldset key={x.key} className="scale">
          <legend>{x.label}</legend>
          <p className="muted">1 — {x.low}; 5 — {x.high}; 3 — по ситуации.</p>
          <div className="scale-opts" role="radiogroup" aria-label={x.label}>
            {scaleLabels(x.low, x.high).map((t, i) => (
              <label key={i} className={`scale-opt${a[x.key] === i + 1 ? " on" : ""}`}>
                <input type="radio" name={`ws-${x.key}`} checked={a[x.key] === i + 1} onChange={() => setAxis(x.key, i + 1)} />
                <span><b>{i + 1}</b> {t}</span>
              </label>))}
          </div>
          <p className="muted">{a[x.key] === undefined ? "Не отвечено" : <>Выбрано: {a[x.key]} — {scaleLabels(x.low, x.high)[a[x.key] - 1]} · <button type="button" className="link" onClick={() => setAxis(x.key, null)}>сбросить</button></>}</p>
        </fieldset>
      ))}
      <p className="muted">Отвечено: {answered} из {q.axes.length}. Пропущенные вопросы не учитываются; для расчёта совпадения нужно минимум 3 общих ответа.</p>
      <button className="primary" disabled={answered === 0}
        onClick={async () => { try { await onSave(a); setMsg("Сохранено"); } catch (e) { setMsg((e as Error).message); } }}>{label}</button>
      {msg && <p role="status">{msg}</p>}
    </div>
  );
}

/** Candidate: goals, work-style questionnaire and personal recommendations. */
export function CandidateFit({ session, go }: { session: Session; go?: (tab: string) => void }) {
  const [q, setQ] = useState<Questions | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [mine, setMine] = useState<{ work_style: Record<string, number> | null; interests: string[]; career_goal: string | null } | null>(null);
  const [recs, setRecs] = useState<RecResponse | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const load = useCallback(() => {
    Promise.all([
      api<Questions>("/api/work-style/questions"), api<Catalog>("/api/catalog"),
      api<typeof mine>("/api/candidates/me/work-style", { token: session.token }),
      api<RecResponse>("/api/candidates/me/recommendations", { token: session.token }),
    ]).then(([qq, c, m, r]) => { setQ(qq); setCatalog(c); setMine(m); setRecs(r); }).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  useEffect(load, [load]);
  if (err) return <ErrorBox message={err} />;
  if (!q || !catalog || !mine || !recs) return <Loading what="Загружаем рекомендации" />;
  const saveGoals = async (interests: string[], goal: string | null) => {
    try { await api("/api/candidates/me/goals", { method: "PUT", token: session.token, body: { interests, career_goal: goal } }); setMsg("Цели сохранены"); load(); }
    catch (e) { setMsg((e as Error).message); }
  };
  const toggle = (c: string) => saveGoals(mine.interests.includes(c) ? mine.interests.filter((x) => x !== c) : [...mine.interests, c], mine.career_goal);
  return (
    <div>
      <div>
        <div className="card-head"><h3>Рекомендованные вакансии</h3></div>
        {recs.next_action && (
          <div className="next-step" role="status">
            <span className="kpi-icon"><Icon name="target" size={16} /></span>
            <div><b>{recs.next_action === "take_assessment" ? "Расчёт соответствия ждёт оценку" : "Заполните ожидания"}</b><span className="muted">{NEXT_RU[recs.next_action]}</span></div>
            {go && recs.next_action === "take_assessment" && <button className="primary" onClick={() => go("test")}>Пройти оценку</button>}
          </div>)}
        {recs.items.length === 0 ? (
          <Empty icon="search" title="Подходящих вакансий пока нет"
            action={go ? <><button className="primary" onClick={() => go("test")}>Подтвердить грейд</button><button onClick={() => go("profile")}>Уточнить предпочтения</button></> : undefined}>
            Вакансии появляются, когда работодатель описывает потребность, подходящую по специализации, зарплате и формату. Подтверждённый грейд и заполненные предпочтения повышают точность.
          </Empty>
        ) : recs.items.map((r) => (
          <article key={r.need_id} className="rec-card">
            <CompanyMark name={r.company} />
            <div>
              <h4>{r.title}</h4>
              <div className="rec-sub">{r.company}</div>
              <div className="chips" style={{ marginTop: 6 }}>
                <Badge tone="muted">{GRADE_RU[r.target_grade]}</Badge>
                <Badge tone="muted">{money(r.salary_from)}–{money(r.salary_to)} ₽ {r.salary_type}</Badge>
                {r.work_formats?.map((f) => <Badge key={f} tone="muted">{FORMAT_RU[f] ?? f}</Badge>)}
                {recs.assessed ? <Badge tone="ok">оценка пройдена</Badge> : <Badge tone="warn">оценка не пройдена</Badge>}
              </div>
            </div>
            {r.fit_state === "insufficient_data" ? (
              <div className="rec-meter na"><b>Недостаточно данных</b><span>{recs.assessed ? "профиль не заполнен" : "нужна оценка компетенций"}</span></div>
            ) : (
              <div className="rec-fits">
                <Meter label="требования" value={r.requirement_fit} />
                <Meter label="ваши ожидания" value={r.reverse_fit} na="Заполните предпочтения" />
                {r.mutual_fit !== null && r.reverse_fit !== null && <Meter label="взаимное" value={r.mutual_fit} />}
              </div>)}
            <div className="rec-body"><Reasons why={r.why} gaps={r.gaps} /></div>
          </article>))}
        <p className="muted" style={{ fontSize: 13 }}>Проценты — эвристика совпадения по данным профиля, а не вероятность найма. Рекомендации ничего не отправляют и не меняют ваш грейд.</p>
      </div>
      <Card title="Интересы и карьерная цель">
        <div className="form-sec">Технологии, с которыми хотите работать</div>
        <div className="chip-pick">
          {catalog.skills.map((s) => <label key={s.code} className={mine.interests.includes(s.code) ? "on" : ""}><input type="checkbox" checked={mine.interests.includes(s.code)} onChange={() => toggle(s.code)} /><span className="mark" />{skillName(s.code, s.name)}</label>)}
        </div>
        <label>Карьерная цель
          <select value={mine.career_goal ?? ""} onChange={(e) => saveGoals(mine.interests, e.target.value || null)}>
            <option value="">не указана</option>
            {Object.entries(q.career_goals).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        {msg && <p role="status">{msg}</p>}
      </Card>
      <Card title="Анкета рабочих предпочтений (добровольно)">
        <p className="muted">Сырые ответы работодателю не показываются — только степень близости с командой по осям.</p>
        <WorkStyleForm q={q} value={mine.work_style} label="Сохранить анкету"
          onSave={async (a) => { await api("/api/candidates/me/work-style", { method: "PUT", token: session.token, body: { answers: a } }); load(); }} />
      </Card>
    </div>
  );
}

/** Employer: favorites, mutual recommendations and the BOTH team profile. */
export function EmployerFit({ session, open, view = "favorites" }: { session: Session; open: (id: number, need: Need | null) => void; view?: "favorites" | "team" }) {
  const [favs, setFavs] = useState<{ note: string; need_id: number | null; candidate: PublicCandidate }[] | null>(null);
  const [recs, setRecs] = useState<{ need_id: number; title: string; candidates: (Rec & { candidate: PublicCandidate })[] }[] | null>(null);
  const [needs, setNeeds] = useState<Need[]>([]);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    Promise.all([
      api<{ items: typeof favs }>("/api/employer/favorites", { token: session.token }),
      api<{ items: typeof recs }>("/api/employer/recommendations", { token: session.token }),
      api<Need[]>("/api/employer/needs", { token: session.token }),
    ]).then(([f, r, n]) => { setFavs(f.items); setRecs(r.items); setNeeds(n); }).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  useEffect(load, [load]);
  if (err) return <ErrorBox message={err} />;
  if (!favs || !recs) return <Loading what="Загружаем избранное и рекомендации" />;
  const unfav = async (id: number) => { await api(`/api/employer/favorites/${id}`, { method: "DELETE", token: session.token }); load(); };
  return (
    <div>
      {view === "favorites" && <Card title="Избранные кандидаты">
        {favs!.length === 0 ? <Empty icon="bookmark" title="Избранное пусто">Сохраняйте интерес в карточке кандидата — приглашение при этом не отправляется.</Empty> : favs!.map((f) => (
          <div key={f.candidate.candidate_id} className="job">
            <b>{f.candidate.display_name}</b> {f.candidate.verified_grade ? <Badge tone="ok">{GRADE_RU[f.candidate.verified_grade]} {f.candidate.verified_sublevel}</Badge> : <Badge tone="muted">не подтверждён</Badge>}
            <p className="muted">{gradeLine(f.candidate)}{f.candidate.work_formats.length > 0 && <> · {f.candidate.work_formats.map((x) => FORMAT_RU[x] ?? x).join(", ")}</>} · <InviteBadge status={f.candidate.invitation_status} /></p>
            {f.note && <p>Заметка: {f.note}</p>}
            <div className="row"><button onClick={() => open(f.candidate.candidate_id, needs.find((n) => n.id === f.need_id) ?? null)}>Открыть карточку</button><button onClick={() => unfav(f.candidate.candidate_id)}>Убрать</button></div>
          </div>))}
      </Card>}
      {view === "team" && needs.length === 0 && <Empty icon="users" title="Потребностей пока нет">Создайте потребность на вкладке «Подбор» — здесь появятся рекомендации и профиль команды.</Empty>}
      {view === "team" && recs!.map((r) => (
        <Card key={r.need_id} title={`Рекомендации: ${r.title}`}>
          {r.candidates.length === 0 ? <Empty>Подходящих кандидатов пока нет.</Empty> : r.candidates.map((c) => (
            <div key={c.candidate.candidate_id} className="job">
              <b>{c.candidate.display_name}</b> <span className="muted">{gradeLine(c.candidate)}</span> <InviteBadge status={c.candidate.invitation_status} /> · требования: {pct(c.requirement_fit)} · ожидания кандидата: {c.reverse_fit === null ? "Недостаточно данных" : pct(c.reverse_fit)}
              <Reasons why={c.why} gaps={c.gaps} />
              <button onClick={() => open(c.candidate.candidate_id, needs.find((n) => n.id === r.need_id) ?? null)}>Открыть карточку</button>
            </div>))}
          <TeamProfile session={session} need={needs.find((n) => n.id === r.need_id)} />
        </Card>))}
    </div>
  );
}

function TeamProfile({ session, need }: { session: Session; need?: Need }) {
  const [q, setQ] = useState<Questions | null>(null);
  const [t, setT] = useState<Team | null>(null);
  const [link, setLink] = useState("");
  const [shown, setShown] = useState(false);
  const load = useCallback(() => {
    if (!need) return;
    Promise.all([api<Questions>("/api/work-style/questions"), api<Team>(`/api/employer/needs/${need.id}/team-profile`, { token: session.token })])
      .then(([qq, tt]) => { setQ(qq); setT(tt); }).catch(() => undefined);
  }, [session.token, need]);
  useEffect(load, [load]);
  if (!need) return null;
  const survey = async () => { const r = await api<{ url: string }>(`/api/employer/needs/${need.id}/team-survey`, { token: session.token, method: "POST" }); setLink(r.url); };
  return (
    <div>
      <button onClick={() => setShown(!shown)}>{shown ? "Скрыть профиль команды" : "Профиль команды (BOTH)"}</button>
      {shown && q && t && (
        <div>
          <p className="muted">Профиль команды строится из вашей анкеты и добровольных анонимных ответов сотрудников; агрегат показывается при {3}+ ответах. Это описание стиля работы, а не оценка людей.</p>
          <WorkStyleForm q={q} value={t.manager} label="Сохранить анкету руководителя"
            onSave={async (a) => { await api(`/api/employer/needs/${need.id}/work-style`, { method: "PUT", token: session.token, body: { answers: a } }); load(); }} />
          <p>Источник профиля: <Badge tone="info">{t.source}</Badge> · ответов сотрудников: {t.employees.responses}{t.employees.note && ` — ${t.employees.note}`}</p>
          {t.profile && <ul>{q.axes.map((x) => <li key={x.key}>{x.label}: {t.profile![x.key]} / 5</li>)}</ul>}
          <button onClick={survey}>Создать анонимную ссылку для сотрудников</button>
          {link && <p>Отправьте сотрудникам: <code>{link}</code></p>}
        </div>)}
    </div>
  );
}

/** Public anonymous survey page (/?team_survey=<token>). */
export function TeamSurvey({ token }: { token: string }) {
  const [q, setQ] = useState<(Questions & { title: string }) | null>(null);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => { api<Questions & { title: string }>(`/api/team-survey/${token}`).then(setQ).catch((e: Error) => setErr(e.message)); }, [token]);
  if (err) return <ErrorBox message={err} />;
  if (!q) return <Loading />;
  if (done) return <p className="ok" role="status">Спасибо! Ответ принят анонимно.</p>;
  return (
    <Card title={`Анонимная анкета команды: ${q.title}`}>
      <p className="muted">Участие добровольное. Ваше имя и контакты не запрашиваются и не сохраняются; работодатель видит только усреднённый результат при 3+ ответах.</p>
      <WorkStyleForm q={q} value={null} label="Отправить анонимно"
        onSave={async (a) => { await api(`/api/team-survey/${token}`, { body: { answers: a } }); setDone(true); }} />
    </Card>
  );
}
