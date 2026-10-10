import { useCallback, useEffect, useState } from "react";
import { api, type Session } from "./api";
import { EmployerFit } from "./TeamFit";
import type { Catalog, Fit, Invitation, MatchRow, Need, PublicCandidate } from "./types";
import {
  Badge, Card, ContactBox, Empty, ErrorBox, FitBlock, FORMAT_RU, GRADE_RU, Loading, SalaryBanner, salaryRange, SALARY_TYPE_RU, skillName,
  STATUS_RU, VerificationBadge, subLabel } from "./ui";

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

export default function EmployerApp({ session }: { session: Session }) {
  const [tab, setTab] = useState<"match" | "pool" | "fit" | "invitations">("match");
  const [detail, setDetail] = useState<{ id: number; need: Need | null } | null>(null);
  const open = (id: number, need: Need | null) => { setDetail({ id, need }); window.scrollTo?.({ top: 0 }); };
  const tabs: [typeof tab, string][] = [["match", "Подбор по потребности"], ["pool", "Весь пул кандидатов"], ["fit", "Избранное и рекомендации"], ["invitations", "Отправленные приглашения"]];
  return (
    <>
      <h2 className="section-title">Кабинет работодателя</h2>
      <nav className="tabs" aria-label="Работодатель">
        {tabs.map(([k, l]) => <button key={k} className={tab === k ? "tab active" : "tab"} onClick={() => { setTab(k); setDetail(null); }}>{l}</button>)}
      </nav>
      {detail && <CandidatePanel session={session} id={detail.id} need={detail.need} close={() => setDetail(null)} />}
      {tab === "match" && <MatchTab session={session} open={open} />}
      {tab === "pool" && <PoolTab session={session} open={(id) => open(id, null)} />}
      {tab === "fit" && <EmployerFit session={session} open={open} />}
      {tab === "invitations" && <SentTab session={session} />}
    </>
  );
}

