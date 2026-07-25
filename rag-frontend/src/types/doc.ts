export interface Document {
  id: string;
  name: string;
  uploadTime: string;
  status: 'processing' | 'completed' | 'failed';
  size: number;
}
