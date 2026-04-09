# Stacks Project 数学文档向量化检索方案

## 1. 目标

将 Stacks Project 这类大规模数学文档项目转化为适合检索增强生成（RAG）和知识检索的结构化语料与向量索引，满足以下目标：

- 支持按定理、引理、定义、命题、注记、例子等数学对象进行高精度检索
- 支持按章节、标签（tag）、编号、关键词、公式片段进行精确定位
- 支持自然语言语义检索，而不是只依赖字符串匹配
- 支持“结论 + 证明 + 前置定义/引理”的关联召回
- 为后续问答系统、知识图谱、引用导航和数学 RAG 提供统一底座

## 2. 数据集特点

根据公开源码结构与官方 API，Stacks Project 的数据组织具有以下特征：

- 主要内容以 `*.tex` 章节文件保存
- 项目维护了稳定的 tag 体系，`tags/tags` 提供 `tag -> full_label` 映射
- `Makefile` 中维护了完整章节清单，章节顺序明确
- 官方 API 可按 tag 提供结构与正文内容
- 数学公式在 HTML 输出中仍保留原始 LaTeX，适合做数学文本检索
- 数学对象之间存在大量交叉引用，天然适合构建引用图

这意味着该项目不适合“整章粗切块后直接 embedding”，而更适合构建“面向数学对象的结构化检索语料”。

## 3. 总体设计原则

### 3.1 以 tag 为核心主键

优先使用 Stacks Project 的稳定 tag 作为知识单元主键，例如 `015I`。  
原因：

- tag 稳定、短小、适合引用
- 可直接映射回官网页面和 API
- 比自己生成 chunk id 更可靠

### 3.2 以数学对象为主切分单元

不建议按固定 token 长度切块，而建议按语义对象切分：

- `definition`
- `lemma`
- `theorem`
- `proposition`
- `remark`
- `example`
- `exercise`
- `section/subsection` 叙述性段落
- `proof` 作为独立子块

这样做的好处：

- 数学语义边界清晰
- 检索结果可直接引用
- 可以区分“找结论”和“找证明”
- 更适合后续重排和引用链扩展

### 3.3 建立混合检索，而不是只做向量检索

建议采用三层检索架构：

1. 精确检索：tag、编号、章节名、环境类型、关键词、公式片段
2. 语义检索：对 statement 和 section 文本做 embedding
3. 重排序：结合数学对象类型、章节位置、引用图距离、tag 命中情况综合排序

原因是数学文档中：

- 精确编号和符号检索非常重要
- 纯向量检索容易受公式噪声影响
- 很多“正确答案”来自定义或前置引理，而不只是表面语义相似

## 4. 数据源设计

建议使用双源融合。

### 4.1 主数据源：项目源码

来源：

- 各章节 `*.tex`
- `chapters.tex`
- `Makefile`
- `tags/tags`

作用：

- 提供最完整的原始结构
- 保留原始 LaTeX
- 提取引用关系、章节位置、环境类型
- 便于离线重建数据集

### 4.2 辅助数据源：官方 API

可用接口：

- `/data/tag/<tag>/structure`
- `/data/tag/<tag>/content/statement`
- `/data/tag/<tag>/content/full`

作用：

- 获取标准化 HTML 内容
- 减少自行解析 TeX 的复杂度
- 为检索展示层提供可直接渲染的正文

注意：

- `structure` 接口并非所有 tag 都有
- 因此不能只依赖 API，仍应以源码解析为主、API 为辅

## 5. 推荐的数据模型

建议先产出一份中间层语料文件，例如 `JSONL` 或 `Parquet`，再写入向量库。

每个知识单元建议包含如下字段：

