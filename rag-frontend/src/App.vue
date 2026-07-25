<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div class="min-h-screen bg-zinc-950 text-zinc-100 selection:bg-violet-500 selection:text-white relative overflow-hidden">
    <!-- Background Decor -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-violet-600/20 rounded-full blur-[120px] -z-10 pointer-events-none opacity-50 mix-blend-screen"></div>
    <div class="absolute bottom-0 right-0 w-[800px] h-[600px] bg-indigo-600/10 rounded-full blur-[100px] -z-10 pointer-events-none opacity-30"></div>

    <!-- Navbar with Glassmorphism -->
    <nav class="fixed w-full z-50 top-0 start-0 border-b border-white/5 bg-zinc-950/80 backdrop-blur-xl supports-[backdrop-filter]:bg-zinc-950/60">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center gap-8">
            <div class="flex-shrink-0 flex items-center gap-3 group cursor-pointer">
              <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20 group-hover:shadow-violet-500/40 transition-all duration-300 group-hover:scale-105">
                <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
              </div>
              <h1 class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-zinc-200 to-zinc-400 tracking-tight group-hover:to-white transition-all duration-300">智能文档检索</h1>
            </div>
            <div class="hidden sm:block">
              <div class="flex items-center p-1 bg-white/5 rounded-lg border border-white/5">
                <router-link to="/" class="px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 flex items-center gap-2" :class="[route.path === '/' ? 'bg-zinc-800 text-white shadow-sm ring-1 ring-white/10' : 'text-zinc-400 hover:text-white hover:bg-white/5']">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  文档管理
                </router-link>
                <router-link to="/query" class="px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 flex items-center gap-2" :class="[route.path === '/query' ? 'bg-zinc-800 text-white shadow-sm ring-1 ring-white/10' : 'text-zinc-400 hover:text-white hover:bg-white/5']">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                  智能问答
                </router-link>
              </div>
            </div>
          </div>
          <!-- Right side status -->
          <div class="flex items-center gap-4">
             <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                <div class="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                <span class="text-[10px] font-bold tracking-wider text-emerald-400 font-mono uppercase">System Online</span>
             </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-24 px-4 sm:px-6 lg:px-8">
      <RouterView v-slot="{ Component }">
        <transition name="fade" mode="out-in">
           <component :is="Component" />
        </transition>
      </RouterView>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(5px);
}
</style>
