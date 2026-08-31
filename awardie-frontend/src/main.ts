import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/theme-chalk/dark/css-vars.css'
// 主题副作用(apply 在模块顶层):App 不再持有主题钮(#25 移入顶栏),登录页也需生效
import './composables/useTheme'
import App from './App.vue'
import router from './router'
import './styles/tokens.css'

// Element Plus 组件与 API 由 unplugin 编译期按需注入(vite.config.ts 双 resolver)
createApp(App).use(createPinia()).use(router).mount('#app')
