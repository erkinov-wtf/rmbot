import { Server, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { getHealth } from "@/lib/api";

type HealthState = "idle" | "loading" | "ok" | "error";

export default function App() {
  const [healthState, setHealthState] = useState<HealthState>("idle");
  const [healthMessage, setHealthMessage] = useState(
    "Backend health has not been checked yet.",
  );

  const checkBackendHealth = async () => {
    setHealthState("loading");

    try {
      const payload = await getHealth();
      setHealthState("ok");
      setHealthMessage(`Backend is reachable. Status: ${payload.status}.`);
    } catch (error) {
      setHealthState("error");
      setHealthMessage(
        error instanceof Error
          ? error.message
          : "Health check failed with an unknown error.",
      );
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#eaf3ff_0%,#f8fafc_40%,#ffffff_100%)] px-4 py-10 md:px-8">
      <section className="mx-auto flex w-full max-w-4xl flex-col gap-6 rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-xl backdrop-blur md:p-10">
        <div className="flex flex-col gap-3">
          <p className="inline-flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
            <ShieldCheck className="h-4 w-4" />
            React + shadcn starter
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
            Rent Market Frontend
          </h1>
          <p className="max-w-2xl text-sm text-slate-600 md:text-base">
            This starter is aligned to the backend API shape: JWT auth, role-based
            endpoints, and a common response envelope. Use it as the base for
            dashboard, ticket workflow, inventory, attendance, and rules pages.
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Server className="h-4 w-4" />
            Backend Connection Check
          </div>
          <p
            className={
              healthState === "error"
                ? "text-sm text-red-600"
                : "text-sm text-slate-700"
            }
          >
            {healthMessage}
          </p>
          <div className="mt-4">
            <Button onClick={checkBackendHealth} disabled={healthState === "loading"}>
              {healthState === "loading" ? "Checking..." : "Check /misc/health"}
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
}
