import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";

type TeamKey = string;
type Tone = "green" | "blue" | "gold" | "orange" | "red" | "muted";
type FactorImpactMap = Record<string, Record<string, number>>;

type Team = {
  key: TeamKey;
  name: string;
  code: string;
  factors: Record<string, number>;
  tournament: {
    champion: number;
    final: number;
    semifinal: number;
    quarterfinal: number;
    change: number;
  };
};

type NewsItem = {
  title: string;
  detail: string;
  impact: string;
  tone: Tone;
  time: string;
};

type ReviewStatus = "confirmed" | "multi_source" | "single_source" | "unverified" | "rumor";

type EventReviewSummary = {
  watched: number;
  applied: number;
  ignored: number;
  reviewRequired: number;
};

type EventReviewItem = NewsItem & {
  id?: string | null;
  team: TeamKey | null;
  source: string;
  sourceLevel: string;
  status: ReviewStatus;
  action: "apply" | "watch" | "ignore";
  factor: string;
  direction: number;
  strength: number;
  url?: string | null;
};

type EventReviewResponse = {
  summary: EventReviewSummary;
  rawNewsCount: number;
  items: EventReviewItem[];
};

type AdminAuditEntry = {
  time: string;
  action: string;
  targetId: string;
  details: Record<string, unknown>;
};

type DailyUpdateStatus = {
  status: string;
  updatedAt: string;
  error?: string;
  feeds?: {
    imported: number;
    skipped: number;
    items: unknown[];
  };
  snapshot?: {
    path: string;
    simulationCount: number;
    lockedResults: number;
    liveMatches: number;
    events: EventReviewSummary;
  };
};

type TournamentBackup = {
  backupId: string;
  path: string;
  createdAt: string;
  isComplete: boolean;
};

type DailyUpdateHealth = {
  status: "missing" | "fresh" | "stale" | "failed" | string;
  label: string;
  hoursSinceUpdate: number | null;
  message: string;
};

function formatDailyStatus(status?: string) {
  if (status === "success") return "成功";
  if (status === "failed") return "失败";
  return status ?? "待更新";
}

function dailyHealthTone(status?: string) {
  if (status === "fresh") return "green";
  if (status === "stale") return "gold";
  if (status === "failed") return "red";
  return "";
}

type AdminOverview = {
  fixtureStatus: {
    scheduled: number;
    live: number;
    finished: number;
  };
  datasetHealth: {
    teamCount: number;
    fixtureCount: number;
    placeholderSlots: number;
    isOfficialDataReady: boolean;
  };
  eventSummary: EventReviewSummary;
  rawNewsCount: number;
  reviewQueue: EventReviewItem[];
  authRequired: boolean;
  recentAudit: AdminAuditEntry[];
  tournamentBackups: TournamentBackup[];
  latestSnapshot: {
    type: string;
    generatedAt: string;
    path: string;
  } | null;
  dailyUpdateStatus: DailyUpdateStatus | null;
  dailyUpdateHealth: DailyUpdateHealth;
  operations: {
    dailyUpdateCommand: string;
    snapshotRebuildEndpoint: string;
    rawNewsEndpoint: string;
    eventReviewEndpoint: string;
    liveScoreEndpoint: string;
    resultEndpoint: string;
    tournamentImportEndpoint: string;
    tournamentRollbackEndpoint: string;
  };
};

type ScoreOutcome = {
  score: string;
  probability: number;
  note: string;
  tone: Tone;
};

type UpcomingMatch = {
  stage: string;
  kickoff: string;
  matchNo?: number | null;
  city?: string | null;
  stadium?: string | null;
  status: string;
  homeTeam: TeamKey;
  awayTeam: TeamKey;
  homeName: string;
  awayName: string;
  homeCode: string;
  awayCode: string;
  homeWin: number;
  draw: number;
  awayWin: number;
  topScore: {
    score: string;
    probability: number;
  };
};

type UpcomingMatchesResponse = {
  updatedAt: string;
  count: number;
  items: UpcomingMatch[];
};

type FinishedMatch = {
  stage: string;
  kickoff: string;
  matchNo?: number | null;
  city?: string | null;
  stadium?: string | null;
  status: string;
  homeTeam: TeamKey;
  awayTeam: TeamKey;
  homeName: string;
  awayName: string;
  homeCode: string;
  awayCode: string;
  homeScore: number;
  awayScore: number;
  modelUse: string;
  modelUseLabel: string;
};

type FinishedMatchesResponse = {
  updatedAt: string;
  count: number;
  items: FinishedMatch[];
};

type AccessProduct = {
  key: string;
  name: string;
  scope: string;
  amountLabel?: string;
  status: string;
};

type AccessOptions = {
  paymentConfigured: boolean;
  products: AccessProduct[];
  disclaimer: string;
};

type PaymentProviderKey = "wechat" | "alipay";

type PaymentProviderConfig = {
  provider: PaymentProviderKey;
  label: string;
  paymentMethod: string;
  configured: boolean;
  missingConfig: string[];
};

type PaymentConfig = {
  ready: boolean;
  providers: PaymentProviderConfig[];
  disclaimer: string;
};

type PaymentOrder = {
  orderId: string;
  productKey: string;
  productName: string;
  amountLabel: string;
  provider: PaymentProviderKey;
  providerLabel: string;
  paymentMethod: string;
  status: string;
  qrCodeUrl: string | null;
  missingConfig: string[];
  nextAction: string;
  createdAt: string;
  expiresAt: string;
};

type AccessDecision = {
  allowed: boolean;
  reason: string;
  orderId?: string;
  productKey?: string | null;
  paymentStatus?: string | null;
  requiredProducts: string[];
};

type ScenarioImpact = {
  label: string;
  probability: number;
  title: string;
  details: string[];
  championShift: string;
  tone: Tone;
};

type DailyMover = {
  team: TeamKey;
  name: string;
  code: string;
  previousChampion: number;
  currentChampion: number;
  change: number;
  direction: "up" | "down";
  reason: string;
  reasons?: string[];
};

type DailyMovers = {
  baseline: "previous_snapshot" | "no_previous_snapshot" | string;
  items: DailyMover[];
  summary: {
    up: number;
    down: number;
    largestUp: DailyMover | null;
    largestDown: DailyMover | null;
  };
};

type MatchPrediction = {
  stage: string;
  kickoff: string;
  matchNo?: number | null;
  city?: string | null;
  stadium?: string | null;
  status: string;
  homeTeam: TeamKey;
  awayTeam: TeamKey;
  homeWin: number;
  draw: number;
  awayWin: number;
  updatedAt: string;
  scoreOutcomes: ScoreOutcome[];
  scenarioImpacts: ScenarioImpact[];
  analysis: string[];
  newsItems: NewsItem[];
  teams?: Team[];
  dailyMovers?: DailyMovers;
  modelMeta?: {
    engine: string;
    simulationCount: number;
    lockedResults: number;
    liveMatches?: number;
    dataset?: {
      source: string;
      teamCount: number;
      fixtureCount: number;
      eventCount: number;
      placeholderSlots?: number;
    };
    events?: {
      watched: number;
      applied: number;
      ignored: number;
      reviewRequired?: number;
    };
    factorImpacts?: FactorImpactMap;
    fixtureContextImpacts?: FactorImpactMap;
  };
};

type MatchDetail = {
  stage: string;
  kickoff: string;
  matchNo?: number | null;
  city?: string | null;
  stadium?: string | null;
  status: string;
  homeTeam: TeamKey;
  awayTeam: TeamKey;
  homeName?: string;
  awayName?: string;
  homeCode?: string;
  awayCode?: string;
  homeWin: number;
  draw: number;
  awayWin: number;
  updatedAt: string;
  scoreOutcomes: ScoreOutcome[];
  scenarioImpacts: ScenarioImpact[];
  analysis: string[];
};

