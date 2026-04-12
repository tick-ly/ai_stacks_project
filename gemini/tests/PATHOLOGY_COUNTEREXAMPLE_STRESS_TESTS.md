# Pathology / Counterexample 高压测试

本组重点压测：

- 是否真的知道“哪里会坏”
- 是否能给出明确对象，而不是只说“缺条件”
- 是否能把反例与相邻真命题区分开
- 是否能解释这个反例为什么经典、它到底打断了哪一步逻辑

## C1. Torsion-free 但不 flat

**Prompt**

```text
请给出一个“torsion-free 但不 flat”的经典模块例子，并完整解释：
1. 这个模块为什么 torsion-free
2. 它为什么不是 flat
3. 这为什么不与“PID 上 torsion-free implies flat”矛盾
4. 这个反例在 commutative algebra / algebraic geometry 里提醒我们什么

不要只写一句“在非 PID 上会失败”，而要给出具体环、具体模，并把失败机制讲清楚。
```

**通过信号**

- 给出具体环和模块，比如局部二维正则环上的非主理想一类经典对象。
- 会真正解释 torsion-free 与 flat 的区别。
- 能指出 PID 结论失效的根源不是“定理错了”，而是环的结构变了。

**失败信号**

- 没有具体例子。
- 误把“非自由”直接当成“非 flat”，却没有补上适用条件。
- 不解释为什么不和 PID 结论矛盾。

## C2. 有限双有理但非同构

**Prompt**

```text
请给出一个“有限且双有理，但不是同构”的经典例子，并说明它为什么逼着我们在很多命题里加入 normality。
要求：
1. 把例子写到具体的环或曲线上。
2. 解释 finite、birational、not isomorphic 分别体现在哪里。
3. 说明这个例子与 normalization 的关系。
4. 最后指出：如果目标改成 normal，会有什么真命题重新成立。
```

**通过信号**

- 给出 cusp 或类似经典正规化例子。
- 三个性质都会解释，而不是只说“这是 normalization”。
- 能清楚说明 normality 在恢复真命题时扮演什么角色。

**失败信号**

- 只有“取一个奇点曲线然后正规化”这种抽象说法。
- 不解释为什么是双有理。
- 说不清 normality 到底修复了什么。

## C3. Reduced 但不 geometrically reduced

**Prompt**

```text
请给出一个有限型 k-代数，它本身是 reduced，但在某个域扩张后不再 reduced。
要求：
1. 写出具体的域与代数。
2. 解释它在原域上为什么 reduced。
3. 解释做了什么域扩张后出现 nilpotent。
4. 最后说明这个反例为什么告诉我们：在代数几何里，“geometrically reduced”不能被普通的 “reduced” 替代。
```

**通过信号**

- 给出具体的非完全域上的纯不可分例子或等价经典反例。
- 能解释 nilpotent 从哪里冒出来，而不只是说“扩域后坏了”。
- 会把 ordinary reduced 与 geometrically reduced 的用途区别讲清楚。

**失败信号**

- 给不出明确扩域。
- 只说“因为特征 p 会有问题”，没有具体机制。
- 不能把这个反例与几何性质的稳定性联系起来。

**续写检查**

```text
继续，再给一个同主题但方向不同的反例：最好换成 scheme 语言，并解释它和 fibrewise reduced / geometrically reduced 的关系。
```
