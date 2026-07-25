<template>
  <div class="space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
          <svg class="w-8 h-8 text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          文档库管理
        </h2>
        <p class="mt-2 text-zinc-400 text-lg">上传并管理您的知识库文档，支持 PDF, Word, Markdown, TXT 格式</p>
      </div>
    </div>

    <!-- Upload Card -->
    <div class="relative group">
      <div class="absolute -inset-0.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-2xl opacity-20 group-hover:opacity-40 transition duration-500 blur"></div>
      <div class="relative bg-zinc-900/80 border border-white/10 rounded-xl p-8 transition-all duration-300 backdrop-blur-md">
        <DocUpload @upload-success="fetchDocList" />
      </div>
    </div>

    <!-- List -->
    <div class="bg-zinc-900/50 border border-white/5 rounded-xl overflow-hidden backdrop-blur-sm shadow-xl">
      <div class="px-6 py-4 border-b border-white/5 bg-white/5 flex items-center justify-between">
        <h3 class="text-lg font-medium text-white flex items-center gap-2">
          <span class="w-1.5 h-4 bg-violet-500 rounded-full"></span>
          已上传文档
        </h3>
        <div class="flex items-center gap-4">
          <!-- Search Input -->
          <div class="relative">
            <input 
              v-model="searchKeyword"
              @keyup.enter="handleSearch"
              type="text" 
              placeholder="搜索文档..." 
              class="w-64 bg-zinc-800/50 border border-white/10 rounded-lg pl-9 pr-4 py-1.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/50 transition-all"
            />
            <svg class="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <span class="text-xs px-2 py-1 bg-zinc-800 rounded border border-white/5 text-zinc-400">Total: {{ totalDocs }}</span>
        </div>
      </div>
      
      <!-- Empty State -->
      <div v-if="docList.length === 0" class="p-12 text-center text-zinc-500 flex flex-col items-center justify-center min-h-[200px]">
        <div class="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-zinc-800/50 mb-6 ring-1 ring-white/5">
           <svg class="w-10 h-10 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
           </svg>
        </div>
        <p class="text-lg font-medium text-zinc-400">暂无文档</p>
        <p class="text-sm mt-1">请上传文档或尝试其他关键词</p>
      </div>

      <!-- Data List -->
      <div v-else class="divide-y divide-white/5">
        <div v-for="doc in docList" :key="doc.id" class="p-4 flex items-center justify-between hover:bg-white/5 transition-colors duration-200">
          <div class="flex items-center gap-4">
            <!-- Icon based on file type -->
            <div class="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-xs shadow-inner"
                 :class="getFileIconClass(doc.name)">
               {{ getFileExtension(doc.name) }}
            </div>
            <div>
              <h4 class="text-white font-medium truncate max-w-[300px]" :title="doc.name">{{ doc.name }}</h4>
              <div class="flex items-center gap-3 text-xs text-zinc-500 mt-1">
                <span>{{ doc.upload_time }}</span>
                <span v-if="doc.size">{{ formatFileSize(doc.size) }}</span>
                <div class="flex items-center gap-2">
                  <span 
                    class="px-2 py-0.5 rounded text-xs border transition-colors duration-200 flex items-center gap-1"
                    :class="doc.status === '已索引' 
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                      : 'bg-zinc-800 text-zinc-400 border-white/10'"
                  >
                    <span class="w-1.5 h-1.5 rounded-full" :class="doc.status === '已索引' ? 'bg-emerald-500' : 'bg-zinc-500'"></span>
                    {{ doc.status }}
                  </span>
                  <button 
                    v-if="doc.status !== '已索引'"
                    @click="handleReindex(doc)"
                    class="p-1 hover:bg-violet-500/20 text-violet-400 rounded transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    :disabled="reindexing[doc.id]"
                    title="重新索引"
                  >
                    <svg v-if="reindexing[doc.id]" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
             <button 
               @click="handlePreview(doc)"
               class="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-lg transition-all" 
               title="查看详情"
             >
               <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
               </svg>
             </button>
             <button 
               @click="handleDelete(doc)"
               class="p-2 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all" 
               title="删除"
             >
               <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
               </svg>
             </button>
          </div>
        </div>
      </div>
      
      <!-- Pagination -->
      <div v-if="totalDocs > 0" class="px-6 py-4 border-t border-white/5 bg-white/5 flex items-center justify-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="totalDocs"
          layout="prev, pager, next"
          background
          @current-change="handlePageChange"
          class="custom-pagination"
        />
      </div>
    </div>

    <!-- Preview Dialog -->
    <el-dialog
      v-model="previewVisible"
      :title="currentDocName"
      width="70%"
      class="preview-dialog"
      :close-on-click-modal="false"
      top="5vh"
    >
      <div v-loading="previewLoading" class="min-h-[400px] max-h-[80vh] overflow-y-auto bg-zinc-50 rounded">
        <!-- DOCX Viewer -->
        <div v-if="currentDocType === 'docx'" class="h-[70vh]">
          <vue-office-docx 
            :src="previewUrl"
            style="height: 100%"
            @rendered="previewLoading = false"
            @error="previewLoading = false"
          />
        </div>

        <!-- PDF Viewer -->
        <div v-if="currentDocType === 'pdf'" class="h-[70vh]">
          <vue-office-pdf 
            :src="previewUrl"
            style="height: 100%"
            @rendered="previewLoading = false"
            @error="previewLoading = false"
          />
        </div>

        <!-- Text/Markdown Viewer -->
        <div v-else-if="!['docx', 'pdf'].includes(currentDocType)" class="p-4 text-zinc-700 whitespace-pre-wrap leading-relaxed">
          {{ previewContent }}
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import DocUpload from '@/components/DocUpload.vue'
import { getDocList, reindexDoc, getDocContent, deleteDoc, type DocItem } from '@/api/doc'
import { ElMessage, ElMessageBox } from 'element-plus'

