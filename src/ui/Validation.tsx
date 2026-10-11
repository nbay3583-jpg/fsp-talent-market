import { useEffect, useState } from "react";
import { api } from "./api";
import { Card, ErrorBox, Kpi, Loading, PageHead } from "./ui";

type Row = Record<string, number>;
interface Summary {
  dataset: { candidates: number; needs: number; label_cells: number; nonzero_labels: number; relevant_threshold: number };
  matching: Record<string, Row>;
  deterministic_ordering: boolean;
  assessment: {
    kind: string; cases: number; grade_accuracy: number; variant_stability: { identical_outcome_rate: number; pairs: number; max_abs_score_diff: number };
    disagreement_over_one_sublevel_rate: number; deterministic: boolean;
    discrimination: Record<string, { auc_knowers_vs_others: number }>;
    guessing_baseline: Record<string, { false_verification_rate: number; items: number }>;
  };
  limitations: string[];
}

const NAMES: Record<string, string> = { keyword_baseline: "Поиск по ключевым словам", hard_filters_only: "Только обязательные ограничения", evidence_matching: "Подбор по подтверждённым компетенциям (наша система)" };
const METRICS: [string, string][] = [["p@3", "Precision@3"], ["p@5", "Precision@5"], ["r@10", "Recall@10"], ["ndcg@10", "nDCG@10"]];
const f3 = (n: number) => n.toFixed(3);
const signed = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(3)}`;

export default function Validation() {
  const [s, setS] = useState<Summary | null>(null);
  const [err, setErr] = useState("");
  const [metric, setMetric] = useState("p@5");
  useEffect(() => { api<Summary>("/api/validation/summary").then(setS).catch((e: Error) => setErr(e.message)); }, []);
  if (err) return <ErrorBox message={`Артефакт валидации недоступен: ${err}`} />;
  if (!s) return <Loading />;

  const methods = Object.keys(NAMES).filter((k) => s.matching[k]);
  const ours = s.matching.evidence_matching, kw = s.matching.keyword_baseline, hf = s.matching.hard_filters_only;
  const label = METRICS.find(([k]) => k === metric)?.[1] ?? metric;
  const toneOf = (k: string) => (k === "evidence_matching" ? "hl" : k === "hard_filters_only" ? "mid" : "");
  const takeaways: string[] = [];
  if (ours && kw) takeaways.push(`Наша система против поиска по ключевым словам: Precision@5 ${f3(ours["p@5"])} против ${f3(kw["p@5"])} (${signed(ours["p@5"] - kw["p@5"])}), nDCG@10 ${f3(ours["ndcg@10"])} против ${f3(kw["ndcg@10"])}.`);
  if (ours && hf) takeaways.push(`Против «только обязательных ограничений»: Precision@5 ${signed(ours["p@5"] - hf["p@5"])}, Recall@10 ${signed(ours["r@10"] - hf["r@10"])}.`);
  if (ours) takeaways.push(`Нарушений обязательных ограничений в top-10 у нашей системы: ${ours["constraint_violations@10"]} из ${ours["returned@10"]}; порядок выдачи детерминирован: ${s.deterministic_ordering ? "да" : "нет"}.`);

  return (
    <div>
      <PageHead title="Валидация" sub="MVP-валидация на собственном фиксированном наборе, воспроизводимая командой python -m fsp_market.validation" />
      <div className="kpis">
        <Kpi tone="mint" icon="users" label="Кандидатов в наборе" value={s.dataset.candidates} sub="синтетические профили" />
        <Kpi label="Потребностей" value={s.dataset.needs} sub="разметка вручную" />
        <Kpi label="Метода подбора" value={methods.length} sub="сравниваются на одних данных" />
        <Kpi tone="mint" label="Детерминизм" value={s.deterministic_ordering && s.assessment.deterministic ? "Да" : s.deterministic_ordering || s.assessment.deterministic ? "Частично" : "Нет"} sub="подбор и оценка" />
      </div>

      <div className="grid-2" style={{ alignItems: "start" }}>
        <Card title="Сравнение методов подбора">
          <div className="cols" role="img" aria-label="Метрики подбора по методам">
            <div className="cols-axis" aria-hidden="true">{[0, 0.25, 0.5, 0.75, 1].map((t) => <span key={t}>{t.toFixed(2)}</span>)}</div>
            <div className="cols-plot" style={{ ["--groups" as string]: METRICS.length }}>
              {METRICS.map(([m]) => (
                <div key={m} className={`cols-group${metric === m ? " sel" : ""}`}>
                  {methods.map((k) => {
                    const val = s.matching[k][m];
                    return <div key={k} className={`col ${toneOf(k)}`} title={`${NAMES[k]}: ${f3(val)}`}><b>{val.toFixed(2)}</b><i style={{ height: `${Math.max(1, val * 100)}%` }} /></div>;
                  })}
                </div>))}
            </div>
            <div className="cols-labels" style={{ ["--groups" as string]: METRICS.length }} role="tablist" aria-label="Метрика">
              {METRICS.map(([k, l]) => <button key={k} role="tab" aria-selected={metric === k} className={metric === k ? "active" : ""} onClick={() => setMetric(k)}>{l}</button>)}
            </div>
          </div>
          <div className="legend-row">
            {methods.map((k) => <span key={k}><i className={toneOf(k)} />{NAMES[k]}</span>)}
          </div>
          <p className="muted" style={{ marginBottom: 0, fontSize: 13 }}>Шкала 0–1, выше — лучше. Все методы оценены на одних данных. Выбранная метрика: {label}.</p>
        </Card>
        <Card title="Основные выводы">
          <ol className="takeaways">
            {takeaways.map((t, i) => <li key={i}><span className="n">{i + 1}</span><span>{t}</span></li>)}
          </ol>
        </Card>
      </div>

      <h2 className="section-title" style={{ marginTop: 28 }}>Основная оценка компетенций</h2>
      <p className="section-sub">{s.assessment.cases} синтетических кейсов. Это проверка корректности, а не психометрическая калибровка.</p>
      <div className="kpis">
        <Kpi tone="mint" label="Точность грейда" value={f3(s.assessment.grade_accuracy)} sub="относительно ожиданий" />
        <Kpi label="Стабильность вариантов" value={f3(s.assessment.variant_stability.identical_outcome_rate)} sub={`${s.assessment.variant_stability.pairs} пар, макс. Δ баллов ${f3(s.assessment.variant_stability.max_abs_score_diff)}`} />
        <Kpi label="Расхождение > 1 подуровня" value={f3(s.assessment.disagreement_over_one_sublevel_rate)} sub="доля кейсов" />
        <Kpi label="Детерминизм оценки" value={s.assessment.deterministic ? "Да" : "Нет"} sub="одинаковый вход → одинаковый результат" />
      </div>
      <div className="grid-2" style={{ alignItems: "start" }}>
        <Card title="Разделение грейдов (AUC)">
          <div className="chart">
            {Object.entries(s.assessment.discrimination).map(([g, d]) => (
              <div key={g} className="cbar hl"><span>{g}</span><span className="track"><span style={{ width: `${d.auc_knowers_vs_others * 100}%` }} /></span><b>{f3(d.auc_knowers_vs_others)}</b></div>
            ))}
          </div>
        </Card>
        <Card title="Случайно угадывающий проходит">
          <div className="chart">
            {Object.entries(s.assessment.guessing_baseline).map(([g, d]) => (
              <div key={g} className="cbar"><span>{g} ({d.items} вопр.)</span><span className="track"><span style={{ width: `${Math.max(1, d.false_verification_rate * 100)}%` }} /></span><b>{(d.false_verification_rate * 100).toFixed(1)}%</b></div>
            ))}
          </div>
          <p className="muted" style={{ marginBottom: 0 }}>Чем ниже, тем лучше: доля ложных подтверждений при случайных ответах.</p>
        </Card>
      </div>

      <div style={{ marginTop: 24 }}>
        <details className="acc">
          <summary>Методология и данные</summary>
          <p>Это MVP-валидация на собственном фиксированном наборе ({s.dataset.candidates} кандидатов, {s.dataset.needs} потребностей, разметка вручную), а не психометрическая калибровка. Организаторы не предоставили официальный датасет.</p>
          <p>Все числа взяты из <code>artifacts/validation/latest.json</code>, который строится командой <code>python -m fsp_market.validation</code>. Размечено ячеек: {s.dataset.label_cells}, ненулевых оценок релевантности: {s.dataset.nonzero_labels}; порог релевантности: {s.dataset.relevant_threshold}.</p>
          <p className="muted">{s.assessment.kind}</p>
        </details>
        <details className="acc">
          <summary>Таблица метрик по методам</summary>
          <table className="table"><thead><tr><th>Метод</th><th>P@3</th><th>P@5</th><th>R@10</th><th>nDCG@10</th><th>Нарушения ограничений в top-10</th></tr></thead><tbody>
            {methods.map((k) => { const r = s.matching[k]; return (
              <tr key={k}><td data-label="Метод">{NAMES[k]}</td><td data-label="P@3">{f3(r["p@3"])}</td><td data-label="P@5">{f3(r["p@5"])}</td><td data-label="R@10">{f3(r["r@10"])}</td><td data-label="nDCG@10">{f3(r["ndcg@10"])}</td><td data-label="Нарушения в top-10">{r["constraint_violations@10"]}/{r["returned@10"]}</td></tr>); })}
          </tbody></table>
        </details>
        <details className="acc">
          <summary>Ограничения ({s.limitations.length})</summary>
          <ul>{s.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </details>
      </div>
    </div>
  );
}
