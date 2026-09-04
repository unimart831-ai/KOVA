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
        /* ── PRIMARY: Pure Blue — brand identity, CTAs, links ── */
        kova: {
          50:  '#E6F0FF',
          100: '#CCE0FF',
          200: '#99C2FF',
          300: '#66A3FF',
          400: '#3385FF',
          500: '#0066FF',
          600: '#0052CC',
          700: '#0047B3',
          800: '#003D99',
          900: '#002966',
          950: '#001433',
        },
        /* ── Interactive / revenue indicators — same blue scale ── */
        growth: {
          50:  '#E6F0FF',
          100: '#CCE0FF',
          200: '#99C2FF',
          300: '#66A3FF',
          400: '#3385FF',
          500: '#0066FF',
          600: '#0052CC',
          700: '#0047B3',
          800: '#003D99',
          900: '#002966',
          950: '#001433',
        },
        /* ── WARNING: Amber — pending / caution only (not brand) ── */
        gold: {
          50:  '#FEFCE8',
          100: '#FEF9C3',
          200: '#FEF08A',
          300: '#FDE047',
          400: '#FACC15',
          500: '#CA8A04',
          600: '#A16207',
          700: '#854D0E',
          800: '#713F12',
          900: '#422006',
          950: '#1A1203',
        },
        /* ── ACCENT: Lighter blue — secondary interactive states ── */
        accent: {
          50:  '#E6F0FF',
          100: '#CCE0FF',
          200: '#99C2FF',
          300: '#66A3FF',
          400: '#3385FF',
          500: '#0066FF',
          600: '#0052CC',
          700: '#0047B3',
          800: '#003D99',
          900: '#002966',
          950: '#001433',
        },
        /* ── NEUTRAL: Slate — text, surfaces, borders ── */
        gray: {
          50:  '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
          950: '#020617',
        },
        /* ── CANVAS: near-black teal-navy — dark-mode-first surfaces ── */
        canvas: {
          DEFAULT: '#06131a',
          muted:   '#0a1c27',
          raised:  '#0e2634',
        },
      },
      boxShadow: {
        kova: "0 1px 2px rgba(0, 102, 255, 0.06), 0 4px 24px rgba(0, 102, 255, 0.08)",
        "kova-lg": "0 4px 6px rgba(0, 102, 255, 0.07), 0 10px 40px rgba(0, 102, 255, 0.1)",
        growth: "0 1px 2px rgba(0, 102, 255, 0.08), 0 4px 24px rgba(0, 102, 255, 0.12)",
        "growth-lg": "0 4px 6px rgba(0, 102, 255, 0.1), 0 10px 40px rgba(0, 102, 255, 0.15)",
        glow: "0 0 20px rgba(0, 102, 255, 0.25)",
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["Sora", "Plus Jakarta Sans", "system-ui", "sans-serif"],
      },
      keyframes: {
        shimmer: {
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
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-20px)" },
        },
        "float-delayed": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-15px)" },
        },
        "agent-glow": {
          "0%, 18%, 100%": { boxShadow: "0 1px 3px rgba(0,0,0,0.08)" },
          "6%, 12%": { boxShadow: "0 0 0 2px rgba(0,102,255,0.2), 0 0 20px rgba(0,102,255,0.1)" },
        },
        "dash-flow": {
          to: { strokeDashoffset: "-20" },
        },
        "dash-flow-reverse": {
          to: { strokeDashoffset: "20" },
        },
        orbit: {
          "0%": { transform: "rotate(0deg) translateX(var(--orbit-radius, 120px)) rotate(0deg)" },
          "100%": { transform: "rotate(360deg) translateX(var(--orbit-radius, 120px)) rotate(-360deg)" },
        },
        blink: {
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
        "kova-busy-bar": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
      },
      animation: {
        shimmer: "shimmer 2.5s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
        "scale-in": "scale-in 0.2s ease-out",
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "float-delayed": "float-delayed 8s ease-in-out infinite",
        "agent-glow": "agent-glow 10s ease-in-out infinite",
        "dash-flow": "dash-flow 2s linear infinite",
        orbit: "orbit 20s linear infinite",
        blink: "blink 1s step-end infinite",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "gradient-shift": "gradient-shift 8s ease infinite",
        "glow-breathe": "glow-breathe 4s ease-in-out infinite",
        "kova-busy-bar": "kova-busy-bar 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
