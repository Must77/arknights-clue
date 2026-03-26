# 形式化模型：明日方舟线索赠送策略

---

## 1. 系统参数

| 符号 | 含义 | 默认值 |
|------|------|--------|
| $N$ | 玩家数量（互为好友的群体规模）| 2, 10, 50 |
| $K$ | 线索类型数 | 7 |
| $\lambda$ | 单个玩家每天产出线索数（泊松率）| 1.2（约20h/条）|
| $C_{\max}$ | 自持线索上限 | 10 |
| $p_k$ | 类型 $k$ 线索的产出概率 | 均匀: $1/7$；非均匀: 见假设A1 |
| $r_E$ | 线索交流的信用点奖励（主人）| 210 |
| $r_V$ | 访问好友线索交流获得的信用点 | 30 |
| $r_G$ | 赠送线索获得的信用点（赠出方）| 20 |
| $\mathbf{r}_R$ | 接收线索获得的信用点序列 | (15, 10, 5) |
| $V_{\max}^{\text{out}}$ | 每日最大访问次数 | 10 |
| $V_{\max}^{\text{in}}$ | 每周最大被访问次数（上周结算）| 10 |
| $D_E$ | 线索交流持续时间 | 1天（24小时）|
| $W$ | 每日信用点钱包上限（每日结束时截断）| 300 |
| $S$ | 信用商店每日可消费上限 | 参数：300/600/∞ |

---

## 2. 状态空间

每名玩家 $i$ 在时间步 $t$（单位：天）的状态为：

$$\mathbf{s}_i(t) = \left( \mathbf{c}_i^{\text{self}}(t),\ \mathbf{c}_i^{\text{recv}}(t),\ w_i(t),\ e_i(t) \right)$$

- $\mathbf{c}_i^{\text{self}} \in \mathbb{Z}_{\geq 0}^K$：自持线索向量，$\sum_k c_{ik}^{\text{self}} \leq C_{\max}$
- $\mathbf{c}_i^{\text{recv}} \in \mathbb{Z}_{\geq 0}^K$：收到的线索向量（无上限，不可转赠）
- $w_i(t) \in [0, W]$：当前信用点钱包（每日结束后截断至 $W$）
- $e_i(t) \in \{0, 1\}$：线索交流是否激活

定义总持有量 $\mathbf{c}_i = \mathbf{c}_i^{\text{self}} + \mathbf{c}_i^{\text{recv}}$。

**集齐条件**（可触发线索交流）：$\min_k c_{ik} \geq 1$

---

## 3. 动态过程（每日时间步）

### 3.1 线索生成

每天，玩家 $i$ 自主产出 $X_i \sim \text{Poisson}(\lambda)$ 条线索，类型 $T_j \sim \text{Categorical}(\mathbf{p})$。

若 $\sum_k c_{ik}^{\text{self}} < C_{\max}$，则加入自持库存；否则被阻塞（丢失或暂停）。

### 3.2 线索赠送

玩家 $i$ 可在产出线索后立即决定是否赠送。赠出 1 条类型 $k$ 线索的效果：

$$c_{ik}^{\text{self}} \mathrel{-}= 1, \quad w_i \mathrel{+}= r_G = 20$$

接收方 $j$ 获得：

$$c_{jk}^{\text{recv}} \mathrel{+}= 1, \quad w_j \mathrel{+}= r_R^{(n_j)}$$

其中 $n_j$ 为玩家 $j$ 当天已接收的线索总数（所有来源共享），$r_R^{(n)} = 15, 10, 5, 0, 0, \ldots$

**约束**：收到的线索不可再赠送（$\mathbf{c}^{\text{recv}}$ 只能由自己的 $\mathbf{c}^{\text{self}}$ 赠出）。

### 3.3 线索交流

若 $\min_k c_{ik} \geq 1$ 且 $e_i = 0$，玩家可触发交流：

$$\forall k:\ \text{若} c_{ik}^{\text{self}} > 0 \text{ 则 } c_{ik}^{\text{self}} \mathrel{-}= 1 \text{，否则 } c_{ik}^{\text{recv}} \mathrel{-}= 1$$

$$e_i \leftarrow 1 \quad \text{（持续 } D_E = 1 \text{ 天）}$$

交流结束后：$e_i \leftarrow 0$，$w_i \mathrel{+}= r_E = 210$

### 3.4 访问好友线索交流

玩家 $i$ 每天可访问最多 $V_{\max}^{\text{out}} = 10$ 位好友的激活交流，每次：

$$w_i \mathrel{+}= r_V = 30$$

被访问方 $j$（累积，下周初结算）：

$$\text{pending\_credit}_j \mathrel{+}= r_V = 30 \quad \text{（每周最多累计 } V_{\max}^{\text{in}} \cdot r_V = 300 \text{）}$$

**假设A**（待确认）：每个好友每天只能访问一次（即使其线索交流仍激活）。

### 3.5 每日结算

每日结束时，信用点截断：

$$w_i \leftarrow \min(w_i,\ W) \quad \text{（多余部分损失）}$$

若商店每日可消费 $S$，则玩家先消费 $\min(w_i, S)$，再截断余额。

**有效每日收益** = 实际可消费信用点 = 已消费 + min(余额, $W$) 的增量。

---

## 4. 策略空间

### 4.1 纯策略定义

