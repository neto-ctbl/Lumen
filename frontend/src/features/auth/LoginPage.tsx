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
      <section className="hero-card auth-card">
        <span className="eyebrow">Lumen Auth Bridge</span>
        <h1>Entrar</h1>
        <p>
          Use o usuario criado no backend S3 para acessar o shell protegido do Lumen.
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-field">
            <span>Email</span>
            <input
              autoComplete="username"
              name="email"
              onChange={(event) => setEmail(event.target.value)}
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
              type="password"
              value={password}
            />
          </label>

          {message ? <p className="auth-error">{message}</p> : null}

          <button className="primary-button" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Validando..." : "Entrar"}
          </button>
        </form>

        <code className="route-pill">/login</code>
      </section>
    </main>
  );
}
