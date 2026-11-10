import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: { DEFAULT: "#FFFFEB", 50: "#FFFFF5", 100: "#FFFFEB", 200: "#F7F6DC", 300: "#EDEBCB" },
        ink: { DEFAULT: "#1A1A1A", 700: "#3A3A36", 500: "#6B6A62", 400: "#8C8B82", 300: "#B5B3A6" },
        forest: { DEFAULT: "#034F46", 900: "#02362F", 700: "#034F46", 500: "#2D6E64", 100: "#DCE9E4", 50: "#EEF5F1" },
        lilac: { DEFAULT: "#F0D7FF", 200: "#F6E6FF", 400: "#E3BDFA", 700: "#6E3C8C" },
        sage: { DEFAULT: "#7FA38C", 100: "#E4EFE6", 700: "#3F6B4E" },
        amber: { DEFAULT: "#C98A1B", 100: "#FBEFD6", 700: "#8A5A06" },
        crimson: { DEFAULT: "#9B1C1C", 100: "#F8E1DE", 700: "#7A1414" },
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(26,26,26,0.04), 0 8px 24px -12px rgba(26,26,26,0.12)",
        lift: "0 2px 4px rgba(26,26,26,0.04), 0 18px 40px -18px rgba(3,79,70,0.28)",
      },
      borderColor: { hair: "rgba(26,26,26,0.10)" },
      keyframes: {
        rise: { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "none" } },
        pulseDot: { "0%,100%": { opacity: "0.35" }, "50%": { opacity: "1" } },
      },
      animation: {
        rise: "rise 360ms cubic-bezier(.2,.7,.2,1) both",
        pulseDot: "pulseDot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