function MatchTab({ session, open }: { session: Session; open: (id: number, need: Need | null) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [needs, setNeeds] = useState<Need[]>([]);
  const [need, setNeed] = useState<Need | null>(null);
  const [res, setRes] = useState<MatchResponse | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ title: "Python Backend (FastAPI)", grade: "MIDDLE", sub: "M2", req: ["api_fastapi", "postgresql"], opt: ["kafka", "docker_basics"],
    from: "200000", to: "250000", type: "GROSS", formats: ["REMOTE"], location: "", start: "", description: "Удалённая команда Python-бэкенда" });
  useEffect(() => {
    Promise.all([api<Catalog>("/api/catalog"), api<Need[]>("/api/employer/needs", { token: session.token })])
      .then(([c, n]) => { setCatalog(c); setNeeds(n); }).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  const run = useCallback(async (n: Need) => {
    setBusy(true); setErr(""); setNeed(n); setShowAll(false);
    try { setRes(await api<MatchResponse>(`/api/employer/needs/${n.id}/match?limit=20`, { token: session.token, method: "POST" })); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [session.token]);
  const create = async () => {
    setErr(""); setBusy(true);
    try {
      const n = await api<Need>("/api/employer/needs", { token: session.token, body: {
        title: f.title, target_grade: f.grade, target_sublevel: f.sub || null, required_skills: f.req, optional_skills: f.opt,
        salary_from: Number(f.from), salary_to: Number(f.to), salary_type: f.type, work_formats: f.formats,
        location: f.location || null, max_start_days: f.start ? Number(f.start) : null, description: f.description } });
      setNeeds([...needs, n]); await run(n);
    } catch (e) { setErr((e as Error).message); setBusy(false); }
  };
  if (!catalog) return err ? <ErrorBox message={err} /> : <Loading />;
  const toggle = (key: "req" | "opt" | "formats", v: string) => setF({ ...f, [key]: f[key].includes(v) ? f[key].filter((x) => x !== v) : [...f[key], v] });
  const rows = res ? (showAll ? res.results : res.results.slice(0, 5)) : [];
  return (
    <div className="grid">
      <Card title="Потребность работодателя">
        <label>Роль<input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
        <div className="row">
          <label>Грейд<select value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value, sub: catalog.grades[e.target.value][1] })}>
            {Object.entries(GRADE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Подуровень<select value={f.sub} onChange={(e) => setF({ ...f, sub: e.target.value })}>
            <option value="">любой</option>{catalog.grades[f.grade].map((s) => <option key={s} value={s}>{subLabel(s)}</option>)}</select></label>
        </div>
        <fieldset><legend>Обязательные навыки</legend>
          {catalog.skills.map((s) => <label key={s.code} className="check"><input type="checkbox" checked={f.req.includes(s.code)} disabled={f.opt.includes(s.code)} onChange={() => toggle("req", s.code)} />{skillName(s.code, s.name)}{!s.verifiable && <span className="muted"> (опыт)</span>}</label>)}
        </fieldset>
        <fieldset><legend>Желательные навыки</legend>
          {catalog.skills.map((s) => <label key={s.code} className="check"><input type="checkbox" checked={f.opt.includes(s.code)} disabled={f.req.includes(s.code)} onChange={() => toggle("opt", s.code)} />{skillName(s.code, s.name)}</label>)}
        </fieldset>
        <div className="row">
          <label>Зарплата от, ₽<input inputMode="numeric" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value.replace(/\D/g, "") })} /></label>
          <label>до, ₽<input inputMode="numeric" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value.replace(/\D/g, "") })} /></label>
          <label>Тип<select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
        </div>
        <fieldset><legend>Формат работы</legend>
          {Object.entries(FORMAT_RU).map(([k, v]) => <label key={k} className="check"><input type="checkbox" checked={f.formats.includes(k)} onChange={() => toggle("formats", k)} />{v}</label>)}
        </fieldset>
        <div className="row">
          <label>Город (для офиса/гибрида)<input value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></label>
          <label>Выход не позже, дней<input inputMode="numeric" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value.replace(/\D/g, "") })} /></label>
        </div>
        <button className="primary" disabled={busy || f.req.length === 0 || f.formats.length === 0} onClick={create}>Подобрать кандидатов</button>
        {needs.length > 0 && (
          <div><h4>Ваши потребности</h4>{needs.map((n) => <button key={n.id} className="link" onClick={() => run(n)}>{n.title} · {salaryRange(n.salary_from, n.salary_to, n.salary_type)}</button>)}</div>
        )}
        {err && <ErrorBox message={err} />}
      </Card>
      <div>
        {busy && <Loading what="Подбираем" />}
        {!res && !busy && <Empty>Опишите потребность — получите небольшой объяснимый список кандидатов: почему подходит и какие пробелы.</Empty>}
        {res && need && (
          <>
            <Card title={`Подбор: ${need.title}`}>
              <p>Рассмотрено кандидатов: {res.candidates_considered}. Обязательные ограничения прошли: {res.matched_total}.</p>
              {Object.keys(res.excluded_summary).length > 0 && (
                <details><summary>Отсеяно по обязательным ограничениям</summary>
                  <ul>{Object.entries(res.excluded_summary).map(([k, v]) => <li key={k}>{EXCLUSION_RU[k] ?? k}: {v}</li>)}</ul></details>)}
            </Card>
            {res.results.length === 0 && <Empty>Подходящих кандидатов нет. Попробуйте расширить вилку или формат работы.</Empty>}
            {rows.map((r) => (
              <Card key={r.candidate.candidate_id} title={`#${r.rank} ${r.candidate.display_name}`} aside={<VerificationBadge status={r.candidate.verification_status} />}>
                <p className="muted">{r.candidate.claimed_grade ? GRADE_RU[r.candidate.claimed_grade] : "—"} (заявлено){r.candidate.verified_grade && ` · подтверждено ${GRADE_RU[r.candidate.verified_grade]} ${subLabel(r.candidate.verified_sublevel)}`}
                  {r.candidate.has_fsp && <> · <Badge tone="info">достижения ФСП (демо-данные)</Badge></>}</p>
                <FitBlock label={r.requirement_fit_label} fit={r.requirement_fit} why={r.why} gaps={r.gaps} />
                <button className="primary" onClick={() => open(r.candidate.candidate_id, need)}>Открыть кандидата</button>
              </Card>))}
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
      <p className="muted">{d.claimed_grade ? GRADE_RU[d.claimed_grade] : "—"} (заявлено){d.verified_grade && ` · подтверждено ${GRADE_RU[d.verified_grade]} ${subLabel(d.verified_sublevel)}`} · {d.work_formats.map((x) => FORMAT_RU[x] ?? x).join(", ")}{d.location && ` · ${d.location}`}
        {d.salary_expectation && ` · ожидания от ${d.salary_expectation.min.toLocaleString("ru-RU")} ₽ ${d.salary_expectation.type}`}</p>
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
            <tr key={s.skill}><td>{skillName(s.skill)}</td><td>
              {s.verified_level ? <Badge tone="ok">подтверждено оценкой: {GRADE_RU[s.verified_level]}</Badge> : s.claimed_only ? <Badge tone="muted">только заявлено</Badge> : null}
              {s.has_professional_experience && <Badge tone="muted">опыт (не подтверждён)</Badge>}
              {s.fsp_achievements.map((a) => <Badge key={a} tone="info">ФСП (демо): {a}</Badge>)}</td></tr>))}
        </tbody></table>)}
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
        : d.contact_status === "LOCKED" && <InviteForm session={session} candidateId={d.candidate_id} need={need} done={(i) => { setSent(i); load(); }} />}
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

