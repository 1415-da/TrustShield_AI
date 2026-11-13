"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * Contains a rendering failure to one part of the page (for example a single chat message), so the rest of
 * the app keeps working instead of falling through to Next.js's full-page "Application error" screen.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode; fallback: (error: Error, reset: () => void) => ReactNode; resetKey?: unknown },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("TrustShield UI error:", error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey?: unknown }) {
    // New data for this part of the page (e.g. the message was updated by a reviewer) gets a fresh attempt.
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  reset = () => this.setState({ error: null });

  render() {
    return this.state.error ? this.props.fallback(this.state.error, this.reset) : this.props.children;
  }
}
