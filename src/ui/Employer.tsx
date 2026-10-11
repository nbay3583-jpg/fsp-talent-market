import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Session } from "./api";
import { EmployerFit } from "./TeamFit";
import type { Catalog, Fit, Invitation, MatchRow, Need, PublicCandidate } from "./types";
import {
  Avatar, Badge, Card, ContactBox, Empty, ErrorBox, FitBlock, FORMAT_RU, GRADE_RU, Icon, Loading, PageHead, SalaryBanner, salaryRange, SALARY_TYPE_RU, skillName, money,
  STATUS_RU, VerificationBadge, subLabel, gradeLine, InviteBadge, OPEN_INVITE } from "./ui";
import Shell, { type ShellCtx } from "./Shell";

interface Detail extends PublicCandidate { compat?: { reverse_fit: number | null; why: { text: string }[]; gaps: { text: string }[] }; fit: Fit | null; contact_status: "LOCKED" | "UNLOCKED"; contacts?: { full_name: string; email: string; phone: string | null } }
interface MatchResponse {
  run_id: number; candidates_considered: number; matched_total: number; excluded_summary: Record<string, number>; results: MatchRow[];
}

const EXCLUSION_RU: Record<string, string> = {
  SALARY_MISMATCH: "зарплатные ожидания выше бюджета", WORK_FORMAT_MISMATCH: "не подходит формат работы",
  GRADE_OUT_OF_RANGE: "уровень вне допуска (±1 подуровень)", SPECIALIZATION_MISMATCH: "другая специализация",
  NOT_VISIBLE: "профиль скрыт", NOT_OPEN_TO_INVITATIONS: "не принимает приглашения", LOCATION_MISMATCH: "другая локация",
  AVAILABILITY_MISMATCH: "не готов выйти в срок", GRADE_UNKNOWN: "грейд не указан",
};

type Tab = "match" | "pool" | "fit" | "team" | "invitations";
const TITLES: Record<Tab, [string, string]> = {
  match: ["Подбор по потребности", "Опишите вакансию — получите короткий объяснимый список с Requirement Fit, причинами выбора и пробелами"],
  pool: ["Поиск кандидатов", "Весь пул: фильтры по подтверждённому грейду, навыкам, формату и ожиданиям"],
  fit: ["Избранное", "Кандидаты, которых вы сохранили. Приглашение при этом не отправляется"],
  team: ["Команда и совместимость", "Рекомендации по потребностям, профиль команды и добровольная анонимная анкета сотрудников"],
  invitations: ["Приглашения", "Отправленные предложения и их статусы"],
};

export default function EmployerApp({ session, shell }: { session: Session; shell: ShellCtx }) {
  const [tab, setTab] = useState<Tab>("match");
  const [company, setCompany] = useState("Работодатель");
  const [detail, setDetail] = useState<{ id: number; need: Need | null } | null>(null);
  const [counts, setCounts] = useState<{ needs: number; invites: number; favs: number } | null>(null);
  useEffect(() => { api<{ company_name: string }>("/api/employers/me", { token: session.token }).then((m) => setCompany(m.company_name)).catch(() => undefined); }, [session.token]);
  useEffect(() => {  // real counters for the sidebar card; refreshed when the tab changes
    Promise.all([
      api<Need[]>("/api/employer/needs", { token: session.token }),
      api<Invitation[]>("/api/employer/invitations", { token: session.token }),
      api<{ items: unknown[] }>("/api/employer/favorites", { token: session.token }),
    ]).then(([n, i, f]) => setCounts({ needs: n.length, invites: i.length, favs: f.items.length })).catch(() => undefined);
  }, [session.token, tab]);
  const open = (id: number, need: Need | null) => setDetail({ id, need });
  const items = [
    { key: "match", label: "Подбор", icon: "search" },
    { key: "pool", label: "Поиск кандидатов", icon: "list" },
    { key: "fit", label: "Избранное", icon: "star", count: counts?.favs },
    { key: "team", label: "Команда / Совместимость", icon: "users" },
    { key: "invitations", label: "Приглашения", icon: "mail", count: counts?.invites },
  ];
  const foot = counts && (
    <div className="side-card" aria-label="Сводка компании">
      Активность
      <div className="grade-big"><strong>{counts.needs}</strong><span className="muted">{counts.needs === 1 ? "потребность" : "потребностей"}</span></div>
      {counts.invites} приглашений отправлено · {counts.favs} в избранном
    </div>
  );
  const [title, sub] = TITLES[tab];
  return (
    <Shell items={items} active={tab} onSelect={(k) => { setTab(k as Tab); setDetail(null); }} who={{ label: company, role: "Работодатель" }} foot={foot} demoSession={session.demo}
      health={shell.health} demoMode={shell.demoMode} onLogout={shell.onLogout} onValidation={shell.onValidation}>
      {shell.banners}
      <PageHead title={title} sub={sub} />
      {detail && (
        <div className="drawer-scrim" onClick={(e) => { if (e.target === e.currentTarget) setDetail(null); }}>
          <div className="drawer" role="dialog" aria-label="Карточка кандидата">
            <CandidatePanel session={session} id={detail.id} need={detail.need} close={() => setDetail(null)} />
          </div>
        </div>
      )}
      {tab === "match" && <MatchTab session={session} open={open} />}
      {tab === "pool" && <PoolTab session={session} open={(id) => open(id, null)} />}
      {tab === "fit" && <EmployerFit session={session} open={open} view="favorites" />}
      {tab === "team" && <EmployerFit session={session} open={open} view="team" />}
      {tab === "invitations" && <SentTab session={session} open={(id) => open(id, null)} />}
    </Shell>
  );
}