// VueOffice components
import VueOfficeDocx from '@vue-office/docx'
import VueOfficePdf from '@vue-office/pdf'
import '@vue-office/docx/lib/index.css'

const docList = ref<DocItem[]>([])
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const totalDocs = ref(0)
const loading = ref(false)
const reindexing = ref<Record<string, boolean>>({})

// Preview related
const previewVisible = ref(false)
const previewContent = ref('')
const previewLoading = ref(false)
const currentDocName = ref('')
const currentDocType = ref('')
const previewUrl = ref('')

const fetchDocList = async () => {
  loading.value = true
  try {
    const res = await getDocList({
      page: currentPage.value,
      size: pageSize.value,
      keyword: searchKeyword.value
    })
    
    // Handle new response format
    if (res && Array.isArray(res.items)) {
      docList.value = res.items
      totalDocs.value = res.total
      // Update pagination if needed
      if (res.page) currentPage.value = res.page
      if (res.size) pageSize.value = res.size
    } 
    // Fallback for older format or direct array
    else if (Array.isArray(res)) {
      docList.value = res
      totalDocs.value = res.length
    }
  } catch (error) {
    console.error('Failed to fetch doc list:', error)
    // ElMessage.error('获取文档列表失败')
  } finally {
    loading.value = false
  }
}

const handleReindex = async (doc: DocItem) => {
  if (reindexing.value[doc.id]) return
  
  reindexing.value[doc.id] = true
  try {
    await reindexDoc(doc.id)
    ElMessage.success('重新索引成功')
    fetchDocList()
  } catch (error) {
    console.error('Reindex failed:', error)
    ElMessage.error('重新索引失败')
  } finally {
    reindexing.value[doc.id] = false
  }
}

const handlePreview = async (doc: DocItem) => {
  currentDocName.value = doc.name
  currentDocType.value = getFileExtension(doc.name).toLowerCase()
  previewVisible.value = true
  previewLoading.value = true
  previewContent.value = ''
  previewUrl.value = ''
  
  try {
    // For DOCX and PDF, we use the file stream endpoint
    if (['docx', 'pdf'].includes(currentDocType.value)) {
      // Direct URL to the file
      previewUrl.value = `/api/docs/file/${doc.id}`
      previewLoading.value = false // Components handle their own loading or are fast enough
    } else {
      // For Markdown/Text, we use the content endpoint
      const res = await getDocContent(doc.id)
      if (res && res.content) {
        previewContent.value = res.content
      } else {
        previewContent.value = '暂无内容或无法解析'
      }
      previewLoading.value = false
    }
  } catch (error) {
    console.error('Preview failed:', error)
    previewContent.value = '加载失败，请稍后重试'
    previewLoading.value = false
  }
}

const handleDelete = async (doc: DocItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${doc.name}" 吗？删除后将无法恢复，并会从知识库中移除。`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    loading.value = true
    await deleteDoc(doc.id)
    ElMessage.success('删除成功')
    
    // Refresh list, go back to page 1 if current page becomes empty
    if (docList.value.length === 1 && currentPage.value > 1) {
      currentPage.value--
    }
    fetchDocList()
    
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete failed:', error)
      ElMessage.error('删除失败')
    }
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchDocList()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchDocList()
}

const getFileExtension = (filename: string) => {
  return filename.split('.').pop()?.toUpperCase() || 'FILE'
}

const getFileIconClass = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'pdf': return 'bg-red-500/20 text-red-500 border border-red-500/20'
    case 'doc':
    case 'docx': return 'bg-blue-500/20 text-blue-500 border border-blue-500/20'
    case 'md':
    case 'markdown': return 'bg-white/10 text-white border border-white/20'
    case 'txt': return 'bg-zinc-700/50 text-zinc-400 border border-zinc-600/30'
    default: return 'bg-violet-500/20 text-violet-500 border border-violet-500/20'
  }
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

onMounted(() => {
  fetchDocList()
})
</script>
