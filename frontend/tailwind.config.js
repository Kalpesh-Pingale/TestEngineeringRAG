/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Semantic surface ramp — darkest is the page, lighter steps come
        // forward. Using names instead of raw slate values keeps the depth
        // hierarchy consistent across components.
        canvas: "#0b1120",
        surface: {
          DEFAULT: "#0f172a",
          raised: "#151f38",
          overlay: "#1e293b",
        },
        edge: {
          DEFAULT: "#1e293b",
          strong: "#334155",
        },
        content: {
          DEFAULT: "#e2e8f0",
          muted: "#94a3b8",
          subtle: "#64748b",
        },
        brand: {
          DEFAULT: "#38bdf8",
          strong: "#0ea5e9",
          dim: "#0369a1",
        },
        accent: "#a78bfa",
        ok: "#22c55e",
        warn: "#f59e0b",
        danger: "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "monospace"],
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.25s ease-out",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