```json
{
  "id": "015I",
  "full_label": "injectives-lemma-cartan-eilenberg",
  "unit_type": "lemma_statement",
  "env_type": "lemma",
  "reference": "13.21.2",
  "title": "Cartan-Eilenberg resolution",
  "chapter_key": "injectives",
  "chapter_name": "Injectives",
  "section_ref": "13.21",
  "section_name": "Cartan-Eilenberg resolutions",
  "statement_text": "Let A be an abelian category with enough injectives...",
  "proof_text": "...",
  "raw_tex": "...",
  "html_text": "...",
  "math_latex_spans": ["\\mathcal{A}", "K^\\bullet"],
  "outgoing_refs": ["0001", "00AB"],
  "incoming_refs": [],
  "source_tex": "injectives.tex",
  "position_in_chapter": 428,
  "dataset_version": "git-sha"
}
```

## 6. 切分策略

### 6.1 一级切分：数学环境对象

优先解析以下对象：

- 具备 tag 的数学环境
- 具备编号或 label 的 section/subsection
- 不带 tag 但语义独立的重要叙述段

### 6.2 二级切分：证明与正文拆分

建议把 statement 和 proof 分开保存：

- `lemma_statement`
- `lemma_proof`
- `theorem_statement`
- `theorem_proof`

这样做的好处：

- 用户问“这个结论是什么”时不被长证明干扰
- 用户问“如何证明”时可以单独召回 proof
- proof 可设置较低默认权重

### 6.3 section 文本切分

对没有显式 tag 的长段落，可按以下规则补充切分：

- 以 section/subsection 为边界
- 以自然段为基本粒度
- 超长段按 token 长度再切分
- 保留父 section 与章节元数据

## 7. 数学文本规范化

数学语料不建议只保留一种文本形态，建议为每个条目生成两套可检索文本。

### 7.1 通道 A：原始保真文本

保留：

- 原始 LaTeX 数学表达式
- 原始环境名
- 原始引用符号

适合：

- 精确展示
- 二次渲染
- 公式回显
- 对数学用户保真输出

### 7.2 通道 B：检索友好文本

将公式做轻量规范化，例如：

- `\\mathcal{A}` -> `A`
- `K^\\bullet` -> `K bullet`
- `\\to` -> `to`
- `\\Spec` -> `Spec`
- `\\mathop{Hom}` -> `Hom`

同时保留一份文本别名字段，例如：

- `normalized_text`
- `normalized_math_tokens`

适合：

- embedding
- 关键词搜索
- 中文/英文混合查询

### 7.3 不建议做的事

- 不建议彻底删除公式
- 不建议把所有 TeX 指令暴力展开为自然语言
- 不建议只保留纯文本摘要而丢掉原始数学表达式

## 8. 索引设计

建议至少建立三类索引。

### 8.1 结构化元数据索引

用于过滤和精确定位：

- tag
- full_label
- env_type
- chapter
- section
- reference
- source file

### 8.2 文本倒排索引

用于关键词和公式检索：

- 原始文本字段
- 规范化文本字段
- 数学 token 字段

推荐用于：

- 搜标签
- 搜环境名
- 搜术语
- 搜公式片段

### 8.3 向量索引

推荐对以下字段生成向量：

- `statement_text`
- `normalized_text`
- section 级叙述段

可选：

- `proof_text` 单独建库或降低权重

不建议默认将整段 proof 和 statement 混合后做一个 embedding。

## 9. 检索流程建议

推荐采用如下流程：

1. 用户查询进入 query parser
2. 判断是否包含 tag、编号、章节名、数学对象类型等强信号
3. 先做结构化过滤与倒排召回
4. 再做向量召回
5. 合并候选集
6. 按以下特征进行重排

重排特征建议包括：

- tag 精确命中
- 标题或术语命中
- 环境类型匹配
- statement 优先于 proof
- 定义在引理前适度加权
- 与已命中条目的引用图距离
- 章节局部邻近性

## 10. 引用图设计

建议额外构建一个图结构层。

节点：

- tag 条目
- section 条目

边：

- `refers_to`
- `used_by`
- `same_section`
- `same_chapter`
- `statement_proof_of`

用途：

- 检索后扩展前置定义
- 补充证明依赖项
- 支持“相关结果”推荐
- 支持数学知识路径追踪

## 11. 数据处理管线

建议的离线处理流程如下：

### 阶段 1：源码收集

- 拉取完整 Stacks Project 源码
- 读取 `Makefile` 中章节顺序
- 读取 `tags/tags` 映射表