type DatasetMeta = NonNullable<MatchPrediction["modelMeta"]>["dataset"];

function fixtureVenueLabel(fixture: { city?: string | null; stadium?: string | null }) {
  return [fixture.stadium, fixture.city].filter(Boolean).join(" · ");
}

const teams: Team[] = [
  {
    key: "brazil",
    name: "巴西",
    code: "BRA",
    factors: { strength: 88, form: 86, path: 76, squad: 84, margin: 84 },
    tournament: { champion: 12.8, final: 25.4, semifinal: 41.2, quarterfinal: 63.8, change: 0.7 },
  },
  {
    key: "argentina",
    name: "阿根廷",
    code: "ARG",
    factors: { strength: 86, form: 84, path: 72, squad: 82, margin: 82 },
    tournament: { champion: 10.9, final: 22.6, semifinal: 38.4, quarterfinal: 60.1, change: -0.4 },
  },
  {
    key: "spain",
    name: "西班牙",
    code: "ESP",
    factors: { strength: 91, form: 87, path: 79, squad: 87, margin: 85 },
    tournament: { champion: 13.6, final: 26.1, semifinal: 43.7, quarterfinal: 66.4, change: 0.3 },
  },
  {
    key: "france",
    name: "法国",
    code: "FRA",
    factors: { strength: 90, form: 88, path: 74, squad: 89, margin: 87 },
    tournament: { champion: 13.1, final: 25.9, semifinal: 42.5, quarterfinal: 64.9, change: -0.2 },
  },
  {
    key: "england",
    name: "英格兰",
    code: "ENG",
    factors: { strength: 85, form: 85, path: 73, squad: 83, margin: 83 },
    tournament: { champion: 9.8, final: 20.2, semifinal: 35.1, quarterfinal: 58.5, change: 0.1 },
  },
  {
    key: "portugal",
    name: "葡萄牙",
    code: "POR",
    factors: { strength: 84, form: 84, path: 70, squad: 82, margin: 81 },
    tournament: { champion: 8.7, final: 18.4, semifinal: 32.6, quarterfinal: 55.2, change: -0.1 },
  },
  {
    key: "germany",
    name: "德国",
    code: "GER",
    factors: { strength: 82, form: 83, path: 71, squad: 81, margin: 83 },
    tournament: { champion: 7.9, final: 17.2, semifinal: 30.4, quarterfinal: 53.8, change: 0.2 },
  },
  {
    key: "netherlands",
    name: "荷兰",
    code: "NED",
    factors: { strength: 82, form: 83, path: 69, squad: 80, margin: 83 },
    tournament: { champion: 7.1, final: 15.8, semifinal: 28.6, quarterfinal: 51.9, change: -0.3 },
  },
];

const modelLayers = [
  {
    layer: "一层模型",
    title: "赛前概率引擎",
    points: ["Elo 实力评分", "Dixon-Coles 比分分布", "50,000 次蒙特卡洛"],
    metric: "单场概率",
  },
  {
    layer: "二层模型",
    title: "事件与赛果修正",
    points: ["已完赛锁定", "伤病停赛", "来源权威等级"],
    metric: "动态权重",
  },
  {
    layer: "三层模型",
    title: "整届路径传导",
    points: ["小组名次", "淘汰赛路径", "晋级 / 夺冠概率"],
    metric: "用户解释",
  },
];

const INTERACTIVE_SIMULATION_COUNT = 1200;
const FORECAST_REFRESH_MS = 15000;
const PAYMENT_STATUS_POLL_MS = 4000;
const API_BASE_URL = import.meta.env.DEV ? "http://127.0.0.1:8000" : "";
const SINGLE_MATCH_ROUTE_PREFIX = "/match/";

const fallbackNewsItems: NewsItem[] = [
  { title: "官方名单", detail: "两队暂无新增停赛，核心阵容可用", impact: "可入模型", tone: "green", time: "1 小时前" },
  { title: "训练信息", detail: "巴西边路主力单独训练，出场仍待确认", impact: "轻微修正", tone: "gold", time: "3 小时前" },
  { title: "社媒传闻", detail: "未证实更衣室消息，不改变概率", impact: "已忽略", tone: "muted", time: "5 小时前" },
];

function buildFallbackPrediction(tick: number): MatchPrediction {
  const homeDrift = [0, 1, -1, 2, 0, -2][tick % 6];
  const drawDrift = [0, -1, 1, -1, 0, 1][tick % 6];
  const homeWin = 46 + homeDrift;
  const draw = 26 + drawDrift;
  const awayWin = 100 - homeWin - draw;

  return {
    stage: "小组赛 E 组",
    kickoff: "6月15日 08:00",
    status: "未开赛",
    homeTeam: "brazil",
    awayTeam: "argentina",
    homeWin,
    draw,
    awayWin,
    updatedAt: new Date().toISOString(),
    scoreOutcomes: [
      { score: "1-1", probability: 14.6, note: "双方基础强度接近", tone: "gold" },
      { score: "2-1", probability: 12.8 + homeDrift * 0.2, note: "巴西边路优势放大", tone: "green" },
      { score: "1-0", probability: 10.7, note: "低比分胜局仍有空间", tone: "blue" },
    ],
    scenarioImpacts: [
      {
        label: "巴西胜",
        probability: homeWin,
        title: "巴西小组第一概率上升",
        details: ["巴西夺冠概率约 +0.9%", "阿根廷路径盘下调", "同组第三名出线门槛抬高"],
        championShift: "+0.9%",
        tone: "green",
      },
      {
        label: "打平",
        probability: draw,
        title: "两队路径保持胶着",
        details: ["小组第一仍取决于末轮", "两队夺冠概率变化都低于 0.4%", "后续净胜球权重上升"],
        championShift: "±0.3%",
        tone: "gold",
      },
      {
        label: "阿根廷胜",
        probability: awayWin,
        title: "阿根廷半区压力下降",
        details: ["阿根廷夺冠概率约 +0.8%", "巴西潜在 16 强对手变强", "小组第二路径风险上升"],
        championShift: "+0.8%",
        tone: "blue",
      },
    ],
    analysis: [
      "巴西基础实力略高，但阵容健康信息还没有完全确认。",
      "平局概率不低，因为双方都可能接受保守开局。",
      "这场更重要的不是单场胜负，而是会直接改变小组第一和淘汰赛半区。",
    ],
    newsItems: fallbackNewsItems.map((item, index) => ({
      ...item,
      time: tick === 0 ? item.time : `${Math.max(1, tick * 5 + index * 8)} 秒前`,
    })),
  };
}

function formatUpdateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未更新";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

