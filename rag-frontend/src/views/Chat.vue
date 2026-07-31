<template>
  <div class="h-[calc(100vh-64px)] flex flex-col">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between px-4 pt-4">
      <div>
        <h1 class="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
           <svg class="w-8 h-8 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
             <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
           </svg>
           智能问答
        </h1>
        <p class="mt-2 text-zinc-400 text-lg">基于已上传文档的 RAG 问答系统</p>
      </div>
      <div class="flex items-center gap-3">
        <div v-if="systemStatus.is_model_ready" class="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-xs text-emerald-400 flex items-center gap-2">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          AI 模型准备就绪
        </div>
        <div v-else class="px-3 py-1 bg-red-500/10 border border-red-500/20 rounded-full text-xs text-red-400 flex items-center gap-2">
          <span class="w-1.5 h-1.5 rounded-full bg-red-400"></span>
          未配置 AI 模型
        </div>
        <button
          @click="chatStore.clearMessages"
          :disabled="loading || messages.length === 0"
          class="px-3 py-1.5 text-xs rounded-lg border border-white/10 text-zinc-300 hover:text-white hover:border-violet-500/50 hover:bg-violet-500/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          新对话
        </button>
      </div>
    </div>

    <!-- Main Chat Area -->
    <div class="flex-1 flex flex-col bg-zinc-900/50 backdrop-blur-sm border border-white/5 rounded-xl overflow-hidden shadow-xl mx-4 mb-4 relative">
      <!-- Background Decor -->
      <div class="absolute top-0 right-0 w-96 h-96 bg-indigo-500/5 rounded-full blur-[100px] -z-0 pointer-events-none"></div>
      <div class="absolute bottom-0 left-0 w-64 h-64 bg-violet-500/5 rounded-full blur-[80px] -z-0 pointer-events-none"></div>

      <!-- Messages List -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6 relative z-10 scroll-smooth" ref="messagesRef">
        
        <!-- Empty State -->
        <div v-if="messages.length === 0" class="h-full flex flex-col items-center justify-center text-zinc-500">
             <div class="w-24 h-24 bg-zinc-800/50 rounded-2xl flex items-center justify-center mb-6 ring-1 ring-white/5 shadow-lg">
               <svg class="w-10 h-10 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
               </svg>
             </div>
             <p class="text-xl font-medium text-zinc-300">有什么可以帮您的吗？</p>
             <p class="text-sm mt-2 text-zinc-500">基于您的文档库，为您提供精准的问答服务</p>
        </div>

        <div v-for="(msg, index) in messages" :key="index" class="flex flex-col gap-2">
          
          <!-- User Message -->
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="bg-indigo-600 text-white px-5 py-3 rounded-2xl rounded-tr-sm max-w-[80%] shadow-lg shadow-indigo-500/10">
              {{ msg.content }}
            </div>
          </div>

          <!-- Assistant Message -->
          <div v-else class="flex flex-col gap-2 max-w-[90%]">
            <div class="flex gap-4">
              <div class="w-10 h-10 rounded-xl bg-violet-600/90 flex items-center justify-center shrink-0 shadow-lg border border-violet-500/20">
                <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div class="flex-1">
                <!-- Process Steps (Thinking Process) -->
                <div v-if="msg.process && msg.process.length > 0" class="mb-4 bg-zinc-900/80 rounded-xl p-4 border border-white/5 shadow-sm">
                   <button @click="msg.showProcess = !msg.showProcess" 
                           class="w-full flex items-center justify-between text-xs font-medium text-zinc-500 hover:text-zinc-300 transition-colors mb-2">
                      <span class="uppercase tracking-wider flex items-center gap-2">
                        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        思考过程
                      </span>
                      <svg class="w-4 h-4 transform transition-transform duration-200" :class="{'rotate-180': msg.showProcess}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                   </button>
                   
                   <div v-show="msg.showProcess" class="space-y-3 mt-2">
                      <div v-for="(step, sIdx) in msg.process" :key="sIdx" class="flex items-start gap-3 text-sm">
                        <div v-if="step.status === 'loading'" class="w-4 h-4 mt-0.5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent"></div>
                        <div v-else-if="step.status === 'done'" class="w-4 h-4 mt-0.5 text-emerald-500 flex items-center justify-center">
                           <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                             <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                           </svg>
                        </div>
                        <div v-else-if="step.status === 'error'" class="w-4 h-4 mt-0.5 text-red-500">✗</div>
                        
                        <div class="flex-1">
                          <span :class="{
                            'text-zinc-300': step.status === 'loading',
                            'text-zinc-500': step.status === 'done',
                            'text-red-400': step.status === 'error'
                          }">{{ step.message }}</span>
                          
                          <!-- Sources Display -->
                          <div v-if="step.type === 'retrieved' && step.data && step.data.length > 0" class="mt-2 grid gap-2">
                             <div v-for="(source, srcIdx) in step.data" :key="srcIdx" class="bg-black/20 p-3 rounded-lg text-xs border border-white/5 hover:border-white/10 transition-colors group">
                                <div class="flex justify-between items-start text-zinc-400 mb-1 group-hover:text-zinc-300 transition-colors gap-2">
                                  <span class="font-medium text-violet-400 flex items-center gap-1 min-w-0">
                                    <svg class="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    <span class="truncate">{{ source.source }}</span>
                                  </span>
                                  <span class="flex items-center gap-1 shrink-0">
                                    <span
                                      v-for="m in source.methods || []"
                                      :key="m"
                                      class="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border"
                                      :class="m === 'vector'
                                        ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20'
                                        : 'bg-amber-500/10 text-amber-300 border-amber-500/20'"
                                      :title="m === 'vector' ? '向量检索命中' : 'BM25 关键词检索命中'"
                                    >{{ m === 'vector' ? '向量' : 'BM25' }}</span>
                                    <span class="bg-white/5 px-1.5 rounded text-[10px]">P{{ source.page }} · {{ (source.score * 100).toFixed(1) }}%</span>
                                  </span>
                                </div>
                                <div class="text-zinc-500 line-clamp-2 leading-relaxed font-serif italic">{{ source.content }}</div>
                             </div>
                          </div>
                        </div>
                      </div>
                   </div>
                </div>

                <!-- Final Answer -->
                <div v-if="msg.content" class="bg-zinc-800/50 border border-white/5 text-zinc-100 px-6 py-5 rounded-2xl rounded-tl-sm prose prose-invert max-w-none shadow-sm backdrop-blur-sm">
                  <div class="whitespace-pre-wrap leading-relaxed">{{ msg.content }}</div>
                </div>
                <div v-else-if="msg.loading && !msg.process?.some(p => p.status === 'error')" class="text-zinc-500 text-sm animate-pulse flex items-center gap-2 px-2">
                  <span class="w-2 h-2 bg-zinc-500 rounded-full"></span>
                  正在生成回答...
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- Input Area -->
      <div class="p-4 bg-zinc-900/80 border-t border-white/5 z-20 backdrop-blur-md">
        <div class="flex gap-4 max-w-5xl mx-auto">
          <textarea 
            v-model="inputQuestion"
            @keydown.enter.exact.prevent="sendMessage"
            placeholder="请输入您的问题..." 
            class="flex-1 bg-zinc-800/50 border-white/10 text-zinc-100 rounded-xl focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/50 resize-none h-24 p-4 shadow-inner transition-all placeholder-zinc-600 focus:bg-zinc-800"
            :disabled="loading"
          ></textarea>
          <div class="flex flex-col justify-end">
            <button 
              @click="sendMessage"
              :disabled="loading || !inputQuestion.trim()"
              class="bg-violet-600 hover:bg-violet-700 text-white px-8 py-2 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed h-12 flex items-center justify-center font-medium shadow-lg hover:shadow-violet-500/20 active:scale-95"
            >
              <svg v-if="!loading" class="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              <span v-if="loading">发送中...</span>
              <span v-else>发送</span>
            </button>
          </div>
        </div>
        <div class="mt-2 text-xs text-zinc-600 text-right max-w-5xl mx-auto flex items-center justify-end gap-1">
          <kbd class="px-1.5 py-0.5 bg-zinc-800 rounded border border-zinc-700 font-mono text-[10px]">Enter</kbd> 发送
          <span class="mx-1">·</span>
          <kbd class="px-1.5 py-0.5 bg-zinc-800 rounded border border-zinc-700 font-mono text-[10px]">Shift + Enter</kbd> 换行
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { storeToRefs } from 'pinia'
import axios from 'axios'

const chatStore = useChatStore()
const { messages, loading } = storeToRefs(chatStore)
const inputQuestion = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const systemStatus = ref({ is_model_ready: false })

const fetchSystemStatus = async () => {
  try {
    const { data } = await axios.get('/api/status')
    systemStatus.value = data
  } catch (e) {
    console.error('Failed to fetch system status', e)
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// Watch for message updates to auto-scroll
watch(
  messages, 
  () => {
    scrollToBottom()
  },
  { deep: true }
)

// Scroll to bottom on mount (in case returning to existing chat)
onMounted(() => {
  scrollToBottom()
  fetchSystemStatus()
})

const sendMessage = async () => {
  const question = inputQuestion.value.trim()
  if (!question || loading.value) return
  
  inputQuestion.value = ''
  await chatStore.sendMessage(question)
}
</script>
