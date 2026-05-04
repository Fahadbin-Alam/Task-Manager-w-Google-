import { StatusBar } from "expo-status-bar";
import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { buildDailyAlexaBrief, connectAlexaMock } from "./src/services/alexaBridge";
import { connectGoogleCalendarMock, syncItemsToGoogleCalendar } from "./src/services/googleCalendar";
import { defaultState, loadState, saveState } from "./src/storage";
import { fonts, palette, spacing, typeScale } from "./src/theme";
import type { ItemKind, PersistedState, Priority, TaskItem } from "./src/types";
import { formatDateKey, lastNDays, parseDateKey } from "./src/utils/date";
import {
  currentStreak,
  dailyCompletionCount,
  levelFromXp,
  progressToNextLevel,
  rankFromLevel,
  weeklyCompletions
} from "./src/utils/gamification";

const HABIT_XP = 10;
const DAILY_QUEST_TARGET = 3;
const DAILY_QUEST_REWARD = 25;
const PRIORITY_XP: Record<Priority, number> = {
  low: 8,
  mid: 12,
  high: 16
};

function createId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function App(): React.JSX.Element {
  const [state, setState] = useState<PersistedState>(defaultState);
  const [isHydrated, setIsHydrated] = useState(false);
  const [activeScreen, setActiveScreen] = useState<"focus" | "dashboard">("focus");
  const [selectedHabitId, setSelectedHabitId] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [habitDraft, setHabitDraft] = useState("");
  const [kindDraft, setKindDraft] = useState<ItemKind>("task");
  const [priorityDraft, setPriorityDraft] = useState<Priority>("mid");
  const [missionFilter, setMissionFilter] = useState<"all" | ItemKind>("all");
  const todayKey = formatDateKey(new Date());

  useEffect(() => {
    let active = true;
    loadState().then((loaded) => {
      if (!active) return;
      setState(loaded);
      setIsHydrated(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    saveState(state).catch(() => undefined);
  }, [state, isHydrated]);

  const level = levelFromXp(state.profile.xp);
  const levelProgress = progressToNextLevel(state.profile.xp);
  const rank = rankFromLevel(level);
  const streak = currentStreak(state.completions, todayKey);
  const todayDoneCount = dailyCompletionCount(state.completions, todayKey);
  const weekly = weeklyCompletions(state.completions);
  const maxWeekly = Math.max(1, ...weekly.map((day) => day.count));
  const questClaimed = state.profile.claimedQuestDays.includes(todayKey);
  const canClaimDailyQuest = todayDoneCount >= DAILY_QUEST_TARGET && !questClaimed;

  const missionItems = useMemo(
    () =>
      state.items
        .filter((item) => item.kind === "habit" || !item.oneOffDone)
        .filter((item) => (missionFilter === "all" ? true : item.kind === missionFilter)),
    [state.items, missionFilter]
  );
  const habitItems = useMemo(() => state.items.filter((item) => item.kind === "habit"), [state.items]);
  const trendDays = useMemo(() => lastNDays(14), [todayKey]);
  const weekDays = useMemo(() => lastNDays(7), [todayKey]);
  const heatmapDays = useMemo(() => lastNDays(35), [todayKey]);
  const selectedHabit = useMemo(
    () => habitItems.find((item) => item.id === selectedHabitId) ?? null,
    [habitItems, selectedHabitId]
  );
  const habitsDoneToday = useMemo(
    () =>
      habitItems.filter((item) =>
        state.completions.some((entry) => entry.itemId === item.id && entry.dateKey === todayKey)
      ).length,
    [habitItems, state.completions, todayKey]
  );
  const selectedHabitTrend = useMemo(() => {
    if (!selectedHabit) return [];
    return trendDays.map((dayKey) => {
      const done = state.completions.some(
        (entry) => entry.itemId === selectedHabit.id && entry.dateKey === dayKey
      );
      return {
        key: dayKey,
        done,
        dayLabel: parseDateKey(dayKey).toLocaleDateString(undefined, { weekday: "narrow" }),
        isToday: dayKey === todayKey
      };
    });
  }, [selectedHabit, trendDays, state.completions, todayKey]);
  const selectedHabitCompletedDays = selectedHabitTrend.filter((day) => day.done).length;
  const selectedHabitWeekDone = useMemo(() => {
    if (!selectedHabit) return 0;
    return weekDays.filter((dayKey) =>
      state.completions.some((entry) => entry.itemId === selectedHabit.id && entry.dateKey === dayKey)
    ).length;
  }, [selectedHabit, weekDays, state.completions]);
  const weekLabels = useMemo(
    () =>
      weekDays.map((dayKey) =>
        parseDateKey(dayKey).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2).toUpperCase()
      ),
    [weekDays]
  );
  const heatmapWeeks = useMemo(() => {
    const chunks: string[][] = [];
    for (let i = 0; i < heatmapDays.length; i += 7) {
      chunks.push(heatmapDays.slice(i, i + 7));
    }
    return chunks;
  }, [heatmapDays]);

  useEffect(() => {
    if (habitItems.length === 0) {
      setSelectedHabitId(null);
      return;
    }
    if (!selectedHabitId || !habitItems.some((item) => item.id === selectedHabitId)) {
      setSelectedHabitId(habitItems[0].id);
    }
  }, [habitItems, selectedHabitId]);

  function isDone(item: TaskItem): boolean {
    if (item.kind === "task") return item.oneOffDone;
    return state.completions.some((entry) => entry.itemId === item.id && entry.dateKey === todayKey);
  }

  function isHabitDoneOnDate(itemId: string, dateKey: string): boolean {
    return state.completions.some((entry) => entry.itemId === itemId && entry.dateKey === dateKey);
  }

  function addMission(): void {
    const trimmed = titleDraft.trim();
    if (!trimmed) return;
    setState((previous) => ({
      ...previous,
      items: [
        {
          id: createId(kindDraft),
          title: trimmed,
          kind: kindDraft,
          priority: priorityDraft,
          createdAt: new Date().toISOString(),
          oneOffDone: false
        },
        ...previous.items
      ]
    }));
    setTitleDraft("");
  }

  function addHabitFromFocus(): void {
    const trimmed = habitDraft.trim();
    if (!trimmed) return;
    setState((previous) => ({
      ...previous,
      items: [
        {
          id: createId("habit"),
          title: trimmed,
          kind: "habit",
          priority: "mid",
          createdAt: new Date().toISOString(),
          oneOffDone: false
        },
        ...previous.items
      ]
    }));
    setHabitDraft("");
  }

  function toggleMission(item: TaskItem): void {
    setState((previous) => {
      if (item.kind === "task") {
        const taskXp = PRIORITY_XP[item.priority];
        const existingCompletion = previous.completions.find((entry) => entry.itemId === item.id);
        if (item.oneOffDone) {
          return {
            ...previous,
            items: previous.items.map((entry) =>
              entry.id === item.id ? { ...entry, oneOffDone: false } : entry
            ),
            completions: existingCompletion
              ? previous.completions.filter((entry) => entry.id !== existingCompletion.id)
              : previous.completions,
            profile: {
              ...previous.profile,
              xp: Math.max(0, previous.profile.xp - (existingCompletion?.xp ?? taskXp))
            }
          };
        }
        return {
          ...previous,
          items: previous.items.map((entry) =>
            entry.id === item.id ? { ...entry, oneOffDone: true } : entry
          ),
          completions: [
            {
              id: createId("log"),
              itemId: item.id,
              dateKey: todayKey,
              xp: taskXp
            },
            ...previous.completions.filter((entry) => entry.itemId !== item.id)
          ],
          profile: {
            ...previous.profile,
            xp: previous.profile.xp + taskXp
          }
        };
      }

      const existingHabitLog = previous.completions.find(
        (entry) => entry.itemId === item.id && entry.dateKey === todayKey
      );
      if (existingHabitLog) {
        return {
          ...previous,
          completions: previous.completions.filter((entry) => entry.id !== existingHabitLog.id),
          profile: {
            ...previous.profile,
            xp: Math.max(0, previous.profile.xp - existingHabitLog.xp)
          }
        };
      }
      return {
        ...previous,
        completions: [
          {
            id: createId("log"),
            itemId: item.id,
            dateKey: todayKey,
            xp: HABIT_XP
          },
          ...previous.completions
        ],
        profile: {
          ...previous.profile,
          xp: previous.profile.xp + HABIT_XP
        }
      };
    });
  }

  function deleteMission(itemId: string): void {
    setState((previous) => ({
      ...previous,
      items: previous.items.filter((item) => item.id !== itemId),
      completions: previous.completions.filter((entry) => entry.itemId !== itemId)
    }));
  }

  function claimDailyQuest(): void {
    if (!canClaimDailyQuest) return;
    setState((previous) => ({
      ...previous,
      profile: {
        ...previous.profile,
        xp: previous.profile.xp + DAILY_QUEST_REWARD,
        claimedQuestDays: [...previous.profile.claimedQuestDays, todayKey]
      }
    }));
  }

  async function linkGoogle(): Promise<void> {
    await connectGoogleCalendarMock();
    setState((previous) => ({
      ...previous,
      profile: {
        ...previous.profile,
        linkedGoogle: true
      }
    }));
    Alert.alert("Google Linked", "Calendar sync is now enabled for this MVP.");
  }

  async function syncGoogleNow(): Promise<void> {
    if (!state.profile.linkedGoogle) {
      Alert.alert("Google not linked", "Link Google first, then run sync.");
      return;
    }
    const result = await syncItemsToGoogleCalendar(missionItems);
    Alert.alert("Sync Complete", `${result.synced} active missions mirrored to calendar.`);
  }

  async function linkAlexa(): Promise<void> {
    await connectAlexaMock();
    setState((previous) => ({
      ...previous,
      profile: {
        ...previous.profile,
        linkedAlexa: true
      }
    }));
    Alert.alert("Alexa Linked", "Daily mission briefing can now be generated.");
  }

  function previewAlexaBrief(): void {
    const brief = buildDailyAlexaBrief({ level, streak, todayDone: todayDoneCount });
    Alert.alert("Alexa Brief", brief);
  }

  function unlockPremiumLifetime(): void {
    setState((previous) => ({
      ...previous,
      profile: {
        ...previous.profile,
        premiumUnlocked: true
      }
    }));
    Alert.alert("Premium Enabled", "Lifetime premium is marked as unlocked (MVP mode).");
  }

  return (
    <LinearGradient colors={[palette.night0, palette.night1, palette.night2]} style={styles.fill}>
      <StatusBar style="light" />
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {activeScreen === "focus" ? (
            <>
              <View style={styles.heroCard}>
                <Text style={styles.heroTag}>HABITS</Text>
                <Text style={styles.heroTitle}>Minimal Tracker</Text>
                <Text style={styles.heroSub}>Tap habit name for graph. Tap check button to mark done.</Text>
                <Text style={styles.focusCountText}>
                  {habitItems.length === 0 ? "No habits yet" : `${habitsDoneToday}/${habitItems.length} done today`}
                </Text>
                <Pressable style={styles.compactSwitchButton} onPress={() => setActiveScreen("dashboard")}>
                  <Text style={styles.compactSwitchText}>Open Dashboard</Text>
                </Pressable>
              </View>

              <View style={styles.card}>
                <View style={styles.minimalAddRow}>
                  <TextInput
                    value={habitDraft}
                    onChangeText={setHabitDraft}
                    placeholder="Add habit..."
                    placeholderTextColor={palette.mutedInk}
                    style={styles.minimalInput}
                  />
                  <Pressable style={styles.minimalAddButton} onPress={addHabitFromFocus}>
                    <Text style={styles.minimalAddText}>+</Text>
                  </Pressable>
                </View>

                {habitItems.length > 0 ? (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.habitCardRow}>
                    {habitItems.slice(0, 6).map((item) => {
                      const weekDone = weekDays.filter((dayKey) => isHabitDoneOnDate(item.id, dayKey)).length;
                      const done = isDone(item);
                      return (
                        <Pressable
                          key={item.id}
                          style={[styles.habitMiniCard, selectedHabitId === item.id && styles.habitMiniCardActive]}
                          onPress={() => setSelectedHabitId(item.id)}
                        >
                          <Text style={styles.habitMiniTitle}>{item.title}</Text>
                          <Text style={styles.habitMiniMeta}>
                            {weekDone}/7 week {done ? "| done today" : ""}
                          </Text>
                          <View style={styles.sparkRow}>
                            {weekDays.map((dayKey) => {
                              const dayDone = isHabitDoneOnDate(item.id, dayKey);
                              return (
                                <View
                                  key={`${item.id}-${dayKey}`}
                                  style={[styles.sparkBar, dayDone ? styles.sparkBarOn : styles.sparkBarOff]}
                                />
                              );
                            })}
                          </View>
                        </Pressable>
                      );
                    })}
                  </ScrollView>
                ) : null}
              </View>

              {selectedHabit ? (
                <View style={styles.card}>
                  <Text style={styles.sectionTitle}>{selectedHabit.title} Graph</Text>
                  <Text style={styles.mutedText}>{selectedHabitCompletedDays}/14 days completed</Text>
                  <View style={styles.focusGraphRowCompact}>
                    {selectedHabitTrend.map((day) => (
                      <View key={day.key} style={styles.focusGraphCol}>
                        <View
                          style={[
                            styles.focusGraphBar,
                            day.done ? styles.focusGraphBarDone : styles.focusGraphBarMiss,
                            { height: day.done ? 48 : 12 },
                            day.isToday && styles.focusGraphBarToday
                          ]}
                        />
                        <Text style={styles.focusGraphLabel}>{day.dayLabel}</Text>
                      </View>
                    ))}
                  </View>
                  <Text style={styles.mutedText}>
                    This week: {selectedHabitWeekDone}/7
                  </Text>
                  <View style={styles.heatmapWrap}>
                    {heatmapWeeks.map((week, weekIndex) => (
                      <View key={`week-${weekIndex}`} style={styles.heatmapCol}>
                        {week.map((dayKey) => {
                          const dayDone = isHabitDoneOnDate(selectedHabit.id, dayKey);
                          const isToday = dayKey === todayKey;
                          return (
                            <View
                              key={`heat-${dayKey}`}
                              style={[
                                styles.heatCell,
                                dayDone ? styles.heatCellDone : styles.heatCellOff,
                                isToday && styles.heatCellToday
                              ]}
                            />
                          );
                        })}
                      </View>
                    ))}
                  </View>
                </View>
              ) : null}

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Weekly Table</Text>
                <View style={styles.weekTableHeader}>
                  <Text style={styles.weekTableHabitHeader}>Habit</Text>
                  {weekLabels.map((label, index) => (
                    <Text key={`head-${weekDays[index]}`} style={styles.weekTableDayHeader}>
                      {label}
                    </Text>
                  ))}
                </View>
                {habitItems.length === 0 ? (
                  <Text style={styles.mutedText}>No habits yet.</Text>
                ) : (
                  habitItems.map((item) => {
                    const doneToday = isDone(item);
                    return (
                      <View key={`table-${item.id}`} style={styles.weekTableRow}>
                        <Pressable style={styles.weekTableHabitCell} onPress={() => setSelectedHabitId(item.id)}>
                          <Text style={styles.weekTableHabitText}>{item.title}</Text>
                        </Pressable>
                        {weekDays.map((dayKey) => {
                          const checked = isHabitDoneOnDate(item.id, dayKey);
                          const isToday = dayKey === todayKey;
                          return (
                            <Pressable
                              key={`${item.id}-week-${dayKey}`}
                              style={[
                                styles.weekTableTick,
                                checked && styles.weekTableTickOn,
                                isToday && styles.weekTableTickToday
                              ]}
                              onPress={() => {
                                if (isToday) toggleMission(item);
                              }}
                            >
                              <Text style={[styles.weekTableTickText, checked && styles.weekTableTickTextOn]}>
                                {checked ? "✓" : isToday ? "•" : "x"}
                              </Text>
                            </Pressable>
                          );
                        })}
                        <View style={[styles.weekTableTodayTag, doneToday && styles.weekTableTodayTagOn]}>
                          <Text style={styles.weekTableTodayTagText}>{doneToday ? "DONE" : "PEND"}</Text>
                        </View>
                      </View>
                    );
                  })
                )}
              </View>
            </>
          ) : (
            <>
              <Pressable style={styles.compactSwitchButton} onPress={() => setActiveScreen("focus")}>
                <Text style={styles.compactSwitchText}>Back To Habit Tracker</Text>
              </Pressable>
              <View style={styles.heroCard}>
                <Text style={styles.heroTag}>ANDROID MVP</Text>
                <Text style={styles.heroTitle}>SHADOW TASK</Text>
                <Text style={styles.heroSub}>Minimal missions. Maximum momentum.</Text>
                <View style={styles.heroStats}>
                  <StatPill label="Level" value={String(level)} />
                  <StatPill label="Rank" value={rank} />
                  <StatPill label="XP" value={String(state.profile.xp)} />
                  <StatPill label="Streak" value={`${streak}d`} />
                </View>
                <View style={styles.progressTrack}>
                  <View
                    style={[styles.progressFill, { width: `${Math.round(levelProgress.progressRatio * 100)}%` }]}
                  />
                </View>
                <Text style={styles.progressMeta}>
                  {levelProgress.remainingXp} XP to reach level {levelProgress.nextLevel}
                </Text>
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>New Mission</Text>
                <TextInput
                  value={titleDraft}
                  onChangeText={setTitleDraft}
                  placeholder="Write one clear target..."
                  placeholderTextColor={palette.mutedInk}
                  style={styles.input}
                />
                <View style={styles.toggleRow}>
                  <ModeButton
                    label="Task"
                    active={kindDraft === "task"}
                    onPress={() => setKindDraft("task")}
                  />
                  <ModeButton
                    label="Habit"
                    active={kindDraft === "habit"}
                    onPress={() => setKindDraft("habit")}
                  />
                  <Pressable style={styles.primaryButton} onPress={addMission}>
                    <Text style={styles.primaryText}>Add</Text>
                  </Pressable>
                </View>
                <Text style={styles.mutedText}>Priority XP</Text>
                <View style={styles.toggleRow}>
                  <PriorityButton
                    label="Low"
                    active={priorityDraft === "low"}
                    onPress={() => setPriorityDraft("low")}
                  />
                  <PriorityButton
                    label="Mid"
                    active={priorityDraft === "mid"}
                    onPress={() => setPriorityDraft("mid")}
                  />
                  <PriorityButton
                    label="High"
                    active={priorityDraft === "high"}
                    onPress={() => setPriorityDraft("high")}
                  />
                </View>
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Daily Quest</Text>
                <Text style={styles.mutedText}>
                  Complete {DAILY_QUEST_TARGET} missions today for +{DAILY_QUEST_REWARD} XP.
                </Text>
                <Text style={styles.questProgress}>
                  Progress: {todayDoneCount}/{DAILY_QUEST_TARGET}
                </Text>
                <Pressable
                  style={[styles.primaryButton, !canClaimDailyQuest && styles.disabledButton]}
                  onPress={claimDailyQuest}
                  disabled={!canClaimDailyQuest}
                >
                  <Text style={styles.primaryText}>
                    {questClaimed ? "Claimed" : canClaimDailyQuest ? "Claim Reward" : "Locked"}
                  </Text>
                </Pressable>
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Missions</Text>
                <View style={styles.toggleRow}>
                  <FilterButton
                    label="All"
                    active={missionFilter === "all"}
                    onPress={() => setMissionFilter("all")}
                  />
                  <FilterButton
                    label="Tasks"
                    active={missionFilter === "task"}
                    onPress={() => setMissionFilter("task")}
                  />
                  <FilterButton
                    label="Habits"
                    active={missionFilter === "habit"}
                    onPress={() => setMissionFilter("habit")}
                  />
                </View>
                {missionItems.length === 0 ? (
                  <Text style={styles.mutedText}>No active missions. Add one and start streaking.</Text>
                ) : (
                  missionItems.map((item) => {
                    const done = isDone(item);
                    return (
                      <View key={item.id} style={styles.missionRow}>
                        <View style={styles.missionMain}>
                          <Text style={styles.missionTitle}>{item.title}</Text>
                          <Text style={styles.missionMeta}>
                            {item.kind.toUpperCase()} | {item.priority.toUpperCase()} XP |{" "}
                            {item.kind === "habit" ? "Repeats daily" : "One-time"}
                          </Text>
                        </View>
                        <View style={styles.rowButtons}>
                          <Pressable
                            style={[styles.circleButton, done ? styles.circleDone : styles.circleOpen]}
                            onPress={() => toggleMission(item)}
                          >
                            <Text style={styles.circleLabel}>{done ? "DONE" : "GO"}</Text>
                          </Pressable>
                          <Pressable style={styles.deleteButton} onPress={() => deleteMission(item.id)}>
                            <Text style={styles.deleteText}>X</Text>
                          </Pressable>
                        </View>
                      </View>
                    );
                  })
                )}
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Weekly Stats</Text>
                <View style={styles.weekWrap}>
                  {weekly.map((day) => (
                    <View key={day.key} style={styles.weekColumn}>
                      <View
                        style={[
                          styles.weekBar,
                          {
                            height: 14 + (70 * day.count) / maxWeekly,
                            opacity: day.count > 0 ? 1 : 0.3
                          }
                        ]}
                      />
                      <Text style={styles.weekCount}>{day.count}</Text>
                      <Text style={styles.weekLabel}>{day.day}</Text>
                    </View>
                  ))}
                </View>
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Integrations</Text>
                <View style={styles.integrationRow}>
                  <Text style={styles.integrationTitle}>
                    Google Calendar {state.profile.linkedGoogle ? "| Linked" : "| Not Linked"}
                  </Text>
                  <Pressable style={styles.secondaryButton} onPress={linkGoogle}>
                    <Text style={styles.secondaryText}>Link</Text>
                  </Pressable>
                </View>
                <Pressable style={styles.primaryButton} onPress={syncGoogleNow}>
                  <Text style={styles.primaryText}>Sync Missions</Text>
                </Pressable>
                <View style={styles.integrationRow}>
                  <Text style={styles.integrationTitle}>
                    Alexa Briefings {state.profile.linkedAlexa ? "| Linked" : "| Not Linked"}
                  </Text>
                  <Pressable style={styles.secondaryButton} onPress={linkAlexa}>
                    <Text style={styles.secondaryText}>Link</Text>
                  </Pressable>
                </View>
                {state.profile.linkedAlexa ? (
                  <Pressable style={styles.primaryButton} onPress={previewAlexaBrief}>
                    <Text style={styles.primaryText}>Preview Alexa Brief</Text>
                  </Pressable>
                ) : null}
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Premium</Text>
                <Text style={styles.mutedText}>Lifetime: $9.99 (hook ready, payment not wired yet).</Text>
                <Text style={styles.mutedText}>
                  Premium unlocks advanced analytics, smart scheduling, and voice packs.
                </Text>
                <Pressable
                  style={[styles.primaryButton, state.profile.premiumUnlocked && styles.premiumDone]}
                  onPress={unlockPremiumLifetime}
                >
                  <Text style={styles.primaryText}>
                    {state.profile.premiumUnlocked ? "Premium Active" : "Unlock Lifetime"}
                  </Text>
                </Pressable>
              </View>
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

function StatPill(props: { label: string; value: string }): React.JSX.Element {
  return (
    <View style={styles.statPill}>
      <Text style={styles.statLabel}>{props.label}</Text>
      <Text style={styles.statValue}>{props.value}</Text>
    </View>
  );
}

function ModeButton(props: { label: string; active: boolean; onPress: () => void }): React.JSX.Element {
  return (
    <Pressable
      style={[styles.modeButton, props.active ? styles.modeButtonActive : styles.modeButtonIdle]}
      onPress={props.onPress}
    >
      <Text style={[styles.modeLabel, props.active && styles.modeLabelActive]}>{props.label}</Text>
    </Pressable>
  );
}

function PriorityButton(props: {
  label: string;
  active: boolean;
  onPress: () => void;
}): React.JSX.Element {
  return (
    <Pressable
      style={[styles.priorityButton, props.active ? styles.priorityActive : styles.priorityIdle]}
      onPress={props.onPress}
    >
      <Text style={[styles.priorityText, props.active && styles.priorityTextActive]}>{props.label}</Text>
    </Pressable>
  );
}

function FilterButton(props: {
  label: string;
  active: boolean;
  onPress: () => void;
}): React.JSX.Element {
  return (
    <Pressable
      style={[styles.filterButton, props.active ? styles.filterActive : styles.filterIdle]}
      onPress={props.onPress}
    >
      <Text style={[styles.filterText, props.active && styles.filterTextActive]}>{props.label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  safe: { flex: 1 },
  content: {
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl
  },
  compactSwitchButton: {
    alignSelf: "flex-start",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.neonCyan,
    backgroundColor: "rgba(71, 244, 231, 0.14)",
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md
  },
  compactSwitchText: {
    color: palette.neonCyan,
    fontFamily: fonts.body,
    fontSize: typeScale.caption,
    letterSpacing: 0.5
  },
  heroCard: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: "rgba(9, 14, 28, 0.85)",
    padding: spacing.lg
  },
  heroTag: {
    color: palette.neonCyan,
    fontSize: typeScale.caption,
    fontFamily: fonts.headline,
    letterSpacing: 2
  },
  heroTitle: {
    color: palette.ink,
    fontSize: typeScale.hero,
    fontFamily: fonts.headline,
    letterSpacing: 2,
    marginTop: spacing.xs
  },
  heroSub: {
    color: palette.mutedInk,
    fontSize: typeScale.body,
    fontFamily: fonts.body,
    marginTop: spacing.xs
  },
  focusCountText: {
    marginTop: spacing.md,
    color: palette.neonGold,
    fontSize: typeScale.section,
    fontFamily: fonts.headline
  },
  heroStats: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md
  },
  progressTrack: {
    marginTop: spacing.sm,
    height: 10,
    borderRadius: 999,
    backgroundColor: "rgba(34, 50, 81, 0.65)",
    overflow: "hidden"
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: palette.neonCyan
  },
  progressMeta: {
    color: palette.mutedInk,
    marginTop: 6,
    fontSize: typeScale.caption,
    fontFamily: fonts.body
  },
  statPill: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: "rgba(36, 51, 83, 0.35)",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs
  },
  statLabel: {
    color: palette.mutedInk,
    fontSize: typeScale.caption,
    fontFamily: fonts.body
  },
  statValue: {
    color: palette.neonGold,
    fontSize: typeScale.body,
    fontFamily: fonts.headline
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: "rgba(10, 16, 31, 0.88)",
    padding: spacing.md,
    gap: spacing.sm
  },
  sectionTitle: {
    color: palette.ink,
    fontSize: typeScale.section,
    fontFamily: fonts.headline,
    letterSpacing: 1
  },
  mutedText: {
    color: palette.mutedInk,
    fontSize: typeScale.body,
    fontFamily: fonts.body
  },
  input: {
    borderWidth: 1,
    borderColor: palette.outline,
    borderRadius: 12,
    backgroundColor: "rgba(24, 34, 58, 0.5)",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: palette.ink,
    fontSize: typeScale.body,
    fontFamily: fonts.body
  },
  minimalAddRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  minimalInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: palette.outline,
    borderRadius: 12,
    backgroundColor: "rgba(24, 34, 58, 0.5)",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: palette.ink,
    fontSize: typeScale.body,
    fontFamily: fonts.body
  },
  minimalAddButton: {
    width: 42,
    height: 42,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.neonBlue,
    backgroundColor: "rgba(65, 194, 255, 0.2)",
    alignItems: "center",
    justifyContent: "center"
  },
  minimalAddText: {
    color: palette.ink,
    fontSize: 24,
    fontFamily: fonts.headline,
    lineHeight: 25
  },
  habitCardRow: {
    gap: spacing.sm,
    paddingVertical: spacing.xs
  },
  habitMiniCard: {
    width: 172,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: "rgba(16, 24, 41, 0.8)",
    padding: spacing.sm,
    gap: spacing.xs
  },
  habitMiniCardActive: {
    borderColor: palette.neonCyan,
    backgroundColor: "rgba(26, 39, 66, 0.9)"
  },
  habitMiniTitle: {
    color: palette.ink,
    fontFamily: fonts.body,
    fontSize: typeScale.body
  },
  habitMiniMeta: {
    color: palette.mutedInk,
    fontFamily: fonts.body,
    fontSize: typeScale.caption
  },
  sparkRow: {
    marginTop: spacing.xs,
    flexDirection: "row",
    gap: 4,
    alignItems: "flex-end"
  },
  sparkBar: {
    width: 16,
    borderRadius: 4,
    borderWidth: 1
  },
  sparkBarOn: {
    height: 20,
    borderColor: palette.success,
    backgroundColor: "rgba(88, 247, 165, 0.65)"
  },
  sparkBarOff: {
    height: 10,
    borderColor: palette.outline,
    backgroundColor: "rgba(34, 50, 81, 0.4)"
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  modeButton: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center"
  },
  modeButtonActive: {
    borderColor: palette.neonBlue,
    backgroundColor: "rgba(65, 194, 255, 0.2)"
  },
  modeButtonIdle: {
    borderColor: palette.outline,
    backgroundColor: "rgba(19, 27, 45, 0.6)"
  },
  modeLabel: {
    color: palette.mutedInk,
    fontFamily: fonts.body,
    fontSize: typeScale.body
  },
  modeLabelActive: {
    color: palette.ink
  },
  priorityButton: {
    flex: 1,
    paddingVertical: spacing.xs,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center"
  },
  priorityActive: {
    borderColor: palette.neonGold,
    backgroundColor: "rgba(241, 197, 99, 0.18)"
  },
  priorityIdle: {
    borderColor: palette.outline,
    backgroundColor: "rgba(19, 27, 45, 0.6)"
  },
  priorityText: {
    color: palette.mutedInk,
    fontFamily: fonts.body,
    fontSize: typeScale.caption
  },
  priorityTextActive: {
    color: palette.neonGold
  },
  filterButton: {
    flex: 1,
    paddingVertical: spacing.xs,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center"
  },
  filterActive: {
    borderColor: palette.neonCyan,
    backgroundColor: "rgba(71, 244, 231, 0.2)"
  },
  filterIdle: {
    borderColor: palette.outline,
    backgroundColor: "rgba(19, 27, 45, 0.6)"
  },
  filterText: {
    color: palette.mutedInk,
    fontFamily: fonts.body,
    fontSize: typeScale.caption
  },
  filterTextActive: {
    color: palette.neonCyan
  },
  primaryButton: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.neonBlue,
    backgroundColor: "rgba(65, 194, 255, 0.2)",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center"
  },
  primaryText: {
    color: palette.ink,
    fontSize: typeScale.body,
    fontFamily: fonts.headline,
    letterSpacing: 1
  },
  secondaryButton: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: "rgba(20, 31, 54, 0.7)",
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md
  },
  secondaryText: {
    color: palette.neonCyan,
    fontFamily: fonts.body,
    fontSize: typeScale.body
  },
  disabledButton: {
    opacity: 0.45
  },
  questProgress: {
    color: palette.neonGold,
    fontSize: typeScale.body,
    fontFamily: fonts.headline
  },
  missionRow: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: "rgba(17, 25, 43, 0.7)",
    padding: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm
  },
  missionMain: {
    flex: 1
  },
  missionTitle: {
    color: palette.ink,
    fontSize: typeScale.body,
    fontFamily: fonts.body
  },
  missionMeta: {
    color: palette.mutedInk,
    fontSize: typeScale.caption,
    fontFamily: fonts.body,
    marginTop: 2
  },
  rowButtons: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs
  },
  circleButton: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1
  },
  circleDone: {
    backgroundColor: "rgba(88, 247, 165, 0.18)",
    borderColor: palette.success
  },
  circleOpen: {
    backgroundColor: "rgba(65, 194, 255, 0.15)",
    borderColor: palette.neonBlue
  },
  circleLabel: {
    color: palette.ink,
    fontFamily: fonts.headline,
    fontSize: typeScale.caption
  },
  deleteButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: palette.danger,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 107, 138, 0.15)"
  },
  deleteText: {
    color: palette.danger,
    fontFamily: fonts.headline
  },
  focusHabitRow: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: "rgba(17, 25, 43, 0.7)",
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm
  },
  focusHabitRowDone: {
    borderColor: palette.success,
    backgroundColor: "rgba(88, 247, 165, 0.12)"
  },
  focusHabitInfo: {
    flex: 1
  },
  focusHabitTitle: {
    color: palette.ink,
    fontSize: typeScale.section,
    fontFamily: fonts.body
  },
  focusHabitHint: {
    marginTop: 2,
    color: palette.mutedInk,
    fontSize: typeScale.caption,
    fontFamily: fonts.body
  },
  focusCheckPill: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.neonBlue,
    backgroundColor: "rgba(65, 194, 255, 0.2)",
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm
  },
  focusCheckPillDone: {
    borderColor: palette.success,
    backgroundColor: "rgba(88, 247, 165, 0.25)"
  },
  focusCheckText: {
    color: palette.ink,
    fontFamily: fonts.headline,
    fontSize: typeScale.caption,
    letterSpacing: 1
  },
  focusGraphRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between"
  },
  focusGraphCol: {
    width: 18,
    alignItems: "center",
    gap: 4
  },
  focusGraphBar: {
    width: 14,
    height: 46,
    borderRadius: 8,
    borderWidth: 1
  },
  focusGraphBarDone: {
    borderColor: palette.success,
    backgroundColor: "rgba(88, 247, 165, 0.7)"
  },
  focusGraphBarMiss: {
    borderColor: palette.outline,
    backgroundColor: "rgba(34, 50, 81, 0.4)"
  },
  focusGraphBarToday: {
    borderColor: palette.neonCyan
  },
  focusGraphLabel: {
    color: palette.mutedInk,
    fontSize: 10,
    fontFamily: fonts.body
  },
  focusGraphRowCompact: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between"
  },
  heatmapWrap: {
    marginTop: spacing.sm,
    flexDirection: "row",
    gap: 4
  },
  heatmapCol: {
    gap: 4
  },
  heatCell: {
    width: 12,
    height: 12,
    borderRadius: 3,
    borderWidth: 1
  },
  heatCellDone: {
    borderColor: palette.success,
    backgroundColor: "rgba(88, 247, 165, 0.65)"
  },
  heatCellOff: {
    borderColor: palette.outline,
    backgroundColor: "rgba(34, 50, 81, 0.4)"
  },
  heatCellToday: {
    borderColor: palette.neonCyan
  },
  weekTableHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: palette.outline
  },
  weekTableHabitHeader: {
    width: 108,
    color: palette.mutedInk,
    fontFamily: fonts.headline,
    fontSize: typeScale.caption
  },
  weekTableDayHeader: {
    width: 28,
    textAlign: "center",
    color: palette.mutedInk,
    fontFamily: fonts.headline,
    fontSize: 11
  },
  weekTableRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(34, 50, 81, 0.45)"
  },
  weekTableHabitCell: {
    width: 108
  },
  weekTableHabitText: {
    color: palette.ink,
    fontFamily: fonts.body,
    fontSize: typeScale.caption
  },
  weekTableTick: {
    width: 28,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "transparent"
  },
  weekTableTickOn: {
    backgroundColor: "rgba(71, 244, 231, 0.2)"
  },
  weekTableTickToday: {
    borderColor: palette.neonBlue
  },
  weekTableTickText: {
    color: palette.mutedInk,
    fontFamily: fonts.headline,
    fontSize: 12
  },
  weekTableTickTextOn: {
    color: palette.neonCyan
  },
  weekTableTodayTag: {
    marginLeft: 6,
    paddingHorizontal: 6,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.outline
  },
  weekTableTodayTagOn: {
    borderColor: palette.success,
    backgroundColor: "rgba(88, 247, 165, 0.12)"
  },
  weekTableTodayTagText: {
    color: palette.mutedInk,
    fontFamily: fonts.headline,
    fontSize: 10
  },
  weekWrap: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    marginTop: spacing.sm
  },
  weekColumn: {
    width: 38,
    alignItems: "center",
    gap: 4
  },
  weekBar: {
    width: 28,
    borderRadius: 8,
    backgroundColor: palette.neonCyan
  },
  weekCount: {
    color: palette.neonGold,
    fontSize: typeScale.caption,
    fontFamily: fonts.headline
  },
  weekLabel: {
    color: palette.mutedInk,
    fontSize: typeScale.caption,
    fontFamily: fonts.body
  },
  integrationRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm
  },
  integrationTitle: {
    color: palette.ink,
    fontSize: typeScale.body,
    fontFamily: fonts.body,
    flex: 1
  },
  premiumDone: {
    backgroundColor: "rgba(88, 247, 165, 0.2)",
    borderColor: palette.success
  }
});
