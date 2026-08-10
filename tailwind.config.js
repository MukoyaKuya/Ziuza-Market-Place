/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './components/**/*.html',
    './apps/**/*.html',
    './apps/**/*.py',
    './static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        kenya: {
          green: {
            DEFAULT: '#008751',
            dark: '#004D25',
            deep: '#00381C',
            light: '#20A068',
            subtle: '#E6F4ED',
          },
          red: {
            DEFAULT: '#C8102E',
            dark: '#9B0A21',
            light: '#E53E53',
            subtle: '#FCEBEF',
          },
          black: {
            DEFAULT: '#111111',
            rich: '#060606',
            muted: '#2A2A2A',
          },
        },
        brand: {
          primary: {
            DEFAULT: '#C8102E', // Matching main CTA red from mockup
            hover: '#9B0A21',
            light: '#FCEBEF',
            dark: '#7A071A',
          },
          accent: {
            DEFAULT: '#008751', // Matching green accent
            hover: '#004D25',
            light: '#E6F4ED',
          },
          surface: {
            DEFAULT: '#FFFFFF',
            ground: '#FAF8F5',
            card: '#FFFFFF',
            muted: '#F3EFEA',
            border: '#E8E4DF',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'Inter', 'sans-serif'],
        serif: ['Georgia', 'Cambria', 'serif'],
      },
      borderRadius: {
        'ziuza': '0.75rem',
        'pill': '9999px',
      },
      boxShadow: {
        'ziuza-sm': '0 1px 3px rgba(17, 17, 17, 0.05)',
        'ziuza-md': '0 4px 14px rgba(17, 17, 17, 0.08)',
        'ziuza-lg': '0 8px 24px rgba(17, 17, 17, 0.12)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
  ],
};
