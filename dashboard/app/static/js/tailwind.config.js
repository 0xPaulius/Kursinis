// Tailwind Play runtime'o konfigūracija (įkeliama iškart po tailwind.min.js abiejuose puslapiuose).
// Spalvos rodo į css/theme.css kintamuosius, todėl ta pati klasė tinka abiem temoms.
// Opacity modifikatoriai (pvz. bg-panel/50) su var() spalvomis neveikia — jų nenaudojame.

tailwind.config = {
  theme: {
    extend: {
      colors: {
        bg:          "var(--bg)",
        panel:       "var(--panel)",
        line:        "var(--line)",
        "line-weak": "var(--line-weak)",
        hover:       "var(--hover)",
        fg:          "var(--text)",
        strong:      "var(--text-strong)",
        muted:       "var(--text-muted)",
        dim:         "var(--text-dim)",
        accent:      "var(--accent)",
        ok:          "var(--ok)",
        warn:        "var(--warn)",
        high:        "var(--high)",
        crit:        "var(--crit)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "Liberation Mono", "monospace"],
      },
    },
  },
};
