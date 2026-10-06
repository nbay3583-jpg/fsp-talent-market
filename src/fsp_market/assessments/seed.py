"""Idempotent loader for the Backend / Python Core Assessment seed (see seed_data.py)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments import seed_data as data
from fsp_market.assessments.models import TaskFamily, TaskPreset, TaskTemplate, TaskVariant
from fsp_market.assessments.variants import render_variant_fields
from fsp_market.common.enums import Grade, TaskFormat
from fsp_market.skills.models import Skill
from fsp_market.taxonomy.models import Competency, Specialization


def _get_or_create(session: Session, model, code: str, **fields):
    row = session.scalar(select(model).where(model.code == code))
    if row is None:
        row = model(code=code, **fields)
        session.add(row)
        session.flush()
    return row


def seed_backend_python(session: Session) -> None:
    spec = _get_or_create(
        session, Specialization, data.SPECIALIZATION["code"], name=data.SPECIALIZATION["name"]
    )
    competencies: dict[str, Competency] = {}
    for item in data.COMPETENCIES:
        comp = _get_or_create(
            session, Competency, item["code"], name=item["name"], specialization_id=spec.id
        )
        competencies[item["code"]] = comp
        _get_or_create(session, Skill, item["code"], name=item["name"], competency_id=comp.id)

    for fam in data.FAMILIES:
        family = _get_or_create(
            session,
            TaskFamily,
            fam["code"],
            competency_id=competencies[fam["competency"]].id,
            target_grade=Grade(fam["target_grade"]),
            difficulty_band=fam["difficulty_band"],
            rubric=fam["rubric"],
            edge_case_classes=fam["edge_case_classes"],
            allowed_formats=fam["allowed_formats"],
        )
        tpl = fam["template"]
        template = _get_or_create(
            session,
            TaskTemplate,
            tpl["code"],
            family_id=family.id,
            task_format=TaskFormat(tpl["task_format"]),
            structure=tpl["structure"],
            parameter_schema=tpl["parameter_schema"],
            scoring_rule=tpl["scoring_rule"],
        )
        for seed, pre in enumerate(fam["presets"], start=1):
            params = pre["parameters"]
            preset = _get_or_create(
                session, TaskPreset, pre["code"], template_id=template.id, parameters=params
            )
            fields = render_variant_fields(tpl["structure"], params, seed)
            _get_or_create(
                session,
                TaskVariant,
                pre["code"].replace(".p", ".v"),
                template_id=template.id,
                preset_id=preset.id,
                seed=seed,
                is_anchor=bool(pre.get("anchor", False)),
                **fields,
            )
