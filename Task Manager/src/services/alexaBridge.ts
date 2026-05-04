function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function connectAlexaMock(): Promise<{ linked: true }> {
  await sleep(450);
  return { linked: true };
}

export function buildDailyAlexaBrief(args: {
  level: number;
  streak: number;
  todayDone: number;
}): string {
  return `Hunter update: Level ${args.level}, streak ${args.streak} days, ${args.todayDone} missions completed today.`;
}

export const ALEXA_SETUP_GUIDE = {
  skillType: "Custom Alexa Skill with account linking.",
  webhook: "POST progress updates to backend endpoint /alexa/briefing.",
  spokenReply: "Alexa reads daily mission briefing and today's task summary."
};
