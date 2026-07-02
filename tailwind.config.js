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
        /* ── PRIMARY: Deep Emerald — brand identity, growth, business success ── */
        kova: {
          50:  '#ECFDF5',
          100: '#D1FAE5',
          200: '#A7F3D0',
          300: '#6EE7B7',
          400: '#34D399',
          500: '#10B981',   // subtle / hover base
          600: '#059669',   // interactive / active states
          700: '#047857',   // ← BRAND PRIMARY (deep emerald)
          800: '#065F46',   // dark brand / pressed
          900: '#064E3B',
          950: '#022C22',
        },
        /* ── SUCCESS / REVENUE: lighter emerald — positive indicators ── */
        growth: {
          50:  '#ECFDF5',
          100: '#D1FAE5',
          200: '#A7F3D0',
          300: '#6EE7B7',
          400: '#34D399',
          500: '#10B981',   // revenue badges, success states
          600: '#059669',
          700: '#047857',
          800: '#065F46',
          900: '#064E3B',
          950: '#022C22',
        },
        /* ── ACHIEVEMENT / OPPORTUNITY: Warm Gold ── */
        gold: {
          50:  '#FFFBEB',
          100: '#FEF3C7',
          200: '#FDE68A',
          300: '#FCD34D',
          400: '#FBBF24',
          500: '#F59E0B',   // approvals, pending, opportunity
          600: '#D97706',
          700: '#B45309',
          800: '#92400E',
          900: '#78350F',
          950: '#451A03',
        },
        /* ── ACCENT: Electric Blue — interactive elements, focus rings, links ONLY ── */
        accent: {
          50:  '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',   // links, focus rings
          600: '#2563EB',   // interactive hover
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
          950: '#172554',
        },
        /* ── NEUTRAL: Clean grays — text, surfaces, borders (true gray, not slate) ── */
        gray: {
          50:  '#FAFAFA',   // app background
          100: '#F4F5F7',   // subtle surface
          200: '#E5E7EB',   // borders
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',   // secondary text
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',   // primary text
          950: '#030712',   // deep dark
        },
      },
      boxShadow: {
        kova: "0 1px 2px rgba(4, 120, 87, 0.06), 0 4px 24px rgba(4, 120, 87, 0.08)",
        "kova-lg": "0 4px 6px rgba(4, 120, 87, 0.07), 0 10px 40px rgba(4, 120, 87, 0.1)",
        growth: "0 1px 2px rgba(16, 185, 129, 0.08), 0 4px 24px rgba(16, 185, 129, 0.12)",
        "growth-lg": "0 4px 6px rgba(16, 185, 129, 0.1), 0 10px 40px rgba(16, 185, 129, 0.15)",
        glow: "0 0 20px rgba(4, 120, 87, 0.25)",
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
          "6%, 12%": { boxShadow: "0 0 0 2px rgba(16,185,129,0.2), 0 0 20px rgba(16,185,129,0.1)" },
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
