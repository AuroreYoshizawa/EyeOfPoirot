# 波洛之眼（Eye of Poirot）

**FIFA 世界杯纪律记录的制裁暴露（sanction exposure）指标，2014–2026。**

[![reproducibility](https://github.com/AuroreYoshizawa/EyeOfPoirot/actions/workflows/ci.yml/badge.svg)](https://github.com/AuroreYoshizawa/EyeOfPoirot/actions/workflows/ci.yml)

[English version → README.md](README.md)

> **冻结范围（2026-07-13）。** 纳入 2014、2018、2022 三届完整赛事，以及
> 2026 年已完成的 M1–M100；尚未进行的 M101–M104 不纳入。方法 v0.2 在
> M101 开赛前冻结，并于同日、仍在 M101 与任何注册提交之前修订为
> v0.2.1（恢复四条委托口径并新增一条；五处变更及其方向见方法文档 §6
> 与 `docs/AMENDMENTS.md`）。

> **草案警告。** `figures/draft-2026-07/` 中的九张图使用已经废止的
> `W1/D1/W2/W2*` 口径，只为保留溯源，不能作为冻结口径的结果引用。
> `figures/official/` 下的四届正式图使用冻结后的 `E_m`、`E_s`、`e_m`、`e_s`。

## 项目测量什么

每张牌的时间、持续影响和后果都不同。本项目把球员牌转换为可审计的
**制裁暴露分钟**，分成两组指标：

- **比赛暴露 `E_m`**：出牌后剩余的实际比赛时间，红牌使用预先规定的
  倍率；淘汰赛输出本方减对手的 `ΔE_m` 与按犯规归一化的 `Δe_m`。
- **停赛暴露 `E_s`**：只计纪律记录对淘汰赛的影响——黄牌到相应清零点的
  风险区间、在淘汰赛场次实际执行的停赛损失，以及得牌球员的机会权重
  `ω`；小组赛黄牌只以 2014–2022 的"带入黄牌"形式进入；主指标 `e_s`
  除以该队全赛事犯规数（不含三四名决赛）。

这些是描述统计，不识别动机或因果。完整定义与不作何种结论的边界见
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md)。

## v0.2.1 已冻结决定

| 项目 | 决定 |
|---|---|
| 届别 | 2014、2018、2022 完整；2026 截至 M100 |
| 比赛终点 | `T_end − 出牌分钟`；含补时和加时，不含点球大战 |
| 停赛暴露范围 | 只计淘汰赛影响：小组赛牌不直接产生条目；小组赛挣得的停赛只在淘汰赛场次执行时计入 |
| 带入黄牌 | 2014–2022 带着一张未清小组赛黄牌进入淘汰赛，视同淘汰赛首战第 0 分钟领牌（十六强场次即 180 分钟） |
| 2026 黄牌 | 小组赛后清零，四分之一决赛后再次清零；没有任何带入 |
| 停止规则 | 后续导致停赛的牌以分钟粒度截停前一张黄牌的风险区间 |
| 精确钟例外 | 补时/加时获得的黄牌，以及半决赛、决赛的全部黄牌，按 `T_end − t` 计 |
| 三四名决赛 | 事件层排除（不产生暴露条目、犯规不入分母）；在该场执行的停赛与可用性数据仍计 |
| 球队出局 | 不提前截断潜在累计风险窗口 |
| 主参数 | 罚下倍率 `ρ = 2`；实际执行停赛倍率 `μ = 1.25` |
| 机会权重 | 球员出场分钟 ÷（球队标准分钟 − 有证据的不可用时间区间） |
| 主分母 | 小组赛与淘汰赛合计的球队犯规数，不含三四名决赛 |
| 深度检查 | 预先声明的分届 Kendall `τ_b`（出场场次 × `e_s`）；绝不跨届合并 |
| 人员范围 | 指标只计球员牌；教练组/官员牌另行审计 |

### 已冻结的扩展队列修订

2026-07-14 批准的修订新增全队列 `E_s^grp`/`E_s^all`、标注为次要分析的
`lambda=0.5` 变体、删除异议/拖延时间牌后的稳健性结果、MD2 加淘汰赛次要
指标，以及描述性的累计犯规表。这些均为新增输出，不替换已注册的 v0.2.1
主表。当前所有 2026 修订输出均标为 `provisional_M100`；尚未摄入
M101–M104，确认性重跑仍在 M104 之后进行。详见
[`docs/AMENDMENTS.md`](docs/AMENDMENTS.md) 与
[`docs/RESULTS.md`](docs/RESULTS.md)。

## 数据与复现

仓库把可公开的衍生事实与权利敏感的原始快照分开：

```text
data/raw/       私有且被 gitignore 的原始快照
data/derived/   公开的标准化与衍生 CSV
pipeline/       采集、构建、验证、作图与一键编排
tests/          人工核对样例与性质测试
figures/        正式结果图及明确标注的旧草案归档
```

复现接口分两条路径：

```bash
# 公共路径：从已提交的衍生表重建结果与图
python3 -m pipeline.build_all --from-derived

# 原始档案持有者：从原始快照重建全部衍生表、结果与图
python3 -m pipeline.build_all --from-raw
```

两条路径都只依赖 Python 标准库。公共路径不发起网络请求，并已在没有
`data/raw/` 的副本中通过。结果见 [`docs/RESULTS.md`](docs/RESULTS.md)，进度
与有来源的纪律决定见 [`docs/BUILD_STATUS.md`](docs/BUILD_STATUS.md)，数据
来源与权利边界见 [`data/README.md`](data/README.md)。

## 来源优先级

1. FIFA calendar、timeline/event、球队统计、match centre 与官方比赛报告；
2. 足协或俱乐部对球员可用性或纪律决定的声明；
3. 可靠媒体的伤病、疾病与出牌原因报道；
4. FotMob、Transfermarkt、Wikipedia 只作为有记录的回退源或交叉核对。

2014 年终场时间是声明过的例外：FIFA 归档事件流缺少可用的终场节标记，
因此用已归档的 FotMob 各节时间重建 `T_end`；点球大战时间不计入。2014
球队犯规总数来自已归档、注明由 Opta 提供数据的 HuffPost 世界杯统计页；
FotMob 中可用的 19 场作为独立交叉核对层保留。

## 注册与发布状态

- Methodology v0.2.1、标准化表、测试、图表与 2026-07-13 SHA-256 清单：
  已在本地准备并验收。
- OSF 公开 Open-Ended Registration（方法 v0.2.1，2026-07-13 于 M101 前冻结并注册）：
  [https://doi.org/10.17605/OSF.IO/3GESM](https://doi.org/10.17605/OSF.IO/3GESM)。
- OSF 复现快照注册（同一注册树的组件，公开；内容为 commit 88fd47c 的公开树 zip）：
  [https://doi.org/10.17605/OSF.IO/TW48K](https://doi.org/10.17605/OSF.IO/TW48K)。
  原计划的四年禁运未启用：快照内容即已公开的仓库树，仓库公开后已无可禁运之物。
- GitHub 公开仓库与复现工作流：
  [AuroreYoshizawa/EyeOfPoirot](https://github.com/AuroreYoshizawa/EyeOfPoirot)。

项目名、上传分层与必须手动完成的步骤见
[`docs/REGISTRATION.md`](docs/REGISTRATION.md)。需要账户确认的操作不会自动执行。

## 先验草案与修订

分析者在冻结 v0.2 前看过以阿根廷为中心的探索性结果。方法文档已披露该
先验知识、草案中的两处规则错误，以及同日完成的 v0.2.1 注册前修订。
冻结后的变更只追加到
[`docs/AMENDMENTS.md`](docs/AMENDMENTS.md)，不静默回改。

## 合作与报错

欢迎独立重采集、足球规则复核和对抗性审查。报错请在 GitHub issue 中写明
届别、比赛编号、来源 URL 与受影响的衍生表行；不要上传受版权保护的原始
报告或私人通信。

## 许可与引用

代码使用 MIT（`LICENSE-CODE`）；项目原创文档、原创图和不含第三方权利
限制的项目衍生表使用 CC BY 4.0（`LICENSE`）。

[![StatsBomb logo](https://raw.githubusercontent.com/statsbomb/open-data/master/img/SB%20-%20Icon%20Lockup%20-%20Colour%20positive.png)](https://statsbomb.com)

**Data source: StatsBomb.** `sb_foul_linked`、四行 StatsBomb 聚合核对表、
2018/2022 事件分段与公开累计犯规计数，以及报告中的相应段落，均属于基于
StatsBomb Open Data 形成的分析，继续受
[StatsBomb Public Data User Agreement](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf)
及其非商业限制约束，不纳入本项目的 CC BY 4.0 再许可。事件级 StatsBomb
记录只保留在 Git 忽略的私有 raw 档案中，不公开再分发；StatsBomb 标志与
商标也不纳入仓库许可。公开发布前，档案负责人还须人工确认已完成协议所
请求的 [StatsBomb Resource Centre](https://statsbomb.com/resource-centre/)
姓名与邮箱登记；构建程序无法验证这一外部事项。

公开累计犯规 CSV 只含项目标识符与衍生计数。StatsBomb 比赛/事件标识符、
序列号、排序键和关联事件引用只保留在 Git 忽略的私有 sidecar；公开链接
只指向 StatsBomb 数据集主页。

仓库也不分发或重新许可 FIFA/FotMob 原始页面、报告及其他第三方材料。
引用信息见 [`CITATION.cff`](CITATION.cff)。
