import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import router from './router'
import './styles/tokens.css'

// Element Plus 组件与 API 由 unplugin 编译期按需注入(vite.config.ts 双 resolver)
createApp(App).use(createPinia()).use(router).mount('#app')
