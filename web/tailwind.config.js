/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ifg: {
          green: "#23A455",
          "green-dark": "#1C7A3F",
          "green-light": "#4CC97A",
        },
        surface: {
          0: "#08090c",
          1: "#0e1116",
          2: "#14181f",
          3: "#1a1f28",
        },
        line: {
          DEFAULT: "#232934",
          strong: "#2c333f",
        },
        text: {
          0: "#f1f4f9",
          1: "#a8b1bf",
          2: "#6b7385",
          3: "#444c5c",
        },
        severity: {
          normal: "#4ade80",
          warning: "#fbbf24",
          alert: "#f43f5e",
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
