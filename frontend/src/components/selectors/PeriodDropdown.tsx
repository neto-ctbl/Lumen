import { useMemo, useState } from "react";

import { useLumenUi } from "../../stores/lumenUiStore";
import { formatCompetencia } from "../../utils/formatters";

const monthNames = [
  "Janeiro",
  "Fevereiro",
  "Marco",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

export function PeriodDropdown() {
  const { periods, selectedPeriod, setSelectedPeriod } = useLumenUi();
  const [open, setOpen] = useState(false);
  const availableYears = useMemo(
    () =>
      [...new Set(periods.map((period) => period.year))]
        .sort((left, right) => right - left),
    [periods],
  );
  const selectedYearFromPeriod = selectedPeriod ? Number(selectedPeriod.slice(0, 4)) : null;
  const [visibleYear, setVisibleYear] = useState<number | null>(selectedYearFromPeriod);

  const effectiveYear = visibleYear ?? selectedYearFromPeriod ?? availableYears[0] ?? new Date().getFullYear();
  const currentYearIndex = availableYears.findIndex((year) => year === effectiveYear);

  const periodsByMonth = useMemo(() => {
    const map = new Map<number, string>();
    periods
      .filter((period) => period.year === effectiveYear)
      .forEach((period) => map.set(period.month, period.competencia));
    return map;
  }, [effectiveYear, periods]);

  function openDropdown() {
    setVisibleYear(selectedYearFromPeriod ?? availableYears[0] ?? new Date().getFullYear());
    setOpen((current) => !current);
  }

  return (
    <div className="selector">
      <button
        aria-label="Selecionar competencia"
        aria-expanded={open}
        className="selector-trigger"
        onClick={openDropdown}
        type="button"
      >
        <span className="selector-label">Competência</span>
        <strong>{selectedPeriod ? formatCompetencia(selectedPeriod) : "Selecionar"}</strong>
      </button>

      {open ? (
        <div className="selector-panel selector-panel-periods">
          <div className="period-calendar">
            <div className="period-calendar-header">
              <button
                className="period-calendar-arrow"
                disabled={currentYearIndex === -1 || currentYearIndex === availableYears.length - 1}
                onClick={() => {
                  if (currentYearIndex >= 0 && currentYearIndex < availableYears.length - 1) {
                    setVisibleYear(availableYears[currentYearIndex + 1]);
                  }
                }}
                type="button"
              >
                ‹
              </button>

              <strong>{effectiveYear}</strong>

              <button
                className="period-calendar-arrow"
                disabled={currentYearIndex <= 0}
                onClick={() => {
                  if (currentYearIndex > 0) {
                    setVisibleYear(availableYears[currentYearIndex - 1]);
                  }
                }}
                type="button"
              >
                ›
              </button>
            </div>

            <div className="period-calendar-grid">
              {monthNames.map((monthName, index) => {
                const month = index + 1;
                const competencia = periodsByMonth.get(month);
                const active = competencia === selectedPeriod;

                return (
                  <button
                    key={`${effectiveYear}-${month}`}
                    className={`period-calendar-month ${active ? "period-calendar-month-active" : ""}`}
                    disabled={!competencia}
                    onClick={() => {
                      if (!competencia) {
                        return;
                      }
                      setSelectedPeriod(competencia);
                      setOpen(false);
                    }}
                    type="button"
                  >
                    {monthName}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
