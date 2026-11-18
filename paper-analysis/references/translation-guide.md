# 中英文献翻译指南

本指南只用于**英文文献**；中文文献的字段直接提取，无需翻译。

## 语言识别

判断一篇 md 是中文还是英文：

- 取正文前若干段，统计 CJK 表意文字（`\u4e00-\u9fff`）占比：
  - CJK 占比 **> 20%** → 中文文献，直接提取
  - CJK 占比 **≤ 20%** → 英文文献，按本指南翻译
- 标题/摘要中英混杂时，以正文主体语言为准。

## 翻译原则

- **学术性**：译文符合经济学/管理学学术书面语，不用口语化表达。
- **术语一致性**：同一英文术语全文统一译名，优先采用下方对照表的既定译名。
- **意译不逐字直译**：以准确传达含义为准，不硬套字面。
- **保留学术语气**：被动语态、正式措辞可适当保留。

## 元数据规则（已与使用者确认）

| 字段 | 规则 | 例 |
| --- | --- | --- |
| 标题 | `中文译名（English Original Title）`，半角圆括号，原文保持原有大小写 | 数字化转型与创新绩效（Digital Transformation and Innovation Performance） |
| 作者 | 保留原文不译，保持原序，用「、」分隔 | Smith, J.、Chen, L. |
| 期刊 | 保留英文全称不译 | Administrative Science Quarterly |
| 年份 | 数字不变 | 2024 |

概括性字段（研究问题/理论框架/研究方法/主要发现/局限性）译为中文后，按 `extraction-guide.md` 的口径填写。

## 经管术语对照表（EN → 标准中文）

**理论类**

| 英文 | 中文 |
| --- | --- |
| resource-based view | 资源基础观 |
| dynamic capabilities | 动态能力 |
| institutional theory | 制度理论 |
| transaction cost economics | 交易成本经济学 |
| agency theory | 委托代理理论 |
| signaling theory | 信号理论 |
| stakeholder theory | 利益相关者理论 |
| upper echelons theory | 高阶理论 |
| absorptive capacity | 吸收能力 |
| organizational learning | 组织学习 |

**方法类**

| 英文 | 中文 |
| --- | --- |
| difference-in-differences (DID) | 双重差分 |
| regression discontinuity design (RDD) | 断点回归 |
| instrumental variable | 工具变量 |
| propensity score matching (PSM) | 倾向得分匹配 |
| fixed effects | 固定效应 |
| random effects | 随机效应 |
| panel data | 面板数据 |
| structural equation modeling (SEM) | 结构方程模型 |
| event study | 事件研究 |
| natural experiment | 自然实验 |
| synthetic control method | 合成控制法 |

**统计与稳健性类**

| 英文 | 中文 |
| --- | --- |
| endogeneity | 内生性 |
| robustness check | 稳健性检验 |
| heterogeneity | 异质性 |
| placebo test | 安慰剂检验 |
| multicollinearity | 多重共线性 |
| omitted variable bias | 遗漏变量偏误 |
| standard errors | 标准误 |
| moderating effect | 调节效应 |
| mediating effect | 中介效应 |
| spillover effect | 溢出效应 |
| sample selection | 样本选择 |

## 术语表定位

- 上表是「标准译名的默认约定」，提取时优先采用。
- 允许按语境补充新词（如领域专有术语），但**全文须保持一致**——同一英文术语不要一会儿译 A 一会儿译 B。
- 表未覆盖的术语按学科惯例翻译，不硬套字面意思。
