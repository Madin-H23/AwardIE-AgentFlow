import { ref } from 'vue'

export type Theme = 'light' | 'dark'

const theme = ref<Theme>((localStorage.getItem('theme') as Theme) || 'light')

function apply(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
  // Element Plus 暗色变量挂 html.dark
  document.documentElement.classList.toggle('dark', t === 'dark')
  localStorage.setItem('theme', t)
}
apply(theme.value)

export function useTheme() {
  function toggle() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    apply(theme.value)
  }
  return { theme, toggle }
}
