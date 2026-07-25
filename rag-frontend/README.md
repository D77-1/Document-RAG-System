# 💻 RAG Frontend Application

基于 Vue 3 和 Tailwind CSS 构建的现代化智能文档检索前端应用。

## ✨ 特性

- 🎨 **现代化 UI**：采用深色玻璃拟态设计风格
- 📱 **响应式布局**：适配各种屏幕尺寸
- 🔄 **实时交互**：基于流式响应的打字机效果问答体验
- 📂 **文档管理**：直观的文档上传、列表管理与搜索
- 📄 **在线预览**：PDF / DOCX 浏览器内直接预览（@vue-office）

## 🛠️ 技术栈

- **Framework**: Vue 3 (Composition API)
- **Build Tool**: Vite
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Element Plus
- **State Management**: Pinia
- **Routing**: Vue Router
- **HTTP Client**: Axios（文档管理）+ 原生 fetch（问答 NDJSON 流式读取）

## 🚀 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

应用将启动在 `http://localhost:5173`。Vite 已将 `/api` 代理到 `http://localhost:8000`，请先启动后端服务。

### 3. 构建生产版本

```bash
npm run build
```

## 📂 目录结构

```
rag-frontend/
├── src/
│   ├── api/          # API 接口定义
│   ├── assets/       # 静态资源
│   ├── components/   # 公共组件
│   ├── router/       # 路由配置
│   ├── stores/       # Pinia 状态管理
│   ├── views/        # 页面视图
│   │   ├── Chat.vue      # 智能问答页
│   │   └── DocManage.vue # 文档管理页
│   └── App.vue       # 根组件
└── index.html
```
