import type { ContentLanguage } from '../context/LangContext';

const zh: Record<string, string> = {
  // Common
  'app.title': '编程学习工具',

  // HomePage
  'home.usageHint': '每张卡片对应一门编程语言，点击进入即可浏览主题并开始学习',
  'home.noCourses': '暂无课程，请先运行 seed 脚本初始化数据',
  'home.topicsCount': '{n} 个主题',
  'home.noTopics': '暂无主题，点击进入课程开始创建',
  'home.more': '+{n} 更多',

  // CourseHome
  'course.back': '返回首页',
  'course.createBtn': '创建主题',
  'course.placeholder': '输入学习主题，如 {examples}',
  'course.topicsTitle': '已创建的主题（{n}）',
  'course.noTopics': '暂无主题，在上方输入框中创建一个吧',
  'course.deleteConfirm': '确认删除该主题？',
  'course.deleteDesc': '所有关联的大纲和课程内容将被永久删除',
  'course.confirmDelete': '确认删除',
  'course.cancel': '取消',
  'course.delete': '删除',
  'course.loadFail': '加载课程失败',
  'course.createSuccess': '主题创建成功',
  'course.createFail': '创建失败，请检查后端服务',
  'course.deleteSuccess': '已删除',
  'course.deleteFail': '删除失败',

  // TopicDetail
  'topic.back': '返回课程',
  'topic.notFound': '主题不存在',
  'topic.loadFail': '加载主题失败',
  'topic.step1Title': '创建大纲',
  'topic.step1Desc': 'AI 生成学习大纲',
  'topic.genOutlineHint': 'AI 将为你的主题创建结构化学习大纲',
  'topic.step2Title': '生成内容',
  'topic.step2Desc': 'AI 展开每一课',
  'topic.step3Title': '开始学习',
  'topic.step3Desc': '课程内容就绪，开始学习之旅',
  'topic.startLearning': '开始学习',
  'topic.genOutlineBtn': '生成大纲',
  'topic.outlineTitle': '学习大纲',
  'topic.feedbackBtn': '发送修改意见',
  'topic.feedbackPlaceholder': '大纲不满意？输入调整意见，如：{examples}',
  'topic.genOutlineStatus': '正在生成大纲，预计需要 10-30 秒...',
  'topic.genContentStatus': '正在生成课程内容...',
  'topic.genProgress': '正在生成第 {current}/{total} 课：{lesson}',
  'topic.outlineRegenOk': '大纲已根据意见重新生成',
  'topic.outlineGenOk': '大纲生成完成',
  'topic.aiFail': 'AI 生成失败，请检查 API 配置',
  'topic.contentGenFail': '内容生成失败，请重试',
  'topic.contentGenOk': '课程内容生成完成',
  'topic.contentGenStarted': '内容生成已启动',
  'topic.alreadyGenerating': '正在生成中，请勿重复操作',
  'topic.pending': '待生成',
  'topic.generating': '生成中...',
  'topic.goLearn': '去学习',
  'topic.sectionProgress': '已完成 {done}/{total}',
  'topic.retry': '重试',
  'topic.retrying': '重试中...',
  'topic.cancel': '取消',

  // Topic status labels
  'status.draft': '草稿',
  'status.generating_outline': '生成大纲中',
  'status.outline_ready': '大纲就绪',
  'status.generating_content': '生成内容中',
  'status.content_ready': '可开始学习',
  'topic.generateContent': '生成学习内容',
  'topic.generateContentDesc': 'AI 将逐一生成每个章节的详细课程内容',
  'topic.generateNewContent': '生成新增内容',
  'topic.generateNewContentDesc': '仅生成新增或内容为空的课时，已有内容不受影响',
  'topic.addSection': '添加章节',
  'topic.addLesson': '添加课时',
  'topic.delete': '删除',
  'topic.deleteSectionConfirm': '确认删除该章节？',
  'topic.deleteLessonConfirm': '确认删除该课时？',
  'topic.newSection': '新章节',
  'topic.newLesson': '新课时',

  // LearningView
  'learn.back': '返回主题',
  'learn.loading': '加载课程内容...',
  'learn.placeholder': '选择左侧课时开始学习',
  'learn.saveSuccess': '保存成功',
  'learn.saveFail': '保存失败',
  'learn.loadFail': '加载课程失败',
  'learn.exportMd': '导出 Markdown',
  'learn.addMd': '+ Markdown',
  'learn.addCode': '+ Code',
  'learn.regenerate': '重新生成',
  'learn.regenerating': '重新生成中...',
  'learn.regenerateSuccess': '内容已重新生成',
  'learn.regenerateFail': '重新生成失败',
  'learn.regenerateConfirm': '重新生成将覆盖当前课程内容，确认继续？',

  // CodeBlock
  'code.run': '运行',
  'code.edit': '编辑',
  'code.copy': '复制',
  'code.execError': '执行错误',
  'code.doneIn': '耗时',
  'code.running': '运行中...',
  'code.stop': '停止',
  'code.moveUp': '上移',
  'code.moveDown': '下移',
  'code.switchToMd': 'code → md',
  'code.switchToCode': 'md → code',

  // AI Chat
  'chat.title': 'AI 助手',
  'chat.placeholder': '输入问题...',
  'chat.send': '发送',
  'chat.typing': 'AI 正在输入...',
  'chat.collapse': '收起',
  'chat.stop': '停止',
  'chat.you': '你',
  'chat.ai': 'AI',

  // Language-specific default code examples
  'code.exampleC': '#include <stdio.h>\n\nint main() {\n  printf("Hello, World!\\n");\n  return 0;\n}',
  'code.exampleCpp': '#include <iostream>\n\nint main() {\n  std::cout << "Hello, World!" << std::endl;\n  return 0;\n}',

  // Environment wizard
  'env.wizardTitle': '环境配置',
  'env.step1Title': '检测结果',
  'env.step2Title': '安装指引',
  'env.step3Title': '手动配置',
  'env.retest': '重新检测',
  'env.next': '下一步',
  'env.skipInstall': '跳过安装，手动配置',
  'env.saveAndRetest': '保存并重新检测',
  'env.cancel': '取消',
  'env.runCmd': '运行',
  'env.running': '运行中...',
  'env.allReady': '所有组件已就绪',
  'env.componentMissing': '{n} 个组件缺失',
  'env.ready': '就绪',
  'env.notReady': '未就绪',
  'env.configure': '配置',
  'env.notInstalled': '未安装',
  'env.runtimePath': '运行时路径',
  'env.compilerPath': '编译器路径',
  'env.compileFlags': '编译选项',
  'env.pythonPathHint': 'Python 可执行文件路径',
  'env.nodePathHint': 'Node.js 可执行文件路径',
  'env.bashPathHint': 'Bash 可执行文件路径',
  'env.gccPathHint': 'GCC 编译器路径',
  'env.gppPathHint': 'G++ 编译器路径',
  'env.tsxPathHint': 'tsx 执行器路径',
  'env.tscPathHint': 'TypeScript 编译器路径',
  'env.leaveEmpty': '留空则使用系统默认路径',
  'env.noInstallNeeded': '所有依赖已就绪，无需安装',

  // Model config
  'model.title': 'AI 模型配置',
  'model.apiKey': 'API Key',
  'model.baseUrl': 'Base URL',
  'model.model': '模型名称',
  'model.save': '保存',
  'model.cancel': '取消',
  'model.hint': '配置大语言模型连接信息，支持 OpenAI 兼容 API。',
  'model.apiKeyPlaceholder': 'sk-...',
  'model.baseUrlPlaceholder': 'https://api.openai.com/v1',
  'model.modelPlaceholder': 'gpt-4o',
  'model.testConnection': '测试连接',
  'model.testing': '测试中...',
  'model.testOk': '连接成功',
  'model.testFail': '连接失败',

  // Workspace settings
  'workspace.label': '工作目录',
  'workspace.path': '工作目录路径',
  'workspace.hint': '代码运行时的工作目录，文件读写和临时文件将存放在此目录下的 workspace 子目录中',
  'workspace.placeholder': '输入工作目录路径，留空使用默认 {defaultPath}',

  // CourseHome
  'course.inputHint': '输入你想学习的主题，AI 将为你生成结构化的课程大纲。',
};

