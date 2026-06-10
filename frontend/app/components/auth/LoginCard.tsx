"use client";

interface LoginCardProps {
  eyebrow: string;
  title?: string;
  description: string;
  footer?: string;
  username: string;
  password: string;
  loading: boolean;
  error?: string | null;
  success?: string | null;
  usernamePlaceholder?: string;
  submitLabel?: string;
  loadingLabel?: string;
  successLabel?: string;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}

export function LoginCard({
  eyebrow,
  title = "Sign in",
  description,
  footer,
  username,
  password,
  loading,
  error,
  success,
  usernamePlaceholder = "Username",
  submitLabel = "Sign in",
  loadingLabel = "Signing in...",
  successLabel = "Redirecting...",
  onUsernameChange,
  onPasswordChange,
  onSubmit,
}: LoginCardProps) {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <p className="mb-2 text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary">
            {eyebrow}
          </p>
          <h1 className="font-editorial text-4xl font-bold tracking-tight text-on-surface">
            {title}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{description}</p>
        </div>

        <div className="rounded-2xl bg-surface-container-lowest p-8 shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]">
          <form onSubmit={onSubmit} className="space-y-6">
            <div className="space-y-2">
              <label
                htmlFor="username"
                className="block px-1 text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(event) => onUsernameChange(event.target.value)}
                placeholder={usernamePlaceholder}
                className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-sm text-on-surface outline-none focus:border-primary"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="password"
                className="block px-1 text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => onPasswordChange(event.target.value)}
                placeholder="Password"
                className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-sm text-on-surface outline-none focus:border-primary"
              />
            </div>

            {error ? (
              <div
                role="alert"
                className="flex items-center gap-2 rounded-xl bg-error-container px-3 py-2.5 text-xs font-editorial text-on-error-container"
              >
                <span className="material-symbols-outlined shrink-0 text-base">error</span>
                {error}
              </div>
            ) : null}

            {success ? (
              <div
                role="status"
                className="flex items-center gap-2 rounded-xl bg-primary-container/30 px-3 py-2.5 text-xs font-editorial text-on-surface"
              >
                <span className="material-symbols-outlined shrink-0 text-base text-primary">
                  check_circle
                </span>
                {success}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-60"
            >
              {success ? successLabel : loading ? loadingLabel : submitLabel}
            </button>
          </form>
        </div>

        {footer ? (
          <p className="mt-6 text-center text-[10px] font-editorial uppercase tracking-widest text-outline">
            {footer}
          </p>
        ) : null}
      </div>
    </div>
  );
}
