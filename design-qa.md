# Design QA - 03 单场支付收银台

source visual truth path: `/Users/andreas/Downloads/世界杯预测app 的视觉包/03-单场支付收银台.png`

implementation URL: `http://127.0.0.1:5178/checkout/netherlands/japan`

implementation screenshots:

- mobile 390: `/tmp/world-cup-checkout-mobile.png`
- comparison: `/tmp/world-cup-checkout-comparison.png`

viewport:

- mobile: 390 x 844
- implementation width cap: 430px

state: 单场支付收银台，默认选中微信支付，未创建订单。

scope:

- 只实现第 3 页单场支付收银台。
- 页面请求 `/api/public-match-summary`、`/api/access-options`、`/api/payments/config`。
- 页面创建订单时请求 `/api/payments/orders`。
- 页面不请求 `/api/match-detail`。
- 页面不展示胜平负概率、最可能比分、比分分布、五大盘面分数或后台环境变量。

full-view comparison evidence:

- 对照图路径：`/tmp/world-cup-checkout-comparison.png`。
- 页面结构对齐参考图的核心内容：返回、确认解锁标题、域名信任标识、单场预测商品卡、微信/支付宝两张支付方式卡、订单提示、金色创建订单按钮和非投注声明。
- 未复刻参考图外层 iPhone 壳，这是产品页面实现的有意处理。
- 背景使用竖屏球场资产，390px 下未压扁或横向拉伸。

focused region comparison evidence:

- 商品卡：已修复 `单场预测` 在 390px 下被挤成两行的问题，商品名、对阵、价格保持同一层级。
- 支付卡：微信和支付宝聚合成两张卡；微信内部按后端配置选择 JSAPI 或 Native，前台不提前承诺“微信内直接调起支付”。
- 安全边界：截图页面未出现 `homeWin`、`draw`、`awayWin`、`topScore`、`missingConfig` 或 `CUSTOMER_`。

verification:

- `npm run test:model`: passed, 176 tests
- `npm run build`: passed
- `GET /api/payments/config`: passed, returns `wechat_jsapi` / `wechat_native` / `alipay_qr`
- `POST /api/payments/orders`: passed, order metadata includes `matchKey=netherlands-japan`
- Playwright CLI screenshot: passed, `/tmp/world-cup-checkout-mobile.png`
- Browser plugin: blocked, `iab` unavailable
- Chrome extension: blocked, `extension` unavailable
- Scripted Playwright interaction: blocked by local package resolution; backend order creation and source-level tests cover provider/match scope

findings:

- 无 P0/P1/P2。
- P3：支付品牌图标暂用项目内可控图标表达，没有使用微信/支付宝官方品牌素材；真实上线前可替换为支付平台许可素材。

patches made:

- 新增 `/checkout/:home/:away` 收银台路由。
- 第 2 页单场 `¥1 解锁本场` 改为进入第 3 页收银台。
- 收银台接入公开赛程摘要、产品价格和支付渠道配置。
- 创建订单时写入 `contentKey`、`matchKey` 和主客队信息。
- 支付等待页确认权限时带上 `matchKey`。
- 后端订单权限判断支持 `matchKey` 范围校验。
- 新增金色足球商品图标和金色支付按钮纹理资产。

final result: passed

# Design QA - 02 单场锁定预览

source visual truth path: `/Users/andreas/Downloads/世界杯预测app 的视觉包/02-单场锁定预览.png`

implementation URL: `http://127.0.0.1:5176/match/spain/cape-verde`

implementation screenshots:

- mobile 390: `/tmp/world-cup-locked-mobile-390.png`
- desktop 1280: `/tmp/world-cup-locked-desktop-1280.png`

viewport:

- mobile: 390 x 844
- desktop: 1280 x 900
- implementation width cap: 430px

state: 未开赛单场锁定预览，用户未支付。

scope:

- 只实现第 2 页单场锁定预览。
- 页面只请求 `/api/public-match-summary` 读取公开赛程摘要。
- 页面不请求 `/api/match-detail`。
- 页面不展示胜平负概率、最可能比分具体值、比分分布具体值、预测结论或任何后台运营字段。
- 单场 `¥1` 和全包 `¥39` 按钮创建后端支付订单后进入支付等待页。

public API evidence:

- `GET /api/public-match-summary?home=spain&away=cape-verde` 只返回 `stage`、`kickoff`、`matchNo`、`status`、`homeTeam`、`awayTeam`、`homeName`、`awayName`、`homeCode`、`awayCode`。
- 接口响应未包含 `homeWin`、`draw`、`awayWin`、`topScore`、`scoreOutcomes`、`scenarioImpacts`。

full-view comparison evidence:

- 页面结构对齐参考图的核心内容：返回、标题、分享、双方队旗与队名、赛程状态、预测已生成、三条锁定预览、三条单场内容、底部 `¥1 / ¥39` 双入口和安全提示。
- 未复刻参考图外层 iPhone 壳；页面只实现 App/Web 页面本体。
- 视觉资产使用项目内球场背景 `public/assets/app/match-locked-stadium-bg-mobile-portrait.png`，390px 与桌面居中视口下均未压扁或拉伸。
- 队伍、场次和时间来自后端公开摘要，本地概念图里的荷兰/日本不写死到页面。

focused region comparison evidence:

- 底部购买入口修正后，`¥1 解锁本场` 和 `全包剩余 92 场 ¥39` 在 390px 宽度保持横排，不再按字符挤断。
- 锁定预览行只显示栏目名和模糊占位，不泄露比分、概率或预测结果。
- Browser 插件在本地页面验证中断开；本次用 Playwright CLI 完成移动端和桌面截图兜底。

