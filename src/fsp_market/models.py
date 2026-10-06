"""Imports every ORM module so Base.metadata is complete (used by Alembic and tests)."""

from fsp_market.assessments import models as assessments_models
from fsp_market.candidates import models as candidates_models
from fsp_market.employers import models as employers_models
from fsp_market.matching import models as matching_models
from fsp_market.skills import models as skills_models
from fsp_market.taxonomy import models as taxonomy_models

__all__ = [
    "assessments_models",
    "candidates_models",
    "employers_models",
    "matching_models",
    "skills_models",
    "taxonomy_models",
]
