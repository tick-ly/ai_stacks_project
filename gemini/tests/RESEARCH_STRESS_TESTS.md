# Research 高压测试

本组重点压测：

- 是否能把文献讲成“问题 - 方法 - 贡献 - 局限”
- 是否会做跨文献比较，而不是分散摘要
- 是否能给出从基础到前沿的阅读路径
- 遇到“最新进展”时，能否既保留 foundational anchor，又加入近期来源

## R1. Cotangent Complex 三路线比较

**Prompt**

```text
请比较 cotangent complex 的三条代表性文献路线：
1. Illusie
2. Toën-Vezzosi
3. Lurie

不要只列书目。请逐篇说明：
- 它在解决什么问题
- 采用了什么技术框架
- 对象范围和语言有什么差异
- 哪些结果最值得读
- 对初学者最难的门槛是什么

最后请做一个真正的综合比较：
- 这三条路线在 philosophy 上哪里一致，哪里不同
- 如果我已经熟悉 The Stacks Project 里的 classical cotangent complex，该怎么走阅读路径进入 DAG 文献
要求带引用，并区分 foundational reference 和 later synthesis。
```

**通过信号**

- 每条路线都不是只有“作者 + 标题”，而是讲清楚问题与技术框架。
- 有跨路线比较，而不是三段互不相干的摘要。
- 会用 Stacks/classical cotangent complex 作为过桥点。
- 阅读路径有顺序，不是无结构地甩书单。

**失败信号**

- 只会列文献标题。
- 没有解释 Illusie / TV / Lurie 的对象范围差异。
- 没有 foundational anchor。

## R2. Derived Deformation Theory 路线图

**Prompt**

```text
如果我要从 classical deformation theory 走到 derived deformation theory，请给一个研究导向的路线图。
要求至少比较以下几类入口：
- classical Schlessinger-style deformation theory
- cotangent complex / obstruction theory
- Lurie / Pridham 一类 derived deformation frameworks

请不要只做教科书式介绍，而要回答：
1. 每条路线到底解决了 classical 方法的哪个缺口？
2. 它们对 functor of points、higher homotopies、obstruction packages 的处理各有什么特点？
3. 如果我只读有限篇幅，最值得优先读哪些文献，为什么？
4. 哪些说法在不同作者那里看似类似，其实假设或语境不同？
```

**通过信号**

- 能明确说出 classical theory 的局限和 derived frameworks 在补什么。
- 比较时不是泛泛说“更一般”，而是落到 obstruction、higher automorphisms、representability 等具体点。
- 能指出 Lurie 与 Pridham 之间的语境差异或等价桥梁。
- 阅读建议是有取舍的。

**失败信号**

- 只写“classical 不够一般，derived 更强”。
- 把所有框架写成一回事。
- 没有任何“为什么先读这篇而不是那篇”的说明。

## R3. 近年 DAG 文献综述能力

**Prompt**

```text
请围绕 “derived moduli / shifted symplectic structures” 给出一份 2010 以后到近年的文献脉络图。
要求：
1. 至少给出 1 个 foundational anchor 和若干后续方向。
2. 每篇重点文献都要说明：问题、方法、贡献、局限。
3. 不能只谈几何直觉，还要解释与 deformation theory、cotangent complex、obstruction theory 的关系。
4. 如果你引用“最新进展”，请明确哪些是较新工作，哪些只是背景。
5. 最后给一个“如果我只有两周时间”的阅读优先级列表。
```

**通过信号**

- 会同时处理 foundational paper 与近年扩展。
- 能把 shifted symplectic 与 moduli/deformation/cotangent complex 接起来。
- “较新工作”有时间意识，不会把老论文伪装成近年趋势。
- 阅读优先级体现取舍。

**失败信号**

- 标题堆积，没有 paper-level interpretation。
- 对 freshness 没有意识。
- 完全不做综合，只是 bibliography dump。
