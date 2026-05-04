# Shadow Task (Android-first MVP)

Minimal task + habit manager with a Solo Leveling-inspired vibe.

## Built in this pass

- Task and habit tracking
- XP, levels, streaks, and daily quest rewards
- Weekly completion stats panel
- Google Calendar linking and sync stubs
- Alexa daily briefing stubs
- Premium lifetime toggle (`$9.99`) as monetization hook

## Run

1. Install dependencies:

```bash
npm install
```

2. Start Expo:

```bash
npm run start
```

3. Android first:

```bash
npm run android
```

4. iOS (later phase):

```bash
npm run ios
```

## Architecture

- `App.tsx`: UI and app flow
- `src/storage.ts`: local persistence
- `src/utils/gamification.ts`: level/rank/streak/stat math
- `src/services/googleCalendar.ts`: Google sync adapter contract
- `src/services/alexaBridge.ts`: Alexa briefing adapter contract

## Next steps for production

1. Replace mock Google link/sync with real OAuth + Calendar API.
2. Implement Alexa skill account linking and backend webhook.
3. Add secure auth and cloud sync.
4. Integrate real in-app purchase flow for lifetime premium.
