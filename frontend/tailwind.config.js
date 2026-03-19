/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'tud-blue':    '#004B87',
        'tud-cyan':    '#009FE3',
        'tud-magenta': '#C8005A',
        'tud-lime':    '#84BD00',
        'tud-navy':    '#002147',
      },
      fontFamily: {
        display: ['"Syne"', 'sans-serif'],
        sans:    ['"Epilogue"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono:    ['"IBM Plex Mono"', '"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'sv-glow':        '0 0 24px rgba(0,159,227,0.30)',
        'sv-glow-strong': '0 0 40px rgba(0,159,227,0.50)',
        'sv-lime':        '0 0 16px rgba(132,189,0,0.30)',
        'sv-magenta':     '0 0 20px rgba(200,0,90,0.30)',
      },
      animation: {
        'pulse-slow':  'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan':        'scan 3s linear infinite',
        'flicker':     'flicker 2s ease-in-out infinite',
        'fade-up':     'fadeUp 0.4s ease-out forwards',
      },
      keyframes: {
        scan: {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(400%)' },
        },
        flicker: {
          '0%, 100%': { opacity: '1' },
          '33%':      { opacity: '0.70' },
          '66%':      { opacity: '0.85' },
        },
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
