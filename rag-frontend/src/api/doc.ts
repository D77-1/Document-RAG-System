import request from '@/utils/request'

export interface UploadResponse {
  status: string
  doc_id: string
  length: number
  message?: string
}

export function uploadDocument(formData: FormData) {
  return request<any, UploadResponse>({
    url: '/upload',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export interface DocItem {
  id: string
  name: string
  upload_time: string
  status: string
  size?: number
}

export interface DocListResponse {
  total: number
  items: DocItem[]
  page: number
  size: number
}

export function getDocList(params?: { page?: number; size?: number; keyword?: string }) {
  return request<any, DocListResponse>({
    url: '/docs/list',
    method: 'get',
    params
  })
}

export const reindexDoc = async (docId: string) => {
  return request.post(`/docs/reindex/${docId}`)
}

export interface DocContentResponse {
  content: string
}

export const getDocContent = async (docId: string) => {
  return request<any, DocContentResponse>({
    url: `/docs/content/${docId}`,
    method: 'get'
  })
}

export const deleteDoc = async (docId: string) => {
  return request<any, any>({
    url: `/docs/${docId}`,
    method: 'delete'
  })
}
