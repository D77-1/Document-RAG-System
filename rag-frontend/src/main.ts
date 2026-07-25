import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import './style.css'
import App from './App.vue'
import router from './router'
import JsonViewer from 'vue3-json-viewer'
import 'vue3-json-viewer/dist/vue3-json-viewer.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, {
  locale: zhCn,
})
app.use(JsonViewer)

app.mount('#app')
