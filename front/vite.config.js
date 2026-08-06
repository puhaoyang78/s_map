import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue({
      devtools: false
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: false,
        secure: false,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('mapbox-gl')) return 'mapbox-vendor'
          if (id.includes('three')) return 'three-vendor'
          if (id.includes('satellite.js')) return 'satellite-vendor'
          if (id.includes('echarts')) return 'chart-vendor'
          // Keep all Ant Design Vue and rc-* UI internals in one chunk.
          // Splitting them into ui-core/ui-select/ui-table bundles creates
          // circular runtime imports in production and causes blank screens.
          if (id.includes('ant-design-vue') || id.includes('@ant-design')) return 'ui-vendor'
          if (
            id.includes('rc-table')
            || id.includes('rc-pagination')
            || id.includes('rc-select')
            || id.includes('rc-virtual-list')
          ) return 'ui-vendor'
          if (id.includes('vue') || id.includes('pinia')) return 'vue-vendor'
          return 'vendor'
        }
      }
    }
  },
  define: {
    __VUE_PROD_DEVTOOLS__: false
  }
})