### 阶段 2：结构解析

- 解析章节文件
- 提取 section/subsection
- 提取数学环境
- 提取 label、tag、引用关系

### 阶段 3：内容补齐

- 根据 tag 调用官方 API
- 获取 `statement` 与 `full` HTML
- 与本地解析结果对齐

### 阶段 4：文本规范化

- 提取正文
- 保留 LaTeX 数学
- 生成规范化数学 token
- 生成 embedding 输入文本

### 阶段 5：中间语料落盘

- 输出 `JSONL` 或 `Parquet`
- 输出引用图边表
- 输出章节映射表

### 阶段 6：建立索引

- 倒排索引
- 向量索引
- 元数据索引
- 图索引

## 12. 向量化建议

向量化时建议按字段分别处理，而不是把所有内容拼成一坨。

### 12.1 推荐向量化字段

- `statement_text`
- `normalized_text`
- `section_summary_text` 或 section narrative

### 12.2 proof 的处理建议

proof 有价值，但不应默认与 statement 同权：

- 方案 A：proof 独立向量化
- 方案 B：proof 进入单独 collection
- 方案 C：proof 召回后重排降权

### 12.3 中文查询兼容

如果未来要支持中文问、英文文档答，建议：

- 保存一份术语词表
- 为常见数学术语构建中英别名表
- 查询时做 query expansion

例如：

- “层” -> `sheaf`
- “概形” -> `scheme`
- “代数栈” -> `algebraic stack`
- “局部自由” -> `locally free`

## 13. 存储建议

推荐分层存储：

### 13.1 原始层

- 原始 `tex`
- 原始 API HTML

### 13.2 清洗层

- `jsonl/parquet`
- 章节表
- tag 表
- 边表

### 13.3 检索层

- 向量库
- 倒排索引
- 元数据过滤索引

这样便于：

- 重新生成 embedding
- 更换向量模型
- 重建索引而不重复抓原始数据

## 14. 推荐输出目录结构

```text
workspace/
  stacks_project_vectorization_plan.md
  data/
    raw/
    processed/
    index/
  scripts/
    parse_tex.py
    fetch_api.py
    build_corpus.py
    build_embeddings.py
    search_demo.py
```

## 15. 实施优先级

建议按以下顺序推进：

### 第一阶段：最小可用版本

- 拉取源码
- 解析 `tags/tags`
- 获取 tag 对应正文
- 生成结构化 `JSONL`
- 对 statement 建立向量索引

### 第二阶段：增强检索

- 增加 proof 拆分
- 增加倒排检索
- 增加元数据过滤
- 支持 tag 直达与章节过滤

### 第三阶段：高级能力

- 构建引用图
- 实现相关定义/前置引理扩展
- 支持中文术语扩展
- 支持高质量重排

## 16. 风险与注意事项

- 本地仓库当前未完整检出，实际落地前需要先拿到完整源码
- 官方 API 明确说明接口并非稳定接口，离线缓存是必要的
- 部分 tag 有正文但没有 `structure`，所以不能完全依赖 API
- 纯向量方案在数学文档上效果通常不如混合检索
- 如果后续要做问答系统，必须保留 tag 与引用链，避免生成无出处结论

## 17. 结论

对 Stacks Project 这类数学文档，最佳路线不是“整章切块 + embedding”，而是：

- 以 tag 为主键
- 以数学对象为单位切分
- 以源码解析为主、API 补齐为辅
- 以混合检索为主、向量检索为辅
- 以引用图增强召回和解释性

这套方案更适合数学知识的结构特性，也更适合后续扩展为严谨可追溯的数学 RAG 系统。

## 18. 参考依据

- 公开仓库 `stacks/stacks-project`
- `Makefile` 中的章节列表与 tags 流程
- `chapters.tex` 中的章节组织方式
- `tags/tags` 中的 tag 映射表
- 官方 API `/data/tag/<tag>/structure`
- 官方 API `/data/tag/<tag>/content/statement`
- 官方 API `/data/tag/<tag>/content/full`
