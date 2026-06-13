# 前端界面设计记录

日期：2026-06-13

## 本次目标

为世界杯动态预测系统生成第一轮 Web App 视觉概念图，帮助后续进入 React 前端实现。

用户明确纠偏：这不是包装图、产品展示板或多设备概念板，而是 Web App 本身。因此最终保留的是三张真实浏览器页面方向的截图式概念图。

用户追加要求：不止电脑端，也要方便移动端用浏览器访问。因此前端不是“先桌面再缩小”，而是响应式 Web App：桌面端负责完整数据视野，移动端负责单列滚动、触控优先和核心信息不丢失。

## 已生成的 Web App 方向

### 1. 绿茵场数据看板

文件：`concepts/webapp-style-01-pitch-dashboard.png`
移动版文件：`concepts/mobile-style-01-pitch-dashboard.png`

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

移动端处理：

- 单列卡片堆叠。
- 顶部保留产品名、Pro 入口和菜单。
- 概率榜、五因子、路径模拟、新闻权重按优先级纵向排列。
- 底部保留付费入口。

### 2. Forecast Lab 数据战情室

文件：`concepts/webapp-style-02-forecast-lab.png`
移动版文件：`concepts/mobile-style-02-forecast-lab.png`

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

移动端处理：

- 用大卡片承载 Champion Probability、Today’s Movers、Model Engine、News Credibility。
- 不把桌面表格硬缩小。
- 路径模块可放到下一屏或折叠卡。
- 适合作为移动付费首页的高冲击方向。

### 3. Forecast Console 转播记分牌终端

文件：`concepts/webapp-style-03-forecast-console.png`
移动版文件：`concepts/mobile-style-03-forecast-console.png`

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

移动端处理：

- 顶部保留比分条和 Live Win Probability。
- Team Selector、Path Preview、News Risk、Model Factors 分段向下滚动。
- 适合单场实时预测页，而不是主首页。

## 当前判断

最适合第一版响应式 Web App 的方向是：

1. 首页采用 `webapp-style-01-pitch-dashboard.png` 的结构和绿色足球场语气。
2. 付费专业感和数据密度参考 `webapp-style-02-forecast-lab.png`。
3. 单场实时预测页或比赛详情页参考 `webapp-style-03-forecast-console.png`。
4. 移动端不是桌面端裁切，必须参考三张 `mobile-style-*` 图单独设计信息顺序。

不采用的方向：

- 多手机壳展示板。
- 纯海报式概念板。
- 过度像小游戏的选择队伍界面。
- 与模型无关的商店、金币、随机按钮。

## 下一步

- 基于方向 1 和方向 2 合并出实际 React 页面信息架构。
- 同步做桌面和移动浏览器布局。
- 页面第一版使用 mock 数据。
- 必须保留核心业务模块：概率榜、路径模拟、五因子、新闻权重、今日变化。

## MVP 实现记录：Forecast Console

日期：2026-06-13

本轮用户选定第三种视觉方向，即 `mobile-style-03-forecast-console.png` 的转播记分牌终端风格。MVP 已按真实 Web App 实现，不是包装图或静态展示图。

已实现内容：

- React + TypeScript + Vite 单页应用。
- 顶部 Forecast Console 品牌栏、Pro 入口和菜单按钮。
- 比分条：BRA 4 - 3 ARG、90:00、+6，并使用代码生成的国旗和战术小场图。
- Live Win Probability：Home / Draw / Away 三项实时胜平负概率。
- 底层模型提示：`Elo + Dixon-Coles + Monte Carlo`。
- Select Team：巴西、阿根廷、西班牙、法国，点击后切换当前球队。
- Path Simulation：小组赛到决赛路径预览。
- News Risk：官方伤病、记者训练信息、无效传闻三类新闻风险。
- Source Weights：S/A/B/C/D 五级新闻来源权重。
- 三层模型：一层底层概率引擎、二层事件与新闻修正、三层产品解释盘面。
- Model Factors：Overall、Attack、Defense、Goalkeeper、Path、Squad。
- 预测权重因子：基础实力、攻防质量、晋级路径、阵容健康、主帅凝聚、关键人物、战术克制、定位球门将、旅程气候、市场舆论。
- 双击或双击触控后进入模块移动模式，点击底部提示也可以切换。

本轮验证：

- `npm run build` 通过。
- 使用内置浏览器打开 `http://localhost:5173/` 验证。
- `127.0.0.1` 受旧 Service Worker 污染，因此本轮浏览器验证使用 `localhost` 这个干净 origin。
- 桌面 1280px、移动 864px、窄屏 390px 均验证 `scrollWidth == clientWidth`，没有横向溢出。
- 交互验证：点击 Argentina 后，`Model Factors` 标题同步变为 `Model Factors · Argentina`。
- 交互验证：双击页面后，底部提示变为 `Modules unlocked`。

当前有意保留的偏差：

- 参考图原本只有单场实时预测模块，本轮按用户要求新增了“三层模型”和“预测权重因子”，因此页面长度会超过参考图。
- MVP 先用 mock 数据和静态新闻样例，后续再接后端模拟、新闻抓取和真实权重更新。
