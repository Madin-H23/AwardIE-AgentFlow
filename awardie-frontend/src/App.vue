<script setup lang="ts">
import { useTheme } from './composables/useTheme'

const { theme, toggle } = useTheme()
</script>

<template>
  <router-view />
  <button
    class="theme-toggle"
    :title="theme === 'dark' ? '切亮色' : '切暗色'"
    @click="toggle"
  >
    {{ theme === 'dark' ? '☀' : '☾' }}
  </button>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
body { background: var(--bg); color: var(--ink); }
.theme-toggle {
  position: fixed; right: 16px; bottom: 16px; z-index: 2000;
  width: 36px; height: 36px; border-radius: 50%;
  border: 1px solid var(--line); background: var(--panel);
  color: var(--ink); cursor: pointer; font-size: 16px;
}
</style>
