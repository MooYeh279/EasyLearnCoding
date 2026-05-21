# 编程学习工具

辅助开发者进行编程学习的软件

## 功能点

1. 课程管理

学习流程:
- 用户选择编程语言(当前支持 python, javascript, typescript, bash, c, cpp)，基于编程语言粒度生成课程
- 选择课程，输入主题，基于主题生成相关的学习大纲、子课程以及测试等
- 生成课程、主题内容等支持持久化，保存和管理

2. 输入主题，ai 辅助生成主题学习大纲

例如用户学习 python 时，输入 asyncio 主题，后台自动生成相关主题学习大纲、子课程以及编程测试，循序渐进介绍 asyncio。

3. 理论结合实践

生成课程不仅仅包括理论介绍，还有实践代码块，代码块支持在线运行、调试等。

每个课程之后都有量身定做的测试编程练习。

4. ai 助手

课程学习界面包括一个 ai 助手，学习过程中的问题、疑问都可以咨询助手。

5. 课程更正

课程由 ai 生成，在学习过程中如果发现课程有错漏，可以进行错误反馈，ai 分析用户反馈，如果的确为错误则进行课程更正。

## 注意事项

1. **所有用户可见文案必须走 i18n**：前端界面中任何用户可见的文本（包括 placeholder、hint、tooltip、message 提示等）都必须通过 `t('key')` 从 `translations.ts` 获取，禁止硬编码中/英文。新增组件、新增字段时同步补充 `zh` 和 `en` 两个字典的 key。

2. **新增编程语言需同步更新多处**：添加语言支持时，除了后端 seed.py 和 env_checker.py 的 COMMANDS/INSTALL_GUIDE，前端还需更新：
   - `translations.ts` 中的 `examplesZh` 和 `examplesEn`（主题输入 placeholder 示例）
   - `EnvConfigWizard.tsx` 中的 `getConfigFields()`（手动配置项）
   - 必要时在 `translations.ts` 中添加语言相关的 path hint key（如 `env.gccPathHint`）

3. **模型配置是全局的**：AI 模型设置（API Key / Base URL / Model）不属于某个编程语言，应放在全局位置（当前在 AppLayout 顶部栏）。

4. **环境配置文案需明确组件具体名称**：配置项的 label 必须指明具体组件（如 "Node.js 可执行文件路径"），不应使用泛化的 "运行时路径"。

5. **禁止提交没有验收的内容**: 功能如果用户没有验收，禁止提交