function formatSignedPercent(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatSignedNumber(value: number) {
  if (Math.abs(value) < 0.05) return "0";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function dataReadinessLabel(dataset?: DatasetMeta) {
  if (!dataset) return "数据待确认";
  const placeholderSlots = dataset.placeholderSlots ?? 0;
  if (placeholderSlots > 0) return `样例数据 · 占位 ${placeholderSlots} 队`;
  if (dataset.teamCount === 48 && dataset.fixtureCount >= 72) return "正式数据就绪";
  return "数据待补全";
}

function matchRouteParams(pathname: string) {
  if (!pathname.startsWith(SINGLE_MATCH_ROUTE_PREFIX)) return null;
  const [, , home, away] = pathname.split("/");
  if (!home || !away) return null;
  return {
    home: decodeURIComponent(home),
    away: decodeURIComponent(away),
  };
}

function matchPagePath(home: TeamKey, away: TeamKey) {
  return `${SINGLE_MATCH_ROUTE_PREFIX}${encodeURIComponent(home)}/${encodeURIComponent(away)}`;
}

function App() {
  if (window.location.pathname === "/admin") {
    return <AdminConsole />;
  }

  const singleMatchRoute = matchRouteParams(window.location.pathname);
  if (singleMatchRoute) {
    return <SingleMatchPage home={singleMatchRoute.home} away={singleMatchRoute.away} />;
  }

  return <HomePredictionPage />;
}

function HomePredictionPage() {
  const [forecastTick, setForecastTick] = useState(0);
  const [apiPrediction, setApiPrediction] = useState<MatchPrediction | null>(null);
  const [upcomingMatches, setUpcomingMatches] = useState<UpcomingMatchesResponse | null>(null);
  const [finishedMatches, setFinishedMatches] = useState<FinishedMatchesResponse | null>(null);
  const [selectedMatchKey, setSelectedMatchKey] = useState<string | null>(null);
  const [matchDetail, setMatchDetail] = useState<MatchDetail | null>(null);
  const [accessOptions, setAccessOptions] = useState<AccessOptions | null>(null);
  const [dataMode, setDataMode] = useState<"api" | "demo">("demo");

  const teamsData = apiPrediction?.teams?.length ? apiPrediction.teams : teams;
  const fallbackPrediction = useMemo(() => buildFallbackPrediction(forecastTick), [forecastTick]);
  const matchPrediction = apiPrediction ?? fallbackPrediction;
  const homeTeam = teamsData.find((team) => team.key === matchPrediction.homeTeam) ?? teamsData[0];
  const awayTeam = teamsData.find((team) => team.key === matchPrediction.awayTeam) ?? teamsData[1];
  const mainVenue = fixtureVenueLabel(matchPrediction);
  const dataModeLabel = dataMode === "api" ? `真实模型 · ${dataReadinessLabel(matchPrediction.modelMeta?.dataset)}` : "演示动态";
  const championBoard = [...teamsData].sort((left, right) => right.tournament.champion - left.tournament.champion);
  const modelSummary = matchPrediction.modelMeta
    ? `${matchPrediction.modelMeta.simulationCount.toLocaleString("zh-CN")} 次模拟 · 已锁定 ${matchPrediction.modelMeta.lockedResults} 场赛果 · 进行中 ${matchPrediction.modelMeta.liveMatches ?? 0} 场 · 事件 ${matchPrediction.modelMeta.events?.applied ?? 0} 入模 / ${matchPrediction.modelMeta.events?.ignored ?? 0} 忽略`
    : "已结束比赛只作为后续权重因子";

  useEffect(() => {
    let active = true;

    async function loadPrediction() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/match-prediction?simulations=${INTERACTIVE_SIMULATION_COUNT}`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`预测接口返回 ${response.status}`);
        const data = (await response.json()) as MatchPrediction;
        if (!active) return;
        setApiPrediction(data);
        setDataMode("api");
      } catch {
        if (!active) return;
        setApiPrediction(null);
        setDataMode("demo");
      }
    }

    async function loadUpcomingMatches() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/upcoming-matches?limit=6`, { cache: "no-store" });
        if (!response.ok) throw new Error(`未赛程接口返回 ${response.status}`);
        const data = (await response.json()) as UpcomingMatchesResponse;
        if (!active) return;
        setUpcomingMatches(data);
      } catch {
        if (!active) return;
        setUpcomingMatches(null);
      }
    }

    async function loadFinishedMatches() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/finished-matches?limit=6`, { cache: "no-store" });
        if (!response.ok) throw new Error(`完赛记录接口返回 ${response.status}`);
        const data = (await response.json()) as FinishedMatchesResponse;
        if (!active) return;
        setFinishedMatches(data);
      } catch {
        if (!active) return;
        setFinishedMatches(null);
      }
    }

    async function loadAccessOptions() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/access-options`, { cache: "no-store" });
        if (!response.ok) throw new Error(`付费接口返回 ${response.status}`);
        const data = (await response.json()) as AccessOptions;
        if (!active) return;
        setAccessOptions(data);
      } catch {
        if (!active) return;
        setAccessOptions(null);
      }
    }

    loadPrediction();
    loadUpcomingMatches();
    loadFinishedMatches();
    loadAccessOptions();
    const timer = window.setInterval(() => {
      setForecastTick((value) => value + 1);
      loadPrediction();
      loadUpcomingMatches();
      loadFinishedMatches();
      loadAccessOptions();
    }, FORECAST_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function loadMatchDetail(match: UpcomingMatch) {
    const key = `${match.homeTeam}-${match.awayTeam}`;
    setSelectedMatchKey(key);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/match-detail?home=${encodeURIComponent(match.homeTeam)}&away=${encodeURIComponent(match.awayTeam)}&simulations=${INTERACTIVE_SIMULATION_COUNT}`,
        { cache: "no-store" },
      );
      if (!response.ok) throw new Error(`单场详情接口返回 ${response.status}`);
      const data = (await response.json()) as MatchDetail;
      setMatchDetail(data);
    } catch {
      setMatchDetail(null);
    }
  }

  return (
    <main className="console-shell user-page-shell">
      <div className="ambient-grid" />
      <header className="topbar">
        <div className="brand">
          <span className="signal-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>世界杯预测</span>
        </div>
        <nav className="top-links" aria-label="用户预测页">
          <a href="#matches">未开赛</a>
          <a href="#trend">走势</a>
          <a href="#access">解锁</a>
        </nav>
      </header>

      <section className="scoreboard" aria-label="未开赛对阵预测">
        <MiniPitch side="left" />
        <div className="score-strip match-strip">
          <div className="score-team home-team">
            <TeamFlag team={homeTeam.key} code={homeTeam.code} />
            <span className="team-code">{homeTeam.code}</span>
          </div>
          <strong className="versus-mark">VS</strong>
          <div className="score-team away-team">
            <span className="team-code">{awayTeam.code}</span>
            <TeamFlag team={awayTeam.key} code={awayTeam.code} />
          </div>
          <div className="match-clock forecast-clock">
            <span>{matchPrediction.kickoff}</span>
            <em>{matchPrediction.status}</em>
          </div>
          <div className="match-meta">
            <span>{matchPrediction.stage}</span>
            {mainVenue ? <span>{mainVenue}</span> : null}
            <b>预测更新 {formatUpdateTime(matchPrediction.updatedAt)}</b>
          </div>
        </div>
        <MiniPitch side="right" />
      </section>

      <div className="module-grid">
        <section className="console-panel wide prediction-hero-panel">
          <div className="panel-kicker">用户预测页 · 免费预览</div>
          <h2>今日重点比赛</h2>
          <div className="probability-row">
            <Probability label={`${homeTeam.name}胜`} value={matchPrediction.homeWin} tone="green" />
            <Probability label="平局" value={matchPrediction.draw} tone="gold" />
            <Probability label={`${awayTeam.name}胜`} value={matchPrediction.awayWin} tone="blue" />
          </div>
          <div className="engine-line">
            <span className="ai-badge">AI</span>
            <span className="engine-copy">
              <strong>{matchPrediction.modelMeta?.engine ?? "Elo + Dixon-Coles + 蒙特卡洛"}</strong>
              <small>
                数据源：{dataModeLabel} · {modelSummary}
              </small>
            </span>
            <a className="primary-link" href={matchPagePath(matchPrediction.homeTeam, matchPrediction.awayTeam)}>
              解锁完整预测
            </a>
          </div>
          <div className="analysis-list">
            {matchPrediction.analysis.slice(0, 2).map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </section>

        <section className="console-panel">
          <h2>免费预览比分</h2>
          <div className="score-outcome-list">
            {matchPrediction.scoreOutcomes.slice(0, 1).map((outcome) => (
              <article className={`score-outcome ${outcome.tone}`} key={outcome.score}>
                <strong>{outcome.score}</strong>
                <div>
                  <b>{outcome.probability.toFixed(1)}%</b>
                  <span>{outcome.note}</span>
                </div>
              </article>
            ))}
          </div>
          <p className="locked-note">完整比分分布在单场页解锁。</p>
        </section>

        <section id="matches" className="console-panel wide">
          <h2>未开赛预测</h2>
          <UpcomingMatchesPanel matches={upcomingMatches?.items ?? []} selectedKey={selectedMatchKey} onSelect={loadMatchDetail} />
        </section>

        <section className="console-panel wide">
          <h2>单场快速预览</h2>
          <MatchDetailPanel detail={matchDetail} teamsData={teamsData} />
        </section>

        <section id="trend" className="console-panel">
          <h2>今日概率变化</h2>
          <DailyMoversPanel movers={matchPrediction.dailyMovers} />
        </section>

        <section className="console-panel">
          <h2>冠军概率榜</h2>
          <ChampionBoard teams={championBoard.slice(0, 8)} />
          <p className="locked-note">完整 48 队榜单随赛事全周期解锁。</p>
        </section>

        <section className="console-panel wide">
          <h2>已结束比赛记录</h2>
          <FinishedMatchesPanel records={finishedMatches?.items ?? []} />
        </section>

        <section className="console-panel">
          <h2>新闻影响摘要</h2>
          <div className="news-list">
            {matchPrediction.newsItems.slice(0, 3).map((item) => (
              <article className={`news-item ${item.tone}`} key={item.title}>
                <span className="news-icon">{item.tone === "red" ? "+" : item.tone === "gold" ? "!" : "?"}</span>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <small>{item.time}</small>
                </div>
                <em>{item.impact}</em>
              </article>
            ))}
          </div>
        </section>

        <section className="console-panel">
          <h2>模型说明</h2>
          <div className="layer-grid compact">
            {modelLayers.map((layer, index) => (
              <article className="layer-card" key={layer.layer}>
                <span>{`0${index + 1}`}</span>
                <strong>{layer.layer}</strong>
                <h3>{layer.title}</h3>
                <ul>
                  {layer.points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
                <em>{layer.metric}</em>
              </article>
            ))}
          </div>
        </section>

        <section id="access" className="console-panel wide">
          <h2>付费解锁</h2>
          <AccessPanel options={accessOptions} contentKey="tournament_probabilities" />
        </section>
      </div>
    </main>
  );
}

function TeamFlag({ team, code }: { team: TeamKey; code?: string }) {
  const knownFlags = new Set(["brazil", "argentina", "spain", "france", "england", "portugal", "germany", "netherlands"]);
  const className = knownFlags.has(team) ? `flag flag-${team}` : "flag flag-generic";
  return (
    <span className={className} aria-hidden="true">
      {knownFlags.has(team) ? null : code?.slice(0, 3)}
    </span>
  );
}

function MiniPitch({ side }: { side: "left" | "right" }) {
  return (
    <div className={`mini-pitch ${side}`} aria-hidden="true">
      {Array.from({ length: 10 }).map((_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}

function Probability({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`probability ${tone}`}>
      <span>{label}</span>
      <strong>{value}%</strong>
      <SegmentBar value={value} tone={tone} />
    </div>
  );
}

function SegmentBar({ value, tone }: { value: number; tone: string }) {
  const filled = Math.max(0, Math.min(12, Math.round((value / 100) * 12)));
  return (
    <span className={`segment-bar ${tone}`} aria-hidden="true">
      {Array.from({ length: 12 }).map((_, index) => (
        <i className={index < filled ? "filled" : ""} key={index} />
      ))}
    </span>
  );
}

function UpcomingMatchesPanel({
  matches,
  selectedKey,
  onSelect,
}: {
  matches: UpcomingMatch[];
  selectedKey: string | null;
  onSelect: (match: UpcomingMatch) => void;
}) {
  if (matches.length === 0) {
    return <p className="review-empty">未开赛预测等待 API 连接</p>;
  }

  return (
    <div className="upcoming-list">
      {matches.map((match) => {
        const key = `${match.homeTeam}-${match.awayTeam}`;
        return (
          <button className={`upcoming-row ${selectedKey === key ? "selected" : ""}`} key={`${key}-${match.kickoff}`} onClick={() => onSelect(match)}>
            <div className="upcoming-teams">
              <span>{match.homeCode}</span>
              <b>VS</b>
              <span>{match.awayCode}</span>
            </div>
            <div className="upcoming-copy">
              <strong>
                {match.homeName} / {match.awayName}
              </strong>
              <small>
                {[match.stage, match.kickoff, fixtureVenueLabel(match), `最可能 ${match.topScore.score} / ${match.topScore.probability.toFixed(1)}%`].filter(Boolean).join(" · ")}
              </small>
            </div>
            <div className="upcoming-probs">
              <em>{match.homeWin}%</em>
              <em>{match.draw}%</em>
              <em>{match.awayWin}%</em>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function FinishedMatchesPanel({ records }: { records: FinishedMatch[] }) {
  if (records.length === 0) {
    return <p className="review-empty">已结束比赛记录等待 API 连接</p>;
  }

  return (
    <div className="finished-list">
      {records.map((match) => (
        <article className="finished-row" key={`${match.homeTeam}-${match.awayTeam}-${match.kickoff}`}>
          <div className="finished-result">
            <div className="finished-side">
              <TeamFlag team={match.homeTeam} code={match.homeCode} />
              <span>{match.homeCode}</span>
            </div>
            <strong>
              {match.homeScore} - {match.awayScore}
            </strong>
            <div className="finished-side away">
              <span>{match.awayCode}</span>
              <TeamFlag team={match.awayTeam} code={match.awayCode} />
            </div>
          </div>
          <div className="finished-copy">
            <strong>
              {match.homeName} / {match.awayName}
            </strong>
            <small>{[match.stage, match.kickoff, fixtureVenueLabel(match)].filter(Boolean).join(" · ")}</small>
          </div>
          <em>{match.modelUseLabel}</em>
        </article>
      ))}
    </div>
  );
}

function MatchDetailPanel({ detail, teamsData }: { detail: MatchDetail | null; teamsData: Team[] }) {
  if (!detail) {
    return <p className="review-empty">从未开赛预测选择比赛</p>;
  }

  const homeTeam = teamsData.find((team) => team.key === detail.homeTeam);
  const awayTeam = teamsData.find((team) => team.key === detail.awayTeam);
  const venue = fixtureVenueLabel(detail);

  return (
    <div className="match-detail-grid">
      <div className="detail-head">
        <strong>
          {homeTeam?.name ?? detail.homeTeam} / {awayTeam?.name ?? detail.awayTeam}
        </strong>
        <span>
          {[detail.stage, detail.kickoff, venue].filter(Boolean).join(" · ")}
        </span>
        <a href={matchPagePath(detail.homeTeam, detail.awayTeam)}>打开单场页</a>
      </div>
      <div className="probability-row compact">
        <Probability label={`${homeTeam?.name ?? detail.homeTeam}胜`} value={detail.homeWin} tone="green" />
        <Probability label="平局" value={detail.draw} tone="gold" />
        <Probability label={`${awayTeam?.name ?? detail.awayTeam}胜`} value={detail.awayWin} tone="blue" />
      </div>
      <div className="score-outcome-list">
        {detail.scoreOutcomes.map((outcome) => (
          <article className={`score-outcome ${outcome.tone}`} key={outcome.score}>
            <strong>{outcome.score}</strong>
            <div>
              <b>{outcome.probability.toFixed(1)}%</b>
              <span>{outcome.note}</span>
            </div>
          </article>
        ))}
      </div>
      <ScenarioImpactList scenarios={detail.scenarioImpacts} />
    </div>
  );
}

function ScenarioImpactList({ scenarios }: { scenarios: ScenarioImpact[] }) {
  return (
    <div className="scenario-grid">
      {scenarios.map((scenario) => (
        <article className={`scenario-card ${scenario.tone}`} key={scenario.label}>
          <div className="scenario-head">
            <span>{scenario.label}</span>
            <strong>{scenario.probability}%</strong>
          </div>
          <h3>{scenario.title}</h3>
          <ul>
            {scenario.details.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
          <em>夺冠概率变化 {scenario.championShift}</em>
        </article>
      ))}
    </div>
  );
}

function accessStatusLabel(status: string) {
  if (status === "available") return "可解锁";
  if (status === "payment_pending") return "支付待接入";
  return "待配置";
}

function paymentStatusLabel(status: string) {
  if (status === "pending_payment") return "等待扫码付款";
  if (status === "customer_interface_ready") return "客户接口已就绪";
  if (status === "provider_config_required") return "客户接口待配置";
  if (status === "paid") return "支付完成";
  return "待处理";
}

function AccessPanel({
  options,
  contentKey,
  onAccessChange,
}: {
  options: AccessOptions | null;
  contentKey?: string;
  onAccessChange?: (allowed: boolean) => void;
}) {
  const [paymentConfig, setPaymentConfig] = useState<PaymentConfig | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<PaymentProviderKey>("wechat");
  const [paymentOrder, setPaymentOrder] = useState<PaymentOrder | null>(null);
  const [unlockDecisions, setUnlockDecisions] = useState<Record<string, AccessDecision>>({});
  const [paymentMessage, setPaymentMessage] = useState<string | null>(null);
  const [creatingProductKey, setCreatingProductKey] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadPaymentConfig() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/payments/config`, { cache: "no-store" });
        if (!response.ok) throw new Error(`支付配置接口返回 ${response.status}`);
        const data = (await response.json()) as PaymentConfig;
        if (!active) return;
        setPaymentConfig(data);
        if (data.providers.length > 0) setSelectedProvider(data.providers[0].provider);
      } catch {
        if (!active) return;
        setPaymentConfig(null);
      }
    }

    loadPaymentConfig();
    return () => {
      active = false;
    };
  }, []);

  async function checkPaymentAccess(orderId: string) {
    if (!contentKey) return;
    const response = await fetch(`${API_BASE_URL}/api/access-decision?orderId=${encodeURIComponent(orderId)}&contentKey=${encodeURIComponent(contentKey)}`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`权限接口返回 ${response.status}`);
    const decision = (await response.json()) as AccessDecision;
    setUnlockDecisions((current) => ({ ...current, [contentKey]: decision }));
    onAccessChange?.(decision.allowed);
  }

  async function pollPaymentOrder(orderId: string) {
    const response = await fetch(`${API_BASE_URL}/api/payments/orders/${encodeURIComponent(orderId)}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`订单查询接口返回 ${response.status}`);
    const order = (await response.json()) as PaymentOrder;
    setPaymentOrder(order);
    if (order.status === "paid") {
      await checkPaymentAccess(order.orderId);
    }
  }

  async function createScanPaymentOrder(productKey: string) {
    if (creatingProductKey) return;
    setCreatingProductKey(productKey);
    setPaymentMessage(null);
    onAccessChange?.(false);
    try {
      const response = await fetch(`${API_BASE_URL}/api/payments/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ productKey, provider: selectedProvider }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail ?? `支付订单接口返回 ${response.status}`);
      const order = payload as PaymentOrder;
      setPaymentOrder(order);
      await checkPaymentAccess(order.orderId);
    } catch (error) {
      setPaymentOrder(null);
      setPaymentMessage(error instanceof Error ? error.message : "支付订单创建失败");
    } finally {
      setCreatingProductKey(null);
    }
  }

  useEffect(() => {
    if (!paymentOrder?.orderId) return;
    let active = true;
    const orderId = paymentOrder.orderId;
    const timer = window.setInterval(() => {
      if (!active) return;
      pollPaymentOrder(orderId).catch((error) => {
        if (active) setPaymentMessage(error instanceof Error ? error.message : "订单状态查询失败");
      });
    }, PAYMENT_STATUS_POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [paymentOrder?.orderId, contentKey]);

  if (!options) {
    return <p className="review-empty">付费配置等待 API 连接</p>;
  }

  const providers = paymentConfig?.providers ?? [
    { provider: "wechat", label: "微信支付", paymentMethod: "scan_qr", configured: false, missingConfig: [] },
    { provider: "alipay", label: "支付宝支付", paymentMethod: "scan_qr", configured: false, missingConfig: [] },
  ];
  const currentProvider = providers.find((provider) => provider.provider === selectedProvider) ?? providers[0];
  const currentDecision = contentKey ? unlockDecisions[contentKey] : null;

  return (
    <div className="access-panel">
      <div className="access-summary">
        <strong>{paymentConfig?.ready ? "客户支付接口已配置" : "扫码付款待配置"}</strong>
        <span>{paymentConfig?.disclaimer ?? options.disclaimer}</span>
      </div>
      <div className="payment-provider-row" aria-label="扫码付款渠道">
        {providers.map((provider) => (
          <button
            type="button"
            className={provider.provider === selectedProvider ? "selected" : ""}
            key={provider.provider}
            onClick={() => setSelectedProvider(provider.provider)}
          >
            {provider.label}
          </button>
        ))}
        <span>{currentProvider?.configured ? "可创建订单意图" : `${currentProvider?.label ?? "支付"}客户接口待配置`}</span>
      </div>
      <div className="access-list">
        {options.products.map((product) => (
          <article className="access-card" key={product.key}>
            <strong>{product.name}</strong>
            <span>{product.scope}</span>
            <small>{product.amountLabel ?? "待定价"}</small>
            <button type="button" disabled={creatingProductKey === product.key} onClick={() => createScanPaymentOrder(product.key)}>
              {creatingProductKey === product.key ? "创建中" : "创建扫码订单"}
            </button>
            <em>{accessStatusLabel(product.status)}</em>
          </article>
        ))}
      </div>
      {paymentOrder ? (
        <div className="payment-order-box">
          <div>
            <strong>
              {paymentOrder.providerLabel} · {paymentStatusLabel(paymentOrder.status)}
            </strong>
            <span>
              {paymentOrder.productName} · {paymentOrder.amountLabel} · 到期 {formatUpdateTime(paymentOrder.expiresAt)}
            </span>
            <p>{paymentOrder.nextAction}</p>
          </div>
          {paymentOrder.qrCodeUrl ? <img src={paymentOrder.qrCodeUrl} alt="扫码付款二维码" /> : <em>二维码待生成</em>}
        </div>
      ) : null}
      {currentDecision?.allowed ? <p className="unlock-message green">已解锁完整预测</p> : null}
      {currentDecision && !currentDecision.allowed ? <p className="unlock-message">支付确认后自动解锁完整内容</p> : null}
      {paymentMessage ? <p className="review-message">{paymentMessage}</p> : null}
    </div>
  );
}

function LockedContent({
  unlocked,
  title,
  preview,
  children,
}: {
  unlocked: boolean;
  title: string;
  preview: string;
  children: ReactNode;
}) {
  if (unlocked) {
    return <>{children}</>;
  }
  return (
    <div className="locked-content">
      <strong>{title}</strong>
      <p>{preview}</p>
      <em>解锁后查看完整预测</em>
    </div>
  );
}

function SingleMatchPage({ home, away }: { home: TeamKey; away: TeamKey }) {
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [accessOptions, setAccessOptions] = useState<AccessOptions | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [matchUnlocked, setMatchUnlocked] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadDetail() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/match-detail?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&simulations=${INTERACTIVE_SIMULATION_COUNT}`,
          { cache: "no-store" },
        );
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw new Error(payload?.detail ?? `单场详情接口返回 ${response.status}`);
        if (!active) return;
        setDetail(payload as MatchDetail);
        setErrorMessage(null);
      } catch (error) {
        if (!active) return;
        setDetail(null);
        setErrorMessage(error instanceof Error ? error.message : "单场预测加载失败");
      }
    }

    async function loadAccessOptions() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/access-options`, { cache: "no-store" });
        if (!response.ok) throw new Error(`付费接口返回 ${response.status}`);
        const data = (await response.json()) as AccessOptions;
        if (!active) return;
        setAccessOptions(data);
      } catch {
        if (!active) return;
        setAccessOptions(null);
      }
    }

    loadDetail();
    loadAccessOptions();
    return () => {
      active = false;
    };
  }, [home, away]);

  const homeTeam = teams.find((team) => team.key === (detail?.homeTeam ?? home));
  const awayTeam = teams.find((team) => team.key === (detail?.awayTeam ?? away));
  const homeName = detail?.homeName ?? homeTeam?.name ?? home;
  const awayName = detail?.awayName ?? awayTeam?.name ?? away;
  const homeCode = detail?.homeCode ?? homeTeam?.code ?? home.slice(0, 3).toUpperCase();
  const awayCode = detail?.awayCode ?? awayTeam?.code ?? away.slice(0, 3).toUpperCase();
  const venue = detail ? fixtureVenueLabel(detail) : "";

  return (
    <main className="console-shell match-page-shell">
      <div className="ambient-grid" />
      <header className="topbar">
        <div className="brand">
          <span className="signal-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>单场预测</span>
        </div>
        <a className="back-link" href="/">
          返回预测页
        </a>
      </header>

      <section className="scoreboard" aria-label="单场预测对阵">
        <MiniPitch side="left" />
        <div className="score-strip match-strip">
          <div className="score-team home-team">
            <TeamFlag team={detail?.homeTeam ?? home} code={homeCode} />
            <span className="team-code">{homeCode}</span>
          </div>
          <strong className="versus-mark">VS</strong>
          <div className="score-team away-team">
            <span className="team-code">{awayCode}</span>
            <TeamFlag team={detail?.awayTeam ?? away} code={awayCode} />
          </div>
          <div className="match-clock forecast-clock">
            <span>{detail?.kickoff ?? "加载中"}</span>
            <em>{detail?.status ?? "待载入"}</em>
          </div>
          <div className="match-meta">
            <span>{detail?.stage ?? "单场预测"}</span>
            {venue ? <span>{venue}</span> : null}
            {detail ? <b>预测更新 {formatUpdateTime(detail.updatedAt)}</b> : null}
          </div>
        </div>
        <MiniPitch side="right" />
      </section>

      <div className="module-grid">
        <section className="console-panel wide">
          <div className="panel-kicker">免费预览</div>
          <h2>赛前胜平负概率</h2>
          {detail ? (
            <>
              <div className="probability-row">
                <Probability label={`${homeName}胜`} value={detail.homeWin} tone="green" />
                <Probability label="平局" value={detail.draw} tone="gold" />
                <Probability label={`${awayName}胜`} value={detail.awayWin} tone="blue" />
              </div>
              <div className="analysis-list">
                {detail.analysis.slice(0, 1).map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            </>
          ) : (
            <p className="review-empty">{errorMessage ?? "单场预测加载中"}</p>
          )}
        </section>

        <section className="console-panel">
          <h2>免费预览比分</h2>
          {detail ? (
            <div className="score-outcome-list">
              {detail.scoreOutcomes.slice(0, 1).map((outcome) => (
                <article className={`score-outcome ${outcome.tone}`} key={outcome.score}>
                  <strong>{outcome.score}</strong>
                  <div>
                    <b>{outcome.probability.toFixed(1)}%</b>
                    <span>{outcome.note}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="review-empty">比分分布等待单场预测</p>
          )}
          <p className="locked-note">完整比分分布需要解锁。</p>
        </section>

        <section className="console-panel conversion-panel">
          <h2>付费解锁</h2>
          <AccessPanel options={accessOptions} contentKey="match_prediction" onAccessChange={setMatchUnlocked} />
        </section>

        <section className="console-panel wide">
          <div className="panel-kicker">完整预测</div>
          <h2>单场完整预测</h2>
          {detail ? (
            <LockedContent unlocked={matchUnlocked} title="完整预测" preview="包含比分分布 Top 3、整届概率传导和完整 AI 分析。">
              <div className="match-full-content">
                <div className="score-outcome-list">
                  {detail.scoreOutcomes.map((outcome) => (
                    <article className={`score-outcome ${outcome.tone}`} key={outcome.score}>
                      <strong>{outcome.score}</strong>
                      <div>
                        <b>{outcome.probability.toFixed(1)}%</b>
                        <span>{outcome.note}</span>
                      </div>
                    </article>
                  ))}
                </div>
                <div className="analysis-list">
                  {detail.analysis.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
                <ScenarioImpactList scenarios={detail.scenarioImpacts} />
              </div>
            </LockedContent>
          ) : (
            <p className="review-empty">路径传导等待单场预测</p>
          )}
        </section>
      </div>
    </main>
  );
}

function AdminConsole() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [eventReview, setEventReview] = useState<EventReviewResponse | null>(null);
  const [adminToken, setAdminToken] = useState(() => window.localStorage.getItem("worldCupAdminToken") ?? "");
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [snapshotPending, setSnapshotPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [fixtureMode, setFixtureMode] = useState<"live" | "finished">("live");
  const [fixtureForm, setFixtureForm] = useState({
    home: "brazil",
    away: "argentina",
    homeScore: "0",
    awayScore: "0",
  });
  const [rawNewsForm, setRawNewsForm] = useState({
    id: "",
    title: "",
    summary: "",
    source: "reuters",
    team: "",
    status: "single_source" as ReviewStatus,
    publishedAt: "刚刚",
    url: "",
  });
  const [tournamentImportText, setTournamentImportText] = useState("");
  const [tournamentRollbackId, setTournamentRollbackId] = useState("");
  const dailyStatus = overview?.dailyUpdateStatus ?? null;
  const dailyHealth = overview?.dailyUpdateHealth;

  function adminHeaders() {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (adminToken.trim()) {
      headers["X-Admin-Token"] = adminToken.trim();
    }
    return headers;
  }

  function saveAdminToken(value: string) {
    setAdminToken(value);
    if (value.trim()) {
      window.localStorage.setItem("worldCupAdminToken", value.trim());
    } else {
      window.localStorage.removeItem("worldCupAdminToken");
    }
  }

  async function loadAdminData() {
    const [overviewResponse, eventsResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/api/admin/overview`, { cache: "no-store" }),
      fetch(`${API_BASE_URL}/api/events`, { cache: "no-store" }),
    ]);
    if (!overviewResponse.ok) throw new Error(`后台概览接口返回 ${overviewResponse.status}`);
    if (!eventsResponse.ok) throw new Error(`事件接口返回 ${eventsResponse.status}`);
    setOverview((await overviewResponse.json()) as AdminOverview);
    setEventReview((await eventsResponse.json()) as EventReviewResponse);
  }

  useEffect(() => {
    let active = true;

    async function run() {
      try {
        await loadAdminData();
      } catch {
        if (active) {
          setOverview(null);
          setEventReview(null);
        }
      }
    }

    run();
    const timer = window.setInterval(run, FORECAST_REFRESH_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function submitReview(item: EventReviewItem, status: ReviewStatus) {
    if (!item.id || pendingId) return;
    setPendingId(item.id);
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/events/review`, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({ id: item.id, status, team: item.team }),
      });
      if (!response.ok) throw new Error(`审核接口返回 ${response.status}`);
      await loadAdminData();
      setMessage("事件已写入");
    } catch {
      setMessage("事件写入失败");
    } finally {
      setPendingId(null);
    }
  }

  async function rebuildSnapshot() {
    if (snapshotPending) return;
    setSnapshotPending(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/snapshot/rebuild`, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error(`快照接口返回 ${response.status}`);
      await loadAdminData();
      setMessage("快照已重建");
    } catch {
      setMessage("快照重建失败");
    } finally {
      setSnapshotPending(false);
    }
  }

  async function submitFixtureScore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    const endpoint = fixtureMode === "live" ? "/api/fixtures/live" : "/api/fixtures/result";
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({
          home: fixtureForm.home.trim(),
          away: fixtureForm.away.trim(),
          homeScore: Number(fixtureForm.homeScore),
          awayScore: Number(fixtureForm.awayScore),
        }),
      });
      if (!response.ok) throw new Error(`比分接口返回 ${response.status}`);
      await loadAdminData();
      setMessage(fixtureMode === "live" ? "进行中比分已写入" : "完赛比分已锁定");
    } catch {
      setMessage("比分写入失败");
    }
  }

  async function submitRawNews(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    const id = rawNewsForm.id.trim() || `manual-${Date.now()}`;
    try {
      const response = await fetch(`${API_BASE_URL}/api/raw-news`, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({
          id,
          title: rawNewsForm.title.trim(),
          summary: rawNewsForm.summary.trim(),
          source: rawNewsForm.source.trim(),
          team: rawNewsForm.team.trim() || null,
          status: rawNewsForm.status,
          publishedAt: rawNewsForm.publishedAt.trim(),
          url: rawNewsForm.url.trim(),
        }),
      });
      if (!response.ok) throw new Error(`新闻录入接口返回 ${response.status}`);
      await loadAdminData();
      setRawNewsForm((current) => ({ ...current, id: "", title: "", summary: "", url: "" }));
      setMessage("新闻线索已录入");
    } catch {
      setMessage("新闻线索录入失败");
    }
  }

  async function submitTournamentImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    try {
      const payload = JSON.parse(tournamentImportText) as Record<string, unknown>;
      const response = await fetch(`${API_BASE_URL}/api/admin/tournament-data/import`, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`赛事导入接口返回 ${response.status}`);
      await loadAdminData();
      setTournamentImportText("");
      setMessage("赛事数据已导入");
    } catch {
      setMessage("赛事数据导入失败");
    }
  }

  async function submitTournamentRollback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}${overview?.operations.tournamentRollbackEndpoint ?? "/api/admin/tournament-data/rollback"}`, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({ backupId: tournamentRollbackId.trim() }),
      });
      if (!response.ok) throw new Error(`赛事回滚接口返回 ${response.status}`);
      await loadAdminData();
      setTournamentRollbackId("");
      setMessage("赛事数据已回滚");
    } catch {
      setMessage("赛事数据回滚失败");
    }
  }

  return (
    <main className="admin-shell">
      <header className="admin-topbar">
        <div>
          <span>World Cup Ops</span>
          <h1>预测运营后台</h1>
        </div>
        <a href="/">返回预测页</a>
      </header>

      <section className="admin-grid">
        <article className="admin-card admin-card-wide">
          <h2>后台权限</h2>
          <div className="admin-auth-row">
            <input
              value={adminToken}
              onChange={(event) => saveAdminToken(event.target.value)}
              aria-label="后台 token"
              placeholder={overview?.authRequired ? "输入后台 token" : "本地未启用 token"}
              type="password"
            />
            <span>{overview?.authRequired ? "写操作需要 token" : "当前为本地开放模式"}</span>
          </div>
        </article>

        <article className="admin-card">
          <h2>赛程状态</h2>
          <div className="admin-metrics">
            <Metric label="未开赛" value={overview?.fixtureStatus.scheduled ?? 0} tone="blue" />
            <Metric label="进行中" value={overview?.fixtureStatus.live ?? 0} tone="gold" />
            <Metric label="已锁定" value={overview?.fixtureStatus.finished ?? 0} tone="green" />
          </div>
        </article>

        <article className="admin-card">
          <h2>事件状态</h2>
          <div className="admin-metrics">
            <Metric label="原始新闻" value={overview?.rawNewsCount ?? 0} tone="blue" />
            <Metric label="待审" value={overview?.eventSummary.reviewRequired ?? 0} tone="gold" />
            <Metric label="入模" value={overview?.eventSummary.applied ?? 0} tone="green" />
          </div>
        </article>

        <article className="admin-card">
          <h2>数据健康</h2>
          <div className="admin-metrics">
            <Metric label="球队" value={overview?.datasetHealth.teamCount ?? 0} tone="blue" />
            <Metric label="赛程" value={overview?.datasetHealth.fixtureCount ?? 0} tone="green" />
            <Metric label="占位" value={overview?.datasetHealth.placeholderSlots ?? 0} tone={overview?.datasetHealth.placeholderSlots ? "gold" : "green"} />
          </div>
        </article>

        <article className="admin-card">
          <h2>日更状态</h2>
          <div className="admin-command">
            <code>{overview?.operations.dailyUpdateCommand ?? "npm run daily:update"}</code>
            <span>{dailyStatus ? `最近日更 ${formatUpdateTime(dailyStatus.updatedAt)}` : "暂无日更状态"}</span>
          </div>
          <div className="daily-status">
            <span>
              <b className={dailyStatus?.status === "failed" ? "red" : ""}>{formatDailyStatus(dailyStatus?.status)}</b>
              <em>执行状态</em>
            </span>
            <span>
              <b>{dailyStatus?.feeds?.imported ?? 0}</b>
              <em>新增新闻</em>
            </span>
            <span>
              <b>{dailyStatus?.snapshot?.simulationCount.toLocaleString("zh-CN") ?? 0}</b>
              <em>模拟次数</em>
            </span>
            <span>
              <b className={dailyHealthTone(dailyHealth?.status)}>{dailyHealth?.label ?? "未执行"}</b>
              <em>日更健康</em>
            </span>
          </div>
          <button className="snapshot-button" disabled={snapshotPending} onClick={rebuildSnapshot}>
            {snapshotPending ? "重建中" : "重建快照"}
          </button>
        </article>

        <article className="admin-card">
          <h2>比分写入</h2>
          <form className="fixture-form" onSubmit={submitFixtureScore}>
            <div className="fixture-mode">
              <button type="button" className={fixtureMode === "live" ? "selected" : ""} onClick={() => setFixtureMode("live")}>
                进行中
              </button>
              <button type="button" className={fixtureMode === "finished" ? "selected" : ""} onClick={() => setFixtureMode("finished")}>
                已完赛
              </button>
            </div>
            <div className="fixture-inputs">
              <input value={fixtureForm.home} onChange={(event) => setFixtureForm((current) => ({ ...current, home: event.target.value }))} aria-label="主队 key" />
              <input value={fixtureForm.away} onChange={(event) => setFixtureForm((current) => ({ ...current, away: event.target.value }))} aria-label="客队 key" />
              <input value={fixtureForm.homeScore} onChange={(event) => setFixtureForm((current) => ({ ...current, homeScore: event.target.value }))} inputMode="numeric" aria-label="主队比分" />
              <input value={fixtureForm.awayScore} onChange={(event) => setFixtureForm((current) => ({ ...current, awayScore: event.target.value }))} inputMode="numeric" aria-label="客队比分" />
            </div>
            <button type="submit">写入比分</button>
          </form>
        </article>

        <article className="admin-card admin-card-wide">
          <h2>赛事导入</h2>
          <form className="tournament-import-form" onSubmit={submitTournamentImport}>
            <textarea
              value={tournamentImportText}
              onChange={(event) => setTournamentImportText(event.target.value)}
              aria-label="赛事导入 JSON"
              placeholder='{"source":"fifa-official","teams":[],"fixtures":[]}'
              required
            />
            <button type="submit">导入赛事数据</button>
          </form>
          <form className="tournament-rollback-form" onSubmit={submitTournamentRollback}>
            <input
              value={tournamentRollbackId}
              onChange={(event) => setTournamentRollbackId(event.target.value)}
              aria-label="回滚备份 ID"
              placeholder="备份目录 ID"
              required
            />
            <button type="submit">回滚赛事数据</button>
          </form>
          <div className="backup-list">
            {(overview?.tournamentBackups ?? []).length > 0 ? (
              overview?.tournamentBackups.map((backup) => (
                <article className="backup-row" key={backup.backupId}>
                  <strong>{backup.backupId}</strong>
                  <span>{backup.isComplete ? "可回滚" : "不完整"}</span>
                  <button type="button" onClick={() => setTournamentRollbackId(backup.backupId)}>
                    选择
                  </button>
                </article>
              ))
            ) : (
              <p className="review-empty">暂无赛事备份</p>
            )}
          </div>
        </article>

        <article className="admin-card admin-card-wide">
          <h2>新闻录入</h2>
          <form className="raw-news-form" onSubmit={submitRawNews}>
            <input value={rawNewsForm.id} onChange={(event) => setRawNewsForm((current) => ({ ...current, id: event.target.value }))} aria-label="新闻 id" placeholder="id 自动生成" />
            <input value={rawNewsForm.title} onChange={(event) => setRawNewsForm((current) => ({ ...current, title: event.target.value }))} aria-label="新闻标题" placeholder="新闻标题" required />
            <textarea value={rawNewsForm.summary} onChange={(event) => setRawNewsForm((current) => ({ ...current, summary: event.target.value }))} aria-label="新闻摘要" placeholder="新闻摘要" required />
            <div className="raw-news-grid">
              <input value={rawNewsForm.source} onChange={(event) => setRawNewsForm((current) => ({ ...current, source: event.target.value }))} aria-label="来源 key" required />
              <input value={rawNewsForm.team} onChange={(event) => setRawNewsForm((current) => ({ ...current, team: event.target.value }))} aria-label="球队 key" placeholder="全局" />
              <select value={rawNewsForm.status} onChange={(event) => setRawNewsForm((current) => ({ ...current, status: event.target.value as ReviewStatus }))} aria-label="新闻状态">
                <option value="single_source">single_source</option>
                <option value="confirmed">confirmed</option>
                <option value="multi_source">multi_source</option>
                <option value="unverified">unverified</option>
                <option value="rumor">rumor</option>
              </select>
              <input value={rawNewsForm.publishedAt} onChange={(event) => setRawNewsForm((current) => ({ ...current, publishedAt: event.target.value }))} aria-label="发布时间" required />
            </div>
            <input value={rawNewsForm.url} onChange={(event) => setRawNewsForm((current) => ({ ...current, url: event.target.value }))} aria-label="新闻链接" placeholder="https://example.com/news" required />
            <button type="submit">录入新闻</button>
          </form>
        </article>

        <article className="admin-card admin-card-wide">
          <h2>事件审核</h2>
          <EventReviewPanel
            eventReview={eventReview}
            pendingId={pendingId}
            snapshotPending={snapshotPending}
            message={message}
            onReview={submitReview}
            onRebuildSnapshot={rebuildSnapshot}
          />
        </article>

        <article className="admin-card admin-card-wide">
          <h2>审计记录</h2>
          <div className="audit-list">
            {(overview?.recentAudit ?? []).length > 0 ? (
              overview?.recentAudit.map((entry) => (
                <article className="audit-row" key={`${entry.time}-${entry.action}-${entry.targetId}`}>
                  <strong>{entry.action}</strong>
                  <span>{entry.targetId}</span>
                  <em>{formatUpdateTime(entry.time)}</em>
                </article>
              ))
            ) : (
              <p className="review-empty">暂无审计记录</p>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone: Tone }) {
  return (
    <div className={`admin-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ChampionBoard({ teams }: { teams: Team[] }) {
  return (
    <div className="champion-list">
      {teams.map((team, index) => (
        <article className="champion-row" key={team.key}>
          <span>{index + 1}</span>
          <TeamFlag team={team.key} code={team.code} />
          <div>
            <strong>{team.name}</strong>
            <small>
              决赛 {team.tournament.final}% · 四强 {team.tournament.semifinal}%
            </small>
          </div>
          <b>{team.tournament.champion}%</b>
          <em className={team.tournament.change >= 0 ? "green" : "red"}>{formatSignedPercent(team.tournament.change)}</em>
        </article>
      ))}
    </div>
  );
}

function DailyMoversPanel({ movers }: { movers?: DailyMovers }) {
  if (!movers) {
    return <p className="review-empty">等待下一次日更快照生成今日变化</p>;
  }
  if (movers.items.length === 0) {
    return <p className="review-empty">{movers.baseline === "previous_snapshot" ? "上一快照暂无冠军概率变化" : "等待下一次日更快照生成今日变化"}</p>;
  }

  return (
    <div className="mover-list">
      <div className="mover-summary">
        <span>
          上调 <b className="green">{movers.summary.up}</b>
        </span>
        <span>
          下调 <b className="red">{movers.summary.down}</b>
        </span>
      </div>
      {movers.items.slice(0, 6).map((item) => (
        <article className={`mover-row ${item.direction}`} key={item.team}>
          <TeamFlag team={item.team} code={item.code} />
          <div>
            <strong>{item.name}</strong>
            <small>
              {item.previousChampion.toFixed(1)}% → {item.currentChampion.toFixed(1)}% · {item.reason}
            </small>
            {item.reasons && item.reasons.length > 1 ? (
              <ul className="mover-reasons">
                {item.reasons.slice(1, 4).map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : null}
          </div>
          <b className={item.direction === "up" ? "green" : "red"}>{formatSignedPercent(item.change)}</b>
        </article>
      ))}
    </div>
  );
}

function EventReviewPanel({
  eventReview,
  pendingId,
  snapshotPending,
  message,
  onReview,
  onRebuildSnapshot,
}: {
  eventReview: EventReviewResponse | null;
  pendingId: string | null;
  snapshotPending: boolean;
  message: string | null;
  onReview: (item: EventReviewItem, status: ReviewStatus) => void;
  onRebuildSnapshot: () => void;
}) {
  if (!eventReview) {
    return <p className="review-empty">事件审核等待 API 连接</p>;
  }

  const reviewItems = eventReview.items.filter((item) => item.id);
  const visibleItems = reviewItems.filter((item) => item.action === "watch");
  const queue = visibleItems.length > 0 ? visibleItems : reviewItems.slice(0, 4);

  return (
    <div className="review-dashboard">
      <div className="review-summary">
        <span>
          原始新闻 <b>{eventReview.rawNewsCount}</b>
        </span>
        <span>
          入模 <b>{eventReview.summary.applied}</b>
        </span>
        <span>
          待审 <b>{eventReview.summary.reviewRequired}</b>
        </span>
        <span>
          忽略 <b>{eventReview.summary.ignored}</b>
        </span>
      </div>
      <button className="snapshot-button" disabled={snapshotPending} onClick={onRebuildSnapshot}>
        {snapshotPending ? "重建中" : "重建快照"}
      </button>
      <div className="review-list">
        {queue.map((item) => (
          <article className={`review-row ${item.action}`} key={item.id}>
            <div className="review-copy">
              <strong>{item.title}</strong>
              <p>{item.detail}</p>
              <small>
                {item.sourceLevel}级 · {item.status} · {item.source}
              </small>
            </div>
            <div className="review-meta">
              <span>{item.team ?? "全局"}</span>
              <em>{item.impact}</em>
            </div>
            {item.action === "watch" ? (
              <div className="review-actions">
                <button disabled={pendingId === item.id} onClick={() => onReview(item, "multi_source")}>
                  多源确认
                </button>
                <button disabled={pendingId === item.id} onClick={() => onReview(item, "unverified")}>
                  忽略
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {message ? <p className="review-message">{message}</p> : null}
    </div>
  );
}

export default App;
