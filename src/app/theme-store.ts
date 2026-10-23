import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemeName = 'dark' | 'light'

const STORAGE_KEY = 'polarmarine-gcs-theme'

function readInitialTheme(): ThemeName {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    if (value === 'dark' || value === 'light') return value
  } catch {
    // A locked-down browser may deny local storage. Dark remains the safe default.
  }
  return 'dark'
}

function applyTheme(theme: ThemeName): void {
  document.documentElement.dataset.theme = theme
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeName>(readInitialTheme())

  function setTheme(nextTheme: ThemeName): void {
    theme.value = nextTheme
  }

  function toggle(): void {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  applyTheme(theme.value)
  watch(theme, (nextTheme) => {
    applyTheme(nextTheme)
    try {
      window.localStorage.setItem(STORAGE_KEY, nextTheme)
    } catch {
      // Theme still applies for the current session.
    }
  })

  return { theme, setTheme, toggle }
})
