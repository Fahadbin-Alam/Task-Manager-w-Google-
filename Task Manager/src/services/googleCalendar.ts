import type { TaskItem } from "../types";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function connectGoogleCalendarMock(): Promise<{ accessToken: string }> {
  await sleep(500);
  return { accessToken: "mock-google-token" };
}

export async function syncItemsToGoogleCalendar(items: TaskItem[]): Promise<{ synced: number }> {
  await sleep(400);
  return { synced: items.length };
}

export const GOOGLE_SETUP_GUIDE = {
  android:
    "Create Google OAuth client for Android, add SHA-1 in Google Cloud, then store client IDs securely.",
  ios: "Create iOS OAuth client and URL scheme in Info.plist when iOS build starts.",
  api: "Use Google Calendar API events.insert / events.update for task mirroring."
};
