"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth/auth-context";
import type { AnalyticsEvent } from "./events";
import { ANALYTICS_EVENTS, ASSISTANT_EVENTS, GOVERNANCE_EVENTS, POLICY_EVENTS, REVIEW_EVENTS, WORKSPACE_EVENTS, AGENT_EVENTS } from "./events";
import { identifyUser, initAnalytics, resetAnalytics, trackEvent, type AnalyticsProperties } from "./mixpanel";

export function useAnalytics() {
  const { user } = useAuth();
  const track = useCallback((event: AnalyticsEvent, properties: Record<string, unknown> = {}) => {
    trackEvent(event, {
      ...(user?.organization?.id ? { workspace_id: `ws_${user.organization.id}` } : {}),
      ...(user?.primary_role ? { user_role: user.primary_role } : {}),
      ...properties,
    });
  }, [user?.organization?.id, user?.primary_role]);
  const identify = useCallback(() => {
    if (user?.organization?.id && user.primary_role) {
      identifyUser({ workspaceId: `ws_${user.organization.id}`, roles: user.role_keys, userRole: user.primary_role });
    }
  }, [user?.organization?.id, user?.primary_role, user?.role_keys]);
  return useMemo(() => ({ track, identify, reset: resetAnalytics }), [track, identify]);
}

function routeEvent(pathname: string): { event: AnalyticsEvent; surface: string } | null {
  if (pathname === "/") return { event: ANALYTICS_EVENTS.LANDING_PAGE_VIEWED, surface: "public_site" };
  if (pathname === "/signup") return { event: ANALYTICS_EVENTS.SIGNUP_STARTED, surface: "auth" };
  if (pathname === "/docs" || pathname.startsWith("/docs/")) return { event: ANALYTICS_EVENTS.DOCS_VIEWED, surface: "public_site" };
  if (pathname === "/assistant") return { event: ASSISTANT_EVENTS.ASSISTANT_OPENED, surface: "web_assistant" };
  if (pathname === "/workspace") return { event: WORKSPACE_EVENTS.WORKSPACE_OPENED, surface: "connected_workspace" };
  if (pathname === "/console/policies" || pathname.startsWith("/console/policies/")) return { event: POLICY_EVENTS.POLICY_STUDIO_OPENED, surface: "policy_studio" };
  if (pathname === "/console/reviews" || pathname.startsWith("/console/reviews/")) return { event: REVIEW_EVENTS.REVIEW_QUEUE_OPENED, surface: "reviewer_console" };
  if (pathname === "/console/agents" || pathname.startsWith("/console/agents/")) return { event: AGENT_EVENTS.AGENT_CONTROL_CENTER_OPENED, surface: "agent_control_center" };
  if (pathname === "/console/evidence" || pathname.startsWith("/console/evidence/")) return { event: GOVERNANCE_EVENTS.EVIDENCE_CENTER_OPENED, surface: "evidence_center" };
  if (pathname === "/console/audit") return { event: GOVERNANCE_EVENTS.AUDIT_LOG_OPENED, surface: "audit_log" };
  return null;
}

/** Mounted once inside AuthProvider; handles safe route events and identity lifecycle. */
export function AnalyticsBridge() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const lastRoute = useRef("");

  useEffect(() => initAnalytics(), []);
  useEffect(() => {
    if (loading) return;
    if (user?.organization?.id && user.primary_role) {
      identifyUser({ workspaceId: `ws_${user.organization.id}`, roles: user.role_keys, userRole: user.primary_role });
    }
  }, [loading, user]);
  useEffect(() => {
    if (loading || !pathname || lastRoute.current === pathname) return;
    lastRoute.current = pathname;
    const mapped = routeEvent(pathname);
    if (!mapped) return;
    trackEvent(mapped.event, {
      surface: mapped.surface,
      feature_area: mapped.surface === "public_site" ? (pathname.startsWith("/docs") ? "docs" : "other") : undefined,
      ...(user?.organization?.id ? { workspace_id: `ws_${user.organization.id}` } : {}),
      ...(user?.primary_role ? { user_role: user.primary_role } : {}),
      ...safeAttribution(),
    });
  }, [loading, pathname, user]);
  return null;
}

function safeAttribution(): AnalyticsProperties {
  if (typeof window === "undefined") return {};
  const params = new URLSearchParams(window.location.search);
  const classify = (value: string | null, allowed: string[]): string => {
    const normalized = (value ?? "").toLowerCase();
    return allowed.includes(normalized) ? normalized : value ? "other" : "direct";
  };
  return {
    referrer: document.referrer ? "other" : "direct",
    utm_source: classify(params.get("utm_source"), ["google", "linkedin", "github", "direct", "referral"]),
    utm_medium: classify(params.get("utm_medium"), ["organic", "paid", "social", "email", "referral"]),
    utm_campaign: classify(params.get("utm_campaign"), ["launch", "demo", "security_checklist"]),
  };
}
