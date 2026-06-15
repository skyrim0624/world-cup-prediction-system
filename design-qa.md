# Design QA - 01 未开赛比赛列表

source visual truth path: `/Users/andreas/Downloads/世界杯预测app 的视觉包/01-未开赛比赛列表.png`

implementation URL: `http://127.0.0.1:5175/`

implementation screenshots:

- blocked: Browser 插件拦截本地 URL 访问，未能完成截图对照；未使用 Playwright CLI 或其它绕路方式。

viewport:

- intended mobile target: 390 x 844 / 430 x 932
- implementation width cap: 430px

state: 公开未开赛比赛列表，默认 `今日` tab。

scope:

- 只实现第 1 页未开赛列表。
- 首页只请求 `/api/public-upcoming-matches?limit=12`。
- 首页不请求 `/api/match-prediction` 或 `/api/upcoming-matches`。
- 首页不展示胜平负概率、最可能比分、比分分布、预测结论。

public API evidence:

- `GET /api/public-upcoming-matches?limit=3` 只返回 `stage`、`kickoff`、`matchNo`、`status`、`homeTeam`、`awayTeam`、`homeName`、`awayName`、`homeCode`、`awayCode`。
- 接口响应未包含 `homeWin`、`draw`、`awayWin`、`topScore`。

source-level comparison evidence:

- 页面结构对齐概念图：顶部品牌区、页面标题、今日/明日/全部筛选、未开赛比赛卡片、底部全包 39 元固定入口、安全支付提示。
- 比赛卡片只展示基础赛程和双方信息，单场预测入口显示 `¥1`。
- 底部通票入口显示 `全包剩余 92 场 ¥39`。
- 背景使用项目内球场视觉资产 `public/assets/app/stadium-bg-mobile-portrait.png`，未拉伸成横向比例。

verification:

- `npm run build`: passed
- `python3 -m unittest discover -s tests -p 'test_frontend_contract.py'`: passed, 8 tests
- `python3 -m unittest discover -s tests -p 'test_api.py'`: passed, 37 tests

findings:

- 无 P0/P1/P2 source-level 泄露问题。
- blocked: Browser 本地 URL 策略阻止截图对照，因此未完成真实渲染像素级 QA。

patches made since previous QA pass:

- 首页改为公开未开赛比赛列表，默认展示今日赛程。
- 首页数据源切到后端公开接口。
- 删除首页免费预览中的比分/概率/预测字段。
- 调整移动端布局、卡片比例、固定底部通票入口和安全提示。

final result: source-level passed; visual screenshot comparison blocked

# Design QA - 04 支付等待刷新状态

source visual truth path: `/Users/andreas/Downloads/世界杯预测app 的视觉包/04-支付等待刷新状态.png`

implementation URL: `http://127.0.0.1:5179/payment/pending?orderId=pay_de620cc83f3749559174f3a74de453c7`

implementation screenshots:

- mobile: `/tmp/world-cup-payment-pending-default-mobile.png`
- desktop: `/tmp/world-cup-payment-pending-desktop.png`

viewport:

- mobile: 430 x 932
- desktop: 1280 x 720

state: 微信 Native 单场预测订单，`customer_interface_ready`，未返回真实 `qrCodeUrl`。

full-view comparison evidence:

- 页面结构已对齐参考图的核心内容区：返回按钮、标题、订单状态卡、订单明细、二维码区域、刷新状态按钮、返回支付方式按钮、安全提示。
- 未复刻参考图里的 iPhone 外壳、Safari 地址栏和底部浏览器工具栏，这是产品页面实现的有意处理。
- 二维码区域保持 1:1 正方形，未压扁或拉伸。

focused region comparison evidence:

- 订单卡：产品、支付方式、创建时间、过期时间、金额、状态标签均由后端订单字段渲染。
- 安全边界：截图 DOM 检查未出现 `CUSTOMER_`、`missingConfig`、`nextAction`、`integrationOwner`。
- 付费边界：页面未展示胜平负、最可能比分、比分分布等预测内容。

findings:

- 无 P0/P1/P2。
- P3：当前本地订单没有真实 `qrCodeUrl`，二维码区显示“二维码待返回”，不是参考图的真实二维码。这是接入真实支付前的有意状态，不生成假二维码。

patches made since previous QA pass:

- 缩短二维码提示文案，避免“返回”单独换行造成误读。
- 压紧订单头部排版，减少订单标题换行。
- 同步后端支付产品价格和客户支付渠道口径。

final result: passed