const en: Record<string, string> = {
  // Common
  'app.title': 'Programming Learning Tool',

  // HomePage
  'home.usageHint': 'Each card is a programming language course — click to explore topics and start learning',
  'home.noCourses': 'No courses yet. Please run the seed script to initialize data.',
  'home.topicsCount': '{n} topics',
  'home.noTopics': 'No topics yet. Click to enter the course and create one.',
  'home.more': '+{n} more',

  // CourseHome
  'course.back': 'Back to Home',
  'course.createBtn': 'Create Topic',
  'course.placeholder': 'Enter a learning topic, e.g. {examples}',
  'course.topicsTitle': 'Topics ({n})',
  'course.noTopics': 'No topics yet. Create one above.',
  'course.deleteConfirm': 'Delete this topic?',
  'course.deleteDesc': 'All associated outline and lesson content will be permanently deleted.',
  'course.confirmDelete': 'Confirm',
  'course.cancel': 'Cancel',
  'course.delete': 'Delete',
  'course.loadFail': 'Failed to load course',
  'course.createSuccess': 'Topic created',
  'course.createFail': 'Creation failed. Please check backend service.',
  'course.deleteSuccess': 'Deleted',
  'course.deleteFail': 'Delete failed',

  // Status labels
  'status.draft': 'Draft',
  'status.generating_outline': 'Generating Outline',
  'status.outline_ready': 'Outline Ready',
  'status.generating_content': 'Generating Content',
  'status.content_ready': 'Ready to Learn',

  // TopicDetail
  'topic.back': 'Back to Course',
  'topic.notFound': 'Topic not found',
  'topic.loadFail': 'Failed to load topic',
  'topic.step1Title': 'Create Outline',
  'topic.step1Desc': 'AI generates learning outline',
  'topic.genOutlineHint': 'AI will create a structured learning outline for your topic',
  'topic.step2Title': 'Generate Content',
  'topic.step2Desc': 'AI expands each lesson',
  'topic.step3Title': 'Start Learning',
  'topic.step3Desc': 'Course content ready — dive in',
  'topic.startLearning': 'Start Learning',
  'topic.genOutlineTitle': 'Generate Outline',
  'topic.genOutlineBtn': 'Generate Outline',
  'topic.regenOutline': 'Regenerate Outline',
  'topic.outlineTitle': 'Learning Outline',
  'topic.regen': 'Regenerate',
  'topic.feedbackBtn': 'Send Feedback',
  'topic.feedbackPlaceholder': 'Not satisfied? Enter feedback, e.g.: {examples}',
  'topic.confirmBtn': 'Confirm Outline, Generate Content',
  'topic.confirmDesc': 'AI will generate detailed lesson content for each section',
  'topic.contentTitle': 'Course Content',
  'topic.genOutlineStatus': 'Generating outline, estimated 10-30 seconds...',
  'topic.genContentStatus': 'Generating lesson content...',
  'topic.genProgress': 'Generating lesson {current}/{total}: {lesson}',
  'topic.outlineRegenOk': 'Outline regenerated based on feedback',
  'topic.outlineGenOk': 'Outline generation complete',
  'topic.aiFail': 'AI generation failed. Please check API configuration.',
  'topic.contentGenFail': 'Content generation failed. Please retry.',
  'topic.contentGenOk': 'Course content generated',
  'topic.contentGenStarted': 'Content generation started',
  'topic.alreadyGenerating': 'Already generating, please wait',
  'topic.pending': 'Pending',
  'topic.generating': 'Generating...',
  'topic.goLearn': 'Learn',
  'topic.sectionProgress': '{done}/{total} done',
  'topic.retry': 'Retry',
  'topic.retrying': 'Retrying...',
  'topic.cancel': 'Cancel',
  'topic.generateContent': 'Generate Content',
  'topic.generateContentDesc': 'AI will generate detailed lessons for each section',
  'topic.generateNewContent': 'Generate New Content',
  'topic.generateNewContentDesc': 'Only generate new or empty lessons, existing content preserved',
  'topic.addSection': 'Add Section',
  'topic.addLesson': 'Add Lesson',
  'topic.delete': 'Delete',
  'topic.deleteSectionConfirm': 'Delete this section?',
  'topic.deleteLessonConfirm': 'Delete this lesson?',
  'topic.newSection': 'New Section',
  'topic.newLesson': 'New Lesson',

  // LearningView
  'learn.back': 'Back to Topic',
  'learn.loading': 'Loading lesson content...',
  'learn.placeholder': 'Select a lesson from the sidebar to start learning',
  'learn.saveSuccess': 'Saved successfully',
  'learn.saveFail': 'Save failed',
  'learn.loadFail': 'Failed to load lesson',
  'learn.exportMd': 'Export Markdown',
  'learn.addMd': '+ Markdown',
  'learn.addCode': '+ Code',
  'learn.regenerate': 'Regenerate',
  'learn.regenerating': 'Regenerating...',
  'learn.regenerateSuccess': 'Content regenerated',
  'learn.regenerateFail': 'Regeneration failed',
  'learn.regenerateConfirm': 'Regenerating will overwrite current lesson content. Continue?',

  // CodeBlock
  'code.run': 'Run',
  'code.edit': 'Edit',
  'code.copy': 'Copy',
  'code.execError': 'Execution Error',
  'code.doneIn': 'Done in',
  'code.running': 'Running...',
  'code.stop': 'Stop',
  'code.moveUp': 'Move up',
  'code.moveDown': 'Move down',
  'code.switchToMd': 'code → md',
  'code.switchToCode': 'md → code',

  // AI Chat
  'chat.title': 'AI Assistant',
  'chat.placeholder': 'Ask a question...',
  'chat.send': 'Send',
  'chat.typing': 'AI is typing...',
  'chat.collapse': 'Collapse',
  'chat.stop': 'Stop',
  'chat.you': 'You',
  'chat.ai': 'AI',

  // Language-specific default code examples
  'code.exampleC': '#include <stdio.h>\n\nint main() {\n  printf("Hello, World!\\n");\n  return 0;\n}',
  'code.exampleCpp': '#include <iostream>\n\nint main() {\n  std::cout << "Hello, World!" << std::endl;\n  return 0;\n}',

  // Environment wizard
  'env.wizardTitle': 'Environment Setup',
  'env.step1Title': 'Detection Results',
  'env.step2Title': 'Installation Guide',
  'env.step3Title': 'Manual Config',
  'env.retest': 'Re-check',
  'env.next': 'Next',
  'env.skipInstall': 'Skip, configure manually',
  'env.saveAndRetest': 'Save & Re-check',
  'env.cancel': 'Cancel',
  'env.runCmd': 'Run',
  'env.running': 'Running...',
  'env.allReady': 'All components ready',
  'env.componentMissing': '{n} component(s) missing',
  'env.ready': 'Ready',
  'env.notReady': 'Not Ready',
  'env.configure': 'Configure',
  'env.notInstalled': 'Not installed',
  'env.runtimePath': 'Runtime Path',
  'env.compilerPath': 'Compiler Path',
  'env.compileFlags': 'Compile Flags',
  'env.pythonPathHint': 'Path to Python executable',
  'env.nodePathHint': 'Path to Node.js executable',
  'env.bashPathHint': 'Path to Bash executable',
  'env.gccPathHint': 'Path to GCC compiler',
  'env.gppPathHint': 'Path to G++ compiler',
  'env.tsxPathHint': 'Path to tsx executor',
  'env.tscPathHint': 'Path to TypeScript compiler',
  'env.leaveEmpty': 'Leave empty to use system default',
  'env.noInstallNeeded': 'All dependencies ready, no installation needed',

  // Model config
  'model.title': 'AI Model Configuration',
  'model.apiKey': 'API Key',
  'model.baseUrl': 'Base URL',
  'model.model': 'Model Name',
  'model.save': 'Save',
  'model.cancel': 'Cancel',
  'model.hint': 'Configure LLM connection. Supports OpenAI-compatible APIs.',
  'model.apiKeyPlaceholder': 'sk-...',
  'model.baseUrlPlaceholder': 'https://api.openai.com/v1',
  'model.modelPlaceholder': 'gpt-4o',
  'model.testConnection': 'Test Connection',
  'model.testing': 'Testing...',
  'model.testOk': 'Connected',
  'model.testFail': 'Connection failed',

  // Workspace settings
  'workspace.label': 'Workspace',
  'workspace.path': 'Workspace Path',
  'workspace.hint': 'Working directory for code execution. File I/O and temp files go under a workspace/ subdirectory.',
  'workspace.placeholder': 'Enter workspace path, leave empty to use default {defaultPath}',

  // CourseHome
  'course.inputHint': 'Enter a topic you want to learn and AI will generate a structured course outline for you.',
};

