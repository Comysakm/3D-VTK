import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  
  plugins: [vue()],

  server: {
    // 确保不拦截静态文件请求
    middlewareMode: false,
    // 增加请求体大小限制 (默认是100MB，但可以显式设置更大)
    maxRequestBodySize: 1000 * 1024 * 1024, // 100MB
  },

  resolve: {
    alias: {
      'vtk.js': 'vtk.js/esm', // ✅ 这样 `vtk.js/Sources/...` 才能解析
    }
  }
})
