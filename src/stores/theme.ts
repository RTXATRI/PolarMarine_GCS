import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeName = 'dark' | 'light'

const STORAGE_KEY = 'polarmarine-gcs-theme'

function readInitial(): ThemeName {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark') return v
  } catch (_e) {
    // ignore
  }
  return 'dark'
}

function applyToDom(theme: ThemeName) {
  const root = document.documentElement
  root.dataset.theme = theme
  if (theme === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeName>(readInitial())

  function setTheme(t: ThemeName) {
    theme.value = t
  }

  function toggle() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  // 立即同步到 DOM,后续变化也跟随
  applyToDom(theme.value)
  watch(theme, t => {
    applyToDom(t)
    try {
      localStorage.setItem(STORAGE_KEY, t)
    } catch (_e) {
      // ignore
    }
  })

  return { theme, setTheme, toggle }
})
