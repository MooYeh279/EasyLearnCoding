# 编程学习工具

辅助开发者进行编程学习的软件

## 编码规范

- Python 遵循: `~/.claude/rules/python` 规范
- TypeScript 遵循: `~/.claude/rules/typescript` 规范

## 开发规范

**始终**采用 superpower 进行方案设计、需求开发、bug 修复等。

- 编写具体代码时需要采用 TTD 规范
- UI 设计始终采用 `skill: frontend-design`
- 编写的代码必须进行检视、评审、修改，知道满足编程规范

## 注意事项

1. **所有用户可见文案必须走 i18n**：前端界面中任何用户可见的文本（包括 placeholder、hint、tooltip、message 提示等）都必须通过 `t('key')` 从 `translations.ts` 获取，禁止硬编码中/英文。新增组件、新增字段时同步补充 `zh` 和 `en` 两个字典的 key。

2. **禁止提交没有验收的内容**: 功能如果用户没有验收，禁止提交

3. **禁止**代码中存在魔鬼数据，配置项需要全局管理
4. **禁止**做任何猜测，必须严谨，对于不清楚、没有验证得事情，不要给出肯定结论