import { defineConfig } from 'vite'

export default defineConfig({
  base: '/essay_search_engine/',  // Match GitHub repo name
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        main: './index.html'
      }
    }
  },
  publicDir: 'public'
})
