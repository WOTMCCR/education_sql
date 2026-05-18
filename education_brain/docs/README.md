# Docs Overview

当前项目已进入前后端联调阶段。`docs/` 目录下同时存在：

- 当前仍在使用的主文档
- 已完成阶段的实现计划和问题记录
- 更早期的参考实现和设计草案

为了避免联调时拿错文档，建议按下面顺序阅读。

## 当前联调主文档

这些文档可视为当前阶段的主要入口：

1. [api-reference.md](/home/ccr/dev/LearningProject/education_brain/docs/api-reference.md)
   当前后端接口契约。前后端联调优先看这份。

2. [需求文档.md](/home/ccr/dev/LearningProject/education_brain/docs/需求文档.md)
   当前项目的业务目标、能力范围和角色背景。

3. [2026-04-19-frontend-backend-integration-report.md](/home/ccr/dev/LearningProject/education_brain/docs/2026-04-19-frontend-backend-integration-report.md)
   当前联调任务记录、阻塞项和后续动作入口。

4. [PLAN.md](/home/ccr/dev/LearningProject/education_brain/docs/PLAN.md)
   项目的总体设计和完整路线图。适合需要理解全局架构时查阅。

5. [env-setup.md](/home/ccr/dev/LearningProject/education_brain/docs/env-setup.md)
   当前开发环境和预检结果。

## 阶段性实现记录

这些文档保留作为实现过程记录，不应作为当前接口契约的唯一来源：

- [archive/phase-records/2026-04-18-step8-chat-refactor-plan.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/phase-records/2026-04-18-step8-chat-refactor-plan.md)
- [archive/phase-records/2026-04-19-fix-search-precision-and-llm-timeout.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/phase-records/2026-04-19-fix-search-precision-and-llm-timeout.md)
- [archive/phase-records/2026-04-19-step9-sse-streaming-plan.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/phase-records/2026-04-19-step9-sse-streaming-plan.md)
- [archive/implementation-plans/2026-04-17-education-kb-implementation.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/implementation-plans/2026-04-17-education-kb-implementation.md)

用途：

- 回看某个阶段为什么这样设计
- 理解历史改动和问题背景
- 排查“文档写过、代码后来又收束过”的差异

## 仅供参考 / 历史草案

以下文档保留为背景材料，不建议前端联调时直接采用：

- [archive/reference/前端业务接口文档.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/reference/前端业务接口文档.md)
- [archive/reference/数据驱动方案.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/reference/数据驱动方案.md)
- [archive/reference/tutorial.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/reference/tutorial.md)
- [archive/reference/参考实现/answer-history-frontend-blueprint.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/reference/参考实现/answer-history-frontend-blueprint.md)
- [archive/reference/参考实现/query-pipeline-blueprint-legacy.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/reference/参考实现/query-pipeline-blueprint-legacy.md)
- [archive/reference/参考实现/vectorized-herding-ripple.md](/home/ccr/dev/LearningProject/education_brain/docs/archive/reference/参考实现/vectorized-herding-ripple.md)

这些文档的问题通常是：

- 讨论的是更早期的四意图或旧接口形态
- 含有设计草案、教程、示意字段，不等同于现网实现
- 某些内容来自其他项目或迁移过程中的参考方案

## 使用建议

- 前端联调只认 [api-reference.md](/home/ccr/dev/LearningProject/education_brain/docs/api-reference.md)
- 遇到接口行为和旧文档冲突时，以当前后端代码实现为准
- 阶段性计划文档看“为什么”，`api-reference.md` 看“现在怎么调”
- 历史和参考材料统一放在 [archive/](/home/ccr/dev/LearningProject/education_brain/docs/archive)