function InviteForm({ session, candidateId, need, done }: { session: Session; candidateId: number; need: Need | null; done: (i: Invitation) => void }) {
  const [f, setF] = useState({ role: need?.title ?? "", description: need ? `Работа в команде: ${need.title}` : "", from: need?.salary_from.toString() ?? "", to: need?.salary_to.toString() ?? "",
    type: "", format: need?.work_formats[0] ?? "REMOTE", message: "Здравствуйте! Нам интересен ваш подтверждённый опыт." });
  const [err, setErr] = useState("");
  const ready = f.role && f.description && f.from && f.to && f.type && f.message;
  const send = async () => {
    setErr("");
    try {
      done(await api<Invitation>("/api/employer/invitations", { token: session.token, body: {
        candidate_id: candidateId, need_id: need?.id ?? null, role: f.role, description: f.description, salary_from: Number(f.from),
        salary_to: Number(f.to), salary_type: f.type, work_format: f.format, message: f.message } }));
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="invite">
      <h4>Приглашение с зарплатой</h4>
      <label>Роль<input value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} /></label>
      <label>Описание<textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
      <div className="row">
        <label>Зарплата от, ₽ *<input inputMode="numeric" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value.replace(/\D/g, "") })} /></label>
        <label>до, ₽ *<input inputMode="numeric" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value.replace(/\D/g, "") })} /></label>
        <label>Тип зарплаты *<select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="">выберите…</option><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
        <label>Формат<select value={f.format} onChange={(e) => setF({ ...f, format: e.target.value })}>{Object.entries(FORMAT_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      </div>
      <label>Сообщение<textarea value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} /></label>
      <p className="muted">Зарплатная вилка и тип зарплаты (GROSS — до налогов, NET — на руки) обязательны — сервер не примет приглашение без них.</p>
      <button className="primary" disabled={!ready} onClick={send}>Отправить приглашение</button>
      {err && <ErrorBox message={err} />}
    </div>
  );
}

