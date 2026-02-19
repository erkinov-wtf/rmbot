import { Languages } from "lucide-react";

import {
  LANGUAGE_OPTIONS,
  type AppLanguage,
  useI18n,
} from "@/i18n";
import { cn } from "@/lib/utils";

type LanguageSwitcherProps = {
  className?: string;
  compact?: boolean;
};

export function LanguageSwitcher({
  className,
  compact = false,
}: LanguageSwitcherProps) {
  const { language, setLanguage, t } = useI18n();

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white/90 p-1",
        className,
      )}
      role="group"
      aria-label={t("Language")}
    >
      <span className="inline-flex items-center px-2 text-slate-500">
        <Languages className="h-4 w-4" />
      </span>
      {LANGUAGE_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => setLanguage(option.value as AppLanguage)}
          className={cn(
            "rounded-lg px-2.5 py-1.5 text-xs font-semibold transition",
            language === option.value
              ? "bg-slate-900 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200",
            compact ? "px-2 py-1 text-[11px]" : "",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

