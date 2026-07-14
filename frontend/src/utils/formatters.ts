const smallWords = new Set(["da", "de", "do", "das", "dos", "e"]);

const sourceLabels: Record<string, string> = {
  ECONTROLE: "eControle",
  MANUAL: "Manual",
  WATCHER_G: "Watcher G",
  WATCHER: "Watcher",
  ACESSORIAS: "Acessórias",
  DOMINIO: "Domínio",
  ECONET: "Econet",
  SITTAX: "Sittax",
};

const statusLabels: Record<string, string> = {
  SEM_DADOS: "Sem dados",
  PENDENTE: "Pendente",
  ENTREGUE: "Entregue",
  DIVERGENCIA: "Divergência",
  DIVERGENTE: "Divergente",
  NAO_INICIADA: "Não iniciada",
  CONFIGURAR: "Configurar",
  OPEN: "Aberto",
  CRITICAL: "Crítico",
  SYNCED: "Sincronizado",
};

const departmentLabels: Record<string, string> = {
  FISCAL: "Fiscal",
  DP: "DP",
  COMPARTILHADO: "Compartilhado",
  SISTEMA: "Sistema",
};

const regimeLabels: Record<string, string> = {
  "AGUARDANDO ACESSORIAS": "Aguardando Acessórias",
  AGUARDANDO_ACESSORIAS: "Aguardando Acessórias",
  "SIMPLES NACIONAL": "Simples Nacional",
  SIMPLES_NACIONAL: "Simples Nacional",
  "LUCRO PRESUMIDO": "Lucro Presumido",
  LUCRO_PRESUMIDO: "Lucro Presumido",
  "LUCRO REAL": "Lucro Real",
  LUCRO_REAL: "Lucro Real",
  "IMUNE ISENTA": "Imune Isenta",
  IMUNE_ISENTA: "Imune Isenta",
};

export function formatCompetencia(value: string) {
  if (!value || !value.includes("-")) return value || "-";
  const [year, month] = value.split("-");
  return `${month}/${year}`;
}

export function formatCnpj(value: string | null | undefined) {
  if (!value) return "-";
  const digits = value.replace(/\D/g, "");
  if (digits.length !== 14) {
    return value;
  }
  return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}

export function ieDisplay(value: string | null | undefined) {
  return value && value.trim() ? value : "ISENTO";
}

export function formatIsoDate(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR").format(date);
}

export function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

export function formatDisplayText(value: string | null | undefined) {
  if (!value) return "-";
  const normalized = value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  return normalized
    .toLowerCase()
    .split(" ")
    .map((word, index) => {
      if (!word) return word;
      if (index > 0 && smallWords.has(word)) {
        return word;
      }
      return `${word[0].toUpperCase()}${word.slice(1)}`;
    })
    .join(" ");
}

export function formatStatusLabel(value: string | null | undefined) {
  if (!value) return "-";
  return statusLabels[value] ?? formatDisplayText(value);
}

export function formatDepartmentLabel(value: string | null | undefined) {
  if (!value) return "-";
  return departmentLabels[value] ?? formatDisplayText(value);
}

export function formatSourceLabel(value: string | null | undefined) {
  if (!value) return "-";
  return sourceLabels[value] ?? formatDisplayText(value);
}

export function formatRegimeLabel(value: string | null | undefined) {
  if (!value) return "Aguardando Acessórias";
  const upper = value.toUpperCase();
  return regimeLabels[upper] ?? formatDisplayText(value);
}

export function formatCompanyName(value: string | null | undefined) {
  return formatDisplayText(value);
}
