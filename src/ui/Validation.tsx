import { useEffect, useState } from "react";
import { api } from "./api";
import { Card, ErrorBox, Loading } from "./ui";

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

const NAMES: Record<string, string> = { keyword_baseline: "Keyword baseline", hard_filters_only: "Hard filters only", evidence_matching: "Evidence matching (наша система)" };

export default function Validation() {
  const [s, setS] = useState<Summary | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Summary>("/api/validation/summary").then(setS).catch((e: Error) => setErr(e.message)); }, []);
  if (err) return <ErrorBox message={`Артефакт валидации недоступен: ${err}`} />;
  if (!s) return <Loading />;
  const f = (n: number) => n.toFixed(3);
  return (
    <div>
      <Card title="Валидация (MVP, воспроизводимая)">
        <p>Это MVP-валидация на собственном фиксированном наборе ({s.dataset.candidates} кандидатов, {s.dataset.needs} потребностей, разметка вручную), а не психометрическая калибровка. Организаторы не предоставили официальный датасет. Все числа взяты из <code>artifacts/validation/latest.json</code>, который строится командой <code>python -m fsp_market.validation</code>.</p>
      </Card>
      <Card title="Подбор: сравнение методов на одних данных">
        <table className="table"><thead><tr><th>Метод</th><th>P@3</th><th>P@5</th><th>R@10</th><th>nDCG@10</th><th>Нарушения ограничений в top-10</th></tr></thead><tbody>
          {Object.entries(NAMES).map(([k, name]) => { const r = s.matching[k]; return (
            <tr key={k}><td>{name}</td><td>{f(r["p@3"])}</td><td>{f(r["p@5"])}</td><td>{f(r["r@10"])}</td><td>{f(r["ndcg@10"])}</td><td>{r["constraint_violations@10"]}/{r["returned@10"]}</td></tr>); })}
        </tbody></table>
        <p className="muted">Порядок выдачи детерминирован: {s.deterministic_ordering ? "да" : "нет"}.</p>
      </Card>
      <Card title="Assessment: reference-validation на синтетических персонах">
        <ul>
          <li>Точность грейда относительно ожиданий: {f(s.assessment.grade_accuracy)} ({s.assessment.cases} кейсов)</li>
          <li>Стабильность вариантов: одинаковый результат в {f(s.assessment.variant_stability.identical_outcome_rate)} пар, макс. разница баллов {f(s.assessment.variant_stability.max_abs_score_diff)}</li>
          <li>Расхождение больше чем на подуровень: {f(s.assessment.disagreement_over_one_sublevel_rate)}</li>
          <li>Разделение грейдов (AUC): {Object.entries(s.assessment.discrimination).map(([g, d]) => `${g} ${f(d.auc_knowers_vs_others)}`).join(" · ")}</li>
          <li>Случайно угадывающий проходит: {Object.entries(s.assessment.guessing_baseline).map(([g, d]) => `${g} ${(d.false_verification_rate * 100).toFixed(1)}% (${d.items} вопр.)`).join(" · ")}</li>
          <li>Детерминизм оценки: {s.assessment.deterministic ? "да" : "нет"}</li>
        </ul>
        <p className="muted">{s.assessment.kind}</p>
      </Card>
      <Card title="Ограничения"><ul>{s.limitations.map((l) => <li key={l}>{l}</li>)}</ul></Card>
    </div>
  );
}
