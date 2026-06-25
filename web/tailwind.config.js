/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Tokens baseados em CSS variables (R G B) → suportam tema claro/escuro
        // e utilitários de alpha (ex.: bg-surface-1/70). Ver src/index.css.
        ifg: {
          green: "#23A455",
          "green-dark": "#1C7A3F",
          "green-light": "#4CC97A",
        },
        surface: {
          0: "rgb(var(--c-surface-0) / <alpha-value>)",
          1: "rgb(var(--c-surface-1) / <alpha-value>)",
          2: "rgb(var(--c-surface-2) / <alpha-value>)",
          3: "rgb(var(--c-surface-3) / <alpha-value>)",
        },
        line: {
          DEFAULT: "rgb(var(--c-line) / <alpha-value>)",
          strong: "rgb(var(--c-line-strong) / <alpha-value>)",
        },
        text: {
          0: "rgb(var(--c-text-0) / <alpha-value>)",
          1: "rgb(var(--c-text-1) / <alpha-value>)",
          2: "rgb(var(--c-text-2) / <alpha-value>)",
          3: "rgb(var(--c-text-3) / <alpha-value>)",
        },
        severity: {
          normal: "rgb(var(--c-sev-normal) / <alpha-value>)",
          warning: "rgb(var(--c-sev-warning) / <alpha-value>)",
          alert: "rgb(var(--c-sev-alert) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: "16px",
      },
      keyframes: {
        pulseGreen: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(74,222,128,0.6)" },
          "70%": { boxShadow: "0 0 0 10px rgba(74,222,128,0)" },
        },
        flashRed: {
          "0%, 100%": { boxShadow: "inset 0 0 60px rgba(244,63,94,0.25)" },
          "50%":      { boxShadow: "inset 0 0 120px rgba(244,63,94,0.50)" },
        },
      },
      animation: {
        "pulse-green": "pulseGreen 1.6s ease-in-out infinite",
        "flash-red":   "flashRed 0.9s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
