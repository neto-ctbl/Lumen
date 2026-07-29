from __future__ import annotations

from backend.app.services.integrations.dominio.rubrics import classify_rubric_signals


def test_classify_rubric_signals_for_pro_labore() -> None:
    signals = classify_rubric_signals("100", "PRO-LABORE")
    assert "has_pro_labore" in signals.signals
    assert "has_employee" not in signals.signals


def test_classify_rubric_signals_for_employee_hours() -> None:
    signals = classify_rubric_signals("1", "HORAS NORMAIS")
    assert "has_employee" in signals.signals
    assert "has_pro_labore" not in signals.signals


def test_classify_rubric_signals_for_autonomous() -> None:
    signals = classify_rubric_signals("235", "AUTONOMO")
    assert "has_autonomous" in signals.signals
    assert "has_employee" not in signals.signals


def test_classify_rubric_signals_for_inss_and_fgts() -> None:
    inss = classify_rubric_signals("998", "I.N.S.S.")
    fgts = classify_rubric_signals("996", "F.G.T.S DO MES")
    assert "has_inss" in inss.signals
    assert "has_employee" in inss.signals
    assert "has_fgts" in fgts.signals
    assert "has_employee" in fgts.signals


def test_classify_rubric_signals_for_employer_inss_does_not_imply_employee() -> None:
    signals = classify_rubric_signals("843", "INSS EMPREGADOR")
    assert "has_inss" in signals.signals
    assert "has_employee" not in signals.signals


def test_classify_rubric_signals_for_inss_do_empregado_implies_employee() -> None:
    signals = classify_rubric_signals("998", "INSS DO EMPREGADO")
    assert "has_inss" in signals.signals
    assert "has_employee" in signals.signals


def test_classify_rubric_signals_for_vacation_termination_and_leave() -> None:
    vacation = classify_rubric_signals("813", "FGTS FERIAS")
    termination = classify_rubric_signals("23", "F.G.T.S DE RESCISAO")
    leave = classify_rubric_signals("5000", "AFASTAMENTO DOENCA")
    assert "has_vacation" in vacation.signals
    assert "has_termination" in termination.signals
    assert "has_leave" in leave.signals
