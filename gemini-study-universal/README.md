# Gemini 通用学习 Gem 使用指导

本目录用于创建一个更通用的学习型 Gemini Gem，适合大学到研究生阶段的知识学习、题目训练、证明分析、复习梳理与文献导读。

这一版继承了你前面项目中已经证明有效的几项做法：

- 先判断问题类型，再决定回答模式
- 单轮回答默认完成一个闭合学习单元，而不是只给很短摘要
- 题目解析强调“每一步为什么这样做”
- 文献导读强调“逐篇解析 + 综合比较 + 阅读路径”
- 续写状态只在内部保留，不向用户暴露控制字段

## 1. 适用范围

优先适用于大学到研究生阶段的学习问题，例如：

- 数学：微积分、线性代数、抽象代数、实分析、复分析、拓扑、概率、统计、优化、数值分析
- 物理：经典力学、电磁学、量子力学、统计物理、数学物理
- 计算机：算法、数据结构、离散数学、形式语言、计算理论、机器学习理论
- 经济与工程中的理论课程：最优化、控制、随机过程、博弈论、计量基础等

如果问题明显偏离“课程学习 / 题目训练 / 学术阅读”范围，Gem 应先提示范围不匹配，而不是强行进入学术讲解。

## 2. 文件说明

- `GEM_填写模板.md`：直接复制到 Gemini 的“名称 / 说明 / 指令”
- `knowledge/STUDY_GEM_CORE_PROTOCOL.md`：总流程与模式路由
- `knowledge/STUDY_GEM_CONTINUATION_PROTOCOL.md`：隐藏式续写协议
- `knowledge/STUDY_GEM_LEARNING_TEMPLATE.md`：知识讲解与题目解析骨架
- `knowledge/STUDY_GEM_SOURCE_POLICY.md`：资料与引用优先级
- `knowledge/STUDY_GEM_EVAL_CHECKLIST.md`：上线前验收清单

## 3. 在 Gemini 中创建 Gem

1. 打开 Gemini 的“新 Gem”页面。
2. 将 `GEM_填写模板.md` 中的内容填入名称、说明、指令。
3. 若可配置工具，建议开启联网检索与 URL 读取。
4. 在“知识”区域上传 `knowledge/` 下的全部 `.md` 文件。

推荐上传顺序：

1. `STUDY_GEM_CORE_PROTOCOL.md`
2. `STUDY_GEM_CONTINUATION_PROTOCOL.md`
3. `STUDY_GEM_LEARNING_TEMPLATE.md`
4. `STUDY_GEM_SOURCE_POLICY.md`
5. `STUDY_GEM_EVAL_CHECKLIST.md`

## 4. 快速验收

建议至少用下面 6 类问题做冒烟测试：

1. 低相关：
- `帮我想一个周末出游计划。`
- 预期：不强行进入学术讲解。

2. 知识讲解：
- `解释一下实分析里一致收敛和逐点收敛的区别。`
- 预期：给定义、例子、反例/误区、用途。

3. 题目解析：
- `求证任何有限维线性空间上的两个范数等价。`
- 预期：先说明策略，再逐步证明，不跳大步。

4. 题目提示：
- `这道概率题先给我提示，不要直接完整解答。`
- 预期：只给提示或分层提示。

5. 复习梳理：
- `把电磁学中高斯定律、散度、通量整理成一页复习提纲。`
- 预期：结构清晰，适合考前复习。

6. 文献导读：
- `比较几篇关于 transformer scaling law 的代表性论文，并给阅读顺序。`
- 预期：不是只列标题，而是逐篇分析贡献、方法、局限与关系。

## 5. 常见问题

如果回答太短：

- 检查主指令里是否仍保留“单轮完成一个闭合学习单元”的要求。
- 检查 `STUDY_GEM_LEARNING_TEMPLATE.md` 是否已上传。

如果题目解答跳步太大：

- 检查是否保留了“每个关键步骤都说明为什么这样做”的约束。
- 检查是否区分了“提示模式”和“完整解答模式”。

如果文献导读变成书目列表：

- 检查主指令是否保留 `Literature Breakdown / Synthesis / Reading Path`。
- 检查 `STUDY_GEM_SOURCE_POLICY.md` 与 `STUDY_GEM_EVAL_CHECKLIST.md` 是否已上传。

如果出现 `CONTINUE_STATE`、`slots_done` 之类片段：

- 说明 Gem 把内部续写状态直接打印出来了。
- 保留“分阶段续写”，但必须只输出自然语言的 `Next Step`。
