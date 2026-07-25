<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadRawFile, type UploadRequestOptions } from 'element-plus'
import { uploadDocument } from '@/api/doc'

const emit = defineEmits<{
  'upload-success': []
}>()

const uploadRef = ref()
const uploadingCount = ref(0)

const beforeUpload = (rawFile: UploadRawFile) => {
  const allowedTypes = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
    'text/markdown',
    'text/plain'
  ]
  // Markdown MIME type can vary, check extension as fallback
  const isMarkdown = rawFile.name.endsWith('.md')

  if (!allowedTypes.includes(rawFile.type) && !isMarkdown) {
    ElMessage.error('仅支持 PDF, Word (.docx), Markdown (.md), TXT 格式文件!')
    return false
  } else if (rawFile.size / 1024 / 1024 > 50) { // 50MB limit
    ElMessage.error('文件大小不能超过 50MB!')
    return false
  }
  return true
}

const customUpload = async (options: UploadRequestOptions) => {
  const { file, onProgress, onSuccess, onError } = options

  const formData = new FormData()
  formData.append('file', file)
  formData.append('filename', file.name)

  uploadingCount.value++

  try {
    onProgress({ percent: 50 } as any)

    const response = await uploadDocument(formData)

    onProgress({ percent: 100 } as any)
    onSuccess(response)
    ElMessage.success(`文档 "${file.name}" 上传成功`)
    emit('upload-success')
  } catch (error: any) {
    onError(error)
    ElMessage.error(`上传失败: ${error.message || '未知错误'}`)
  } finally {
    uploadingCount.value--
    if (uploadingCount.value === 0) {
      uploadRef.value?.clearFiles()
    }
  }
}
</script>

<template>
  <div class="w-full">
    <el-upload
      ref="uploadRef"
      class="upload-demo"
      drag
      multiple
      action="#"
      :http-request="customUpload"
      :before-upload="beforeUpload"
      :show-file-list="true"
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">
        拖拽文件到此处或 <em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip text-zinc-400">
          支持 PDF, Word, Markdown, TXT 格式，支持多文件上传，单个文件不超过 50MB
        </div>
      </template>
    </el-upload>
  </div>
</template>

<style scoped>
:deep(.el-upload-dragger) {
  background-color: rgba(24, 24, 27, 0.5); /* zinc-950/50 */
  border-color: rgba(63, 63, 70, 0.5); /* zinc-700/50 */
  transition: all 0.3s ease;
}

:deep(.el-upload-dragger:hover) {
  border-color: #8b5cf6; /* violet-500 */
  background-color: rgba(139, 92, 246, 0.05);
}

:deep(.el-upload__text) {
  color: #a1a1aa; /* zinc-400 */
}

:deep(.el-upload__text em) {
  color: #8b5cf6; /* violet-500 */
}

:deep(.el-icon--upload) {
  color: #71717a; /* zinc-500 */
  margin-bottom: 16px;
}

/* File list styling */
:deep(.el-upload-list__item) {
  background-color: rgba(39, 39, 42, 0.5);
  border: 1px solid rgba(63, 63, 70, 0.3);
  color: #e4e4e7;
}

:deep(.el-upload-list__item:hover) {
  background-color: rgba(39, 39, 42, 0.8);
}

:deep(.el-upload-list__item-name) {
  color: #e4e4e7;
}

:deep(.el-upload-list__item .el-icon--close) {
  color: #a1a1aa;
}
</style>
