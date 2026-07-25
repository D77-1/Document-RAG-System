import { createRouter, createWebHistory } from 'vue-router'
import DocManage from '../views/DocManage.vue'
import Chat from '../views/Chat.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'doc-manage',
      component: DocManage
    },
    {
      path: '/query',
      name: 'chat',
      component: Chat
    }
  ]
})

export default router
