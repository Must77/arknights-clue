# 明日方舟线索赠送策略研究计划

---

## 一、机制说明（已确认）

### 1. 线索生成
- 会客室干员每约20小时产出1条线索（可被技能加速）
- 线索共7种类型，类型随机产出
- 自持上限：10条；收到赠送的线索不占此上限
- 收到的赠送线索有效期10天

### 2. 线索赠送
- 消耗自己的1条线索
- 赠送者获得 **+20 信用点**
- 接收者获得线索 + 信用点（第1条+15，第2条+10，第3条+5）
- 无赠送次数上限

### 3. 线索交流（集齐7种触发）
- 主动发起，消耗持有的全部7种线索（每种各1条）
- 主人在交流结束后获得 **+210 信用点**
- 期间好友每次访问主人的会客室，好友获得 **+30 信用点**
- 发起后24小时有效

### 4. 访问好友线索交流
- 自己主动访问好友正在进行线索交流的会客室，可获得 **+30 信用点**
- 每天最多访问 **10次**（即每日最多+300信用点来自此项）

### 5. 被好友访问
- 自己发起线索交流期间，每次被好友访问获得 **+30 信用点**
- 每周最多被访问 **10次**（即每周最多+300信用点来自此项）
- 奖励在下一周开始时结算领取（即本周被访问的收益，下周初才能收取）

### 6. 信用点上限
- 每日结束时超过300的部分被截断
- 信用商店通常提供足够的物品供消费（消费上限视为假设参数）

---

## 二、研究问题

> **核心问题**：在一个由 N 名玩家组成的互动群体中，玩家采取何种线索赠送策略，能够：
> 1. **最大化个人**长期每日信用点收益？
> 2. **最大化群体**长期信用点总收益？
> 3. 群体博弈的**纳什均衡**是什么？该均衡与社会最优是否一致？

**策略空间定义**：策略 s ∈ {0, ..., 1} 的连续谱，其中：
- **s = 0（最大利他）**：只要自己持有任何线索，立即赠送，无论是否已集齐7种
- **s = 1（最大利己）**：永远不赠送，所有线索留给自己集满7种做线索交流
- **中间策略**：例如"只赠送多余的重复线索"、"集齐7种后再赠送"等阈值策略

---

## 三、原始假设（需在研究中探讨的参数）

### A. 线索系统假设

| 假设编号 | 变量 | 假设选项 |
|---------|------|---------|
| A1 | 7种线索概率分布 | (a) 均匀分布 1/7；(b) 非均匀（7号更高概率） |
| A2 | 线索生成速率 | (a) 固定 20h/条；(b) 含干员技能加成（+15%~+35%） |
| A3 | 玩家自持线索上限 | 固定为10条 |
| A4 | 收到赠送线索的有效期行为 | (a) 玩家总能在10天内使用；(b) 存在到期丢失概率 |

### B. 玩家行为假设

| 假设编号 | 变量 | 假设选项 |
|---------|------|---------|
| B1 | 玩家活跃度 | (a) 完全活跃（每天登录、访问好友、消费信用点）；(b) 部分活跃（按概率） |
| B2 | 玩家是否完全理性 | (a) 完全理性（最大化预期收益）；(b) 行为经济学（互惠偏好、利他偏好） |
| B3 | 好友关系是否对称 | (a) 互相为好友（双向）；(b) 单向访问 |
| B4 | 玩家访问好友的行为 | (a) 总是最大化访问（每天访问10次）；(b) 随机/部分访问 |

### C. 信用点系统假设

| 假设编号 | 变量 | 假设选项 |
|---------|------|---------|
| C1 | 信用商店每日消费上限 | (a) 300（刚好等于每日截断上限）；(b) 400；(c) 600；(d) 800+ |
| C2 | 每日300截断的影响 | (a) 截断总是发生（玩家收益≥300时）；(b) 玩家总能及时消费 |
| C3 | 线索交流210信用点是否被截断 | 取决于C1和当日其他信用点来源 |

### D. 群体结构假设

| 假设编号 | 变量 | 假设选项 |
|---------|------|---------|
| D1 | 群体规模 N | (a) N=2（双人对称）；(b) N=10（小群体）；(c) N=50（大群体） |
| D2 | 好友网络结构 | (a) 全连接（所有人互为好友）；(b) 随机网络；(c) 小世界网络 |
| D3 | 群体策略异质性 | (a) 所有人策略相同；(b) 混合策略群体 |
| D4 | 重复博弈时间跨度 | (a) 单次博弈；(b) 有限期重复博弈；(c) 无限期重复博弈 |

