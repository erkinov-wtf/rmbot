import { CircleCheck, LockKeyhole, LogIn, UserRound } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import { loginWithPassword, type LoginTokens } from "@/lib/api";

type LoginFormProps = {
  onLoggedIn: (tokens: LoginTokens) => void;
  noticeMessage?: string;
};

export function LoginForm({ onLoggedIn, noticeMessage }: LoginFormProps) {
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage("");
    setIsLoading(true);

    try {
      const tokens = await loginWithPassword(username.trim(), password);
      onLoggedIn(tokens);
    } catch (error) {
      if (
        error instanceof TypeError &&
        error.message.toLowerCase().includes("fetch")
      ) {
        setErrorMessage(
          t("Cannot reach backend. Check CORS and backend availability."),
        );
      } else {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : t("Login failed with an unknown error."),
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="rm-shell px-4 py-6 sm:px-6 sm:py-8 md:px-8 md:py-10">
      <section className="mx-auto grid w-full max-w-5xl gap-4 md:grid-cols-[1.1fr_1fr] md:gap-6">
        <div className="rm-panel rm-animate-enter p-5 sm:p-6 md:p-8">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
            <LogIn className="h-4 w-4" />
            {t("Secure access")}
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            {t("Rent Market")}
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
            {t("Sign in with your backend account to continue.")}
          </p>
          <p className="mt-4 text-xs text-slate-500">
            {t(
              "Session is stored in localStorage and expires automatically when JWT `exp` is reached.",
            )}
          </p>
          <ul className="mt-5 space-y-2 text-sm text-slate-600">
            <li className="inline-flex items-center gap-2">
              <CircleCheck className="h-4 w-4 text-emerald-600" />
              {t("Fast login and persistent session")}
            </li>
            <li className="inline-flex items-center gap-2">
              <CircleCheck className="h-4 w-4 text-emerald-600" />
              {t("Automatic logout on token expiry")}
            </li>
          </ul>
          {noticeMessage ? (
            <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              {noticeMessage}
            </p>
          ) : null}
        </div>

        <form className="rm-panel rm-animate-enter-delayed p-5 sm:p-6 md:p-8" onSubmit={handleSubmit}>
          <div className="mb-5">
            <h2 className="text-lg font-semibold text-slate-900">{t("Login")}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {t("Enter your username and password.")}
            </p>
          </div>

          <div className="space-y-2">
            <label
              htmlFor="username"
              className="text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              {t("Username")}
            </label>
            <div className="relative">
              <UserRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="username"
                type="text"
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="rm-input h-12 pl-10 pr-3"
                placeholder={t("your.username")}
              />
            </div>
          </div>

          <div className="mt-4 space-y-2">
            <label
              htmlFor="password"
              className="text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              {t("Password")}
            </label>
            <div className="relative">
              <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="rm-input h-12 pl-10 pr-3"
                placeholder="••••••••"
              />
            </div>
          </div>

          {errorMessage ? (
            <p
              className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
              aria-live="polite"
            >
              {errorMessage}
            </p>
          ) : null}

          <div className="mt-6 space-y-3">
            <Button
              type="submit"
              className="h-12 w-full text-sm font-semibold"
              disabled={isLoading}
            >
              {isLoading ? t("Signing in...") : t("Sign In")}
            </Button>
            <p className="text-center text-xs text-slate-500">
              {t("API endpoint")}: <code>/api/v1/auth/login/</code>
            </p>
          </div>
        </form>
      </section>
    </main>
  );
}
