export interface ChatRequest {
  question: string;
  top_k?: number;
}

export interface ChatSource {
  content: string;
  score: number;
  source: string;
  page: number;
  methods?: string[];          // ["vector"], ["bm25"], or ["vector", "bm25"]
  vector_rank?: number | null;
  bm25_rank?: number | null;
}

export interface ChatStep {
  step:
    | 'init'
    | 'retrieving'
    | 'retrieved'
    | 'reranking'
    | 'generating'
    | 'answer'
    | 'completed'
    | 'error';
  message?: string;
  data?: ChatSource[] | string;
  done?: boolean;
}

// Stream reader helper
export async function streamChat(
  request: ChatRequest, 
  onStep: (step: ChatStep) => void
) {
  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is null');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep the last incomplete line in buffer

      for (const line of lines) {
        if (line.trim()) {
          try {
            const step = JSON.parse(line) as ChatStep;
            onStep(step);
          } catch (e) {
            console.error('Error parsing JSON line:', line, e);
          }
        }
      }
    }
    
    // Process any remaining buffer
    if (buffer.trim()) {
      try {
        const step = JSON.parse(buffer) as ChatStep;
        onStep(step);
      } catch (e) {
        console.error('Error parsing JSON line:', buffer, e);
      }
    }

  } catch (error) {
    console.error('Stream error:', error);
    onStep({
      step: 'error',
      message: error instanceof Error ? error.message : 'Network error'
    });
  }
}