---

## 四、研究方向

### 方向 A：形式化建模
**目标**：构建数学模型，为后续分析奠基

- 定义状态空间：玩家的线索持有向量 $\mathbf{c} = (c_1, ..., c_7)$
- 定义策略类：纯策略（阈值策略）与混合策略
- 定义单期收益函数 $R(s_i, \mathbf{s}_{-i}, \mathbf{c})$
- 建立状态转移方程（线索生成、赠送、交流的马尔可夫过程）

### 方向 B：单人最优分析（固定他人策略）
**目标**：给定他人策略已知，求个人最优响应

- 关键权衡：赠出1条线索 = +20信用点 vs 可能延迟自己的线索交流（延迟成本）
- 分析集齐7种线索的期望线索总数（与分布假设A1有关）
- 求解：什么条件下赠送比囤积合算？

### 方向 C：群体最优（社会规划者视角）
**目标**：找到使总信用点最大化的策略分配

- 对比完全利他 vs 完全利己下群体总收益
- 分析群体规模 N 和好友网络结构对最优策略的影响
- 关键问题：若所有人都完全利他，群体总收益是否最高？

### 方向 D：博弈论分析
**目标**：求纳什均衡，分析是否存在社会困境

- 建立 N 人策略式博弈
- 求纯策略纳什均衡（可能为"永不赠送"）
- 分析重复博弈中合作能否通过声誉/互惠机制维持（Folk Theorem）
- 对比均衡收益 vs 社会最优收益的效率损失（Price of Anarchy）

### 方向 E：Monte Carlo 仿真验证
**目标**：数值验证理论结论，探索参数敏感性

- 实现线索生成、赠送、交流全流程仿真
- 参数扫描：N、策略 s、线索分布、信用商店容量
- 可视化：策略-收益热图、群体总收益随 N 变化曲线

---

## 五、研究路径

```
A（建模）→ B（单人最优）→ D（均衡分析）
                              ↓
               C（社会最优）→ 对比 PoA → E（仿真验证） → 结论
```

---

## 六、相关文献

### 最相关方向

**公共物品博弈（Public Goods Games）**
- Cooperation and control in multiplayer social dilemmas – *PNAS*
- Explaining Cooperative Behavior in Public Goods Games – *MDPI Games* (2021)
- Decisions of Public Goods Game Through the lens of Game Theory – *arXiv:2511.15686*
- Participation Incentives in Online Cooperative Games – *arXiv:2502.19791*

**礼物交换与互惠（Gift Exchange & Reciprocity）**
- Reciprocity in Gift-Exchange-Games – *ResearchGate*
- Classical and belief-based gift exchange models – *ScienceDirect*
- Friendship, Altruism, and Reward Sharing in Stable Matching and Contribution Games – *arXiv:1204.5780*
- The Shared Reward Dilemma – *arXiv:0707.2587*

**公地悲剧与社交游戏（Tragedy of Commons in Games）**
- Tragedies of the ludic commons: understanding cooperation in multiplayer games – *Game Studies* (2013)
- The Tragedy of the Commons in Multi-Population Resource Games – *arXiv:2602.20603*

**重复博弈与合作维持**
- Iterated Prisoner's Dilemma contains strategies that dominate any evolutionary opponent – *PNAS* (2013)
- Properties of winning Iterated Prisoner's Dilemma strategies – *PLOS Comp. Bio.* (2024)

**奖励分配与合作博弈**
- Multi-Player Resource-Sharing Games with Fair Reward Allocation – *arXiv:2402.05300*
- Interplay of Reward and Size of Groups in Optional Public Goods Game – *arXiv:2409.14311*

**声誉与信用系统**
- An evolutionary game model with reputation threshold and reputation score – *Scientific Reports* (2025)
- Cooperation and Reputation Dynamics with Reinforcement Learning – *arXiv:2102.07523*

### 补充参考（Gacha游戏经济分析）
- Gacha Game: When Prospect Theory Meets Optimal Pricing – *arXiv:2208.03602*
- Gacha Game Analysis and Design – *ACM SIGMETRICS* (2023)

> **注**：目前未发现专门分析明日方舟基建线索机制的学术论文，本研究具有一定的原创性。

---

## 七、预期输出

1. `model.md` — 形式化数学模型
2. `analysis_individual.md` — 单人最优分析
3. `analysis_social.md` — 社会最优与博弈均衡
4. `simulation/` — Python 仿真代码
5. `results/` — 仿真结果与可视化
6. `conclusion.md` — 策略建议与结论

