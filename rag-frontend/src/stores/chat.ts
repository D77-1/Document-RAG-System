import { defineStore } from 'pinia'
import { ref } from 'vue'
import { streamChat, type ChatStep, type ChatSource } from '@/api/chat'

export interface ProcessStep {
  message: string
  status: 'loading' | 'done' | 'error'
  type?: string
  data?: ChatSource[]
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  process?: ProcessStep[]
  showProcess?: boolean
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const loading = ref(false)
  const topK = ref(3)

  const finish = (msg: Message) => {
    loading.value = false
    msg.loading = false
  }

  const sendMessage = async (question: string) => {
    if (!question || loading.value) return

    messages.value.push({ role: 'user', content: question })

    const assistantMsg = ref<Message>({
      role: 'assistant',
      content: '',
      loading: true,
      process: [],
      showProcess: true,
    })
    messages.value.push(assistantMsg.value)
    loading.value = true

    try {
      await streamChat({ question, top_k: topK.value }, (step: ChatStep) => {
        const currentProcess = assistantMsg.value.process || []

        // Auto-mark the previous loading step as done when a new informational
        // step arrives. Answer/completed are terminal and handled separately.
        if (
          currentProcess.length > 0 &&
          !['answer', 'completed', 'error'].includes(step.step)
        ) {
          const lastStep = currentProcess[currentProcess.length - 1]
          if (lastStep && lastStep.status === 'loading') {
            lastStep.status = 'done'
          }
        }

        switch (step.step) {
          case 'init':
          case 'retrieving':
          case 'reranking':
          case 'generating':
            currentProcess.push({
              message: step.message || 'Processing...',
              status: 'loading',
              type: step.step,
            })
            break

          case 'retrieved': {
            const retrievingStep = [...currentProcess]
              .reverse()
              .find((p) => p.type === 'retrieving')
            if (retrievingStep) {
              retrievingStep.status = 'done'
              retrievingStep.message = step.message || '检索完成'
              retrievingStep.data = step.data as ChatSource[]
              retrievingStep.type = 'retrieved'
            }
            break
          }

          case 'answer': {
            const generatingStep = currentProcess.find((p) => p.type === 'generating')
            if (generatingStep) generatingStep.status = 'done'
            if (typeof step.data === 'string') {
              assistantMsg.value.content = step.data
            }
            assistantMsg.value.showProcess = false
            // Empty-KB path: backend sends answer with done=true and no following
            // "completed" step. Make sure the spinner stops here too.
            if (step.done) finish(assistantMsg.value)
            break
          }

          case 'completed':
            finish(assistantMsg.value)
            break

          case 'error':
            currentProcess.push({
              message: step.message || 'Error occurred',
              status: 'error',
              type: 'error',
            })
            finish(assistantMsg.value)
            break
        }
      })
    } catch (e) {
      console.error(e)
      if (loading.value) {
        const currentProcess = assistantMsg.value.process || []
        currentProcess.push({
          message: '网络连接异常，请检查后端服务',
          status: 'error',
          type: 'error',
        })
        finish(assistantMsg.value)
      }
    }
  }

  const clearMessages = () => {
    messages.value = []
    loading.value = false
  }

  return {
    messages,
    loading,
    topK,
    sendMessage,
    clearMessages,
  }
})
