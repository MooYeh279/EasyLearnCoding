export interface Language {
  id: number;
  name: string;
  display_name: string;
}

export interface Course {
  id: number;
  language_id: number;
  title: string;
  language?: Language;
  topics?: Topic[];
}

export interface Topic {
  id: number;
  course_id: number;
  title: string;
  status: 'draft' | 'generating_outline' | 'outline_ready' | 'generating_content' | 'content_ready';
  generation_progress?: {
    current: number;
    total: number;
    current_section: string;
    current_lesson: string;
  } | null;
  created_at: string;
  course?: { language?: Language };
  sections?: Section[];
}

export interface TopicOutline {
  id: number;
  topic_id: number;
  sections: OutlineSection[];
}

export interface OutlineSection {
  title: string;
  description: string;
  lessons: { title: string }[];
}

export interface Section {
  id: number;
  topic_id: number;
  title: string;
  order: number;
  lessons?: Lesson[];
}

export interface Lesson {
  id: number;
  section_id: number;
  title: string;
  order: number;
  content: string;
  lesson_type: 'concept' | 'example' | 'exercise' | 'summary';
  has_content?: boolean;
}

export interface CellOutput {
  stdout: string;
  stderr: string;
  exit_code: number;
  duration_ms: number;
}

export interface MarkdownCell {
  id: string;
  type: 'markdown';
  content: string;
}

export interface CodeCell {
  id: string;
  type: 'code';
  language: string;
  code: string;
  output: CellOutput | null;
}

export type NotebookCell = MarkdownCell | CodeCell;

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
}

export interface ToolCall {
  id?: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResult {
  name: string;
  result: Record<string, unknown>;
}

export interface AgentEvent {
  type: 'agent_start' | 'agent_thinking' | 'tool_call' | 'tool_result' | 'agent_done' | 'agent_error' | 'progress' | 'all_done' | 'outline_saved';
  message?: string;
  content?: string;
  thinking?: string;
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
  lesson_id?: number;
  lesson_title?: string;
  total?: number;
  current?: number;
  current_section?: string;
  current_lesson?: string;
  sections?: OutlineSection[];
  topic_id?: number;
}

export interface EnvComponent {
  name: string;
  available: boolean;
  version: string | null;
  path: string | null;
  install_cmd: string | null;
}

export interface EnvState {
  language: string;
  runtime_available: boolean;
  runtime_path: string | null;
  version: string | null;
  package_manager: string | null;
  package_manager_ok: boolean;
  config_override: Record<string, any>;
  components: EnvComponent[];
  ready: boolean;
  os: 'win' | 'linux' | 'mac';
}

export interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

export interface ExerciseRunResponse {
  results: TestResult[];
  all_passed: boolean;
  error?: string;
  duration_ms: number;
  raw_output?: string;
}

export interface Exercise {
  id: number;
  question: string;
  template: string;
  test_cases: string;
  knowledge_tags: string[];
  hints: string[];
  section_id: number | null;
  type: 'section' | 'topic';
  language: string;
  regenerating: boolean;
}
