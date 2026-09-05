import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3002,
    proxy: {
      '/agent': {
        target: 'http://localhost:8081',
        changeOrigin: true,
      },
    },
  },
})
