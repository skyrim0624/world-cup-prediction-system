# 前端界面设计记录

日期：2026-06-13

## 本次目标

为世界杯动态预测系统生成第一轮 Web App 视觉概念图，帮助后续进入 React 前端实现。

用户明确纠偏：这不是包装图、产品展示板或多设备概念板，而是 Web App 本身。因此最终保留的是三张真实浏览器页面方向的截图式概念图。

## 已生成的 Web App 方向

### 1. 绿茵场数据看板

文件：`concepts/webapp-style-01-pitch-dashboard.png`

特点：

- 绿色足球场背景，白色场线作为页面秩序。
- 页面结构清晰，偏真实可用的桌面 Web App。
- 核心模块完整：冠军概率、蒙特卡洛路径、五因子模型、新闻权重。
- 适合作为第一版 MVP 的主视觉参考。

适合采用的元素：

- 左侧冠军概率榜。
- 中间路径模拟图。
- 底部五因子卡片。
- 右侧新闻可信度权重。
- “Double tap to move modules” 的交互提示。

### 2. Forecast Lab 数据战情室

文件：`concepts/webapp-style-02-forecast-lab.png`

特点：

- 深色底，强烈世界杯专题视觉。
- 斜切色块和大面积数据卡片让页面更有冲击力。
- 模型权重、路径难度、今日变化和新闻可信度都清楚。
- 适合做付费版或专业版页面方向。

适合采用的元素：

- 左侧深色导航栏。
- “Elo + Dixon-Coles + Monte Carlo / 50,000 simulations” 模型说明条。
- 今日变化榜。
- 模型权重面板。
- 新闻可信度 S/A/B/C/D 分层。

### 3. Forecast Console 转播记分牌终端

文件：`concepts/webapp-style-03-forecast-console.png`

特点：

- 记分牌 + 像素战术终端风格。
- 有即时比赛状态、胜平负概率、球队选择、路径模拟、新闻风险。
- 情绪更强，但要控制不要变成小游戏。
- 适合做实时比赛页或单场预测页，而不一定适合作为首页主风格。

适合采用的元素：

- 顶部比分条。
- Live Win Probability 模块。
- Select Team 列表。
- News Risk 卡片。
- Source Weights 权重条。
- 底部模型因子条。

## 当前判断

最适合第一版 Web App 的方向是：

1. 首页采用 `webapp-style-01-pitch-dashboard.png` 的结构和绿色足球场语气。
2. 付费专业感和数据密度参考 `webapp-style-02-forecast-lab.png`。
3. 单场实时预测页或比赛详情页参考 `webapp-style-03-forecast-console.png`。

不采用的方向：

- 多手机壳展示板。
- 纯海报式概念板。
- 过度像小游戏的选择队伍界面。
- 与模型无关的商店、金币、随机按钮。

## 下一步

- 基于方向 1 和方向 2 合并出实际 React 页面信息架构。
- 先做桌面 Web App 首页，再适配移动端。
- 页面第一版使用 mock 数据。
- 必须保留核心业务模块：概率榜、路径模拟、五因子、新闻权重、今日变化。