verification:

- `npm run validate:data`: passed
- `npm run build`: passed
- `npm run test:model`: passed, 176 tests
- `GET /api/public-match-summary?home=spain&away=cape-verde`: passed, paid prediction fields absent
- Playwright CLI screenshots: passed, mobile and desktop captures generated

findings:

- 无 P0/P1/P2。
- P3：当前按钮默认创建 `wechat_native` 支付订单；真实上线前还需要填入微信/支付宝商户配置，否则支付等待页会显示渠道未配置状态。

patches made:

- 新增公开单场摘要接口 `/api/public-match-summary`。
- 将第 2 页改为只消费公开摘要，不再直接读取付费预测详情。
- 复原 02 锁定页结构、背景、锁定卡片和底部双付费入口。
- 补充 API 和前端契约测试，确保未支付页不泄露比分/概率字段。

final result: passed

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

# Design QA - 07 冠军概率榜

source visual truth path: `/Users/andreas/Downloads/世界杯预测app 的视觉包/07-冠军概率榜.png`

implementation URL: `http://127.0.0.1:5179/champion-board`

implementation screenshots:

- mobile 390: `research-screenshots/champion-board-390-fixed.png`
- mobile 430: `research-screenshots/champion-board-430-fixed.png`
- desktop: `research-screenshots/champion-board-desktop.png`
- comparison: `research-screenshots/champion-board-design-qa-comparison.png`

viewport:

- mobile: 390 x 844 / 430 x 932
- desktop: 1280 x 720

state: 冠军概率榜，展示最新预测快照 Top 6 队伍。

scope:

- 只实现第 7 页冠军概率榜。
- 页面请求 `/api/match-prediction?simulations=1200&useSnapshot=true`。
- 页面只读取后端返回的 `teams[].tournament.champion`、`final`、`semifinal`、`change` 以及球队名称和队码。
- 页面不展示单场胜平负、最可能比分、比分分布、支付配置或本地后台字段。

visual comparison evidence:

- 只复原 App 页面内部：状态栏、返回按钮、信息按钮、标题、副标题、通票入口、冠军概率表、底部风险提示。
- 未复原外层手机壳、球场背景和奖杯背景，避免把参考图外部包装当成产品页面资产。
- 表格行保持正常手机比例；390px 检查无横向溢出。
- 变化标签按后端 `change` 正负显示绿色或红色，不写死本地 UI 数据。

verification:

- `npm run build`: passed
- `python3 -m unittest discover -s tests -p 'test_frontend_contract.py'`: passed, 8 tests
- `npm run test:model`: passed, 176 tests
- Chrome 390 x 844 render check: passed, no horizontal overflow

findings:

- 无 P0/P1/P2。
- P3：通票入口当前按参考图显示“全包查看全部队伍”，具体 `¥39` 定价保留在付费解锁页，不塞进冠军榜标题区。

final result: passed

# Design QA - 05 已解锁完整单场预测

source visual truth path: `/Users/andreas/Downloads/世界杯预测app 的视觉包/05-已解锁完整单场预测.png`

implementation URL: `http://127.0.0.1:5174/match/netherlands/japan?unlocked=1`

implementation screenshots:

- blocked: Browser 插件在首轮成功打开并检查 DOM 后断连，后续无法重新截图；本地环境未安装 Playwright 包，不能补做最终截图对照。

viewport:

- mobile: 390 x 844
- width cap: 430px

state: 已解锁完整单场预测，仅用于第 5 页。

scope:

- 只实现第 5 页已解锁完整单场预测。
- 页面请求 `/api/match-detail`，使用后端返回的胜平负概率、最可能比分、比分分布、路径传导、五大盘面和新闻依据。
- 页面不渲染 `fairPrices`、`fairDecimal`、`fairAmerican` 或任何投注语境字段。
- 本地预览可用 `?unlocked=1`；生产可通过 `WORLD_CUP_REQUIRE_MATCH_DETAIL_PAYMENT=1` 强制要求有效 `orderId`。

backend API evidence:

- `GET /api/match-detail?home=netherlands&away=japan&simulations=1200` 返回 `pillars` 和 `newsItems`。
- `newsItems` 至少包含 3 条后端生成或事件库校验后的依据。
- 接口仍可能返回底层 `fairPrices`，但第 5 页前端未消费或展示该字段。

source-level comparison evidence:

- 页面结构对齐概念图：深色球场背景、顶部返回与已解锁状态、对阵英雄区、完整预测卡、比分分布、五大盘面、路径传导和新闻依据。
- 比分矩阵使用真实后端 `scoreMatrix`，并保持格子比例，不拉伸背景资产。
- 五大盘面使用后端 `pillars` 渲染雷达图，不使用本地静态 mock。
- 新闻依据使用后端 `newsItems`，不展示本地后台字段、配置字段或集成备注。

verification:

- `npm run build`: passed
- `npm run test:model`: passed, 176 tests
- local API check: passed, `pillars` present, `newsItems` count 3
- Browser DOM check before disconnect: page contained `完整预测`、`已解锁`、`最可能比分`、`比分分布`; console warnings/errors count 0

findings:

- 无 P0/P1/P2 source-level 问题。
- blocked: Browser 插件断连，未完成最终像素级截图对照。

patches made:

- 新增已解锁完整预测路由状态：`/match/:home/:away?unlocked=1` 或支付成功后的 `orderId`。
- 新增第 5 页完整预测组件和样式。
- 后端 `match-detail` 增加五大盘面与新闻依据字段。
- 生产环境可选开启订单权限校验。
- 支付等待页单场订单成功后跳转到已解锁单场预测页。

final result: source-level passed; visual screenshot comparison blocked
