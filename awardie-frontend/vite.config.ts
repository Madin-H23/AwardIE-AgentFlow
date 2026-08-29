import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// Element Plus 按需引入:AutoImport(api)+ Components(组件)双 resolver
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
  ],
  server: {
    port: 5199,
    proxy: {
      // dev 同源代理:会话 cookie 直达 Java(生产由 Nginx 路径分流承担)
      '/api/v2': { target: 'http://127.0.0.1:18080', changeOrigin: true },
    },
  },
})
