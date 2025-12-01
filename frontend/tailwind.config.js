/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // --- NEW DESIGN SYSTEM: LIQUID CHARCOAL (Low Fatigue) ---
        void: '#0a0a0a',           // Was #000000 -> Now Deep Charcoal
        surface: '#141414',        // Was #0f0f0f -> Now slightly lighter
        elevated: '#1f1f1f',       // Was #1a1a1a -> Better separation without harsh borders
        
        // Semantic Borders (Softer)
        border: {
          subtle: '#27272a',       // Zinc-800
          active: '#3f3f46',       // Zinc-700
          invisible: 'rgba(255,255,255,0.03)',
        },

        // Typography (Reduced Contrast)
        txt: {
          primary: '#e5e5e5',      // Was #ffffff -> Now 90% White (prevents eye strain)
          body: '#a1a1aa',         // Was #b0b0b0 -> Zinc-400 (smoother read)
          secondary: '#71717a',    // Zinc-500
          tertiary: '#52525b',     // Zinc-600
        },

        // The "Electric" Accent (Slightly Desaturated)
        accent: {
          DEFAULT: '#ff9e80',           // Softer Coral (Was #ff8a65)
          bright: '#ffb088',            
          glow: 'rgba(255,158,128,0.15)', // Lower opacity glow
          dim: 'rgba(255,158,128,0.05)',
        },

        // --- LEGACY PALETTE (Preserved) ---
        earth: {
          950: '#0c0a09', 900: '#171514', 850: '#211F1E', 800: '#2E2B2A', 700: '#45413E',
          200: '#E5E2DC', 400: '#A39F98', 500: '#78716c',
        },
        flair: {
          sage: '#A6B18C', clay: '#D4A373', rose: '#C89F9C', lavender: '#9D9EB8', mustard: '#C9B072',
        }
      },
      fontFamily: {
        sans: ['"Inter"', '"SF Pro Display"', 'system-ui', 'sans-serif'],
        mono: ['"Courier Prime"', 'monospace'],
      },
      borderRadius: {
        '4xl': '2rem',
        '5xl': '2.5rem',
      },
      boxShadow: {
        'glow': '0 0 24px rgba(255,158,128,0.1)',
        'float': '0 4px 20px rgba(0,0,0,0.2), 0 0 0 1px rgba(255,255,255,0.03)',
      },
      animation: {
        'slide-up': 'slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'fade-in': 'fade-in 0.3s ease-out forwards',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'input-pulse': 'input-pulse 2s ease-in-out infinite',
        'orb': 'orb-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'input-pulse': {
          '0%, 100%': { boxShadow: '0 0 0 1px rgba(255,158,128,0.08), 0 0 12px rgba(255,158,128,0.05)' },
          '50%': { boxShadow: '0 0 0 2px rgba(255,158,128,0.12), 0 0 20px rgba(255,158,128,0.1)' },
        },
        'orb-pulse': {
          '0%, 100%': { opacity: '0.2', transform: 'scale(0.95)' },
          '50%': { opacity: '0.6', transform: 'scale(1.02)' },
        }
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      }
    },
  },
  plugins: [],
}