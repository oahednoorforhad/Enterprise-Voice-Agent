/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}', './app/**/*.css'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Space Grotesk"', 'Inter', 'ui-sans-serif', 'system-ui'],
        sans: ['Inter', 'Arial', 'ui-sans-serif', 'system-ui'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      colors: {
        // Brand & Accent (Cohere-inspired)
        ink: '#212121',
        'muted-slate': '#93939f',
        slate: '#75758a',
        hairline: '#d9d9dd',
        'border-light': '#e5e7eb',

        // Core palette
        brand: {
          black: '#000000',
          near: '#17171c',
          green: '#003c33',
          navy: '#071829',
          blue: '#1863dc',
          coral: '#ff7759',
          'coral-soft': '#ffad9b',
        },

        // Surfaces
        surface: {
          white: '#ffffff',
          stone: '#eeece7',
          'green-wash': '#edfce9',
          'blue-wash': '#f1f5ff',
          DEFAULT: '#f8fafc',
          dark: '#17171c',
          'dark-elevated': '#22222a',
        },

        // Semantic
        focus: '#4c6ee6',
        'form-focus': '#9b60aa',
        error: '#b30000',

        // Utility accents
        coral: {
          50: '#fff0ed',
          100: '#ffddd6',
          200: '#ffc1b3',
          300: '#ffad9b',
          400: '#ff7759',
          500: '#ff5a36',
          600: '#e84a1e',
          700: '#c23b14',
          800: '#9e3214',
          900: '#802d17',
        },
        green: {
          50: '#edfce9',
          100: '#d4f7cc',
          200: '#acf09e',
          300: '#7ae368',
          400: '#4ed13b',
          500: '#2fb51e',
          600: '#239215',
          700: '#1f7414',
          800: '#1e5c17',
          900: '#1b4c18',
          950: '#003c33',
        },
        navy: {
          50: '#f0f6ff',
          100: '#dce8ff',
          200: '#c0d6ff',
          300: '#94bbff',
          400: '#6096ff',
          500: '#3b72f6',
          600: '#2554eb',
          700: '#1d42d8',
          800: '#1d37b0',
          900: '#1d338b',
          950: '#071829',
        },
      },
      borderRadius: {
        xs: '4px',
        sm: '8px',
        md: '16px',
        lg: '22px',
        xl: '30px',
        pill: '32px',
      },
      spacing: {
        2.5: '10px',
        4.5: '18px',
        5.5: '22px',
        7: '28px',
        9: '36px',
        10: '40px',
        14: '56px',
        15: '60px',
        16: '64px',
        20: '80px',
      },
      fontSize: {
        // Display scale
        'display-hero': ['96px', { lineHeight: '1', letterSpacing: '-0.02em', fontWeight: '400' }],
        'display-product': ['72px', { lineHeight: '1', letterSpacing: '-0.015em', fontWeight: '400' }],
        'display-section': ['60px', { lineHeight: '1', letterSpacing: '-0.01em', fontWeight: '400' }],
        // Heading scale
        'heading-section': ['48px', { lineHeight: '1.2', letterSpacing: '-0.01em', fontWeight: '400' }],
        'heading-card': ['32px', { lineHeight: '1.2', letterSpacing: '-0.01em', fontWeight: '400' }],
        'heading-feature': ['24px', { lineHeight: '1.3', letterSpacing: '0', fontWeight: '400' }],
        // Body scale
        'body-large': ['18px', { lineHeight: '1.4', fontWeight: '400' }],
        'body': ['16px', { lineHeight: '1.5', fontWeight: '400' }],
        'body-small': ['14px', { lineHeight: '1.4', fontWeight: '400' }],
        'caption': ['14px', { lineHeight: '1.4', fontWeight: '400' }],
        'micro': ['12px', { lineHeight: '1.4', fontWeight: '400' }],
        // Button
        'btn': ['14px', { lineHeight: '1.71', fontWeight: '500' }],
        // Mono label
        'mono-label': ['14px', { lineHeight: '1.4', letterSpacing: '0.02em', fontWeight: '400' }],
      },
      maxWidth: {
        container: '1440px',
        narrow: '1200px',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'stagger-1': 'fadeIn 0.4s ease-out 0.1s both',
        'stagger-2': 'fadeIn 0.4s ease-out 0.2s both',
        'stagger-3': 'fadeIn 0.4s ease-out 0.3s both',
        'stagger-4': 'fadeIn 0.4s ease-out 0.4s both',
        'stagger-5': 'fadeIn 0.4s ease-out 0.5s both',
        'scale-in': 'scaleIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
