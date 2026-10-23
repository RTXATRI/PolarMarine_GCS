<template>
  <div class="app-shell">
    <header class="app-top"><TopBar /></header>
    <aside class="app-side"><SideNavigation /></aside>
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <aside class="app-right"><DeviceInspector /></aside>
    <footer class="app-bottom"><EventTicker /></footer>
  </div>
</template>

<script setup lang="ts">
import DeviceInspector from '@/widgets/layout/DeviceInspector.vue'
import EventTicker from '@/widgets/layout/EventTicker.vue'
import SideNavigation from '@/widgets/layout/SideNavigation.vue'
import TopBar from '@/widgets/layout/TopBar.vue'
</script>

<style scoped>
.app-shell {
  display: grid;
  grid-template:
    'top top top' 48px
    'side main right' minmax(0, 1fr)
    'bottom bottom bottom' 168px / 200px minmax(0, 1fr) 320px;
  width: 100vw;
  min-width: 1180px;
  height: 100vh;
  color: var(--text-1);
  background: var(--bg-page);
}

.app-top {
  z-index: 10;
  grid-area: top;
  border-bottom: 1px solid var(--border);
  background: var(--bg-app);
}

.app-side {
  grid-area: side;
  min-height: 0;
  overflow-y: auto;
  border-right: 1px solid var(--border);
  background: var(--bg-app);
}

.app-main {
  grid-area: main;
  min-width: 0;
  min-height: 0;
  padding: 12px;
  overflow: auto;
  background: var(--bg-page);
}

.app-right {
  grid-area: right;
  min-height: 0;
  overflow: hidden;
  border-left: 1px solid var(--border);
  background: var(--bg-app);
}

.app-bottom {
  grid-area: bottom;
  min-width: 0;
  overflow: hidden;
  border-top: 1px solid var(--border);
  background: var(--bg-app);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
