import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  title: string;
  children: ReactNode;
  failedPrefix?: string;
  reloadHint?: string;
  unknownErrorHint?: string;
};

type ErrorBoundaryState = {
  hasError: boolean;
  errorMessage: string;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    errorMessage: "",
  };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: "",
    };
  }

  componentDidCatch(error: unknown, errorInfo: ErrorInfo): void {
    // Keep console logging in dev/prod to avoid silent white-screen failures.
    console.error("UI rendering error:", error, errorInfo);
    const message =
      error instanceof Error
        ? `${error.name}: ${error.message}`
        : String(error);
    this.setState({
      hasError: true,
      errorMessage: message || this.props.unknownErrorHint || "Unknown rendering error.",
    });
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <section className="rm-panel p-4 sm:p-5">
          <p className="inline-flex items-center gap-2 text-sm font-semibold text-rose-700">
            <AlertTriangle className="h-4 w-4" />
            {this.props.failedPrefix || "Failed To Render"} {this.props.title}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            {this.props.reloadHint ||
              "Reload this page. If the issue continues, contact support."}
          </p>
          {this.state.errorMessage ? (
            <p className="mt-2 break-all rounded-md bg-slate-100 px-3 py-2 font-mono text-xs text-slate-700">
              {this.state.errorMessage}
            </p>
          ) : null}
        </section>
      );
    }
    return this.props.children;
  }
}