function PoolTab({ session, open }: { session: Session; open: (id: number) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [q, setQ] = useState({ grade: "", sublevel: "", verification: "", skill: "", has_fsp: "", work_format: "", location: "", salary_max: "" });
  const [res, setRes] = useState<{ total: number; candidates: PublicCandidate[] } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Catalog>("/api/catalog").then(setCatalog).catch((e: Error) => setErr(e.message)); }, []);
  const search = useCallback(() => {
    const p = new URLSearchParams({ limit: "100" });
    Object.entries(q).forEach(([k, v]) => { if (v) p.set(k, v); });
    api<{ total: number; candidates: PublicCandidate[] }>(`/api/employer/pool?${p}`, { token: session.token }).then(setRes).catch((e: Error) => setErr(e.message));
  }, [q, session.token]);
  useEffect(search, [search]);
  const sel = (k: keyof typeof q, opts: [string, string][], label: string) => (
    <label>{label}<select value={q[k]} onChange={(e) => setQ({ ...q, [k]: e.target.value, ...(k === "grade" ? { sublevel: "" } : {}) })}><option value="">любой</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>);
  return (
    <div className="grid">
      <Card title="Фильтры">
        {sel("grade", Object.entries(GRADE_RU), "Подтверждённый грейд платформы")}
        {sel("sublevel", (q.grade && catalog ? catalog.grades[q.grade] : ["J1", "J2", "J3", "M1", "M2", "M3", "S1", "S2", "S3"]).map((s) => [s, subLabel(s)]), "Подуровень (подтверждён тестом)")}
        {sel("verification", [["VERIFIED", "Подтверждено"], ["NOT_VERIFIED", "Не подтверждено"], ["UNVERIFIED", "Оценка не пройдена"]], "Статус подтверждения")}
        {catalog && sel("skill", catalog.skills.map((s) => [s.code, skillName(s.code, s.name)]), "Подтверждённый навык")}
        {sel("has_fsp", [["true", "есть"], ["false", "нет"]], "Достижения ФСП")}
        {sel("work_format", Object.entries(FORMAT_RU), "Формат работы")}
        <label>Город<input value={q.location} onChange={(e) => setQ({ ...q, location: e.target.value })} /></label>
        <label>Ожидания не выше, ₽<input inputMode="numeric" value={q.salary_max} onChange={(e) => setQ({ ...q, salary_max: e.target.value.replace(/\D/g, "") })} /></label>
      </Card>
      <div>
        {err && <ErrorBox message={err} />}
        {!res ? <Loading /> : (<>
          <p className="muted">Найдено: {res.total}. Контакты кандидатов скрыты до их согласия (открытие контактов — только после принятия приглашения).</p>
          {res.candidates.length === 0 && <Empty>По этим фильтрам никого нет.</Empty>}
          {res.candidates.map((c) => (
            <Card key={c.candidate_id} title={c.display_name} aside={<VerificationBadge status={c.verification_status} />}>
              <p className="muted">{c.claimed_grade ? GRADE_RU[c.claimed_grade] : "—"} (заявлено){c.verified_grade && ` · подтверждено ${GRADE_RU[c.verified_grade]} ${subLabel(c.verified_sublevel)}`}
                {c.has_fsp ? " · ФСП (демо)" : ""}{c.salary_expectation ? ` · от ${c.salary_expectation.min.toLocaleString("ru-RU")} ₽ ${c.salary_expectation.type}` : ""}</p>
              <button onClick={() => open(c.candidate_id)}>Открыть</button>
            </Card>))}
        </>)}
      </div>
    </div>
  );
}

function SentTab({ session }: { session: Session }) {
  const [list, setList] = useState<Invitation[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => { api<Invitation[]>("/api/employer/invitations", { token: session.token }).then(setList).catch((e: Error) => setErr(e.message)); }, [session.token]);
  useEffect(load, [load]);
  if (err) return <ErrorBox message={err} />;
  if (!list) return <Loading />;
  return (
    <div>
      <button onClick={load}>Обновить статусы</button>
      {list.length === 0 ? <Empty>Вы ещё не отправляли приглашений. Откройте кандидата из подбора и отправьте предложение с зарплатой.</Empty> : list.map((i) => (
        <Card key={i.id} title={`Кандидат #${i.candidate_id} — ${i.role}`} aside={<Badge tone={i.status === "DECLINED" ? "bad" : i.contacts_unlocked ? "ok" : "info"}>{STATUS_RU[i.status]}</Badge>}>
          <SalaryBanner from={i.salary_from} to={i.salary_to} type={i.salary_type} />
          <ContactBox unlocked={!!i.contacts_unlocked} contacts={i.contacts} />
        </Card>))}
    </div>
  );
}