| 策略 | 名称 | 定义 |
|------|------|------|
| $\sigma_0$ | 完全利他 | 每次产出线索立即赠送给随机好友（即使是自己仅有的某类型）|
| $\sigma_1$ | 完全利己 | 永不赠送 |
| $\sigma^*$ | 最优个体策略 | 当 $c_{ik}^{\text{self}} + c_{ik}^{\text{recv}} \geq 2$ 时赠出 1 条类型 $k$（即只赠多余的）|
| $\sigma_\theta$ | 阈值策略 | 当总持有量 $\geq \theta$ 且有重复时才赠出 |

### 4.2 策略空间的连续参数化

令 $\sigma_\alpha$（$\alpha \in [0,1]$）表示以概率 $\alpha$ 赠出所有自持线索、以概率 $1-\alpha$ 仅赠出重复线索。则：
- $\alpha = 1$ 对应 $\sigma_0$（完全利他）
- $\alpha = 0$ 对应 $\sigma^*$（只赠重复）
- $\sigma_1$（完全利己）在此参数化外（永不赠送）

---

## 5. 目标函数

### 5.1 个人收益

玩家 $i$ 在 $T$ 天内的**有效信用点**：

$$U_i(T) = \text{total\_spent}_i(T)$$

即 $T$ 天内实际可消费的信用点总量。

长期平均日收益：$\bar{u}_i = \lim_{T \to \infty} U_i(T) / T$

### 5.2 群体收益

$$U_{\text{group}}(T) = \sum_{i=1}^N U_i(T)$$

社会最优：$\boldsymbol{\sigma}^{\text{SW}} = \arg\max_{\boldsymbol{\sigma}} U_{\text{group}}$

### 5.3 纳什均衡

$\boldsymbol{\sigma}^{\text{NE}}$：任意玩家单方面偏离均衡策略均不能增加自身收益。

**无谓损失（Price of Anarchy）**：

$$\text{PoA} = \frac{U_{\text{group}}(\boldsymbol{\sigma}^{\text{SW}})}{U_{\text{group}}(\boldsymbol{\sigma}^{\text{NE}})}$$

---

## 6. 关键分析命题（待证）

**命题 1**（均匀分布下的集线期望）：

在均匀分布 $p_k = 1/7$ 下，单玩家无赠送/接收时，集齐7种线索的期望线索数为：

$$\mathbb{E}[\text{total clues}] = K \cdot H_K = 7 \cdot \sum_{k=1}^7 \frac{1}{k} = 7 \cdot \frac{363}{140} \approx 18.15$$

期望周期长度：$\mathbb{E}[T_{\text{cycle}}] = 18.15 / 1.2 \approx 15.1 \text{ 天}$

期望重复线索数/周期：$18.15 - 7 = 11.15$

**命题 2**（赠出重复线索是弱优势策略）：

对任意玩家 $i$，若 $c_{ik} \geq 2$（类型 $k$ 有重复），赠出一条严格优于持有：
- 赠出：+20 信用点，持有量仍满足交流条件
- 持有：0 收益，占用库存位

**命题 3**（完全利己被弱优势策略支配）：

$\sigma_1$（永不赠送）被 $\sigma^*$（赠重复）支配——$\sigma^*$ 在任何对手策略下均弱优于 $\sigma_1$。

**命题 4**（赠出唯一线索的代价估计）：

若玩家赠出其仅持有的类型 $k$ 线索（$c_{ik} = 1 \to 0$），期望延误自身交流周期约：

$$\Delta T \approx \frac{1}{p_k} \cdot \frac{1}{\lambda} \text{ 天} = \frac{7}{1.2} \approx 5.83 \text{ 天（均匀分布）}$$

对应损失信用点：$\Delta T \cdot \frac{r_E}{\mathbb{E}[T_{\text{cycle}}]} \approx 5.83 \cdot 13.9 \approx 81 \text{ 信用点}$

而赠出仅得 $r_G = 20$ 信用点，净损失约 **61 信用点**。

**命题 5**（社会最优仅在极端情况下要求赠出唯一线索）：

接收方缺 $m$ 种线索时，赠出类型 $k$（接收方恰好缺少该类型）的社会价值约为：

$$\Delta U_{\text{social}} \approx \frac{r_E}{\mathbb{E}[T_{\text{cycle}}]} \cdot \frac{1}{p_k \cdot \lambda} \cdot \frac{1}{m} \approx \frac{81}{m}$$

仅当 $m = 1$（接收方只差这一种）时 $\Delta U_{\text{social}} \approx 81 > 61$（赠出代价），社会上才值得赠唯一线索。

---

## 7. 原始假设汇总（与研究计划一致）

| 编号 | 变量 | 假设 |
|------|------|------|
| A1 | 线索类型分布 | (a) 均匀 $p_k=1/7$；(b) 非均匀 $p_7=0.4$，其余 $0.1$ |
| A2 | 线索生成速率 | 固定 $\lambda=1.2$/天（20h/条）|
| B1 | 玩家活跃度 | (a) 完全活跃；(b) 部分活跃（按概率登录）|
| B2 | 访问行为 | (a) 每个好友每天最多访问1次；(b) 同一个可多次访问 |
| C1 | 商店每日消费上限 | (a) 300；(b) 600；(c) ∞ |
| D1 | 群体规模 | $N \in \{2, 10, 50\}$ |
| D2 | 好友网络 | 全连接图（所有人互为好友）|
| D3 | 赠送目标选择 | 随机均匀选一位好友 |
