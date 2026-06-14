# 2026 世界杯动态预测系统

这是一个面向客户验收和后续 Agent 接手的世界杯动态预测产品原型。它不是静态文章，而是把单场赛前预测、比分概率、路径传导、冠军概率变化、新闻事件影响和付费解锁流程放在同一个响应式 Web App 里。

线上验收地址：[world-cup-prediction-system.pages.dev](https://world-cup-prediction-system.pages.dev/)

GitHub 仓库：[skyrim0624/world-cup-prediction-system](https://github.com/skyrim0624/world-cup-prediction-system)

## 当前状态

- 前端：React + TypeScript + Vite，已部署到 Cloudflare Pages。
- 后端：Python + FastAPI，已有 Poisson 单场比分模型、蒙特卡洛路径模拟、事件权重、后台录入和付费订单接口。
- 数据：当前是 2026 赛制骨架 + 样例球队/赛程/事件，可替换为真实授权数据。
- 线上版本：目前 Cloudflare Pages 是静态前端验收版，生产 API、日更任务、支付回调和用户权限仍需下一阶段部署。
- 产品边界：这是概率分析产品，不是投注建议产品；不承诺命中，不使用未授权商业数据，不暗示内幕信息。

## 客户验收重点

客户打开线上地址后，建议重点看这几块：

1. 首页工作台是否能快速解释“今天该看哪场、为什么重要”。
2. 单场预测是否包含胜平负、最可能比分、比分矩阵、进球市场视角。
3. 路径传导是否能说明一场比赛如何影响小组排名、晋级路径和冠军概率。
4. 冠军概率榜和今日变化榜是否适合专业博主做每日内容。
5. 新闻影响和来源权重是否能解释概率变化原因。
6. 付费锁定区是否符合“赛前预测包 / 全周期查看”的商业形态。

## 给后续 Agent 的接手说明

先读这些文件：

- `AGENTS.md`：项目规则、模型边界、开发日志。
- `README.md`：客户和 Agent 的入口说明。
- `docs/`：当前开发记录和数据导入说明。
- `handoff/customer-agent-docs/`：从 Obsidian 打包出来的客户交接文档。
- `handoff/world-cup-customer-agent-docs-2026-06-14.zip`：可直接发给客户或外部 Agent 的文档包。

关键代码位置：

- `src/App.tsx`：主要前端页面和交互。
- `src/styles.css`：页面样式、响应式布局、移动端适配。
- `backend/model.py`：单场比分概率和整届模拟核心。
- `backend/main.py`：FastAPI 接口入口。
- `backend/data_files/*.json`：球队、赛程、事件、来源权重和当前比赛配置。
- `scripts/`：数据导入、日更、新闻导入、快照生成脚本。
- `tests/`：后端模型、接口、前端契约和部署检查。

本地运行：

```bash
npm install
pip install -r requirements.txt
npm run dev:api
npm run dev
```

常用验证：

```bash
npm run build
npm run test:model
npm run validate:data
```

日更和快照：

```bash
npm run daily:update
npm run daily:check
npm run update:snapshot
```

## 后续优先级

1. 把 FastAPI 后端部署到正式 API 环境，前端接真实生产接口。
2. 接入真实 2026 官方赛程、比分、积分、红黄牌和首发数据。
3. 完成新闻源自动抓取、多源交叉验证和后台审核流。
4. 接入授权市场价格源，只作为市场热度和偏差参考。
5. 完成微信 / 支付宝支付、用户权限和付费解锁。
6. 给专业博主补截图导出、单场长图和每日选题包。

## 合规边界

- 页面输出使用“概率”“模型公平概率”“市场价格源待接入”等表达。
- 不写下注建议，不承诺预测命中，不使用未授权商业数据。
- 官方结果、赛程、积分、红黄牌、首发可以进入模型。
- 伤病、训练、发布会和媒体报道必须区分来源等级。
- 社媒传闻原则上只做风险提醒，不直接大幅改变模型。