/** Favorite ids for the star toggle; the server is the source of truth. */
function useFavorites(session: Session) {
  const [ids, setIds] = useState<Set<number>>(new Set());
  useEffect(() => {
    api<{ items: { candidate: { candidate_id: number } }[] }>("/api/employer/favorites", { token: session.token })
      .then((r) => setIds(new Set(r.items.map((i) => i.candidate.candidate_id)))).catch(() => undefined);
  }, [session.token]);
  const toggle = async (candidateId: number, needId: number | null) => {
    const on = ids.has(candidateId);
    try {
      if (on) await api(`/api/employer/favorites/${candidateId}`, { method: "DELETE", token: session.token });
      else await api("/api/employer/favorites", { token: session.token, body: { candidate_id: candidateId, need_id: needId, note: "" } });
      setIds((p) => { const n = new Set(p); if (on) n.delete(candidateId); else n.add(candidateId); return n; });
    } catch { /* the star stays as it was; the detail card shows the server message */ }
  };
  return { ids, toggle };
}

function CandidateRow({ c, fit, starred, onStar, onOpen, children }: {
  c: PublicCandidate; fit?: number; starred: boolean; onStar: () => void; onOpen: () => void; children?: React.ReactNode;
}) {
  const allVerified = (c.skills ?? []).filter((s) => s.verified_level);
  const verified = allVerified.slice(0, 4);
  return (
    <div className="cand">
      <Avatar name={c.display_name} />
      <div className="cand-main">
        <div className="cand-name">{c.display_name}<VerificationBadge status={c.verification_status} /></div>
        <div className="cand-meta">{gradeLine(c)}{c.location ? ` · ${c.location}` : ""}{c.salary_expectation ? ` · от ${c.salary_expectation.min.toLocaleString("ru-RU")} ₽ ${c.salary_expectation.type}` : ""}</div>
        <div className="chips">
          {verified.map((s) => <span key={s.skill} className="chip-skill on mini" title={`${skillName(s.skill)}: результат комплексной оценки по направлению (не сертификат)`}><Icon name="tick" size={12} />{skillName(s.skill)}</span>)}
          {allVerified.length > verified.length && <span className="chip-skill mini">+{allVerified.length - verified.length}</span>}
          {(c.work_experience ?? []).length > 0 && <Badge tone="muted">опыт: {c.work_experience!.length} (заявлен)</Badge>}
          {c.has_fsp && <Badge tone="info">ФСП (демо)</Badge>}
          {c.invitation_status && <InviteBadge status={c.invitation_status} />}
        </div>
      </div>
      <div className="cand-actions">
        {fit !== undefined && <div className="fit-pct"><b>{Math.round(fit * 100)}%</b><span>Соответствие требованиям</span><div className="progress thin" aria-hidden="true"><span style={{ width: `${Math.round(fit * 100)}%` }} /></div></div>}
        <button className="primary" onClick={onOpen}>Открыть</button>
        <button className={`star${starred ? " on" : ""}`} aria-pressed={starred} aria-label={starred ? "Убрать из избранного" : "В избранное"} title={starred ? "Убрать из избранного" : "В избранное"} onClick={onStar}><Icon name="star" size={16} /></button>
      </div>
      {children && <div className="cand-why">{children}</div>}
    </div>
  );
}

