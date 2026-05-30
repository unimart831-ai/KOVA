/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        kova: {
          50:  "#edfcf8",
          100: "#d0f4ec",
          200: "#a3e8d7",
          300: "#6dd4be",
          400: "#37b8a0",
          500: "#1a9d88",
          600: "#0d8474",
          700: "#0a6d60",
          800: "#08564a",
          900: "#065040",
          950: "#02281f",
        },
      },
      boxShadow: {
        kova: "0 1px 2px rgba(13, 132, 116, 0.06), 0 4px 24px rgba(13, 132, 116, 0.08)",
        "kova-lg": "0 4px 6px rgba(13, 132, 116, 0.07), 0 10px 40px rgba(13, 132, 116, 0.12)",
        glow: "0 0 20px rgba(13, 132, 116, 0.15)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      keyframes: {
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(8px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-20px)" },
        },
        "float-delayed": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-15px)" },
        },
        "agent-glow": {
          "0%, 18%, 100%": { boxShadow: "0 1px 3px rgba(0,0,0,0.08)" },
          "6%, 12%": { boxShadow: "0 0 0 2px rgba(26,157,136,0.15), 0 0 20px rgba(26,157,136,0.08)" },
        },
        "dash-flow": {
          "to": { strokeDashoffset: "-20" },
        },
        "dash-flow-reverse": {
          "to": { strokeDashoffset: "20" },
        },
        "orbit": {
          "0%": { transform: "rotate(0deg) translateX(var(--orbit-radius, 120px)) rotate(0deg)" },
          "100%": { transform: "rotate(360deg) translateX(var(--orbit-radius, 120px)) rotate(-360deg)" },
        },
        "blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(1)", opacity: "0.6" },
          "100%": { transform: "scale(1.8)", opacity: "0" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        "glow-breathe": {
          "0%, 100%": { opacity: "0.4", transform: "scale(1)" },
          "50%": { opacity: "0.7", transform: "scale(1.05)" },
        },
      },
      animation: {
        "shimmer": "shimmer 2.5s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
        "scale-in": "scale-in 0.2s ease-out",
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        "float-delayed": "float-delayed 8s ease-in-out infinite",
        "agent-glow": "agent-glow 10s ease-in-out infinite",
        "dash-flow": "dash-flow 2s linear infinite",
        "orbit": "orbit 20s linear infinite",
        "blink": "blink 1s step-end infinite",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "gradient-shift": "gradient-shift 8s ease infinite",
        "glow-breathe": "glow-breathe 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
