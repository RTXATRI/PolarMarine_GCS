<template>
  <div class="app-layout">
    <header class="app-top">
      <TopStatusBar />
    </header>
    <aside class="app-side">
      <SideNav />
    </aside>
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <aside class="app-right">
      <RightStatusPanel />
    </aside>
    <footer class="app-bottom">
      <BottomLogPanel />
    </footer>
  </div>
</template>

<script setup lang="ts">
import TopStatusBar from './TopStatusBar.vue'
import SideNav from './SideNav.vue'
import RightStatusPanel from './RightStatusPanel.vue'
import BottomLogPanel from './BottomLogPanel.vue'
</script>

<style scoped>
.app-layout {
  display: grid;
  grid-template-columns: 200px 1fr 320px;
  grid-template-rows: 48px 1fr 168px;
  grid-template-areas:
    'top top top'
    'side main right'
    'bottom bottom bottom';
  height: 100vh;
  width: 100vw;
  background: var(--bg-page);
  color: var(--text-1);
}

.app-top {
  grid-area: top;
  border-bottom: 1px solid var(--border);
  background: var(--bg-app);
  z-index: 10;
}
.app-side {
  grid-area: side;
  border-right: 1px solid var(--border);
  background: var(--bg-app);
  overflow-y: auto;
}
.app-main {
  grid-area: main;
  overflow: auto;
  padding: 12px;
  background: var(--bg-page);
}
.app-right {
  grid-area: right;
  border-left: 1px solid var(--border);
  background: var(--bg-app);
  overflow: hidden;
}
.app-bottom {
  grid-area: bottom;
  border-top: 1px solid var(--border);
  background: var(--bg-app);
  overflow: hidden;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