async function download(session: Session, runId: number, format: "csv" | "json"): Promise<void> {
  const r = await fetch(`/api/employer/match-runs/${runId}/export?format=${format}`, { headers: { authorization: `Bearer ${session.token}` } });
  if (!r.ok) return;
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `fsp-match-run-${runId}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

function MatchTab({ session, open }: { session: Session; open: (id: number, need: Need | null) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [needs, setNeeds] = useState<Need[]>([]);
  const [need, setNeed] = useState<Need | null>(null);
  const [res, setRes] = useState<MatchResponse | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const favs = useFavorites(session);
  const [f, setF] = useState({ title: "Python Backend (FastAPI)", grade: "MIDDLE", sub: "M2", req: ["api_fastapi", "postgresql"], opt: ["kafka", "docker_basics"],
    from: "200000", to: "250000", type: "GROSS", formats: ["REMOTE"], location: "", start: "", description: "Удалённая команда Python-бэкенда" });
  useEffect(() => {
    Promise.all([api<Catalog>("/api/catalog"), api<Need[]>("/api/employer/needs", { token: session.token })])
      .then(([c, n]) => { setCatalog(c); setNeeds(n); }).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  const replaceNeed = (n: Need) => setNeeds((cur) => cur.map((x) => (x.id === n.id ? n : x)));
  const setNeedState = async (n: Need, action: "close" | "reopen") => {
    try { replaceNeed(await api<Need>(`/api/employer/needs/${n.id}/${action}`, { token: session.token, method: "POST", body: {} })); } catch (e) { setErr((e as Error).message); }
  };
  const setPublic = async (n: Need, value: boolean) => {
    try { replaceNeed(await api<Need>(`/api/employer/needs/${n.id}/publication`, { token: session.token, method: "PUT", body: { public: value } })); } catch (e) { setErr((e as Error).message); }
  };
  const run = useCallback(async (n: Need) => {
    setBusy(true); setErr(""); setNeed(n); setShowAll(false);
    try { setRes(await api<MatchResponse>(`/api/employer/needs/${n.id}/match?limit=20`, { token: session.token, method: "POST" })); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [session.token]);
  const payload = () => ({
    title: f.title.trim(), target_grade: f.grade, target_sublevel: f.sub || null, required_skills: f.req, optional_skills: f.opt,
    salary_from: Number(f.from), salary_to: Number(f.to), salary_type: f.type, work_formats: f.formats,
    location: f.location || null, max_start_days: f.start ? Number(f.start) : null, description: f.description });
  const sameSet = (a: string[], b: string[]) => a.length === b.length && [...a].sort().join("|") === [...b].sort().join("|");
  /** An open need that already has exactly the form's terms: matching is re-run on it instead of creating a duplicate. */
  const existing = needs.find((n) => {
    const p = payload();
    return n.status !== "CLOSED" && n.title === p.title && n.target_grade === p.target_grade && (n.target_sublevel ?? null) === p.target_sublevel
      && n.salary_from === p.salary_from && n.salary_to === p.salary_to && n.salary_type === p.salary_type
      && (n.location ?? null) === p.location && (n.max_start_days ?? null) === p.max_start_days && (n.description ?? "") === p.description
      && sameSet(n.required_skills.map((x) => x.skill), p.required_skills) && sameSet(n.optional_skills.map((x) => x.skill), p.optional_skills)
      && sameSet(n.work_formats, p.work_formats);
  });
  const create = async () => {
    if (existing) { await run(existing); return; }
    setErr(""); setBusy(true);
    try {
      const n = await api<Need>("/api/employer/needs", { token: session.token, body: payload() });
      setNeeds([...needs, n]); await run(n);
    } catch (e) { setErr((e as Error).message); setBusy(false); }
  };
  if (!catalog) return err ? <ErrorBox message={err} /> : <Loading />;
  const toggle = (key: "req" | "opt" | "formats", v: string) => setF({ ...f, [key]: f[key].includes(v) ? f[key].filter((x) => x !== v) : [...f[key], v] });
  const rows = res ? (showAll ? res.results : res.results.slice(0, 5)) : [];
  return (
    <div className="grid">
      <Card title="Потребность работодателя">
        <div className="form-sec">Роль и уровень</div>
        <label>Роль *<input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
        <div className="row">
          <label>Грейд *<select value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value, sub: catalog.grades[e.target.value][1] })}>
            {Object.entries(GRADE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Подуровень<select value={f.sub} onChange={(e) => setF({ ...f, sub: e.target.value })}>
            <option value="">любой</option>{catalog.grades[f.grade].map((s) => <option key={s} value={s}>{subLabel(s)}</option>)}</select></label>
        </div>
        <div className="form-sec">Обязательные навыки *</div>
        <div className="chip-pick">
          {catalog.skills.map((s) => <label key={s.code} className={`${f.req.includes(s.code) ? "on" : ""}${f.opt.includes(s.code) ? " off" : ""}`}><input type="checkbox" checked={f.req.includes(s.code)} disabled={f.opt.includes(s.code)} onChange={() => toggle("req", s.code)} /><span className="mark" />{skillName(s.code, s.name)}</label>)}
        </div>
        <div className="form-sec">Желательные навыки</div>
        <div className="chip-pick">
          {catalog.skills.map((s) => <label key={s.code} className={`${f.opt.includes(s.code) ? "on" : ""}${f.req.includes(s.code) ? " off" : ""}`}><input type="checkbox" checked={f.opt.includes(s.code)} disabled={f.req.includes(s.code)} onChange={() => toggle("opt", s.code)} /><span className="mark" />{skillName(s.code, s.name)}</label>)}
        </div>
        <div className="form-sec">Условия</div>
        <div className="row compact">
          <label>Зарплата от, ₽<input inputMode="numeric" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value.replace(/\D/g, "") })} /></label>
          <label>до, ₽<input inputMode="numeric" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value.replace(/\D/g, "") })} /></label>
          <label>Тип<select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
        </div>
        <div className="chip-pick">
          {Object.entries(FORMAT_RU).map(([k, v]) => <label key={k} className={f.formats.includes(k) ? "on" : ""}><input type="checkbox" checked={f.formats.includes(k)} onChange={() => toggle("formats", k)} /><span className="mark" />{v}</label>)}
        </div>
        <div className="row">
          <label>Город (для офиса/гибрида)<input value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></label>
          <label>Выход не позже, дней<input inputMode="numeric" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value.replace(/\D/g, "") })} /></label>
        </div>
        <button className="primary large" style={{ width: "100%", marginTop: 8 }} disabled={busy || f.req.length === 0 || f.formats.length === 0} onClick={create}><Icon name="search" size={16} />{existing ? `Повторить подбор (потребность №${existing.id})` : "Создать потребность и подобрать"}</button>
        {needs.length > 0 && (
          <div><div className="form-sec">Ваши потребности</div>
            <div className="need-list">{needs.map((n) => (
              <span key={n.id} className="row" style={{ alignItems: "center", gap: 6, opacity: n.status === "CLOSED" ? 0.6 : 1 }}>
                <button className="small" disabled={n.status === "CLOSED"} onClick={() => run(n)} title={salaryRange(n.salary_from, n.salary_to, n.salary_type)}><Icon name="target" size={14} />{n.title} №{n.id} · {money(n.salary_from)}–{money(n.salary_to)} · {n.target_sublevel ? subLabel(n.target_sublevel) : "любой подуровень"} · обяз.: {n.required_skills.map((x) => skillName(x.skill, x.skill)).join(", ")}{n.status === "CLOSED" ? " · закрыта" : ""}</button>
                <button className="small" title="Закрытая потребность не участвует в подборе и новых приглашениях; история сохраняется" onClick={() => void setNeedState(n, n.status === "CLOSED" ? "reopen" : "close")}>{n.status === "CLOSED" ? "Открыть" : "Закрыть"}</button>
                {n.status !== "CLOSED" && <label className="muted" title="Кандидаты видят только опубликованные потребности"><input type="checkbox" checked={!!n.public_to_candidates} onChange={(e) => void setPublic(n, e.target.checked)} /> видна кандидатам</label>}
              </span>))}</div></div>
        )}
        {err && <ErrorBox message={err} />}
      </Card>
      <div className="stack">
        {busy && <Loading what="Подбираем" />}
        {!res && !busy && <Empty icon="search" title="Здесь появится короткий список">Опишите потребность слева — получите небольшой объяснимый список кандидатов: соответствие требованиям, почему подходит и какие пробелы. Контакты скрыты до согласия кандидата.</Empty>}
        {res && need && (
          <>
            <Card title={`Подбор: ${need.title}`}>
              <div className="stat-row" style={{ marginTop: 0, marginBottom: 10 }}>
                <span className="stat-pill"><b>{res.candidates_considered}</b>рассмотрено</span>
                <span className="stat-pill ok"><b>{res.matched_total}</b>прошли ограничения</span>
              </div>
              <div className="row" style={{ alignItems: "center", gap: 8 }}>
                <span className="muted">Экспорт в ATS (без контактов):</span>
                <button className="small" onClick={() => void download(session, res.run_id, "csv")}><Icon name="download" size={14} /> CSV</button>
                <button className="small" onClick={() => void download(session, res.run_id, "json")}><Icon name="download" size={14} /> JSON</button>
              </div>
              {Object.keys(res.excluded_summary).length > 0 && (
                <details><summary>Отсеяно по обязательным ограничениям</summary>
                  <ul>{Object.entries(res.excluded_summary).map(([k, v]) => <li key={k}>{EXCLUSION_RU[k] ?? k}: {v}</li>)}</ul></details>)}
            </Card>
            {res.results.length === 0 && <Empty icon="filter" title="Подходящих кандидатов нет">Попробуйте расширить зарплатную вилку, формат работы или снизить требования к подуровню.</Empty>}
            <div className="rows">
              {rows.map((r) => (
                <CandidateRow key={r.candidate.candidate_id} c={r.candidate} fit={r.requirement_fit} starred={favs.ids.has(r.candidate.candidate_id)}
                  onStar={() => void favs.toggle(r.candidate.candidate_id, need.id)} onOpen={() => open(r.candidate.candidate_id, need)}>
                  <details><summary>Почему подходит и пробелы ({r.why.length + r.gaps.length})</summary>
                    <FitBlock label={r.requirement_fit_label} fit={r.requirement_fit} why={r.why} gaps={r.gaps} />
                  </details>
                </CandidateRow>))}
            </div>
            {!showAll && res.results.length > 5 && <button onClick={() => setShowAll(true)}>Показать ещё ({res.results.length - 5})</button>}
          </>
        )}
      </div>
    </div>
  );
}

function CandidatePanel({ session, id, need, close }: { session: Session; id: number; need: Need | null; close: () => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState<Invitation | null>(null);
  const load = useCallback(() => {
    api<Detail>(`/api/employer/candidates/${id}${need ? `?need_id=${need.id}` : ""}`, { token: session.token }).then(setD).catch((e: Error) => setErr(e.message));
  }, [id, need, session.token]);
  useEffect(load, [load]);
  if (err) return <Card title="Кандидат"><ErrorBox message={err} /><button onClick={close}>Закрыть</button></Card>;
  if (!d) return <Loading what="Открываем кандидата" />;
  const fit = d.fit && d.fit.eligible ? d.fit : null;
  return (
    <Card title={d.display_name} aside={<><VerificationBadge status={d.verification_status} /><button onClick={close}>Закрыть</button></>}>
      <p className="muted">{gradeLine(d)} · {d.work_formats.map((x) => FORMAT_RU[x] ?? x).join(", ")}{d.location && ` · ${d.location}`}
        {d.salary_expectation && ` · ожидания от ${d.salary_expectation.min.toLocaleString("ru-RU")} ₽ ${d.salary_expectation.type}`}</p>
      <p><InviteBadge status={d.invitation_status} /></p>
      {d.verification_status !== "VERIFIED" && <p className="warn">Грейд кандидата не подтверждён основной оценкой — в подборе он учитывается с понижением.</p>}
      {d.fit && !d.fit.eligible && <p className="warn">Не проходит обязательные ограничения этой потребности: {d.fit.exclusions?.map((x) => EXCLUSION_RU[x] ?? x).join(", ")}.</p>}
      {fit && fit.requirement_fit !== undefined && <FitBlock label={fit.requirement_fit_label ?? ""} fit={fit.requirement_fit} why={fit.why ?? []} gaps={fit.gaps ?? []} />}
      {d.compat && (
        <>
          <h4>Ожидания кандидата и вакансия {d.compat.reverse_fit !== null && <Badge tone="info">{Math.round(d.compat.reverse_fit * 100)}%</Badge>}</h4>
          <ul>{d.compat.why.map((r, i) => <li key={i} className="ok">{r.text}</li>)}{d.compat.gaps.map((r, i) => <li key={i} className="warn">{r.text}</li>)}</ul>
          {d.compat.why.length + d.compat.gaps.length === 0 && <p className="muted">Кандидат не указал интересы и цели — оценить ожидания нельзя.</p>}
        </>)}
      <h4>Навыки и подтверждения</h4>
      {d.skills.length === 0 ? <Empty>Подтверждённых навыков нет.</Empty> : (
        <table className="table"><thead><tr><th>Навык</th><th>Подтверждение</th></tr></thead><tbody>
          {d.skills.map((s) => (
            <tr key={s.skill}><td data-label="Навык">{skillName(s.skill)}</td><td data-label="Подтверждение">
              {s.confirmed_by_exam && <Badge tone="ok">независимый экзамен по технологии</Badge>}
              {s.verified_level ? <Badge tone="ok">результат оценки: {GRADE_RU[s.verified_level]}</Badge> : s.claimed_only ? <Badge tone="muted">только заявлено</Badge> : null}
              {s.has_professional_experience && <Badge tone="muted">опыт (не подтверждён)</Badge>}
              {s.fsp_achievements.map((a) => <Badge key={a} tone="info">ФСП (демо): {a}</Badge>)}</td></tr>))}
        </tbody></table>)}
      {d.skills.length > 0 && <p className="muted" style={{ fontSize: 13 }}>«Результат оценки» — диагностика внутри комплексной оценки платформы. «Независимый экзамен» — отдельный экзамен по одной технологии (10–12 заданий); он подтверждает только этот навык, а не общий грейд. «Опыт» и «только заявлено» платформой не проверялись.</p>}
      {d.work_experience && d.work_experience.length > 0 && (
        <>
          <h4>Заявленный опыт работы <Badge tone="muted">не подтверждён</Badge></h4>
          <ul>{d.work_experience.map((e, i) => (
            <li key={i}>{e.position}, {e.company} · {e.start_date} — {e.end_date ?? "по настоящее время"}{e.stack.length > 0 && ` · ${e.stack.map((s) => skillName(s)).join(", ")}`}</li>))}</ul>
        </>)}
      {!d.has_fsp && <p className="muted">Истории ФСП нет — это не снижает грейд кандидата.</p>}
      <FavoriteButton session={session} candidateId={d.candidate_id} needId={need?.id ?? null} />
      <ContactBox unlocked={d.contact_status === "UNLOCKED"} contacts={d.contacts} />
      {sent ? <p className="ok" role="status">Приглашение отправлено ({STATUS_RU[sent.status]}). Открытие контактов — только после согласия кандидата.</p>
        : d.invitation_status && OPEN_INVITE.includes(d.invitation_status)
          ? <p className="muted">Приглашение этому кандидату уже отправлено ({STATUS_RU[d.invitation_status] ?? d.invitation_status}) — повторно приглашать нельзя, пока оно активно.</p>
          : <InviteForm session={session} candidateId={d.candidate_id} need={need} declined={d.invitation_status === "DECLINED"} done={(i) => { setSent(i); load(); }} />}
    </Card>
  );
}

function FavoriteButton({ session, candidateId, needId }: { session: Session; candidateId: number; needId: number | null }) {
  const [msg, setMsg] = useState("");
  const [note, setNote] = useState("");
  const save = async () => {
    try { await api("/api/employer/favorites", { token: session.token, body: { candidate_id: candidateId, need_id: needId, note } }); setMsg("Сохранено в избранное. Кандидат ничего не получает."); }
    catch (e) { setMsg((e as Error).message); }
  };
  return (
    <div className="row">
      <input placeholder="Заметка (необязательно)" value={note} onChange={(e) => setNote(e.target.value)} />
      <button onClick={save}>★ В избранное</button>
      {msg && <span role="status">{msg}</span>}
    </div>
  );
}

function InviteForm({ session, candidateId, need, declined, done }: { session: Session; candidateId: number; need: Need | null; declined: boolean; done: (i: Invitation) => void }) {
  const [needs, setNeeds] = useState<Need[]>([]);
  const [mode, setMode] = useState<"need" | "custom">(need ? "need" : "custom");
  const [needId, setNeedId] = useState<number | null>(need?.id ?? null);
  const [f, setF] = useState({ role: "", tasks: "", reqs: "", terms: "", from: "", to: "", type: "", format: "REMOTE", message: "Здравствуйте! Нам интересен ваш подтверждённый опыт." });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  // Тексты (задачи/требования/условия/сообщение) хранятся отдельно для каждой потребности: A → B → A возвращает A.
  const drafts = useRef<Record<number, { tasks: string; reqs: string; terms: string; message: string }>>({});
  const activeNeed = useRef<number | null>(null);
  const fRef = useRef(f);
  fRef.current = f;
  const applyNeed = useCallback((n: Need) => {  // условия потребности фиксируются; правится только текст в её рамках
    if (activeNeed.current !== null && activeNeed.current !== n.id) {
      const c = fRef.current;
      drafts.current[activeNeed.current] = { tasks: c.tasks, reqs: c.reqs, terms: c.terms, message: c.message };
    }
    const keep = activeNeed.current === n.id;
    activeNeed.current = n.id;
    setNeedId(n.id);
    setF((p) => {
      const d = keep ? { tasks: p.tasks, reqs: p.reqs, terms: p.terms, message: p.message }
        : drafts.current[n.id] ?? { tasks: n.description ?? "", reqs: "", terms: "", message: p.message };
      return { ...p, ...d, role: n.title, from: String(n.salary_from), to: String(n.salary_to), type: n.salary_type,
        format: n.work_formats.includes(p.format) && keep ? p.format : n.work_formats[0] ?? p.format };
    });
  }, []);
  useEffect(() => { api<Need[]>("/api/employer/needs", { token: session.token }).then(setNeeds).catch(() => undefined); }, [session.token]);
  useEffect(() => { if (need) applyNeed(need); }, [need, applyNeed]);
  const chosen = needs.find((n) => n.id === needId) ?? (need && need.id === needId ? need : null);
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });
  const locked = mode === "need" && chosen !== null;  // role / salary type / range / format come from the saved need
  const missing: string[] = [];
  if (mode === "need" && needId === null) missing.push("выберите потребность или переключитесь на самостоятельное предложение");
  if (!f.role.trim()) missing.push("укажите должность");
  if (f.tasks.trim().length < 5) missing.push("опишите задачи");
  if (f.reqs.trim().length < 5) missing.push("опишите требования");
  if (f.terms.trim().length < 5) missing.push("опишите условия работы");
  if (!f.from || !f.to) missing.push("укажите зарплатную вилку");
  else if (Number(f.to) < Number(f.from)) missing.push("«до» не может быть меньше «от»");
  else if (locked && (Number(f.from) < chosen!.salary_from || Number(f.to) > chosen!.salary_to)) missing.push(`вилка должна быть в пределах потребности: ${chosen!.salary_from}–${chosen!.salary_to}`);
  if (!f.type) missing.push("выберите тип зарплаты (GROSS или NET)");
  if (!f.message.trim()) missing.push("напишите сообщение кандидату");
  const description = `Задачи:\n${f.tasks.trim()}\n\nТребования:\n${f.reqs.trim()}\n\nУсловия:\n${f.terms.trim()}`;
  const send = async () => {
    if (missing.length || busy) return;  // защита от обхода disabled; сервер проверяет всё повторно
    setErr(""); setBusy(true);
    try {
      done(await api<Invitation>("/api/employer/invitations", { token: session.token, body: {
        candidate_id: candidateId, need_id: mode === "need" ? needId : null, role: f.role.trim(), description, salary_from: Number(f.from),
        salary_to: Number(f.to), salary_type: f.type, work_format: f.format, message: f.message.trim() } }));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="invite">
      <h4>Приглашение с зарплатой</h4>
      {declined && <p className="muted">Кандидат ранее отклонил приглашение — можно отправить новое предложение с другими условиями.</p>}
      <div className="row">
        <button className={mode === "need" ? "tab active" : "tab"} onClick={() => { setMode("need"); if (chosen) applyNeed(chosen); }}>По потребности</button>
        <button className={mode === "custom" ? "tab active" : "tab"} onClick={() => { setMode("custom"); setNeedId(null); activeNeed.current = null; }}>Самостоятельное предложение</button>
      </div>
      {mode === "need" && (
        <label>Потребность *<select value={needId ?? ""} onChange={(e) => { const n = needs.find((x) => x.id === Number(e.target.value)); if (n) applyNeed(n); else setNeedId(null); }}>
          <option value="">выберите…</option>{needs.filter((n) => n.status !== "CLOSED").map((n) => <option key={n.id} value={n.id}>{n.title} · №{n.id} · {money(n.salary_from)}–{money(n.salary_to)}</option>)}</select></label>)}
      <div className="row">
        <label>Должность *<input value={f.role} readOnly={locked} onChange={(e) => set("role", e.target.value)} /></label>
        <label>Формат<select value={f.format} onChange={(e) => set("format", e.target.value)}>{Object.entries(FORMAT_RU).filter(([k]) => !locked || chosen!.work_formats.includes(k)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      </div>
      <label>Задачи *<textarea rows={2} placeholder="Чем предстоит заниматься" value={f.tasks} onChange={(e) => set("tasks", e.target.value)} /></label>
      <label>Требования *<textarea rows={2} placeholder="Стек, опыт, что важно" value={f.reqs} onChange={(e) => set("reqs", e.target.value)} /></label>
      <label>Условия *<textarea rows={2} placeholder="График, команда, оформление, бонусы" value={f.terms} onChange={(e) => set("terms", e.target.value)} /></label>
      <div className="row">
        <label>Зарплата от, ₽ *<input inputMode="numeric" value={f.from} onChange={(e) => set("from", e.target.value.replace(/\D/g, ""))} /></label>
        <label>до, ₽ *<input inputMode="numeric" value={f.to} onChange={(e) => set("to", e.target.value.replace(/\D/g, ""))} /></label>
        <label>Тип зарплаты *<select value={f.type} disabled={locked} onChange={(e) => set("type", e.target.value)}><option value="">выберите…</option><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
      </div>
      {locked && <p className="muted">Должность, формат, тип и вилка зарплаты заданы потребностью «{chosen!.title}»: {salaryRange(chosen!.salary_from, chosen!.salary_to, chosen!.salary_type)}. Для других условий используйте «Самостоятельное предложение».</p>}
      <label>Сообщение *<textarea rows={2} value={f.message} onChange={(e) => set("message", e.target.value)} /></label>
      <p className="muted">Зарплатная вилка и тип зарплаты обязательны — сервер не примет приглашение без них. Контакты кандидата откроются только после его согласия.</p>
      {missing.length > 0 && <ul className="warn" aria-label="Что нужно заполнить">{missing.map((m) => <li key={m}>{m}</li>)}</ul>}
      <button className="primary" disabled={missing.length > 0 || busy} onClick={send}>Отправить приглашение</button>
      {err && <ErrorBox message={err} />}
    </div>
  );
}

function PoolTab({ session, open }: { session: Session; open: (id: number) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [q, setQ] = useState({ grade: "", sublevel: "", verification: "", skill: "", has_fsp: "", work_format: "", location: "", salary_max: "" });
  const [res, setRes] = useState<{ total: number; candidates: PublicCandidate[] } | null>(null);
  const [err, setErr] = useState("");
  const [text, setText] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [seg, setSeg] = useState<"all" | "verified" | "fsp" | "saved">("all");
  const favs = useFavorites(session);
  useEffect(() => { api<Catalog>("/api/catalog").then(setCatalog).catch((e: Error) => setErr(e.message)); }, []);
  const search = useCallback(() => {
    const p = new URLSearchParams({ limit: "100" });
    Object.entries(q).forEach(([k, v]) => { if (v) p.set(k, v); });
    api<{ total: number; candidates: PublicCandidate[] }>(`/api/employer/pool?${p}`, { token: session.token }).then(setRes).catch((e: Error) => setErr(e.message));
  }, [q, session.token]);
  useEffect(search, [search]);
  const sel = (k: keyof typeof q, opts: [string, string][], label: string) => (
    <label>{label}<select value={q[k]} onChange={(e) => setQ({ ...q, [k]: e.target.value, ...(k === "grade" ? { sublevel: "" } : {}) })}><option value="">любой</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>);
  const needle = text.trim().toLowerCase();
  const shown = (res?.candidates ?? []).filter((c) => !needle || [c.display_name, c.specialization ?? "", c.location ?? "", ...(c.skills ?? []).map((s) => skillName(s.skill))].join(" ").toLowerCase().includes(needle));
  const active = Object.values(q).filter(Boolean).length;
  const SEGS: { key: typeof seg; label: string; test: (c: PublicCandidate) => boolean }[] = [
    { key: "all", label: "Все кандидаты", test: () => true },
    { key: "verified", label: "Подтверждённые", test: (c) => c.verification_status === "VERIFIED" },
    { key: "fsp", label: "С достижениями ФСП", test: (c) => c.has_fsp },
    { key: "saved", label: "Сохранённые", test: (c) => favs.ids.has(c.candidate_id) },
  ];
  const countOf = (t: (c: PublicCandidate) => boolean) => shown.filter(t).length;
  const list = shown.filter((SEGS.find((x) => x.key === seg) ?? SEGS[0]).test);
  return (
    <div>
      <div className="search">
        <input aria-label="Поиск по имени, навыкам, городу" placeholder="Поиск по имени, навыкам, городу…" value={text} onChange={(e) => setText(e.target.value)} />
        <button onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}><Icon name="filter" size={16} /> Фильтры{active > 0 ? ` (${active})` : ""}</button>
      </div>
      {showFilters && (
        <div className="filters">
          {sel("grade", Object.entries(GRADE_RU), "Подтверждённый грейд платформы")}
          {sel("sublevel", (q.grade && catalog ? catalog.grades[q.grade] : ["J1", "J2", "J3", "M1", "M2", "M3", "S1", "S2", "S3"]).map((s) => [s, subLabel(s)]), "Подуровень (подтверждён тестом)")}
          {sel("verification", [["VERIFIED", "Подтверждено"], ["NOT_VERIFIED", "Не подтверждено"], ["UNVERIFIED", "Оценка не пройдена"]], "Статус подтверждения")}
          {catalog && sel("skill", catalog.skills.map((s) => [s.code, skillName(s.code, s.name)]), "Подтверждённый навык")}
          {sel("has_fsp", [["true", "есть"], ["false", "нет"]], "Достижения ФСП")}
          {sel("work_format", Object.entries(FORMAT_RU), "Формат работы")}
          <label>Город<input value={q.location} onChange={(e) => setQ({ ...q, location: e.target.value })} /></label>
          <label>Ожидания не выше, ₽<input inputMode="numeric" value={q.salary_max} onChange={(e) => setQ({ ...q, salary_max: e.target.value.replace(/\D/g, "") })} /></label>
        </div>)}
      {err && <ErrorBox message={err} />}
      {!res ? <Loading /> : (<>
        <div className="pool-tabs" role="tablist" aria-label="Сегмент">
          {SEGS.map((x) => <button key={x.key} role="tab" aria-selected={seg === x.key} className={seg === x.key ? "active" : ""} onClick={() => setSeg(x.key)}>{x.label} <b>{x.key === "all" ? shown.length : countOf(x.test)}</b></button>)}
        </div>
        <p className="muted" style={{ marginTop: 0 }}>Контакты кандидатов скрыты до их согласия (открытие контактов — только после принятия приглашения).</p>
        {list.length === 0 ? <Empty icon="filter" title="Никого не найдено">Измените фильтры, сегмент или поисковый запрос — часть кандидатов скрыта настройками видимости.</Empty> : (
          <div className="rows">
            {list.map((c) => <CandidateRow key={c.candidate_id} c={c} starred={favs.ids.has(c.candidate_id)} onStar={() => void favs.toggle(c.candidate_id, null)} onOpen={() => open(c.candidate_id)} />)}
          </div>)}
      </>)}
    </div>
  );
}

function SentTab({ session, open }: { session: Session; open: (id: number) => void }) {
  const [list, setList] = useState<Invitation[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => { api<Invitation[]>("/api/employer/invitations", { token: session.token }).then(setList).catch((e: Error) => setErr(e.message)); }, [session.token]);
  useEffect(load, [load]);
  if (err) return <ErrorBox message={err} />;
  if (!list) return <Loading />;
  return (
    <div className="stack">
      <div><button onClick={load}>Обновить статусы</button></div>
      {list.length === 0 ? <Empty icon="mail" title="Приглашений пока нет">Откройте кандидата из подбора и отправьте предложение с зарплатой — статусы появятся здесь.</Empty> : list.map((i) => (
        <Card key={i.id} title={`${i.candidate?.display_name ?? "Кандидат"} — ${i.role}`} aside={<Badge tone={i.status === "DECLINED" ? "bad" : i.contacts_unlocked ? "ok" : "info"}>{STATUS_RU[i.status]}</Badge>}>
          {i.candidate && <p className="muted">{gradeLine(i.candidate)}</p>}
          <SalaryBanner from={i.salary_from} to={i.salary_to} type={i.salary_type} />
          {i.description && <details><summary>Описание предложения</summary><p style={{ whiteSpace: "pre-wrap" }}>{i.description}</p></details>}
          {i.candidate_id !== undefined && <button onClick={() => open(i.candidate_id!)}>Открыть карточку кандидата</button>}
          <ContactBox unlocked={!!i.contacts_unlocked} contacts={i.contacts} />
        </Card>))}
    </div>
  );
}
