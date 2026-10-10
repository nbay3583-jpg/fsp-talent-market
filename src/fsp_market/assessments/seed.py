"""Idempotent loader for the Backend / Python Core Assessment (see content.py).

Families that are no longer part of the current content are DEACTIVATED, not deleted, so that old
attempts and results stay intact.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments import content
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
        session, Specialization, content.SPECIALIZATION["code"], name=content.SPECIALIZATION["name"]
    )
    competencies: dict[str, Competency] = {}
    for item in content.COMPETENCIES:
        comp = _get_or_create(
            session, Competency, item["code"], name=item["name"], specialization_id=spec.id
        )
        competencies[item["code"]] = comp
        _get_or_create(session, Skill, item["code"], name=item["name"], competency_id=comp.id)

    current = {fam["code"] for fam in content.FAMILIES}
    for old in session.scalars(select(TaskFamily).where(TaskFamily.code.notin_(current))):
        old.is_active = False

    for fam in content.FAMILIES:
        formats = sorted({t["task_format"] for t in fam["templates"]})
        family = _get_or_create(
            session,
            TaskFamily,
            fam["code"],
            competency_id=competencies[fam["competency"]].id,
            target_grade=Grade(fam["grade"]),
            difficulty_band=fam["band"],
            rubric=fam["rubric"],
            edge_case_classes=sorted({d for t in fam["templates"] for d in t["dimensions"]}),
            allowed_formats=formats,
            is_active=True,
            rubric_version=content.RUBRIC_VERSION,
        )
        for tpl in fam["templates"]:
            template = _get_or_create(
                session,
                TaskTemplate,
                tpl["code"],
                family_id=family.id,
                task_format=TaskFormat(tpl["task_format"]),
                structure=tpl["structure"],
                parameter_schema={"generator": tpl["gen"].__name__},
                scoring_rule={"type": "see scoring_contract of the variant"},
            )
            for index, params in enumerate(content.generate_presets(tpl, fam["code"]), start=1):
                code = f"{tpl['code']}.p{index}"
                preset = _get_or_create(
                    session, TaskPreset, code, template_id=template.id, parameters=params
                )
                fields = render_variant_fields(tpl["structure"], params, index)
                _get_or_create(
                    session,
                    TaskVariant,
                    f"{tpl['code']}.v{index}",
                    template_id=template.id,
                    preset_id=preset.id,
                    seed=index,
                    is_anchor=False,
                    **fields,
                )
