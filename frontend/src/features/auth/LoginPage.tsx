import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "../../stores/authStore";

type LoginPageProps = {
  onLoginSuccess: () => void;
};

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const { errorMessage, isAuthenticated, login, status } = useAuth();
  const [email, setEmail] = useState("admin@example.local");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      onLoginSuccess();
    }
  }, [isAuthenticated, onLoginSuccess]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);

    try {
      await login(email, password);
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Nao foi possivel fazer login.",
      );
    }
  }

  const isSubmitting = status === "loading";
  const message = localError ?? errorMessage;

  return (
    <main className="app-shell">
      <section className="auth-stage">
        <div className="auth-card auth-card-panel">
          <section className="auth-panel auth-panel-form">
            <div className="auth-brand">
              <div className="auth-brand-mark">L</div>
              <div>
                <strong>Lumen Fiscal Cockpit</strong>
                <span>Portal corporativo protegido</span>
              </div>
            </div>

            <div className="auth-copy">
              <span className="eyebrow">Acesso autenticado</span>
              <h1>Entrar</h1>
              <p>
                Acesse com seu e-mail corporativo para abrir o cockpit fiscal,
                acompanhar entregas e consultar empresas por competencia.
              </p>
            </div>

            <form className="auth-form" onSubmit={handleSubmit}>
              <label className="auth-field">
                <span>Email</span>
                <input
                  autoComplete="username"
                  name="email"
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="seu.nome@empresa.com.br"
                  type="email"
                  value={email}
                />
              </label>

              <label className="auth-field">
                <span>Senha</span>
                <input
                  autoComplete="current-password"
                  name="password"
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Digite sua senha"
                  type="password"
                  value={password}
                />
              </label>

              <div className="auth-meta-row">
                <span>Somente usuarios vinculados a organizacao ativa.</span>
                <a className="auth-inline-link" href="mailto:suporte@lumen.local">
                  Preciso de acesso
                </a>
              </div>

              {message ? <p className="auth-error">{message}</p> : null}

              <button className="primary-button auth-submit" disabled={isSubmitting} type="submit">
                {isSubmitting ? "Validando..." : "Entrar"}
              </button>
            </form>

            <div className="auth-footer-card">
              <span>RBAC: VIEW, ADMIN e DEV</span>
              <span>JWT + tenant ativo</span>
              <span>Frontend SaaS read-only</span>
            </div>

            <div className="auth-legal">
              <code className="route-pill">/login</code>
              <small>Ambiente local do Lumen</small>
            </div>
          </section>

          <aside className="auth-panel auth-panel-showcase">
            <div className="auth-showcase-header">
              <span className="auth-showcase-tag">Acesso controlado</span>
              <span className="auth-showcase-tag auth-showcase-tag-muted">Read-only S5.1</span>
            </div>

            <div className="auth-showcase-copy">
              <span className="eyebrow">Portal Lumen</span>
              <h2>Controle fiscal com leitura clara, contexto e rastreabilidade.</h2>
              <p>
                O shell foi desenhado para operar como SaaS profissional: navegação
                objetiva, contexto sempre visível e estados vazios honestos.
              </p>
            </div>

            <div className="auth-showcase-card">
              <div className="auth-showcase-metric">
                <strong>Painel</strong>
                <span>KPIs, contexto e visão por competência.</span>
              </div>
              <div className="auth-showcase-metric">
                <strong>Cockpit</strong>
                <span>Empresas reais, filtros e navegação operacional.</span>
              </div>
              <div className="auth-showcase-pills">
                <span>Empresas</span>
                <span>Envios</span>
                <span>Evidências</span>
                <span>Integrações</span>
              </div>
            </div>

            <p className="auth-showcase-note">
              Após o login, o portal preserva autenticação, organização ativa e contexto
              de leitura por empresa e competência.
            </p>
          </aside>
        </div>
      </section>
    </main>
  );
}
