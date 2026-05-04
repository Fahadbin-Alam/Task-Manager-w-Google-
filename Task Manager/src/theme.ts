import { Platform } from "react-native";

export const palette = {
  night0: "#070A12",
  night1: "#0D1322",
  night2: "#151E35",
  ink: "#E6ECFF",
  mutedInk: "#9BA6C7",
  neonBlue: "#41C2FF",
  neonCyan: "#47F4E7",
  neonGold: "#F1C563",
  outline: "#223251",
  success: "#58F7A5",
  danger: "#FF6B8A"
};

export const spacing = {
  xs: 6,
  sm: 10,
  md: 14,
  lg: 18,
  xl: 24
};

export const typeScale = {
  caption: 12,
  body: 14,
  section: 16,
  title: 20,
  hero: 30
};

export const fonts = {
  headline: Platform.select({ android: "monospace", ios: "Courier", default: "monospace" }),
  body: Platform.select({ android: "sans-serif-medium", ios: "AvenirNext-Medium", default: "System" })
};
