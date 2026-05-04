import AsyncStorage from "@react-native-async-storage/async-storage";
import type { PersistedState, TaskItem } from "./types";

const STORAGE_KEY = "shadow_task_state_v1";

function seedItems(): TaskItem[] {
  const now = new Date().toISOString();
  return [
    {
      id: "seed-priority",
      title: "Plan top 3 missions for today",
      kind: "task",
      priority: "high",
      createdAt: now,
      oneOffDone: false
    },
    {
      id: "seed-deep-focus",
      title: "45m deep focus habit",
      kind: "habit",
      priority: "mid",
      createdAt: now,
      oneOffDone: false
    }
  ];
}

export function defaultState(): PersistedState {
  return {
    items: seedItems(),
    completions: [],
    profile: {
      xp: 0,
      premiumUnlocked: false,
      linkedGoogle: false,
      linkedAlexa: false,
      claimedQuestDays: []
    }
  };
}

export async function loadState(): Promise<PersistedState> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw) as PersistedState;
    return {
      items: (parsed.items ?? []).map((item) => ({
        ...item,
        priority: item.priority ?? "mid"
      })),
      completions: parsed.completions ?? [],
      profile: {
        xp: parsed.profile?.xp ?? 0,
        premiumUnlocked: parsed.profile?.premiumUnlocked ?? false,
        linkedGoogle: parsed.profile?.linkedGoogle ?? false,
        linkedAlexa: parsed.profile?.linkedAlexa ?? false,
        claimedQuestDays: parsed.profile?.claimedQuestDays ?? []
      }
    };
  } catch {
    return defaultState();
  }
}

export async function saveState(state: PersistedState): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}
