<script setup lang="ts">
import { useTheme } from './composables/useTheme'

const { theme, toggle } = useTheme()
</script>

<template>
  <router-view />
  <el-button
    class="theme-toggle"
    circle
    :title="theme === 'dark' ? '切亮色' : '切暗色'"
    data-testid="theme-toggle"
    @click="toggle"
  >
    {{ theme === 'dark' ? '☀' : '☾' }}
  </el-button>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
body { background: var(--bg); color: var(--ink); }
.theme-toggle {
  position: fixed; right: 16px; bottom: 16px; z-index: 2000;
}
</style>
