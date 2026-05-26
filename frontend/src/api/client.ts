const API_BASE = 'http://localhost:8000/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    const raw = err.detail;
    const detail = typeof raw === 'object' ? (raw as any).message || JSON.stringify(raw) : raw;
    throw new Error(String(detail || `HTTP ${res.status}`));
  }
  return res.json();
}

async function sseRequest(
  url: string,
  body: Record<string, unknown>,
  onEvent: (event: import('../types').AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let eventCount = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    let eventType = '';
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        try {
          const parsed = JSON.parse(line.slice(6));
          parsed._eventType = eventType;
          onEvent(parsed);
          // Yield to event loop every 8 events to prevent main thread blocking
          eventCount++;
          if (eventCount % 8 === 0) {
            await new Promise(r => setTimeout(r, 0));
          }
        } catch { /* skip malformed */ }
        eventType = '';
      }
    }
  }
}

export const api = {
  // Languages
  getLanguages: () => request<import('../types').Language[]>('/languages'),

  getCourses: () => request<import('../types').Course[]>('/courses'),
  getCourse: (id: number) => request<import('../types').Course>(`/courses/${id}`),

  // Topics
  createTopic: (courseId: number, title: string) =>
    request<import('../types').Topic>(`/courses/${courseId}/topics`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  getTopic: (id: number, params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<import('../types').Topic>(`/topics/${id}${qs}`);
  },
  deleteTopic: (id: number) =>
    request<void>(`/topics/${id}`, { method: 'DELETE' }),
  getOutline: (topicId: number) =>
    request<import('../types').TopicOutline>(`/topics/${topicId}/outline`),

  generateOutlineStream: (
    topicId: number,
    topicTitle: string,
    onEvent: (event: import('../types').AgentEvent) => void,
    feedback?: string,
    contentLanguage?: string,
    signal?: AbortSignal,
  ): Promise<void> =>
    sseRequest(
      `${API_BASE}/topics/${topicId}/generate-outline-stream`,
      { topic_title: topicTitle, feedback, content_language: contentLanguage || 'zh' },
      onEvent,
      signal,
    ),

  generateContentStream: (
    topicId: number,
    onEvent: (event: import('../types').AgentEvent) => void,
    contentLanguage?: string,
    signal?: AbortSignal,
  ): Promise<void> =>
    sseRequest(
      `${API_BASE}/topics/${topicId}/generate-content-stream`,
      { content_language: contentLanguage || 'zh' },
      onEvent,
      signal,
    ),

  // Lessons
  getLesson: (id: number) => request<import('../types').Lesson>(`/lessons/${id}`),
  regenerateLesson: (lessonId: number) =>
    request<import('../types').Lesson>(`/lessons/${lessonId}/regenerate`, { method: 'POST' }),
  updateLesson: (lessonId: number, content: string) =>
    request<{ id: number; title: string; content: string }>(`/lessons/${lessonId}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),

  // Outline
  updateOutline: (topicId: number, sections: import('../types').OutlineSection[]) =>
    request<{ sections: import('../types').OutlineSection[] }>(`/topics/${topicId}/outline`, {
      method: 'PUT',
      body: JSON.stringify({ sections }),
    }),

  // Code execution (SSE streaming)
  runCodeStream: (code: string, language: string, onEvent: (event: string, data: any) => void, signal?: AbortSignal): Promise<void> => {
    return new Promise(async (resolve, reject) => {
      try {
        const res = await fetch(`${API_BASE}/code/run/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, language }),
          signal,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const reader = res.body!.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          let eventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              try {
                const parsed = JSON.parse(line.slice(6));
                onEvent(eventType, parsed);
              } catch { /* skip malformed */ }
              eventType = '';
            }
          }
        }
        resolve();
      } catch (err: any) {
        if (err.name === 'AbortError') resolve();
        else reject(err);
      }
    });
  },

  // AI Chat (SSE streaming with agent loop events)
  chat: (
    lessonId: number,
    message: string,
    history: import('../types').ChatMessage[],
    onEvent: (event: import('../types').AgentEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> =>
    sseRequest(
      `${API_BASE}/chat`,
      { lesson_id: lessonId, message, history },
      onEvent,
      signal,
    ),

  // Environment
  getEnvironment: (language: string, force?: boolean): Promise<import('../types').EnvState> =>
    request(`/environment/${language}${force ? '?force=true' : ''}`),

  updateEnvironment: (language: string, config: { runtime_path?: string; compile_flags?: string; tsx_path?: string; tsc_path?: string }): Promise<{
    message: string;
    env_config: Record<string, any>;
  }> => request(`/environment/${language}`, {
    method: 'PUT',
    body: JSON.stringify(config),
  }),

  // AI Settings
  getAiSettings: (): Promise<{ api_key: string; base_url: string; model: string }> =>
    request('/settings/ai'),

  updateAiSettings: (config: { api_key: string; base_url: string; model: string }): Promise<{ message: string }> =>
    request('/settings/ai', { method: 'PUT', body: JSON.stringify(config) }),

  testAiConnection: (config: { api_key: string; base_url: string; model: string }): Promise<{ ok: boolean; latency_ms: number; error?: string }> =>
    request('/settings/ai/test', { method: 'POST', body: JSON.stringify(config) }),

  // Search Settings
  getSearchSettings: (): Promise<{ enabled: boolean; provider: string; api_key: string }> =>
    request('/settings/search'),

  updateSearchSettings: (config: { enabled: boolean; provider: string; api_key: string }): Promise<{ message: string }> =>
    request('/settings/search', { method: 'PUT', body: JSON.stringify(config) }),

  // Exercises
  generateSectionExercise: (sectionId: number) =>
    request<import('../types').Exercise>(`/sections/${sectionId}/generate-exercise`, {
      method: 'POST',
    }),

  generateTopicExercise: (topicId: number) =>
    request<import('../types').Exercise>(`/topics/${topicId}/generate-comprehensive-exercise`, {
      method: 'POST',
    }),

  getExercise: (id: number) =>
    request<import('../types').Exercise>(`/exercises/${id}`),

  runExercise: (id: number, code: string) =>
    request<import('../types').ExerciseRunResponse>(`/exercises/${id}/run`, {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),

  saveExerciseCode: (id: number, code: string) =>
    request<{ ok: boolean }>(`/exercises/${id}/code`, {
      method: 'PUT',
      body: JSON.stringify({ code }),
    }),

  regenerateExercise: (id: number) =>
    request<import('../types').Exercise>(`/exercises/${id}/regenerate`, {
      method: 'POST',
    }),

  getSectionExercises: (sectionId: number) =>
    request<import('../types').Exercise[]>(`/sections/${sectionId}/exercises`),

  getTopicExercises: (topicId: number) =>
    request<import('../types').Exercise[]>(`/topics/${topicId}/exercises`),

  // Workspace settings
  getWorkspace: (): Promise<{ path: string }> =>
    request('/settings/workspace'),

  updateWorkspace: (path: string): Promise<{ message: string; path: string }> =>
    request('/settings/workspace', { method: 'PUT', body: JSON.stringify({ path }) }),
};