const dicts: Record<ContentLanguage, Record<string, string>> = { zh, en };

export function t(key: string, lang: ContentLanguage, params?: Record<string, string | number>): string {
  let text = dicts[lang]?.[key] || dicts.zh[key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

// Language-specific example keywords for input placeholders
type ExamplesMap = Record<string, { topics: string; feedback: string }>;

const examplesZh: ExamplesMap = {
  python:     { topics: 'asyncio、闭包、泛型...',       feedback: '协程章节应该放到事件循环之前' },
  javascript: { topics: 'Promise、闭包、原型链...',     feedback: '异步编程章节应该放到事件循环之前' },
  typescript: { topics: '泛型、装饰器、类型守卫...',     feedback: '类型守卫章节应该放到接口之前' },
  go:         { topics: 'goroutine、channel、接口...',  feedback: 'goroutine 章节应该放到 channel 之前' },
  java:       { topics: 'Stream、多线程、泛型...',       feedback: '多线程章节应该放到集合框架之前' },
  kotlin:     { topics: '协程、扩展函数、密封类...',     feedback: '协程章节应该放到 Flow 之前' },
  swift:      { topics: 'Combine、异步、协议...',        feedback: '协议章节应该放到泛型之前' },
  rust:       { topics: '所有权、生命周期、异步...',     feedback: '所有权章节应该放到智能指针之前' },
  ruby:       { topics: 'block、元编程、mixin...',       feedback: 'block 章节应该放到枚举之前' },
  c:          { topics: '指针、内存管理、数据结构...',     feedback: '指针章节应该放到结构体之前' },
  cpp:        { topics: '智能指针、模板、STL...',           feedback: '模板章节应该放到 STL 之前' },
};

const examplesEn: ExamplesMap = {
  python:     { topics: 'asyncio, closures, generics...',      feedback: 'Move the coroutine section before the event loop' },
  javascript: { topics: 'Promise, closures, prototype...',     feedback: 'Move async section before event loop section' },
  typescript: { topics: 'generics, decorators, type guards...', feedback: 'Move type guards section before interfaces' },
  go:         { topics: 'goroutine, channel, interface...',    feedback: 'Move goroutine section before channel section' },
  java:       { topics: 'Stream, concurrency, generics...',    feedback: 'Move concurrency section before collections' },
  kotlin:     { topics: 'coroutines, extensions, sealed...',   feedback: 'Move coroutines section before Flow section' },
  swift:      { topics: 'Combine, async, protocols...',        feedback: 'Move protocols section before generics' },
  rust:       { topics: 'ownership, lifetimes, async...',      feedback: 'Move ownership section before smart pointers' },
  ruby:       { topics: 'block, metaprogramming, mixin...',    feedback: 'Move block section before enumerable section' },
};

const examplesByLang = (lang: ContentLanguage): ExamplesMap => lang === 'zh' ? examplesZh : examplesEn;
const defaultLangName = 'python';

export function langPlaceholder(key: 'course.placeholder' | 'topic.feedbackPlaceholder', lang: ContentLanguage, languageName?: string): string {
  const name = languageName || defaultLangName;
  const examples = examplesByLang(lang)[name] || examplesByLang(lang)[defaultLangName];
  return t(key, lang, {
    examples: key === 'course.placeholder' ? examples.topics : examples.feedback,
  });
}
