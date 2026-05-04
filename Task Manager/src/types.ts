export type ItemKind = "task" | "habit";
export type Priority = "low" | "mid" | "high";

export type TaskItem = {
  id: string;
  title: string;
  kind: ItemKind;
  priority: Priority;
  createdAt: string;
  oneOffDone: boolean;
};

export type CompletionLog = {
  id: string;
  itemId: string;
  dateKey: string;
  xp: number;
};

export type ShadowProfile = {
  xp: number;
  premiumUnlocked: boolean;
  linkedGoogle: boolean;
  linkedAlexa: boolean;
  claimedQuestDays: string[];
};

export type PersistedState = {
  items: TaskItem[];
  completions: CompletionLog[];
  profile: ShadowProfile;
};
