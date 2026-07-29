from backend.app.services.integrations.dominio.competence import (
    PayrollCompetenceMapping,
    map_payroll_to_assessment_competence,
    normalize_payroll_competence,
)
from backend.app.services.integrations.dominio.contracts import (
    DominioDocumentContract,
    DominioEvidenceSource,
    DominioSelectionScope,
)

__all__ = [
    "DominioDocumentContract",
    "DominioEvidenceSource",
    "DominioSelectionScope",
    "PayrollCompetenceMapping",
    "map_payroll_to_assessment_competence",
    "normalize_payroll_competence",
]
