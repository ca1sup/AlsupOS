import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  publicDir: 'public',
  server: {
    // 1. Frontend runs on HTTPS (Required for Mobile Microphone)
    https: {
      key: fs.readFileSync(path.resolve(__dirname, 'localhost+1-key.pem')),
      cert: fs.readFileSync(path.resolve(__dirname, 'localhost+1.pem')),
    },
    host: '0.0.0.0', // Listen on all IPs
    
    // 2. Proxy securely tunnels requests to the HTTP Backend
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', 
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',   
        changeOrigin: true,
        secure: false,
        ws: true
      }
    }
  },
  build: {
    rollupOptions: {
      external: ['fsevents']
    }
  }
})