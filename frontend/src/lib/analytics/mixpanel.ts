"use client";

import mixpanel from "mixpanel-browser";

import { sanitizeAnalyticsProperties } from "./privacy";

const MIXPANEL_TOKEN = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
const ANALYTICS_ID_KEY = "trustshield_analytics_subject";
let isInitialized = false;

export type AnalyticsProperties = Record<string, string | number | boolean | string[]>;

export function initAnalytics(): void {
  if (typeof window === "undefined" || !MIXPANEL_TOKEN || isInitialized) return;
  try {
    mixpanel.init(MIXPANEL_TOKEN, {
      debug: process.env.NODE_ENV === "development",
      track_pageview: "url-with-path",
      persistence: "localStorage",
      ignore_dnt: false,
      store_google: false,
      hooks: {
        before_send_events: (payload) => {
          const props = sanitizeAnalyticsProperties(payload.properties);
          // Mixpanel requires its public project token and a distinct ID in the transport payload.
          // The distinct ID is generated locally and never comes from the TrustShield account.
          if (payload.properties.token === MIXPANEL_TOKEN) props.token = MIXPANEL_TOKEN;
          const distinctId = payload.properties.distinct_id;
          if (typeof distinctId === "string" && (/^anon_[a-zA-Z0-9_-]{8,100}$/.test(distinctId) || /^\$device:[a-zA-Z0-9_-]{8,100}$/.test(distinctId))) {
            props.distinct_id = distinctId;
          }
          return { event: payload.event, properties: props };
        },
        before_register: (properties) => sanitizeAnalyticsProperties(properties),
      },
    });
    isInitialized = true;
  } catch {
    // Product flows must continue even if the analytics SDK fails to initialize.
  }
}

function getAnalyticsSubject(): string {
  const existing = window.localStorage.getItem(ANALYTICS_ID_KEY);
  if (existing) return existing;
  const generated = `anon_${window.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(36).slice(2)}`}`;
  window.localStorage.setItem(ANALYTICS_ID_KEY, generated);
  return generated;
}

/** Uses a random analytics-only ID. No TrustShield account ID, email, name, or user profile is sent. */
export function identifyUser(input: { workspaceId: string; roles: string[]; userRole: string }): void {
  if (typeof window === "undefined" || !MIXPANEL_TOKEN) return;
  try {
    initAnalytics();
    if (!isInitialized) return;
    mixpanel.identify(getAnalyticsSubject());
    const props = sanitizeAnalyticsProperties({ workspace_id: input.workspaceId, user_role: input.userRole });
    mixpanel.register(props);
    if (props.workspace_id) mixpanel.set_group("workspace", String(props.workspace_id));
  } catch {
    // Analytics must not interrupt sign-in or navigation.
  }
}

export function resetAnalytics(): void {
  if (typeof window === "undefined" || !MIXPANEL_TOKEN) return;
  try {
    initAnalytics();
    if (isInitialized) mixpanel.reset();
    window.localStorage.removeItem(ANALYTICS_ID_KEY);
  } catch {
    // Analytics must not interrupt sign-out.
  }
}

export function trackEvent(event: string, properties: Record<string, unknown> = {}): void {
  if (typeof window === "undefined" || !MIXPANEL_TOKEN) return;
  try {
    initAnalytics();
    if (!isInitialized) return;
    mixpanel.track(event, sanitizeAnalyticsProperties(properties));
  } catch {
    // Analytics must never break a product action.
  }
}

export function hasAnalyticsToken(): boolean {
  return Boolean(MIXPANEL_TOKEN);
}
