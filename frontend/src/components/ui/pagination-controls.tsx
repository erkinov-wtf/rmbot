import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

type PaginationControlsProps = {
  page: number;
  pageCount: number;
  perPage: number;
  totalCount: number;
  isLoading?: boolean;
  onPageChange: (page: number) => void;
  onPerPageChange?: (perPage: number) => void;
  perPageOptions?: number[];
  className?: string;
};

export function PaginationControls({
  page,
  pageCount,
  perPage,
  totalCount,
  isLoading = false,
  onPageChange,
  onPerPageChange,
  perPageOptions = [10, 20, 50],
  className,
}: PaginationControlsProps) {
  const { t } = useI18n();
  const normalizedPageCount = Math.max(1, pageCount);
  const normalizedPage = Math.min(Math.max(1, page), normalizedPageCount);
  const from = totalCount === 0 ? 0 : (normalizedPage - 1) * perPage + 1;
  const to = totalCount === 0 ? 0 : Math.min(totalCount, normalizedPage * perPage);

  return (
    <div
      className={cn(
        "flex flex-col gap-2 border-t border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
        <span>
          {t("Showing {{from}}-{{to}} of {{total}}", {
            from,
            to,
            total: totalCount,
          })}
        </span>
        {onPerPageChange ? (
          <label className="inline-flex items-center gap-2">
            <span>{t("Rows per page")}</span>
            <select
              className="h-8 rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-700"
              value={perPage}
              onChange={(event) => {
                const parsed = Number(event.target.value);
                if (Number.isInteger(parsed) && parsed > 0) {
                  onPerPageChange(parsed);
                }
              }}
              disabled={isLoading}
            >
              {perPageOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-600">
          {t("Page {{page}} of {{pages}}", {
            page: normalizedPage,
            pages: normalizedPageCount,
          })}
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8 px-2"
          onClick={() => onPageChange(normalizedPage - 1)}
          disabled={isLoading || normalizedPage <= 1}
        >
          <ChevronLeft className="h-4 w-4" />
          {t("Previous")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8 px-2"
          onClick={() => onPageChange(normalizedPage + 1)}
          disabled={isLoading || normalizedPage >= normalizedPageCount}
        >
          {t("Next")}
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
