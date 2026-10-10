import { useCallback, useEffect, useState } from "react";
import { api, type Session } from "./api";
import type { Catalog, Need, PublicCandidate, Reason } from "./types";
import { Badge, Card, Empty, ErrorBox, FORMAT_RU, GRADE_RU, Loading, skillName } from "./ui";

interface Axis { key: string; label: string; low: string; high: string }
interface Questions { axes: Axis[]; note: string; career_goals: Record<string, string> }
interface Rec {
  need_id: number; title: string; company: string; target_grade: string; salary_from: number; salary_to: number;
  salary_type: string; mutual_fit: number; requirement_fit: number; reverse_fit: number | null; why: Reason[]; gaps: Reason[];
}
interface Team {
  manager: Record<string, number> | null; source: string; profile: Record<string, number> | null;
  employees: { responses: number; aggregate: Record<string, number> | null; note: string | null };
}

const pct = (x: number | null) => (x === null ? "—" : `${Math.round(x * 100)}%`);

function Reasons({ why, gaps }: { why: Reason[]; gaps: Reason[] }) {
  return (
    <div className="row">
      <div><b>Почему подходит</b><ul>{why.length ? why.map((r, i) => <li key={i} className="ok">{r.text}</li>) : <li className="muted">—</li>}</ul></div>
      <div><b>Пробелы</b><ul>{gaps.length ? gaps.map((r, i) => <li key={i} className="warn">{r.text}</li>) : <li className="muted">—</li>}</ul></div>
    </div>
  );
}

export function WorkStyleForm({ q, value, onSave, label }: { q: Questions; value: Record<string, number> | null; onSave: (a: Record<string, number>) => Promise<void>; label: string }) {
  const [a, setA] = useState<Record<string, number>>(value ?? Object.fromEntries(q.axes.map((x) => [x.key, 3])));
  const [msg, setMsg] = useState("");
  return (
    <div>
      <p className="muted">{q.note}</p>
      {q.axes.map((x) => (
        <label key={x.key}>{x.label}: <span className="muted">{x.low} ← {a[x.key]} → {x.high}</span>
          <input type="range" min={1} max={5} value={a[x.key]} onChange={(e) => { setMsg(""); setA({ ...a, [x.key]: Number(e.target.value) }); }} />
        </label>
      ))}
      <button className="primary" onClick={async () => { try { await onSave(a); setMsg("Сохранено"); } catch (e) { setMsg((e as Error).message); } }}>{label}</button>
      {msg && <p role="status">{msg}</p>}
    </div>
  );
}

/** Candidate: goals, work-style questionnaire and personal recommendations. */
export function CandidateFit({ session }: { session: Session }) {
  const [q, setQ] = useState<Questions | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [mine, setMine] = useState<{ work_style: Record<string, number> | null; interests: string[]; career_goal: string | null } | null>(null);
  const [recs, setRecs] = useState<Rec[] | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const load = useCallback(() => {
    Promise.all([
      api<Questions>("/api/work-style/questions"), api<Catalog>("/api/catalog"),
      api<typeof mine>("/api/candidates/me/work-style", { token: session.token }),
      api<{ items: Rec[] }>("/api/candidates/me/recommendations", { token: session.token }),
    ]).then(([qq, c, m, r]) => { setQ(qq); setCatalog(c); setMine(m); setRecs(r.items); }).catch((e: Error) => setErr(e.message));
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
      <Card title="Рекомендованные вакансии">
        {recs.length === 0 ? <Empty>Подходящих вакансий пока нет. Подтвердите грейд и заполните предпочтения.</Empty> : recs.map((r) => (
          <div key={r.need_id} className="job">
            <b>{r.title}</b>, {r.company} · {GRADE_RU[r.target_grade]} · {r.salary_from.toLocaleString("ru-RU")}–{r.salary_to.toLocaleString("ru-RU")} ₽ {r.salary_type}
            <p>Взаимное соответствие: <b>{pct(r.mutual_fit)}</b> (требования: {pct(r.requirement_fit)}, ваши ожидания: {pct(r.reverse_fit)})</p>
            <Reasons why={r.why} gaps={r.gaps} />
          </div>))}
        <p className="muted">Рекомендации — подсказка, а не отбор: они ничего не отправляют и не меняют ваш грейд.</p>
      </Card>
      <Card title="Интересы и карьерная цель">
        <fieldset><legend>Технологии, с которыми хотите работать</legend>
          {catalog.skills.map((s) => <label key={s.code} className="check"><input type="checkbox" checked={mine.interests.includes(s.code)} onChange={() => toggle(s.code)} />{skillName(s.code, s.name)}</label>)}
        </fieldset>
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
export function EmployerFit({ session, open }: { session: Session; open: (id: number, need: Need | null) => void }) {
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
      <Card title="Избранные кандидаты">
        {favs!.length === 0 ? <Empty>Избранное пусто. Сохраняйте интерес в карточке кандидата — приглашение при этом не отправляется.</Empty> : favs!.map((f) => (
          <div key={f.candidate.candidate_id} className="job">
            <b>{f.candidate.display_name}</b> {f.candidate.verified_grade ? <Badge tone="ok">{GRADE_RU[f.candidate.verified_grade]} {f.candidate.verified_sublevel}</Badge> : <Badge tone="muted">не подтверждён</Badge>}
            {f.candidate.work_formats.length > 0 && <> · {f.candidate.work_formats.map((x) => FORMAT_RU[x] ?? x).join(", ")}</>}
            {f.note && <p>Заметка: {f.note}</p>}
            <div className="row"><button onClick={() => open(f.candidate.candidate_id, needs.find((n) => n.id === f.need_id) ?? null)}>Открыть карточку</button><button onClick={() => unfav(f.candidate.candidate_id)}>Убрать</button></div>
          </div>))}
      </Card>
      {recs!.map((r) => (
        <Card key={r.need_id} title={`Рекомендации: ${r.title}`}>
          {r.candidates.length === 0 ? <Empty>Подходящих кандидатов пока нет.</Empty> : r.candidates.map((c) => (
            <div key={c.candidate.candidate_id} className="job">
              <b>{c.candidate.display_name}</b> · взаимное соответствие {pct(c.mutual_fit)} (требования {pct(c.requirement_fit)}, ожидания кандидата {pct(c.reverse_fit)})
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
