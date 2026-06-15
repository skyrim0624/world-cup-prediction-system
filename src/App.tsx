import { Fragment, FormEvent, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BatteryFull,
  CalendarDays,
  ChevronRight,
  CheckCircle2,
  CircleDollarSign,
  Clock,
  Crown,
  FileText,
  Hourglass,
  Info,
  Lock,
  LockKeyhole,
  Menu,
  Newspaper,
  QrCode,
  RefreshCw,
  Share2,
  ShieldCheck,
  Signal,
  Target,
  Trophy,
  WalletCards,
  Wifi,
  type LucideIcon,
} from "lucide-react";

type TeamKey = string;
type Tone = "green" | "blue" | "gold" | "orange" | "red" | "muted";
type UserScreenKey = "forecast" | "matches" | "board" | "news";
type LoadStatus = "loading" | "ready" | "failed";
type FactorImpactMap = Record<string, Record<string, number>>;
type CustomStyle = CSSProperties & Record<string, string | number>;

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

type MatchNewsItem = NewsItem & {
  sourceLabel?: string;
  sourceTier?: string;
  direction?: "positive" | "neutral" | "negative";
  affectedTeam?: string;
  factor?: string;
};

type ReviewStatus = "confirmed" | "multi_source" | "single_source" | "unverified" | "rumor";
type AdminAccessState = "checking" | "locked" | "ready";

type EventReviewSummary = {
  watched: number;
  applied: number;
  ignored: number;
  reviewRequired: number;
  singleSource: number;
  multiSource: number;
  confirmed: number;
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
  newsVerification?: {
    rawNews: number;
    singleSource: number;
    multiSource: number;
    confirmed: number;
    reviewRequired: number;
    ignored: number;
    applied: number;
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

function predictionRunStatusLabel(status: PredictionRunStatus) {
  if (status === "ran") return "已执行";
  if (status === "skipped") return "跳过";
  if (status === "manual") return "待人工";
  if (status === "available") return "可调用";
  if (status === "snapshot") return "快照";
  if (status === "live_compute") return "实时算";
  return status;
}

function predictionRunStatusTone(status: PredictionRunStatus): Tone {
  if (status === "ran" || status === "snapshot") return "green";
  if (status === "manual" || status === "available") return "gold";
  if (status === "skipped") return "muted";
  return "blue";
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

type PredictionRunStatus = "ran" | "skipped" | "manual" | "available" | "snapshot" | "live_compute" | string;

type PredictionRunStep = {
  id: string;
  label: string;
  functionName: string;
  moduleName: string;
  status: PredictionRunStatus;
  detail: string;
  interfacePath?: string | null;
};

type PredictionRunStage = {
  id: string;
  title: string;
  status: PredictionRunStatus;
  steps: PredictionRunStep[];
};

type PredictionRunInterface = {
  method: string;
  path: string;
  status: PredictionRunStatus;
  detail: string;
};

type PredictionInterventionPoint = {
  label: string;
  endpoint: string;
  affects: string;
};

type PredictionRunMonitor = {
  generatedAt: string;
  match: {
    homeTeam: string;
    awayTeam: string;
    homeName: string;
    awayName: string;
    homeCode: string;
    awayCode: string;
    stage: string;
    kickoff: string;
    status: string;
  };
  summary: {
    totalSteps: number;
    ranSteps: number;
    skippedSteps: number;
    manualSteps: number;
    interventionPoints: number;
    snapshotReady: boolean;
  };
  pipeline: PredictionRunStage[];
  interfaces: PredictionRunInterface[];
  interventionPoints: PredictionInterventionPoint[];
};

type ScoreOutcome = {
  score: string;
  probability: number;
  note: string;
  tone: Tone;
};

type ScoreMatrixCell = {
  score: string;
  homeGoals: number;
  awayGoals: number;
  probability: number;
};

type GoalMarket = {
  label: string;
  probability: number;
  fairDecimal: number;
  note: string;
  tone: Tone;
};

type FairPrice = {
  label: string;
  probability: number;
  fairDecimal: number;
  note: string;
  tone: Tone;
};

type MarketSource = {
  status: string;
  label: string;
  detail: string;
};

type CreatorTopic = {
  title: string;
  detail: string;
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

type PublicUpcomingMatch = {
  stage: string;
  kickoff: string;
  matchNo?: number | null;
  status: string;
  homeTeam: TeamKey;
  awayTeam: TeamKey;
  homeName: string;
  awayName: string;
  homeCode: string;
  awayCode: string;
};

type PublicMatchSummary = PublicUpcomingMatch;

type PublicUpcomingMatchesResponse = {
  updatedAt: string;
  count: number;
  items: PublicUpcomingMatch[];
};

type PostMatchReview = {
  status: string;
  actualScore?: string | null;
  message?: string;
  hasPredictionBaseline?: boolean;
  predictedTopScore?: string;
  predictedTopProbability?: number;
  summary?: string;
  severity?: "low" | "medium" | "high" | string;
  winnerMissed?: boolean;
  totalGoalError?: number;
  rootCauses?: string[];
};

type FinishedMatch = PublicUpcomingMatch & {
  city?: string | null;
  stadium?: string | null;
  homeScore: number;
  awayScore: number;
  modelUse?: string;
  modelUseLabel?: string;
  postMatchReview?: PostMatchReview;
};

type FinishedMatchesResponse = {
  updatedAt: string;
  count: number;
  items: FinishedMatch[];
};

type PublicMatchFilter = "today" | "tomorrow" | "all";

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
  scoreMatrix?: ScoreMatrixCell[];
  goalMarkets?: GoalMarket[];
  fairPrices?: FairPrice[];
  marketSource?: MarketSource;
  scenarioImpacts: ScenarioImpact[];
  creatorTopics?: CreatorTopic[];
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
  scoreMatrix?: ScoreMatrixCell[];
  goalMarkets?: GoalMarket[];
  fairPrices?: FairPrice[];
  marketSource?: MarketSource;
  pillars?: {
    home: Record<string, number>;
    away: Record<string, number>;
  };
  scenarioImpacts: ScenarioImpact[];
  creatorTopics?: CreatorTopic[];
  newsItems?: MatchNewsItem[];
  analysis: string[];
};

type PaymentOrderStatus = "customer_interface_ready" | "provider_config_required" | "pending" | "payment_pending" | "paid" | "expired" | "failed" | string;

type PaymentOrder = {
  orderId: string;
  productKey: string;
  productName: string;
  amountLabel?: string;
  provider: string;
  providerLabel: string;
  paymentMethod: string;
  paymentMethodLabel?: string;
  status: PaymentOrderStatus;
  qrCodeUrl?: string | null;
  createdAt: string;
  expiresAt: string;
  metadata?: {
    contentKey?: string;
    matchKey?: string;
    homeTeam?: TeamKey;
    awayTeam?: TeamKey;
    homeName?: string;
    awayName?: string;
  };
};

type AccessProduct = {
  key: string;
  name: string;
  scope: string;
  amountLabel: string;
  status: string;
};

type AccessOptions = {
  paymentConfigured: boolean;
  products: AccessProduct[];
  disclaimer: string;
};

type PaymentProviderConfig = {
  provider: string;
  label: string;
  paymentMethod: string;
  paymentMethodLabel?: string;
  configured: boolean;
};

type PaymentConfig = {
  ready: boolean;
  providers: PaymentProviderConfig[];
  disclaimer: string;
};

type CheckoutProviderOption = {
  key: "wechat" | "alipay";
  provider: string;
  label: string;
  methodLabel: string;
  configured: boolean;
  Icon: LucideIcon;
};

type CheckoutState = "loading_config" | "ready" | "creating_order" | "provider_config_required" | "failed";

type AccessDecision = {
  allowed: boolean;
  reason: string;
  orderId?: string;
  productKey?: string | null;
  paymentStatus?: string | null;
  requiredProducts: string[];
};

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
    key: "curacao",
    name: "库拉索",
    code: "CUW",
    factors: { strength: 61, form: 68, path: 60, squad: 69, margin: 68 },
    tournament: { champion: 0, final: 0, semifinal: 0, quarterfinal: 0.4, change: 0 },
  },
  {
    key: "netherlands",
    name: "荷兰",
    code: "NED",
    factors: { strength: 82, form: 83, path: 69, squad: 80, margin: 83 },
    tournament: { champion: 7.1, final: 15.8, semifinal: 28.6, quarterfinal: 51.9, change: -0.3 },
  },
];

const INTERACTIVE_SIMULATION_COUNT = 1200;
const FORECAST_REFRESH_MS = 15000;
const TOURNAMENT_YEAR = 2026;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
const FORCE_ADMIN_CONSOLE = import.meta.env.VITE_FORCE_ADMIN === "1";
const SINGLE_MATCH_ROUTE_PREFIX = "/match/";
const SINGLE_MATCH_CHECKOUT_ROUTE_PREFIX = "/checkout/";
const POST_MATCH_REVIEW_ROUTE_PREFIX = "/review/";
const PAYMENT_PENDING_ROUTE = "/payment/pending";
const CHAMPION_BOARD_ROUTE = "/champion-board";
const PAYMENT_ORDER_REFRESH_MS = 5000;
const UNLOCKED_MATCH_PREVIEW_PARAM = "unlocked";

const USER_SCREENS: { key: UserScreenKey; hash: string; label: string; Icon: LucideIcon }[] = [
  { key: "forecast", hash: "forecast", label: "预测", Icon: Target },
  { key: "matches", hash: "matches", label: "赛程", Icon: CalendarDays },
  { key: "board", hash: "board", label: "榜单", Icon: Trophy },
  { key: "news", hash: "news", label: "新闻", Icon: Newspaper },
];

const PUBLIC_MATCH_TABS: { key: PublicMatchFilter; label: string }[] = [
  { key: "today", label: "今日" },
  { key: "tomorrow", label: "明日" },
  { key: "all", label: "全部" },
];

const STATIC_UPCOMING_MATCHES_FALLBACK: UpcomingMatch[] = [
  {
    stage: "小组赛 E 组",
    kickoff: "6月14日 13:00 ET",
    matchNo: 10,
    city: "Houston",
    stadium: "Houston Stadium",
    status: "scheduled",
    homeTeam: "germany",
    awayTeam: "curacao",
    homeName: "德国",
    awayName: "库拉索",
    homeCode: "GER",
    awayCode: "CUW",
    homeWin: 84,
    draw: 11,
    awayWin: 5,
    topScore: { score: "3-0", probability: 11.6 },
  },
  {
    stage: "小组赛 F 组",
    kickoff: "6月14日 16:00 ET",
    matchNo: 11,
    city: "Dallas",
    stadium: "Dallas Stadium",
    status: "scheduled",
    homeTeam: "netherlands",
    awayTeam: "japan",
    homeName: "荷兰",
    awayName: "日本",
    homeCode: "NED",
    awayCode: "JPN",
    homeWin: 50,
    draw: 24,
    awayWin: 26,
    topScore: { score: "1-1", probability: 10.6 },
  },
  {
    stage: "小组赛 E 组",
    kickoff: "6月14日 19:00 ET",
    matchNo: 9,
    city: "Philadelphia",
    stadium: "Philadelphia Stadium",
    status: "scheduled",
    homeTeam: "cote-divoire",
    awayTeam: "ecuador",
    homeName: "科特迪瓦",
    awayName: "厄瓜多尔",
    homeCode: "CIV",
    awayCode: "ECU",
    homeWin: 33,
    draw: 26,
    awayWin: 41,
    topScore: { score: "1-1", probability: 11.8 },
  },
  {
    stage: "小组赛 F 组",
    kickoff: "6月14日 22:00 ET",
    matchNo: 12,
    city: "Monterrey",
    stadium: "Monterrey Stadium",
    status: "scheduled",
    homeTeam: "sweden",
    awayTeam: "tunisia",
    homeName: "瑞典",
    awayName: "突尼斯",
    homeCode: "SWE",
    awayCode: "TUN",
    homeWin: 46,
    draw: 25,
    awayWin: 29,
    topScore: { score: "1-1", probability: 11.8 },
  },
  {
    stage: "小组赛 H 组",
    kickoff: "6月15日 12:00 ET",
    matchNo: 14,
    city: "Atlanta",
    stadium: "Atlanta Stadium",
    status: "scheduled",
    homeTeam: "spain",
    awayTeam: "cape-verde",
    homeName: "西班牙",
    awayName: "佛得角",
    homeCode: "ESP",
    awayCode: "CPV",
    homeWin: 85,
    draw: 10,
    awayWin: 5,
    topScore: { score: "3-0", probability: 12.0 },
  },
  {
    stage: "小组赛 G 组",
    kickoff: "6月15日 15:00 ET",
    matchNo: 16,
    city: "Seattle",
    stadium: "Seattle Stadium",
    status: "scheduled",
    homeTeam: "belgium",
    awayTeam: "egypt",
    homeName: "比利时",
    awayName: "埃及",
    homeCode: "BEL",
    awayCode: "EGY",
    homeWin: 57,
    draw: 22,
    awayWin: 21,
    topScore: { score: "1-1", probability: 10.0 },
  },
  {
    stage: "小组赛 H 组",
    kickoff: "6月15日 18:00 ET",
    matchNo: 13,
    city: "Miami",
    stadium: "Miami Stadium",
    status: "scheduled",
    homeTeam: "saudi-arabia",
    awayTeam: "uruguay",
    homeName: "沙特阿拉伯",
    awayName: "乌拉圭",
    homeCode: "KSA",
    awayCode: "URU",
    homeWin: 18,
    draw: 22,
    awayWin: 60,
    topScore: { score: "0-1", probability: 10.3 },
  },
  {
    stage: "小组赛 G 组",
    kickoff: "6月15日 21:00 ET",
    matchNo: 15,
    city: "Los Angeles",
    stadium: "Los Angeles Stadium",
    status: "scheduled",
    homeTeam: "iran",
    awayTeam: "new-zealand",
    homeName: "伊朗",
    awayName: "新西兰",
    homeCode: "IRN",
    awayCode: "NZL",
    homeWin: 62,
    draw: 21,
    awayWin: 17,
    topScore: { score: "2-0", probability: 11.2 },
  },
  {
    stage: "小组赛 J 组",
    kickoff: "6月16日 00:00 ET",
    matchNo: 20,
    city: "San Francisco Bay Area",
    stadium: "San Francisco Bay Stadium",
    status: "scheduled",
    homeTeam: "austria",
    awayTeam: "jordan",
    homeName: "奥地利",
    awayName: "约旦",
    homeCode: "AUT",
    awayCode: "JOR",
    homeWin: 63,
    draw: 21,
    awayWin: 16,
    topScore: { score: "2-0", probability: 10.9 },
  },
  {
    stage: "小组赛 I 组",
    kickoff: "6月16日 15:00 ET",
    matchNo: 17,
    city: "New York/New Jersey",
    stadium: "New York New Jersey Stadium",
    status: "scheduled",
    homeTeam: "france",
    awayTeam: "senegal",
    homeName: "法国",
    awayName: "塞内加尔",
    homeCode: "FRA",
    awayCode: "SEN",
    homeWin: 63,
    draw: 20,
    awayWin: 17,
    topScore: { score: "2-1", probability: 9.8 },
  },
  {
    stage: "小组赛 I 组",
    kickoff: "6月16日 18:00 ET",
    matchNo: 18,
    city: "Boston",
    stadium: "Boston Stadium",
    status: "scheduled",
    homeTeam: "iraq",
    awayTeam: "norway",
    homeName: "伊拉克",
    awayName: "挪威",
    homeCode: "IRQ",
    awayCode: "NOR",
    homeWin: 25,
    draw: 24,
    awayWin: 51,
    topScore: { score: "1-1", probability: 10.8 },
  },
  {
    stage: "小组赛 J 组",
    kickoff: "6月16日 21:00 ET",
    matchNo: 19,
    city: "Kansas City",
    stadium: "Kansas City Stadium",
    status: "scheduled",
    homeTeam: "argentina",
    awayTeam: "algeria",
    homeName: "阿根廷",
    awayName: "阿尔及利亚",
    homeCode: "ARG",
    awayCode: "ALG",
    homeWin: 68,
    draw: 18,
    awayWin: 14,
    topScore: { score: "2-0", probability: 10.5 },
  },
];

const TEAM_FLAG_ASSET_BY_KEY: Record<TeamKey, string> = {
  mexico: "mx",
  "south-africa": "za",
  "south-korea": "kr",
  czechia: "cz",
  canada: "ca",
  "bosnia-herzegovina": "ba",
  qatar: "qa",
  switzerland: "ch",
  brazil: "br",
  morocco: "ma",
  haiti: "ht",
  scotland: "gb-sct",
  usa: "us",
  paraguay: "py",
  australia: "au",
  turkiye: "tr",
  germany: "de",
  curacao: "cw",
  "cote-divoire": "ci",
  ecuador: "ec",
  netherlands: "nl",
  japan: "jp",
  tunisia: "tn",
  sweden: "se",
  belgium: "be",
  egypt: "eg",
  iran: "ir",
  "new-zealand": "nz",
  spain: "es",
  "cape-verde": "cv",
  "saudi-arabia": "sa",
  uruguay: "uy",
  france: "fr",
  senegal: "sn",
  iraq: "iq",
  norway: "no",
  argentina: "ar",
  algeria: "dz",
  austria: "at",
  jordan: "jo",
  portugal: "pt",
  "dr-congo": "cd",
  uzbekistan: "uz",
  colombia: "co",
  england: "gb-eng",
  croatia: "hr",
  ghana: "gh",
  panama: "pa",
};

const TEAM_FLAG_ASSET_BY_CODE: Record<string, string> = {
  MEX: "mx",
  RSA: "za",
  KOR: "kr",
  CZE: "cz",
  CAN: "ca",
  BIH: "ba",
  QAT: "qa",
  SUI: "ch",
  BRA: "br",
  MAR: "ma",
  HAI: "ht",
  SCO: "gb-sct",
  USA: "us",
  PAR: "py",
  AUS: "au",
  TUR: "tr",
  GER: "de",
  CUW: "cw",
  CIV: "ci",
  ECU: "ec",
  NED: "nl",
  JPN: "jp",
  TUN: "tn",
  SWE: "se",
  BEL: "be",
  EGY: "eg",
  IRN: "ir",
  NZL: "nz",
  ESP: "es",
  CPV: "cv",
  KSA: "sa",
  URU: "uy",
  FRA: "fr",
  SEN: "sn",
  IRQ: "iq",
  NOR: "no",
  ARG: "ar",
  ALG: "dz",
  AUT: "at",
  JOR: "jo",
  POR: "pt",
  COD: "cd",
  UZB: "uz",
  COL: "co",
  ENG: "gb-eng",
  CRO: "hr",
  GHA: "gh",
  PAN: "pa",
};

const fallbackNewsItems: NewsItem[] = [
  { title: "官方赛程", detail: "德国对库拉索为 FIFA 官方赛程中的小组赛 E 组比赛", impact: "赛程确认", tone: "green", time: "官方" },
  { title: "数据兜底", detail: "预测接口短暂不可用时，只保留已核验赛程，不展示未核验对阵", impact: "保护展示", tone: "gold", time: "自动" },
  { title: "新闻校验", detail: "未证实传闻不进入公开预测主判断", impact: "不采信", tone: "muted", time: "持续" },
];

const fallbackGoalMarkets: GoalMarket[] = [
  { label: "大 2.5", probability: 71.3, fairDecimal: 1.4, note: "总进球至少 3", tone: "green" },
  { label: "小 2.5", probability: 28.7, fairDecimal: 3.49, note: "总进球不超过 2", tone: "blue" },
  { label: "BTTS 是", probability: 45.2, fairDecimal: 2.21, note: "双方都有进球", tone: "blue" },
  { label: "BTTS 否", probability: 54.8, fairDecimal: 1.82, note: "至少一队零进球", tone: "gold" },
];

const fallbackScoreMatrix: ScoreMatrixCell[] = [
  { score: "0-0", homeGoals: 0, awayGoals: 0, probability: 2.3 },
  { score: "0-1", homeGoals: 0, awayGoals: 1, probability: 1.5 },
  { score: "0-2", homeGoals: 0, awayGoals: 2, probability: 0.5 },
  { score: "0-3", homeGoals: 0, awayGoals: 3, probability: 0.1 },
  { score: "0-4", homeGoals: 0, awayGoals: 4, probability: 0 },
  { score: "1-0", homeGoals: 1, awayGoals: 0, probability: 7.1 },
  { score: "1-1", homeGoals: 1, awayGoals: 1, probability: 4.7 },
  { score: "1-2", homeGoals: 1, awayGoals: 2, probability: 1.5 },
  { score: "1-3", homeGoals: 1, awayGoals: 3, probability: 0.3 },
  { score: "1-4", homeGoals: 1, awayGoals: 4, probability: 0.1 },
  { score: "2-0", homeGoals: 2, awayGoals: 0, probability: 11.1 },
  { score: "2-1", homeGoals: 2, awayGoals: 1, probability: 7.3 },
  { score: "2-2", homeGoals: 2, awayGoals: 2, probability: 2.4 },
  { score: "2-3", homeGoals: 2, awayGoals: 3, probability: 0.5 },
  { score: "2-4", homeGoals: 2, awayGoals: 4, probability: 0.1 },
  { score: "3-0", homeGoals: 3, awayGoals: 0, probability: 11.6 },
  { score: "3-1", homeGoals: 3, awayGoals: 1, probability: 7.6 },
  { score: "3-2", homeGoals: 3, awayGoals: 2, probability: 2.5 },
  { score: "3-3", homeGoals: 3, awayGoals: 3, probability: 0.5 },
  { score: "3-4", homeGoals: 3, awayGoals: 4, probability: 0.1 },
  { score: "4-0", homeGoals: 4, awayGoals: 0, probability: 9.1 },
  { score: "4-1", homeGoals: 4, awayGoals: 1, probability: 5.9 },
  { score: "4-2", homeGoals: 4, awayGoals: 2, probability: 1.9 },
  { score: "4-3", homeGoals: 4, awayGoals: 3, probability: 0.4 },
  { score: "4-4", homeGoals: 4, awayGoals: 4, probability: 0.1 },
];

const fallbackMarketSource: MarketSource = {
  status: "pending",
  label: "市场热度暂不展示",
  detail: "授权数据确认后，再开放市场热度参考。",
};

function buildFallbackPrediction(referenceDate = new Date()): MatchPrediction {
  const match = firstStaticUpcomingMatch(referenceDate);
  const homeWin = match.homeWin;
  const draw = match.draw;
  const awayWin = match.awayWin;

  return {
    stage: match.stage,
    kickoff: match.kickoff,
    matchNo: match.matchNo,
    city: match.city,
    stadium: match.stadium,
    status: "未开赛",
    homeTeam: match.homeTeam,
    awayTeam: match.awayTeam,
    homeWin,
    draw,
    awayWin,
    updatedAt: new Date().toISOString(),
    scoreOutcomes: [
      { score: "3-0", probability: 11.6, note: "德国进攻盘优势明显", tone: "green" },
      { score: "2-0", probability: 11.1, note: "低失球胜局仍有空间", tone: "blue" },
      { score: "4-0", probability: 9.1, note: "强弱差扩大时的高比分分支", tone: "gold" },
    ],
    scoreMatrix: fallbackScoreMatrix,
    goalMarkets: fallbackGoalMarkets,
    fairPrices: [
      { label: `${match.homeName}胜`, probability: homeWin, fairDecimal: Number((100 / homeWin).toFixed(2)), note: "90 分钟模型公平概率", tone: "green" },
      { label: "平局", probability: draw, fairDecimal: Number((100 / draw).toFixed(2)), note: "90 分钟模型公平概率", tone: "gold" },
      { label: `${match.awayName}胜`, probability: awayWin, fairDecimal: Number((100 / awayWin).toFixed(2)), note: "90 分钟模型公平概率", tone: "blue" },
    ],
    marketSource: fallbackMarketSource,
    scenarioImpacts: [
      {
        label: `${match.homeName}胜`,
        probability: homeWin,
        title: `${match.homeName}小组第一概率上升`,
        details: [`${match.homeName}夺冠概率小幅上调`, `${match.awayName}路径盘下调`, "同组竞争队出线门槛抬高"],
        championShift: "+0.2%",
        tone: "green",
      },
      {
        label: "打平",
        probability: draw,
        title: "小组路径保留变数",
        details: [`${match.homeName}小组第一概率回落`, `${match.awayName}保留抢分空间`, "后续净胜球权重上升"],
        championShift: "-0.6%",
        tone: "gold",
      },
      {
        label: `${match.awayName}胜`,
        probability: awayWin,
        title: `${match.awayName}爆冷后路径压力下降`,
        details: [`${match.awayName}小组出线概率上升`, `${match.homeName}潜在淘汰赛路径变难`, "小组第二路径风险上升"],
        championShift: "±0.0%",
        tone: "blue",
      },
    ],
    analysis: [
      `${match.homeName}单场胜率 ${homeWin}%，优势来自基础实力和进攻盘。`,
      `平局概率 ${draw}%，会让小组第一继续依赖后续赛果。`,
      "预测接口短暂不可用时，公开页只使用已核验官方赛程兜底。",
    ],
    newsItems: fallbackNewsItems,
    creatorTopics: [
      { title: "3-0 为什么是最可能比分？", detail: "从进球期望、双方防守质量和小组赛动机解释。" },
      { title: "德国赢球会怎样改变半区？", detail: "把小组第一、潜在 32 强对手和冠军概率串起来。" },
      { title: "大小球与 BTTS 的分歧点", detail: "用比分矩阵说明总进球和双方进球不一定同向。" },
    ],
  };
}

function predictionToUpcomingMatch(prediction: MatchPrediction, homeTeam: Team | undefined, awayTeam: Team | undefined): UpcomingMatch {
  const topScore = prediction.scoreOutcomes[0] ?? { score: "--", probability: 0 };
  return {
    stage: prediction.stage,
    kickoff: prediction.kickoff,
    matchNo: prediction.matchNo ?? null,
    city: prediction.city ?? null,
    stadium: prediction.stadium ?? null,
    status: prediction.status,
    homeTeam: prediction.homeTeam,
    awayTeam: prediction.awayTeam,
    homeName: homeTeam?.name ?? prediction.homeTeam,
    awayName: awayTeam?.name ?? prediction.awayTeam,
    homeCode: homeTeam?.code ?? prediction.homeTeam.toUpperCase().slice(0, 3),
    awayCode: awayTeam?.code ?? prediction.awayTeam.toUpperCase().slice(0, 3),
    homeWin: prediction.homeWin,
    draw: prediction.draw,
    awayWin: prediction.awayWin,
    topScore: {
      score: topScore.score,
      probability: topScore.probability,
    },
  };
}

function formatUpdateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未更新";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

function parseKickoffDate(value: string) {
  if (!value || value === "待定" || value === "进行中" || value === "已结束") return null;
  const easternMatch = value.match(/(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})\s*ET/i);
  if (easternMatch) {
    const [, month, day, hour, minute] = easternMatch;
    return new Date(Date.UTC(TOURNAMENT_YEAR, Number(month) - 1, Number(day), Number(hour) + 4, Number(minute)));
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function compareUpcomingMatches(left: UpcomingMatch, right: UpcomingMatch) {
  const leftTime = parseKickoffDate(left.kickoff)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  const rightTime = parseKickoffDate(right.kickoff)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  return leftTime - rightTime || (left.matchNo ?? 999) - (right.matchNo ?? 999);
}

function isUpcomingMatch(match: Pick<UpcomingMatch, "kickoff" | "status">, referenceDate = new Date()) {
  if (match.status !== "scheduled" && match.status !== "未开赛") return false;
  const kickoffDate = parseKickoffDate(match.kickoff);
  if (!kickoffDate) return true;
  return kickoffDate.getTime() > referenceDate.getTime();
}

function filterUpcomingMatches(matches: UpcomingMatch[], referenceDate = new Date()) {
  return matches.filter((match) => isUpcomingMatch(match, referenceDate)).sort(compareUpcomingMatches);
}

function toPublicUpcomingMatch(match: UpcomingMatch): PublicUpcomingMatch {
  return {
    stage: match.stage,
    kickoff: match.kickoff,
    matchNo: match.matchNo ?? null,
    status: match.status,
    homeTeam: match.homeTeam,
    awayTeam: match.awayTeam,
    homeName: match.homeName,
    awayName: match.awayName,
    homeCode: match.homeCode,
    awayCode: match.awayCode,
  };
}

function comparePublicUpcomingMatches(left: PublicUpcomingMatch, right: PublicUpcomingMatch) {
  const leftTime = parseKickoffDate(left.kickoff)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  const rightTime = parseKickoffDate(right.kickoff)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  return leftTime - rightTime || (left.matchNo ?? 999) - (right.matchNo ?? 999);
}

function isPublicUpcomingMatch(match: Pick<PublicUpcomingMatch, "kickoff" | "status">, referenceDate = new Date()) {
  if (match.status !== "scheduled" && match.status !== "未开赛") return false;
  const kickoffDate = parseKickoffDate(match.kickoff);
  if (!kickoffDate) return true;
  return kickoffDate.getTime() > referenceDate.getTime();
}

function filterPublicUpcomingMatches(matches: PublicUpcomingMatch[], referenceDate = new Date()) {
  return matches.filter((match) => isPublicUpcomingMatch(match, referenceDate)).sort(comparePublicUpcomingMatches);
}

function publicMatchesForTab(matches: PublicUpcomingMatch[], activeFilter: PublicMatchFilter, referenceDate = new Date()) {
  if (activeFilter === "all") return matches;

  const targetDate = new Date(referenceDate);
  if (activeFilter === "tomorrow") {
    targetDate.setUTCDate(targetDate.getUTCDate() + 1);
  }
  const targetKey = formatDateKeyInTimeZone(targetDate, "America/New_York");
  return matches.filter((match) => {
    const kickoffDate = parseKickoffDate(match.kickoff);
    return kickoffDate ? formatDateKeyInTimeZone(kickoffDate, "America/New_York") === targetKey : false;
  });
}

function buildStaticPublicUpcomingMatchesFallback(referenceDate = new Date()): PublicUpcomingMatchesResponse {
  const items = filterPublicUpcomingMatches(STATIC_UPCOMING_MATCHES_FALLBACK.map(toPublicUpcomingMatch), referenceDate);
  return {
    updatedAt: "static-fallback",
    count: items.length,
    items,
  };
}

function publicMatchStatusLabel(status: string) {
  if (status === "scheduled") return "未开赛";
  if (status === "live") return "进行中";
  if (status === "finished") return "已结束";
  return status;
}

function formatDateKeyInTimeZone(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function formatKickoffForPublicList(value: string) {
  if (!value || value === "待定" || value === "进行中" || value === "已结束") return value;
  if (/\bET\b/i.test(value)) return value.replace(/\s+/g, " ").trim();

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "America/New_York",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("month")}月${part("day")}日 ${part("hour")}:${part("minute")} ET`;
}

function buildStaticUpcomingMatchesFallback(referenceDate = new Date()): UpcomingMatchesResponse {
  const items = filterUpcomingMatches(STATIC_UPCOMING_MATCHES_FALLBACK, referenceDate);
  return {
    updatedAt: "static-fallback",
    count: items.length,
    items,
  };
}

function firstStaticUpcomingMatch(referenceDate = new Date()) {
  return filterUpcomingMatches(STATIC_UPCOMING_MATCHES_FALLBACK, referenceDate)[0] ?? STATIC_UPCOMING_MATCHES_FALLBACK[0];
}

function publicSummaryFromUpcomingMatch(match: UpcomingMatch): PublicUpcomingMatch {
  return {
    stage: match.stage,
    kickoff: match.kickoff,
    matchNo: match.matchNo ?? null,
    status: match.status,
    homeTeam: match.homeTeam,
    awayTeam: match.awayTeam,
    homeName: match.homeName,
    awayName: match.awayName,
    homeCode: match.homeCode,
    awayCode: match.awayCode,
  };
}

function staticMatchSummaryFallback(home: TeamKey, away: TeamKey): PublicUpcomingMatch | null {
  const match = STATIC_UPCOMING_MATCHES_FALLBACK.find((item) => item.homeTeam === home && item.awayTeam === away);
  return match ? publicSummaryFromUpcomingMatch(match) : null;
}

function teamFromUpcomingFallback(teamKey: TeamKey): Team | null {
  const match = STATIC_UPCOMING_MATCHES_FALLBACK.find((item) => item.homeTeam === teamKey || item.awayTeam === teamKey);
  if (!match) return null;
  const isHome = match.homeTeam === teamKey;
  return {
    key: teamKey,
    name: isHome ? match.homeName : match.awayName,
    code: isHome ? match.homeCode : match.awayCode,
    factors: { strength: 70, form: 70, path: 70, squad: 70, margin: 70 },
    tournament: { champion: 0, final: 0, semifinal: 0, quarterfinal: 0, change: 0 },
  };
}

function resolveDisplayTeam(teamKey: TeamKey, teamsData: Team[]): Team {
  return teamsData.find((team) => team.key === teamKey) ?? teamFromUpcomingFallback(teamKey) ?? {
    key: teamKey,
    name: teamKey,
    code: teamKey.toUpperCase().slice(0, 3),
    factors: { strength: 70, form: 70, path: 70, squad: 70, margin: 70 },
    tournament: { champion: 0, final: 0, semifinal: 0, quarterfinal: 0, change: 0 },
  };
}

function formatKickoffForUser(value: string) {
  if (!value || value === "待定" || value === "进行中" || value === "已结束") return value;
  if (value.includes("北京时间")) return value;

  const easternMatch = value.match(/(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})\s*ET/i);
  if (easternMatch) {
    const [, month, day, hour, minute] = easternMatch;
    const beijingDate = new Date(Date.UTC(TOURNAMENT_YEAR, Number(month) - 1, Number(day), Number(hour) + 12, Number(minute)));
    const beijingMonth = beijingDate.getUTCMonth() + 1;
    const beijingDay = beijingDate.getUTCDate();
    const beijingHour = String(beijingDate.getUTCHours()).padStart(2, "0");
    const beijingMinute = String(beijingDate.getUTCMinutes()).padStart(2, "0");
    return `${beijingMonth}月${beijingDay}日 ${beijingHour}:${beijingMinute} 北京时间`;
  }

  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    const parts = new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(date);
    const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
    return `${part("month")}月${part("day")}日 ${part("hour")}:${part("minute")} 北京时间`;
  }

  return value.replace(/\s*ET\b/i, "");
}

function formatSignedPercent(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatSignedNumber(value: number) {
  if (Math.abs(value) < 0.05) return "0";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function formatSignedDecimal(value: number) {
  if (Math.abs(value) < 0.05) return "0.0";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function formatProbabilityValue(value: number) {
  return `${value.toFixed(1)}%`;
}

function userNewsImpactLabel(value: string) {
  if (value.includes("不入模型") || value.includes("已忽略")) return "不采信";
  if (value.includes("入模") || value.includes("可入模型")) return "已确认";
  return value.replace(/模型/g, "判断");
}

function userNewsDetail(value: string) {
  return value.replace("不改变概率", "暂不采信").replace(/模型/g, "判断");
}

function fairPriceLabel(value: number) {
  if (!value) return "--";
  return value.toFixed(2);
}

function scoreMatrixFallbackFromOutcomes(outcomes: ScoreOutcome[]): ScoreMatrixCell[] {
  if (outcomes.length === 0) return fallbackScoreMatrix;
  return fallbackScoreMatrix.map((cell) => {
    const matching = outcomes.find((outcome) => outcome.score === cell.score);
    return matching ? { ...cell, probability: matching.probability } : cell;
  });
}

function goalMarketsFallback(): GoalMarket[] {
  return fallbackGoalMarkets;
}

function creatorTopicsFallback(homeName: string, awayName: string, topScore?: string): CreatorTopic[] {
  return [
    { title: `${topScore ?? "最可能比分"} 的内容切入`, detail: `解释 ${homeName} / ${awayName} 的进球期望和比分集中区间。` },
    { title: "路径影响怎么讲", detail: "把单场结果接到小组名次、潜在淘汰赛对手和夺冠概率变化。" },
    { title: "赛果影响怎么讲", detail: "先看胜平负和比分，再解释这场比赛怎样改变小组路径。" },
  ];
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

function checkoutRouteParams(pathname: string) {
  if (!pathname.startsWith(SINGLE_MATCH_CHECKOUT_ROUTE_PREFIX)) return null;
  const [, , home, away] = pathname.split("/");
  if (!home || !away) return null;
  return {
    home: decodeURIComponent(home),
    away: decodeURIComponent(away),
  };
}

function postMatchReviewRouteParams(pathname: string) {
  if (!pathname.startsWith(POST_MATCH_REVIEW_ROUTE_PREFIX)) return null;
  const [, , home, away] = pathname.split("/");
  if (!home || !away) return null;
  return {
    home: decodeURIComponent(home),
    away: decodeURIComponent(away),
  };
}

function userScreenFromHash(): UserScreenKey {
  const hash = window.location.hash.replace("#", "");
  const screen = USER_SCREENS.find((item) => item.hash === hash || item.key === hash);
  if (screen) return screen.key;
  if (hash) {
    window.history.replaceState(null, "", "#forecast");
  }
  return "forecast";
}

function matchPagePath(home: TeamKey, away: TeamKey) {
  return `${SINGLE_MATCH_ROUTE_PREFIX}${encodeURIComponent(home)}/${encodeURIComponent(away)}`;
}

function checkoutPagePath(home: TeamKey, away: TeamKey) {
  return `${SINGLE_MATCH_CHECKOUT_ROUTE_PREFIX}${encodeURIComponent(home)}/${encodeURIComponent(away)}`;
}

function postMatchReviewPagePath(home: TeamKey, away: TeamKey) {
  return `${POST_MATCH_REVIEW_ROUTE_PREFIX}${encodeURIComponent(home)}/${encodeURIComponent(away)}`;
}

function paymentPendingRouteParams(pathname: string) {
  if (pathname !== PAYMENT_PENDING_ROUTE) return null;
  return new URLSearchParams(window.location.search).get("orderId") ?? "";
}

function isChampionBoardRoute(pathname: string) {
  return pathname.replace(/\/$/, "") === CHAMPION_BOARD_ROUTE;
}

function App() {
  if (FORCE_ADMIN_CONSOLE || window.location.pathname === "/admin") {
    return <AdminConsole />;
  }

  if (isChampionBoardRoute(window.location.pathname)) {
    return <ChampionProbabilityPage />;
  }

  const paymentPendingOrderId = paymentPendingRouteParams(window.location.pathname);
  if (paymentPendingOrderId !== null) {
    return <PaymentPendingPage orderId={paymentPendingOrderId} />;
  }

  const checkoutRoute = checkoutRouteParams(window.location.pathname);
  if (checkoutRoute) {
    return <SingleMatchCheckoutPage home={checkoutRoute.home} away={checkoutRoute.away} />;
  }

  const singleMatchRoute = matchRouteParams(window.location.pathname);
  if (singleMatchRoute) {
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.get(UNLOCKED_MATCH_PREVIEW_PARAM) === "1" || searchParams.has("orderId")) {
      return <UnlockedMatchPage home={singleMatchRoute.home} away={singleMatchRoute.away} />;
    }
    return <SingleMatchPage home={singleMatchRoute.home} away={singleMatchRoute.away} />;
  }

  return <HomePredictionPage />;
}

function HomePredictionPage() {
  const [refreshTick, setRefreshTick] = useState(0);
  const [activeFilter, setActiveFilter] = useState<PublicMatchFilter>("today");
  const [matchesStatus, setMatchesStatus] = useState<LoadStatus>("loading");
  const [publicMatches, setPublicMatches] = useState<PublicUpcomingMatchesResponse>(() => buildStaticPublicUpcomingMatchesFallback());
  const referenceDate = useMemo(() => new Date(), [refreshTick]);
  const upcomingMatchItems = useMemo(() => filterPublicUpcomingMatches(publicMatches.items, referenceDate), [publicMatches, referenceDate]);
  const visibleMatches = useMemo(() => publicMatchesForTab(upcomingMatchItems, activeFilter, referenceDate), [upcomingMatchItems, activeFilter, referenceDate]);

  useEffect(() => {
    let active = true;

    async function loadPublicUpcomingMatches() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/public-upcoming-matches?limit=12`, { cache: "no-store" });
        if (!response.ok) throw new Error(`公开赛程接口返回 ${response.status}`);
        const data = (await response.json()) as PublicUpcomingMatchesResponse;
        if (!active) return;
        const items = filterPublicUpcomingMatches(data.items);
        setPublicMatches({ ...data, count: items.length, items });
        setMatchesStatus("ready");
      } catch {
        if (!active) return;
        setPublicMatches(buildStaticPublicUpcomingMatchesFallback());
        setMatchesStatus("failed");
      }
    }

    void loadPublicUpcomingMatches();
    const timer = window.setInterval(() => {
      setRefreshTick((value) => value + 1);
      void loadPublicUpcomingMatches();
    }, FORECAST_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  function openMatchPage(match: PublicUpcomingMatch) {
    window.location.href = matchPagePath(match.homeTeam, match.awayTeam);
  }

  return (
    <main className="public-match-shell">
      <div className="public-match-bg" aria-hidden="true" />
      <section className="public-match-app" aria-labelledby="public-match-title">
        <header className="public-match-header">
          <div className="public-brand-mark" aria-hidden="true">
            <Trophy size={27} strokeWidth={2.1} />
          </div>
          <div className="public-brand-copy">
            <strong>世界杯预测</strong>
            <span>zhugejunshi.com</span>
          </div>
          <button className="public-icon-button" type="button" aria-label="菜单">
            <Menu size={22} strokeWidth={2.6} />
          </button>
        </header>

        <section className="public-page-title">
          <h1 id="public-match-title">未开赛比赛</h1>
          <p>公开赛程 · 预测需解锁</p>
        </section>

        <nav className="public-match-tabs" aria-label="比赛筛选">
          {PUBLIC_MATCH_TABS.map((tab) => (
            <button
              className={activeFilter === tab.key ? "active" : ""}
              type="button"
              aria-current={activeFilter === tab.key ? "page" : undefined}
              key={tab.key}
              onClick={() => setActiveFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <PublicUpcomingMatchesPanel matches={visibleMatches} status={matchesStatus} activeFilter={activeFilter} onSelect={openMatchPage} />
      </section>
      <TournamentPassBar />
      <footer className="public-safety-footer">
        <ShieldCheck size={14} strokeWidth={2.2} />
        <span>数据加密保护 · 安全支付 · 随时可查</span>
      </footer>
    </main>
  );
}

function PublicUpcomingMatchesPanel({
  matches,
  status,
  activeFilter,
  onSelect,
}: {
  matches: PublicUpcomingMatch[];
  status: LoadStatus;
  activeFilter: PublicMatchFilter;
  onSelect: (match: PublicUpcomingMatch) => void;
}) {
  if (matches.length === 0 && status === "loading") {
    return <p className="public-match-empty">赛程加载中</p>;
  }

  if (matches.length === 0 && status === "failed") {
    return <p className="public-match-empty">赛程暂时没有连上，正在自动刷新</p>;
  }

  if (matches.length === 0) {
    return <p className="public-match-empty">{activeFilter === "all" ? "暂无未开赛比赛" : "这个分组暂无未开赛比赛"}</p>;
  }

  return (
    <div className="public-match-list" aria-label="未开赛比赛列表">
      {matches.map((match) => (
        <PublicMatchCard match={match} key={`${match.homeTeam}-${match.awayTeam}-${match.kickoff}`} onSelect={onSelect} />
      ))}
    </div>
  );
}

function PublicMatchCard({ match, onSelect }: { match: PublicUpcomingMatch; onSelect: (match: PublicUpcomingMatch) => void }) {
  return (
    <button className="public-match-card" type="button" onClick={() => onSelect(match)}>
      <div className="public-match-info">
        <strong>{match.matchNo ? `#${match.matchNo}` : "#--"}</strong>
        <span>{match.stage}</span>
        <em>
          <CalendarDays size={13} strokeWidth={2.4} />
          {formatKickoffForPublicList(match.kickoff)}
        </em>
      </div>
      <div className="public-match-teams">
        <div>
          <TeamFlag team={match.homeTeam} code={match.homeCode} />
          <strong>{match.homeName}</strong>
        </div>
        <b>vs</b>
        <div>
          <TeamFlag team={match.awayTeam} code={match.awayCode} />
          <strong>{match.awayName}</strong>
        </div>
      </div>
      <div className="public-match-action">
        <small>{publicMatchStatusLabel(match.status)}</small>
        <span>
          <LockKeyhole size={15} strokeWidth={2.5} />
          <b>¥1</b>
          <em>查看预测</em>
        </span>
      </div>
    </button>
  );
}

function TournamentPassBar() {
  return (
    <div className="public-pass-bar" aria-label="全包购买入口">
      <div>
        <Crown size={20} strokeWidth={2.5} />
        <span>全包剩余 92 场 ¥39</span>
      </div>
      <button type="button" aria-label="查看全包方案">
        <ChevronRight size={24} strokeWidth={2.4} />
      </button>
    </div>
  );
}

function TeamFlag({ team, code }: { team: TeamKey; code?: string }) {
  const flagAsset = TEAM_FLAG_ASSET_BY_KEY[team] ?? (code ? TEAM_FLAG_ASSET_BY_CODE[code.toUpperCase()] : undefined);
  const flagSource = flagAsset ? `/assets/flags/${flagAsset}.png` : null;
  const fallbackCode = code?.slice(0, 3).toUpperCase() ?? team.slice(0, 3).toUpperCase();

  return (
    <span className={`flag ${flagSource ? "" : "flag-generic"}`} aria-label={`${fallbackCode} 国旗`}>
      {flagSource ? <img src={flagSource} alt="" loading="lazy" /> : <span>{fallbackCode}</span>}
    </span>
  );
}

function ChampionProbabilityPage() {
  const [prediction, setPrediction] = useState<MatchPrediction | null>(null);
  const [loadStatus, setLoadStatus] = useState<LoadStatus>("loading");
  const [showInfo, setShowInfo] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadChampionBoard() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/match-prediction?simulations=${INTERACTIVE_SIMULATION_COUNT}&useSnapshot=true`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`冠军概率接口返回 ${response.status}`);
        const data = (await response.json()) as MatchPrediction;
        if (!active) return;
        setPrediction(data);
        setLoadStatus("ready");
      } catch {
        if (!active) return;
        setPrediction(null);
        setLoadStatus("failed");
      }
    }

    void loadChampionBoard();
    const timer = window.setInterval(loadChampionBoard, FORECAST_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const boardRows = useMemo(() => {
    const sourceTeams = prediction?.teams?.length ? prediction.teams : teams;
    return [...sourceTeams]
      .filter((team) => typeof team.tournament?.champion === "number")
      .sort((left, right) => right.tournament.champion - left.tournament.champion)
      .slice(0, 6);
  }, [prediction]);

  const snapshotMeta = prediction?.modelMeta;
  const snapshotLine =
    loadStatus === "ready" && snapshotMeta
      ? `${snapshotMeta.simulationCount.toLocaleString("zh-CN")} 次模拟 · 已锁定 ${snapshotMeta.lockedResults} 场赛果`
      : loadStatus === "loading"
        ? "正在读取最新预测快照"
        : "预测接口暂不可用，显示本地榜单";

  function goBack() {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/";
  }

  function openTournamentPass() {
    window.location.href = "/#board";
  }

  return (
    <main className="champion-page-shell">
      <div className="champion-mobile-status" aria-hidden="true">
        <span>9:41</span>
        <div>
          <Signal size={15} strokeWidth={2.7} />
          <Wifi size={15} strokeWidth={2.7} />
          <BatteryFull size={19} strokeWidth={2.3} />
        </div>
      </div>

      <header className="champion-page-header">
        <button type="button" aria-label="返回" onClick={goBack}>
          <ArrowLeft aria-hidden="true" size={20} strokeWidth={2.7} />
        </button>
        <div>
          <h1>冠军概率榜</h1>
          <p>来自最新预测快照</p>
        </div>
        <button type="button" aria-label="查看模型说明" aria-pressed={showInfo} onClick={() => setShowInfo((value) => !value)}>
          <Info aria-hidden="true" size={19} strokeWidth={2.4} />
        </button>
      </header>

      <button className="champion-pass-cta" type="button" onClick={openTournamentPass}>
        <Crown aria-hidden="true" size={16} strokeWidth={2.6} />
        <span>全包查看全部队伍</span>
        <ChevronRight aria-hidden="true" size={15} strokeWidth={2.8} />
      </button>

      {showInfo ? <p className="champion-snapshot-note">{snapshotLine}</p> : null}

      <section className="champion-board-page-card" aria-label="冠军概率榜">
        <div className="champion-board-page-head" aria-hidden="true">
          <span>球队</span>
          <span>夺冠</span>
          <span>决赛</span>
          <span>四强</span>
          <span>变化</span>
        </div>
        <div className="champion-board-page-list">
          {boardRows.map((team, index) => (
            <article className="champion-board-page-row" key={team.key}>
              <div className="champion-board-team">
                <b className={index < 3 ? "podium" : ""}>{index + 1}</b>
                <TeamFlag team={team.key} code={team.code} />
                <span>
                  <strong>{team.name}</strong>
                  <em>{team.code}</em>
                </span>
              </div>
              <strong>{formatProbabilityValue(team.tournament.champion)}</strong>
              <strong>{formatProbabilityValue(team.tournament.final)}</strong>
              <strong>{formatProbabilityValue(team.tournament.semifinal)}</strong>
              <em className={`champion-change-badge ${team.tournament.change >= 0 ? "positive" : "negative"}`}>
                {formatSignedDecimal(team.tournament.change)}
              </em>
            </article>
          ))}
        </div>
      </section>

      <footer className="champion-page-footer">
        <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.1} />
        <span>概率分析，不是投注建议</span>
      </footer>

      <div className="champion-home-indicator" aria-hidden="true" />
    </main>
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

function CompactScoreList({ outcomes }: { outcomes: ScoreOutcome[] }) {
  if (outcomes.length === 0) {
    return <p className="review-empty">比分预测生成中</p>;
  }
  return (
    <div className="compact-score-list" aria-label="最可能比分 Top 3">
      <span className="compact-score-kicker">比分备选</span>
      {outcomes.map((outcome, index) => (
        <article className={`compact-score ${outcome.tone}`} key={outcome.score}>
          <span>{index === 0 ? "首选" : "备选"}</span>
          <strong>{outcome.score}</strong>
          <em>{outcome.probability.toFixed(1)}%</em>
        </article>
      ))}
    </div>
  );
}

function FairPricePanel({ prices }: { prices: FairPrice[] }) {
  return (
    <div className="fair-price-list">
      {prices.map((price) => (
        <article className={`fair-price-row ${price.tone}`} key={price.label}>
          <div>
            <strong>{price.label}</strong>
            <span>{price.note}</span>
          </div>
          <b>{price.probability.toFixed(1)}%</b>
          <em>{fairPriceLabel(price.fairDecimal)}</em>
        </article>
      ))}
    </div>
  );
}

function GoalMarketPanel({ markets, compact = false }: { markets: GoalMarket[]; compact?: boolean }) {
  if (markets.length === 0) {
    return <p className="review-empty">进球预测生成中</p>;
  }
  return (
    <div className={`goal-market-grid ${compact ? "compact" : ""}`}>
      {markets.map((market) => (
        <article className={`goal-market-card ${market.tone}`} key={market.label}>
          <span>{market.label}</span>
          <strong>{market.probability.toFixed(1)}%</strong>
          <small>{market.note}</small>
          <em>公平价 {fairPriceLabel(market.fairDecimal)}</em>
        </article>
      ))}
    </div>
  );
}

function ScoreMatrix({ cells }: { cells: ScoreMatrixCell[] }) {
  const visibleCells = cells.filter((cell) => cell.homeGoals <= 4 && cell.awayGoals <= 4);
  const maxHome = Math.max(3, ...visibleCells.map((cell) => cell.homeGoals));
  const maxAway = Math.max(3, ...visibleCells.map((cell) => cell.awayGoals));
  const homeGoals = Array.from({ length: maxHome + 1 }, (_, index) => index);
  const awayGoals = Array.from({ length: maxAway + 1 }, (_, index) => index);
  const cellMap = new Map(visibleCells.map((cell) => [`${cell.homeGoals}-${cell.awayGoals}`, cell]));

  return (
    <div className="score-matrix" style={{ "--matrix-columns": awayGoals.length + 1 } as CustomStyle}>
      <span className="matrix-axis">主/客</span>
      {awayGoals.map((awayGoal) => (
        <span className="matrix-head" key={`away-${awayGoal}`}>
          {awayGoal}
        </span>
      ))}
      {homeGoals.map((homeGoal) => (
        <Fragment key={`row-${homeGoal}`}>
          <span className="matrix-head">{homeGoal}</span>
          {awayGoals.map((awayGoal) => {
            const cell = cellMap.get(`${homeGoal}-${awayGoal}`);
            const probability = cell?.probability ?? 0;
            return (
              <span
                className="matrix-cell"
                key={`${homeGoal}-${awayGoal}`}
                style={{ "--heat": Math.min(probability / 16, 1).toFixed(2) } as CustomStyle}
              >
                <b>{`${homeGoal}-${awayGoal}`}</b>
                <em>{probability.toFixed(1)}%</em>
              </span>
            );
          })}
        </Fragment>
      ))}
    </div>
  );
}

function CreatorTopicsPanel({ topics }: { topics: CreatorTopic[] }) {
  if (topics.length === 0) {
    return <p className="review-empty">今日选题等待模型输出</p>;
  }
  return (
    <div className="creator-topic-list">
      {topics.slice(0, 3).map((topic, index) => (
        <article className="creator-topic" key={topic.title}>
          <span>{`0${index + 1}`}</span>
          <div>
            <strong>{topic.title}</strong>
            <p>{topic.detail}</p>
          </div>
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
  const scoreMatrix = detail.scoreMatrix?.length ? detail.scoreMatrix : scoreMatrixFallbackFromOutcomes(detail.scoreOutcomes);
  const goalMarkets = detail.goalMarkets?.length ? detail.goalMarkets : goalMarketsFallback();
  const fairPrices = detail.fairPrices?.length
    ? detail.fairPrices
    : [
        { label: `${homeTeam?.name ?? detail.homeTeam}胜`, probability: detail.homeWin, fairDecimal: Number((100 / detail.homeWin).toFixed(2)), note: "90 分钟模型公平概率", tone: "green" as Tone },
        { label: "平局", probability: detail.draw, fairDecimal: Number((100 / detail.draw).toFixed(2)), note: "90 分钟模型公平概率", tone: "gold" as Tone },
        { label: `${awayTeam?.name ?? detail.awayTeam}胜`, probability: detail.awayWin, fairDecimal: Number((100 / detail.awayWin).toFixed(2)), note: "90 分钟模型公平概率", tone: "blue" as Tone },
      ];

  return (
    <div className="match-detail-grid">
      <div className="detail-head">
        <div className="detail-title">
          <TeamFlag team={detail.homeTeam} code={detail.homeCode} />
          <strong>
            {homeTeam?.name ?? detail.homeTeam} / {awayTeam?.name ?? detail.awayTeam}
          </strong>
          <TeamFlag team={detail.awayTeam} code={detail.awayCode} />
        </div>
        <span>
          {[detail.stage, formatKickoffForUser(detail.kickoff)].filter(Boolean).join(" · ")}
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
      <div className="match-detail-splits">
        <FairPricePanel prices={fairPrices} />
        <GoalMarketPanel markets={goalMarkets} compact />
      </div>
      <ScoreMatrix cells={scoreMatrix} />
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

function UserMethodPanel() {
  const methodItems = [
    { title: "实力", detail: "球队长期强度和攻防质量" },
    { title: "状态", detail: "近期表现、阵容连续性" },
    { title: "路径", detail: "小组名次和潜在对手" },
    { title: "人员", detail: "伤停、停赛、核心球员风险" },
  ];

  return (
    <div className="user-method-panel">
      {methodItems.map((item) => (
        <article key={item.title}>
          <strong>{item.title}</strong>
          <span>{item.detail}</span>
        </article>
      ))}
    </div>
  );
}

const PILLAR_ITEMS = [
  { key: "strength", label: "实力盘" },
  { key: "form", label: "状态盘" },
  { key: "path", label: "路径盘" },
  { key: "squad", label: "人员盘" },
  { key: "margin", label: "边际盘" },
];

function matchDetailOrderId() {
  return new URLSearchParams(window.location.search).get("orderId");
}

function formatRawKickoff(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

function goBackFromUnlockedMatch() {
  if (window.history.length > 1) {
    window.history.back();
    return;
  }
  window.location.href = "/";
}

function fallbackPillars(): Record<string, number> {
  return { strength: 7, form: 7, path: 7, squad: 7, margin: 7 };
}

function detailPillars(detail: MatchDetail | null, side: "home" | "away") {
  return detail?.pillars?.[side] ?? fallbackPillars();
}

function UnlockedPanel({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`unlocked-panel ${className}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function UnlockedTeamMark({ team, code, name }: { team: TeamKey; code: string; name: string }) {
  return (
    <div className="unlocked-team-mark">
      <span className="unlocked-flag-frame">
        <TeamFlag team={team} code={code} />
      </span>
      <span>{name}</span>
    </div>
  );
}

function UnlockedProbabilityTriplet({ detail, homeName, awayName }: { detail: MatchDetail; homeName: string; awayName: string }) {
  const rows = [
    { label: `${homeName}胜`, value: detail.homeWin, tone: "home" },
    { label: "平局", value: detail.draw, tone: "draw" },
    { label: `${awayName}胜`, value: detail.awayWin, tone: "away" },
  ];

  return (
    <div className="unlocked-probability-grid">
      {rows.map((row) => (
        <article className={`unlocked-probability ${row.tone}`} key={row.label}>
          <span>{row.label}</span>
          <strong>{row.value}%</strong>
          <i style={{ "--value": row.value } as CustomStyle} />
        </article>
      ))}
    </div>
  );
}

function UnlockedTopScores({ outcomes }: { outcomes: ScoreOutcome[] }) {
  return (
    <div className="unlocked-score-top-list">
      {outcomes.slice(0, 3).map((outcome, index) => (
        <article key={outcome.score}>
          <span>{index + 1}</span>
          <strong>{outcome.score}</strong>
          <em>{outcome.probability.toFixed(1)}%</em>
        </article>
      ))}
    </div>
  );
}

function UnlockedScoreMatrix({ cells }: { cells: ScoreMatrixCell[] }) {
  const visibleCells = cells.filter((cell) => cell.homeGoals <= 4 && cell.awayGoals <= 4);
  const goals = [0, 1, 2, 3, 4];
  const maxProbability = Math.max(1, ...visibleCells.map((cell) => cell.probability));
  const cellMap = new Map(visibleCells.map((cell) => [`${cell.homeGoals}-${cell.awayGoals}`, cell.probability]));

  return (
    <div className="unlocked-score-matrix" style={{ "--matrix-columns": goals.length + 1 } as CustomStyle}>
      <span className="matrix-muted" aria-hidden="true" />
      {goals.map((goal) => (
        <span className="matrix-muted" key={`away-${goal}`}>
          {goal}
        </span>
      ))}
      {goals.map((homeGoal) => (
        <Fragment key={`row-${homeGoal}`}>
          <span className="matrix-muted">{homeGoal}</span>
          {goals.map((awayGoal) => {
            const probability = cellMap.get(`${homeGoal}-${awayGoal}`) ?? 0;
            return (
              <span
                className="unlocked-score-cell"
                key={`${homeGoal}-${awayGoal}`}
                style={{ "--heat-alpha": (0.16 + Math.min(probability / maxProbability, 1) * 0.58).toFixed(2) } as CustomStyle}
              >
                {probability.toFixed(1)}%
              </span>
            );
          })}
        </Fragment>
      ))}
    </div>
  );
}

function FivePillarsRadar({ values }: { values: Record<string, number> }) {
  const center = 58;
  const radius = 42;
  const points = PILLAR_ITEMS.map((item, index) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / PILLAR_ITEMS.length;
    const value = Math.max(0, Math.min(10, values[item.key] ?? 0)) / 10;
    return `${center + Math.cos(angle) * radius * value},${center + Math.sin(angle) * radius * value}`;
  }).join(" ");

  return (
    <div className="unlocked-pillars">
      <div className="unlocked-radar" aria-hidden="true">
        <svg viewBox="0 0 116 116" role="img">
          <polygon className="radar-grid outer" points="58,10 103.7,43.1 86.2,96.9 29.8,96.9 12.3,43.1" />
          <polygon className="radar-grid inner" points="58,30 84.7,49.4 74.5,80.6 41.5,80.6 31.3,49.4" />
          <polygon className="radar-shape" points={points} />
        </svg>
      </div>
      <div className="unlocked-pillar-values">
        {PILLAR_ITEMS.map((item) => (
          <article key={item.key}>
            <span>{item.label}</span>
            <strong>{(values[item.key] ?? 0).toFixed(1)}</strong>
          </article>
        ))}
      </div>
    </div>
  );
}

function UnlockedScenarioCards({ scenarios }: { scenarios: ScenarioImpact[] }) {
  const icons = [CheckCircle2, Target, Trophy];
  return (
    <div className="unlocked-scenario-list">
      {scenarios.slice(0, 3).map((scenario, index) => {
        const Icon = icons[index] ?? Target;
        return (
          <article className={`unlocked-scenario ${scenario.tone}`} key={scenario.label}>
            <Icon aria-hidden="true" size={18} strokeWidth={2.5} />
            <span>{scenario.label}</span>
            <strong>{scenario.probability}%</strong>
          </article>
        );
      })}
    </div>
  );
}

function UnlockedNewsList({ items }: { items: MatchNewsItem[] }) {
  if (items.length === 0) {
    return <p className="unlocked-empty">本场暂未接入新增新闻依据</p>;
  }

  return (
    <div className="unlocked-news-list">
      {items.slice(0, 3).map((item) => {
        const Icon = item.direction === "negative" ? AlertTriangle : item.direction === "neutral" ? Clock : CheckCircle2;
        return (
          <article className={`unlocked-news ${item.tone}`} key={`${item.title}-${item.impact}`}>
            <Icon aria-hidden="true" size={16} strokeWidth={2.4} />
            <div>
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </div>
            <em>{item.impact}</em>
          </article>
        );
      })}
    </div>
  );
}

function UnlockedMatchPage({ home, away }: { home: TeamKey; away: TeamKey }) {
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [loadStatus, setLoadStatus] = useState<LoadStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadDetail() {
      setLoadStatus("loading");
      try {
        const params = new URLSearchParams({
          home,
          away,
          simulations: String(INTERACTIVE_SIMULATION_COUNT),
        });
        const orderId = matchDetailOrderId();
        if (orderId) params.set("orderId", orderId);
        const response = await fetch(`${API_BASE_URL}/api/match-detail?${params.toString()}`, { cache: "no-store" });
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw new Error(payload?.detail ?? `单场详情接口返回 ${response.status}`);
        if (!active) return;
        setDetail(payload as MatchDetail);
        setLoadStatus("ready");
        setErrorMessage(null);
      } catch (error) {
        if (!active) return;
        setDetail(null);
        setLoadStatus("failed");
        setErrorMessage(error instanceof Error ? error.message : "单场预测加载失败");
      }
    }

    void loadDetail();
    return () => {
      active = false;
    };
  }, [home, away]);

  const fallbackHomeTeam = resolveDisplayTeam(home, teams);
  const fallbackAwayTeam = resolveDisplayTeam(away, teams);
  const homeName = detail?.homeName ?? fallbackHomeTeam.name;
  const awayName = detail?.awayName ?? fallbackAwayTeam.name;
  const homeCode = detail?.homeCode ?? fallbackHomeTeam.code;
  const awayCode = detail?.awayCode ?? fallbackAwayTeam.code;
  const scoreMatrix = detail?.scoreMatrix?.length ? detail.scoreMatrix : detail ? scoreMatrixFallbackFromOutcomes(detail.scoreOutcomes) : [];
  const homePillars = detailPillars(detail, "home");
  const newsItems = detail?.newsItems ?? [];

  return (
    <main className="match-unlocked-shell">
      <header className="unlocked-header">
        <button type="button" aria-label="返回" onClick={goBackFromUnlockedMatch}>
          <ArrowLeft aria-hidden="true" size={24} strokeWidth={2.5} />
        </button>
        <strong>完整预测</strong>
        <span className="unlock-badge">
          <Crown aria-hidden="true" size={15} strokeWidth={2.4} />
          已解锁
        </span>
      </header>

      <section className="unlocked-match-hero" aria-label={`${homeName} 对 ${awayName}`}>
        <UnlockedTeamMark team={detail?.homeTeam ?? home} code={homeCode} name={homeName} />
        <div className="unlocked-versus">
          <h1>
            {homeName}
            <span>vs</span>
            {awayName}
          </h1>
          <div>
            <span>{detail?.stage ?? "单场预测"}</span>
            <span>{detail ? formatRawKickoff(detail.kickoff) : "加载中"}</span>
          </div>
        </div>
        <UnlockedTeamMark team={detail?.awayTeam ?? away} code={awayCode} name={awayName} />
      </section>

      {loadStatus === "failed" ? (
        <section className="unlocked-panel unlocked-state-panel">
          <AlertTriangle aria-hidden="true" size={24} strokeWidth={2.4} />
          <strong>预测加载失败</strong>
          <p>{errorMessage}</p>
        </section>
      ) : null}

      {detail ? (
        <>
          <UnlockedPanel title="胜平负概率">
            <UnlockedProbabilityTriplet detail={detail} homeName={homeName} awayName={awayName} />
          </UnlockedPanel>

          <section className="unlocked-score-layout">
            <UnlockedPanel title="最可能比分" className="score-top-panel">
              <UnlockedTopScores outcomes={detail.scoreOutcomes} />
            </UnlockedPanel>
            <UnlockedPanel title="比分分布" className="score-matrix-panel">
              <UnlockedScoreMatrix cells={scoreMatrix} />
            </UnlockedPanel>
          </section>

          <section className="unlocked-score-layout lower">
            <UnlockedPanel title="五大盘面">
              <FivePillarsRadar values={homePillars} />
            </UnlockedPanel>
            <UnlockedPanel title="路径传导">
              <UnlockedScenarioCards scenarios={detail.scenarioImpacts} />
            </UnlockedPanel>
          </section>

          <UnlockedPanel title="新闻依据">
            <UnlockedNewsList items={newsItems} />
          </UnlockedPanel>

          <footer className="unlocked-footer">
            <ShieldCheck aria-hidden="true" size={16} strokeWidth={2.2} />
            <span>概率分析，不是投注建议</span>
          </footer>
        </>
      ) : loadStatus === "loading" ? (
        <section className="unlocked-panel unlocked-state-panel">
          <Clock aria-hidden="true" size={24} strokeWidth={2.4} />
          <strong>完整预测加载中</strong>
          <p>正在读取后端单场预测、比分矩阵和路径传导</p>
        </section>
      ) : null}
    </main>
  );
}

function SingleMatchPage({ home, away }: { home: TeamKey; away: TeamKey }) {
  const [summary, setSummary] = useState<PublicMatchSummary | null>(() => staticMatchSummaryFallback(home, away));
  const [loadStatus, setLoadStatus] = useState<LoadStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [paymentMessage, setPaymentMessage] = useState<string | null>(null);
  const [paymentPendingProduct, setPaymentPendingProduct] = useState<"single_match" | "tournament_pass" | null>(null);

  useEffect(() => {
    let active = true;

    async function loadSummary() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/public-match-summary?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`, {
          cache: "no-store",
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw new Error(payload?.detail ?? `单场赛程接口返回 ${response.status}`);
        if (!active) return;
        setSummary(payload as PublicMatchSummary);
        setLoadStatus("ready");
        setErrorMessage(null);
      } catch (error) {
        if (!active) return;
        setSummary((current) => current ?? staticMatchSummaryFallback(home, away));
        setLoadStatus("failed");
        setErrorMessage(error instanceof Error ? error.message : "单场赛程加载失败");
      }
    }

    void loadSummary();
    return () => {
      active = false;
    };
  }, [home, away]);

  const homeFallbackTeam = resolveDisplayTeam(home, teams);
  const awayFallbackTeam = resolveDisplayTeam(away, teams);
  const displaySummary: PublicMatchSummary = summary ?? {
    stage: "单场预测",
    kickoff: "加载中",
    matchNo: null,
    status: "scheduled",
    homeTeam: home,
    awayTeam: away,
    homeName: homeFallbackTeam.name,
    awayName: awayFallbackTeam.name,
    homeCode: homeFallbackTeam.code,
    awayCode: awayFallbackTeam.code,
  };
  const matchNumberLabel = displaySummary.matchNo ? `#${displaySummary.matchNo}` : "#--";
  const statusLabel = displaySummary.status === "scheduled" ? "未开赛" : displaySummary.status;
  const singleMatchDisabled = paymentPendingProduct !== null || loadStatus === "loading";
  const matchKey = `${displaySummary.homeTeam}-${displaySummary.awayTeam}`;

  async function createUnlockOrder(productKey: "single_match" | "tournament_pass") {
    if (productKey === "single_match") {
      window.location.href = checkoutPagePath(displaySummary.homeTeam, displaySummary.awayTeam);
      return;
    }

    setPaymentPendingProduct(productKey);
    setPaymentMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/payments/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          productKey,
          provider: "wechat_native",
          contentKey: "tournament_probabilities",
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.orderId) throw new Error(payload?.detail ?? "支付订单创建失败");
      window.location.href = `${PAYMENT_PENDING_ROUTE}?orderId=${encodeURIComponent(payload.orderId)}`;
    } catch (error) {
      setPaymentMessage(error instanceof Error ? error.message : "支付订单创建失败");
      setPaymentPendingProduct(null);
    }
  }

  async function shareMatch() {
    const shareUrl = window.location.href;
    const title = `${displaySummary.homeName} vs ${displaySummary.awayName} 世界杯预测`;
    try {
      if (navigator.share) {
        await navigator.share({ title, text: "完整预测需解锁后查看", url: shareUrl });
        return;
      }
      await navigator.clipboard?.writeText(shareUrl);
      setPaymentMessage("链接已复制");
    } catch {
      setPaymentMessage("当前浏览器不支持分享");
    }
  }

  function goBackToMatches() {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/#matches";
  }

  return (
    <main className="locked-match-shell">
      <header className="locked-match-nav">
        <button type="button" aria-label="返回未开赛列表" onClick={goBackToMatches}>
          <ArrowLeft aria-hidden="true" size={22} strokeWidth={2.5} />
        </button>
        <span>世界杯预测</span>
        <button type="button" aria-label="分享本场预测" onClick={shareMatch}>
          <Share2 aria-hidden="true" size={21} strokeWidth={2.4} />
        </button>
      </header>

      <section className="locked-match-hero" aria-label="单场锁定预览">
        <div className="locked-teams">
          <div className="locked-team">
            <span className="locked-team-emblem">
              <TeamFlag team={displaySummary.homeTeam} code={displaySummary.homeCode} />
            </span>
            <strong>{displaySummary.homeName}</strong>
          </div>
          <b>VS</b>
          <div className="locked-team away">
            <span className="locked-team-emblem">
              <TeamFlag team={displaySummary.awayTeam} code={displaySummary.awayCode} />
            </span>
            <strong>{displaySummary.awayName}</strong>
          </div>
        </div>

        <div className="locked-match-meta">
          <span>{`${matchNumberLabel} ${displaySummary.stage}`}</span>
          <em>
            <CalendarDays aria-hidden="true" size={14} strokeWidth={2.3} />
            {formatKickoffForUser(displaySummary.kickoff)}
          </em>
          <em>
            <Clock aria-hidden="true" size={14} strokeWidth={2.3} />
            {statusLabel}
          </em>
        </div>
      </section>

      <div className="locked-match-stack">
        <section className="locked-panel locked-generated-card">
          <div className="locked-section-heading">
            <Target aria-hidden="true" size={22} strokeWidth={2.3} />
            <div>
              <strong>预测已生成</strong>
              <span>完整预测需支付后查看</span>
            </div>
          </div>
          <div className="locked-preview-list">
            <LockedPreviewRow Icon={ShieldCheck} title="胜平负概率" />
            <LockedPreviewRow Icon={Target} title="最可能比分" />
            <LockedPreviewRow Icon={Trophy} title="比分分布" />
          </div>
        </section>

        <section className="locked-panel locked-content-card">
          <div className="locked-section-heading gold">
            <Lock aria-hidden="true" size={22} strokeWidth={2.4} />
            <div>
              <strong>单场内容</strong>
              <span>支付后可查看以下完整内容</span>
            </div>
          </div>
          <div className="locked-content-list">
            <LockedContentRow Icon={Target} title="单场胜平负" detail="胜平负概率与关键战局分析" />
            <LockedContentRow Icon={Trophy} title="比分分布" detail="比分概率分布与关键比分解读" />
            <LockedContentRow Icon={Newspaper} title="路径传导" detail="本场结果对小组与淘汰赛路径的影响" />
          </div>
        </section>

        {errorMessage && loadStatus === "failed" ? <p className="locked-inline-message">{errorMessage}</p> : null}
        {paymentMessage ? <p className="locked-inline-message">{paymentMessage}</p> : null}
      </div>

      <section className="locked-purchase-bar" aria-label="购买入口">
        <button type="button" className="locked-buy-button primary" onClick={() => void createUnlockOrder("single_match")} disabled={singleMatchDisabled}>
          <span>
            <Lock aria-hidden="true" size={21} strokeWidth={2.5} />
          </span>
          <strong>{paymentPendingProduct === "single_match" ? "创建订单中" : "¥1 解锁本场"}</strong>
          <small>查看本场完整预测</small>
        </button>
        <button type="button" className="locked-buy-button pass" onClick={() => void createUnlockOrder("tournament_pass")} disabled={singleMatchDisabled}>
          <strong>{paymentPendingProduct === "tournament_pass" ? "创建订单中" : "全包剩余 92 场 ¥39"}</strong>
          <small>解锁所有未开赛场次</small>
          <Trophy aria-hidden="true" size={22} strokeWidth={2.3} />
        </button>
      </section>

      <footer className="locked-safety-footer">
        <ShieldCheck aria-hidden="true" size={16} strokeWidth={2.1} />
        <span>数据加密保护 · 安全支付 · 随时可查</span>
      </footer>
    </main>
  );
}

function LockedPreviewRow({ Icon, title }: { Icon: LucideIcon; title: string }) {
  return (
    <article className="locked-preview-row">
      <Icon aria-hidden="true" size={30} strokeWidth={2.3} />
      <div>
        <strong>{title}</strong>
        <span>待解锁</span>
      </div>
      <span className="locked-blur-lines" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <Lock aria-hidden="true" size={28} strokeWidth={2.4} />
    </article>
  );
}

function LockedContentRow({ Icon, title, detail }: { Icon: LucideIcon; title: string; detail: string }) {
  return (
    <article className="locked-content-row">
      <Icon aria-hidden="true" size={31} strokeWidth={2.3} />
      <div>
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
      <Lock aria-hidden="true" size={25} strokeWidth={2.4} />
    </article>
  );
}

function paymentStatusMeta(status: PaymentOrderStatus) {
  if (status === "paid") {
    return { label: "支付成功", tone: "paid", detail: "正在确认解锁权限" };
  }
  if (status === "expired") {
    return { label: "订单已过期", tone: "expired", detail: "请重新创建支付订单" };
  }
  if (status === "failed") {
    return { label: "支付失败", tone: "failed", detail: "请返回选择支付方式" };
  }
  if (status === "provider_config_required") {
    return { label: "支付通道暂不可用", tone: "unavailable", detail: "请返回选择其他支付方式" };
  }
  return { label: "待支付", tone: "pending", detail: "请在有效时间内完成支付" };
}

function paymentMethodLabel(order: PaymentOrder) {
  if (order.paymentMethodLabel) return order.paymentMethodLabel;
  if (order.provider === "wechat_jsapi" || order.paymentMethod === "jsapi") return "JSAPI 支付";
  if (order.provider === "wechat_native" || order.paymentMethod === "native") return "扫码支付";
  if (order.provider === "alipay_qr" || order.paymentMethod === "scan_qr") return "扫码支付";
  return order.paymentMethod;
}

function paymentContentKey(order: PaymentOrder) {
  if (order.metadata?.contentKey) return order.metadata.contentKey;
  return order.productKey === "tournament_pass" ? "tournament_probabilities" : "match_prediction";
}

function paymentProductTitle(order: PaymentOrder) {
  const { metadata } = order;
  if (metadata?.homeName && metadata.awayName) return `${metadata.homeName} vs ${metadata.awayName}`;
  if (order.productKey === "tournament_pass") return "剩余未开赛预测";
  return order.productName;
}

function formatPaymentDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "待确认";
  const parts = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")} ${part("hour")}:${part("minute")}:${part("second")}`;
}

function formatPaymentRemaining(expiresAt: string) {
  const expires = new Date(expiresAt);
  if (Number.isNaN(expires.getTime())) return "有效时间待确认";
  const minutes = Math.ceil((expires.getTime() - Date.now()) / 60000);
  if (minutes <= 0) return "已过期";
  return `${minutes}分钟内有效`;
}

function shortOrderId(orderId: string) {
  if (!orderId) return "未创建";
  if (orderId.length <= 14) return orderId;
  return `${orderId.slice(0, 7)}...`;
}

function paymentRedirectPath(order: PaymentOrder) {
  if (order.productKey === "tournament_pass") return "/#board";
  const { homeTeam, awayTeam } = order.metadata ?? {};
  if (homeTeam && awayTeam) return `${matchPagePath(homeTeam, awayTeam)}?orderId=${encodeURIComponent(order.orderId)}`;
  return "/";
}

function isQrPayment(order: PaymentOrder) {
  return order.provider === "wechat_native" || order.provider === "alipay_qr" || order.paymentMethod === "native" || order.paymentMethod === "scan_qr";
}

function isWechatBrowser() {
  return /micromessenger/i.test(window.navigator.userAgent);
}

function methodLabelFromProvider(provider: PaymentProviderConfig | undefined) {
  if (!provider) return "扫码支付";
  if (provider.paymentMethodLabel) return provider.paymentMethodLabel;
  if (provider.paymentMethod === "jsapi") return "JSAPI 支付";
  return "扫码支付";
}

function fallbackCheckoutProviderOptions(): CheckoutProviderOption[] {
  return [
    { key: "wechat", provider: "wechat_native", label: "微信支付", methodLabel: "扫码支付", configured: false, Icon: WalletCards },
    { key: "alipay", provider: "alipay_qr", label: "支付宝支付", methodLabel: "扫码支付", configured: false, Icon: CircleDollarSign },
  ];
}

function buildCheckoutProviderOptions(providers: PaymentProviderConfig[], preferJsapi: boolean): CheckoutProviderOption[] {
  if (providers.length === 0) return fallbackCheckoutProviderOptions();
  const wechatNative = providers.find((provider) => provider.provider === "wechat_native" || provider.provider === "wechat");
  const wechatJsapi = providers.find((provider) => provider.provider === "wechat_jsapi");
  const wechatProvider = preferJsapi ? wechatJsapi ?? wechatNative : wechatNative ?? wechatJsapi;
  const alipayProvider = providers.find((provider) => provider.provider === "alipay_qr" || provider.provider === "alipay");
  return [
    wechatProvider
      ? {
          key: "wechat" as const,
          provider: wechatProvider.provider,
          label: "微信支付",
          methodLabel: methodLabelFromProvider(wechatProvider),
          configured: wechatProvider.configured,
          Icon: WalletCards,
        }
      : null,
    alipayProvider
      ? {
          key: "alipay" as const,
          provider: alipayProvider.provider,
          label: "支付宝支付",
          methodLabel: methodLabelFromProvider(alipayProvider),
          configured: alipayProvider.configured,
          Icon: CircleDollarSign,
        }
      : null,
  ].filter((option): option is CheckoutProviderOption => Boolean(option));
}

function SingleMatchCheckoutPage({ home, away }: { home: TeamKey; away: TeamKey }) {
  const [summary, setSummary] = useState<PublicMatchSummary | null>(() => staticMatchSummaryFallback(home, away));
  const [accessOptions, setAccessOptions] = useState<AccessOptions | null>(null);
  const [paymentConfig, setPaymentConfig] = useState<PaymentConfig | null>(null);
  const [selectedProviderKey, setSelectedProviderKey] = useState<CheckoutProviderOption["key"]>("wechat");
  const [checkoutState, setCheckoutState] = useState<CheckoutState>("loading_config");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadCheckoutData() {
      setCheckoutState("loading_config");
      try {
        const [summaryResponse, accessResponse, paymentResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/public-match-summary?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`, { cache: "no-store" }),
          fetch(`${API_BASE_URL}/api/access-options`, { cache: "no-store" }),
          fetch(`${API_BASE_URL}/api/payments/config`, { cache: "no-store" }),
        ]);
        const [summaryPayload, accessPayload, paymentPayload] = await Promise.all([
          summaryResponse.json().catch(() => null),
          accessResponse.json().catch(() => null),
          paymentResponse.json().catch(() => null),
        ]);
        if (!active) return;
        if (summaryResponse.ok && summaryPayload) setSummary(summaryPayload as PublicMatchSummary);
        if (accessResponse.ok && accessPayload) setAccessOptions(accessPayload as AccessOptions);
        if (paymentResponse.ok && paymentPayload) setPaymentConfig(paymentPayload as PaymentConfig);
        setCheckoutState("ready");
      } catch {
        if (!active) return;
        setCheckoutState("ready");
        setMessage("支付配置暂未连上，已保留页面预览");
      }
    }

    void loadCheckoutData();
    return () => {
      active = false;
    };
  }, [home, away]);

  const fallbackHome = resolveDisplayTeam(home, teams);
  const fallbackAway = resolveDisplayTeam(away, teams);
  const displaySummary: PublicMatchSummary = summary ?? {
    stage: "单场预测",
    kickoff: "待定",
    matchNo: null,
    status: "scheduled",
    homeTeam: home,
    awayTeam: away,
    homeName: fallbackHome.name,
    awayName: fallbackAway.name,
    homeCode: fallbackHome.code,
    awayCode: fallbackAway.code,
  };
  const singleProduct = accessOptions?.products.find((product) => product.key === "single_match") ?? {
    key: "single_match",
    name: "单场预测",
    scope: "解锁一场未开赛比赛的胜平负、比分分布和路径传导",
    amountLabel: "¥1.00",
    status: "payment_pending",
  };
  const providerOptions = useMemo(() => buildCheckoutProviderOptions(paymentConfig?.providers ?? [], isWechatBrowser()), [paymentConfig]);
  const selectedProvider = providerOptions.find((provider) => provider.key === selectedProviderKey) ?? providerOptions[0];
  const matchKey = `${displaySummary.homeTeam}-${displaySummary.awayTeam}`;
  const isCreating = checkoutState === "creating_order";
  const shortScope = "胜平负、比分分布、路径传导";
  const disclaimer = paymentConfig?.disclaimer ?? accessOptions?.disclaimer ?? "概率分析，不是投注建议。";

  useEffect(() => {
    if (providerOptions.length > 0 && !providerOptions.some((provider) => provider.key === selectedProviderKey)) {
      setSelectedProviderKey(providerOptions[0].key);
    }
  }, [providerOptions, selectedProviderKey]);

  function goBackToLockedPreview() {
    window.location.href = matchPagePath(displaySummary.homeTeam, displaySummary.awayTeam);
  }

  async function createCheckoutOrder() {
    if (!selectedProvider || isCreating) return;
    setCheckoutState("creating_order");
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/payments/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          productKey: "single_match",
          provider: selectedProvider.provider,
          contentKey: "match_prediction",
          matchKey,
          homeTeam: displaySummary.homeTeam,
          awayTeam: displaySummary.awayTeam,
          homeName: displaySummary.homeName,
          awayName: displaySummary.awayName,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.orderId) throw new Error(payload?.detail ?? "支付订单创建失败");
      window.location.href = `${PAYMENT_PENDING_ROUTE}?orderId=${encodeURIComponent(payload.orderId)}`;
    } catch (error) {
      setCheckoutState("failed");
      setMessage(error instanceof Error ? error.message : "支付订单创建失败");
    }
  }

  return (
    <main className="checkout-page-shell">
      <header className="checkout-topbar">
        <button type="button" aria-label="返回单场预览" onClick={goBackToLockedPreview}>
          <ArrowLeft aria-hidden="true" size={22} strokeWidth={2.7} />
        </button>
        <div>
          <strong>确认解锁</strong>
          <span>
            <ShieldCheck aria-hidden="true" size={14} strokeWidth={2.4} />
            zhugejunshi.com
          </span>
        </div>
      </header>

      <section className="checkout-product-card" aria-label="解锁商品">
        <img src="/assets/app/gold-football-product-icon.png" alt="" />
        <div className="checkout-product-main">
          <span>{singleProduct.name}</span>
          <strong>
            <TeamFlag team={displaySummary.homeTeam} code={displaySummary.homeCode} />
            {displaySummary.homeName}
            <em>vs</em>
            {displaySummary.awayName}
            <TeamFlag team={displaySummary.awayTeam} code={displaySummary.awayCode} />
          </strong>
          <small>{shortScope}</small>
        </div>
        <b>{singleProduct.amountLabel}</b>
      </section>

      <section className="checkout-section-heading">
        <i aria-hidden="true" />
        <strong>选择支付方式</strong>
      </section>

      <section className="checkout-provider-list" aria-label="微信支付和支付宝支付">
        {providerOptions.map((option) => {
          const Icon = option.Icon;
          const selected = selectedProvider?.key === option.key;
          return (
            <button
              className={`checkout-provider-card ${selected ? "selected" : ""}`}
              type="button"
              key={option.key}
              aria-pressed={selected}
              onClick={() => setSelectedProviderKey(option.key)}
            >
              <span className="checkout-provider-radio">{selected ? <CheckCircle2 aria-hidden="true" size={22} strokeWidth={2.7} /> : null}</span>
              <span className={`checkout-provider-icon ${option.key}`}>
                <Icon aria-hidden="true" size={27} strokeWidth={2.25} />
              </span>
              <span className="checkout-provider-copy">
                <strong>{option.label}</strong>
                <small>{option.methodLabel}</small>
              </span>
            </button>
          );
        })}
      </section>

      <section className="checkout-notice" aria-live="polite">
        <Info aria-hidden="true" size={18} strokeWidth={2.3} />
        <span>{message ?? "创建订单后等待支付确认"}</span>
      </section>

      <button className="checkout-create-button" type="button" disabled={!selectedProvider || isCreating} onClick={() => void createCheckoutOrder()}>
        {isCreating ? "订单创建中" : checkoutState === "failed" ? "重新创建支付订单" : "创建支付订单"}
      </button>

      <footer className="checkout-disclaimer">
        <ShieldCheck aria-hidden="true" size={14} strokeWidth={2.2} />
        <span>{disclaimer.replace("微信支付和支付宝仅用于解锁概率分析内容，不提供投注建议。", "概率分析，不是投注建议")}</span>
      </footer>
    </main>
  );
}

function PaymentInfoRow({
  Icon,
  label,
  children,
  aside,
}: {
  Icon: LucideIcon;
  label: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className="payment-info-row">
      <Icon aria-hidden="true" size={20} strokeWidth={2.1} />
      <div>
        <span>{label}</span>
        <strong>{children}</strong>
      </div>
      {aside ? <em>{aside}</em> : null}
    </div>
  );
}

function PaymentPendingPage({ orderId }: { orderId: string }) {
  const [order, setOrder] = useState<PaymentOrder | null>(null);
  const [loadStatus, setLoadStatus] = useState<LoadStatus>("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function confirmAccess(nextOrder: PaymentOrder) {
    const contentKey = paymentContentKey(nextOrder);
    const matchKey = nextOrder.metadata?.matchKey;
    const params = new URLSearchParams({
      orderId: nextOrder.orderId,
      contentKey,
    });
    if (matchKey) params.set("matchKey", matchKey);
    const response = await fetch(
      `${API_BASE_URL}/api/access-decision?${params.toString()}`,
      { cache: "no-store" },
    );
    const decision = (await response.json().catch(() => null)) as AccessDecision | null;
    if (!response.ok || !decision?.allowed) {
      setMessage("支付状态已更新，解锁权限仍在确认中");
      return;
    }
    setMessage("支付已确认，正在进入预测页面");
    window.setTimeout(() => {
      window.location.href = paymentRedirectPath(nextOrder);
    }, 700);
  }

  async function loadOrder(checkAccess = false) {
    if (!orderId) {
      setLoadStatus("failed");
      setMessage("缺少支付订单编号");
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/payments/orders/${encodeURIComponent(orderId)}`, { cache: "no-store" });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail ?? `支付订单接口返回 ${response.status}`);
      const nextOrder = payload as PaymentOrder;
      setOrder(nextOrder);
      setLoadStatus("ready");
      if (checkAccess && nextOrder.status === "paid") {
        await confirmAccess(nextOrder);
      } else if (checkAccess) {
        setMessage(paymentStatusMeta(nextOrder.status).detail);
      }
    } catch (error) {
      setLoadStatus("failed");
      setMessage(error instanceof Error ? error.message : "支付订单加载失败");
    }
  }

  useEffect(() => {
    let active = true;

    async function loadActiveOrder() {
      if (!active) return;
      await loadOrder(false);
    }

    void loadActiveOrder();
    const timer = window.setInterval(() => {
      void loadActiveOrder();
    }, PAYMENT_ORDER_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [orderId]);

  async function refreshOrder() {
    setRefreshing(true);
    setMessage(null);
    try {
      await loadOrder(true);
    } finally {
      setRefreshing(false);
    }
  }

  function goBackToPayment() {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/";
  }

  const statusMeta = paymentStatusMeta(order?.status ?? "pending");
  const orderTitle = order ? paymentProductTitle(order) : "订单加载中";
  const amountLabel = order?.amountLabel ?? "待确认";
  const paymentLine = order ? `${order.providerLabel} · ${paymentMethodLabel(order)}` : "支付方式待确认";
  const hasQrCode = Boolean(order?.qrCodeUrl && isQrPayment(order) && statusMeta.tone === "pending");

  return (
    <main className="payment-page-shell">
      <header className="payment-page-header">
        <button type="button" aria-label="返回" onClick={goBackToPayment}>
          <ArrowLeft aria-hidden="true" size={24} strokeWidth={2.4} />
        </button>
        <span>2026 世界杯预测</span>
      </header>

      <section className="payment-hero" aria-label="支付确认状态">
        <span className="payment-hero-icon" aria-hidden="true">
          <FileText size={23} strokeWidth={2.2} />
        </span>
        <h1>等待支付确认</h1>
        <p>{statusMeta.detail}</p>
      </section>

      <section className="payment-card" aria-label="支付订单">
        <div className="payment-card-head">
          <span className="payment-order-icon" aria-hidden="true">
            <FileText size={22} strokeWidth={2.2} />
          </span>
          <strong>
            订单 {shortOrderId(order?.orderId ?? orderId)} · {order?.productName ?? "支付订单"}
          </strong>
          <b className={`payment-status-pill ${statusMeta.tone}`}>{statusMeta.label}</b>
        </div>

        <div className="payment-info-panel">
          <PaymentInfoRow Icon={CircleDollarSign} label="产品" aside={amountLabel}>
            {orderTitle}
          </PaymentInfoRow>
          <PaymentInfoRow Icon={WalletCards} label="支付方式">
            {paymentLine}
          </PaymentInfoRow>
          <PaymentInfoRow Icon={Clock} label="创建时间">
            {order ? formatPaymentDate(order.createdAt) : "待确认"}
          </PaymentInfoRow>
          <PaymentInfoRow Icon={Hourglass} label="过期时间" aside={order ? formatPaymentRemaining(order.expiresAt) : undefined}>
            {order ? formatPaymentDate(order.expiresAt) : "待确认"}
          </PaymentInfoRow>
        </div>

        <div className={`payment-qr-panel ${hasQrCode ? "ready" : ""}`}>
          {hasQrCode ? <img src={order?.qrCodeUrl ?? ""} alt="支付二维码" /> : <QrCode aria-hidden="true" size={34} strokeWidth={1.8} />}
          <span>{hasQrCode ? "请扫码完成支付" : order?.paymentMethod === "jsapi" ? "微信支付弹窗等待完成" : "二维码待返回"}</span>
        </div>

        <div className="payment-hint-card">
          {statusMeta.tone === "unavailable" ? <AlertTriangle aria-hidden="true" size={34} strokeWidth={2.1} /> : <ShieldCheck aria-hidden="true" size={34} strokeWidth={2.1} />}
          <div>
            <strong>{statusMeta.tone === "unavailable" ? "当前支付通道暂不可用" : "请完成支付后刷新状态"}</strong>
            <p>{order?.productKey === "tournament_pass" ? "支付完成后，系统将自动确认并解锁剩余未开赛预测" : "支付完成后，系统将自动确认并解锁本场预测"}</p>
          </div>
        </div>

        {message ? <p className="payment-message">{message}</p> : null}

        <button className="payment-refresh-button" type="button" onClick={refreshOrder} disabled={refreshing || loadStatus === "loading"}>
          {order?.status === "paid" ? <CheckCircle2 aria-hidden="true" size={20} strokeWidth={2.4} /> : <RefreshCw aria-hidden="true" size={20} strokeWidth={2.4} />}
          <span>{refreshing ? "正在刷新状态" : "我已支付，刷新状态"}</span>
        </button>

        <button className="payment-back-button" type="button" onClick={goBackToPayment}>
          <ArrowLeft aria-hidden="true" size={20} strokeWidth={2.4} />
          <span>返回选择支付方式</span>
        </button>

        <div className="payment-lock-note">
          <Lock aria-hidden="true" size={14} strokeWidth={2.2} />
          <span>支付成功后自动解锁本场预测</span>
        </div>
      </section>

      <footer className="payment-footer">
        <ShieldCheck aria-hidden="true" size={14} strokeWidth={2.1} />
        <span>概率分析，不是投注建议</span>
      </footer>
    </main>
  );
}

function AdminConsole() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [eventReview, setEventReview] = useState<EventReviewResponse | null>(null);
  const [predictionRun, setPredictionRun] = useState<PredictionRunMonitor | null>(null);
  const [adminToken, setAdminToken] = useState(() => window.localStorage.getItem("worldCupAdminToken") ?? "");
  const [adminAccess, setAdminAccess] = useState<AdminAccessState>("checking");
  const [authError, setAuthError] = useState<string | null>(null);
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

  function adminHeaders(token = adminToken) {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token.trim()) {
      headers["X-Admin-Token"] = token.trim();
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

  async function loadAdminData(token = adminToken) {
    const headers = adminHeaders(token);
    const [overviewResponse, eventsResponse, predictionRunResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/api/admin/overview`, { cache: "no-store", headers }),
      fetch(`${API_BASE_URL}/api/events`, { cache: "no-store", headers }),
      fetch(`${API_BASE_URL}/api/admin/prediction-run`, { cache: "no-store", headers }),
    ]);
    if (!overviewResponse.ok) throw new Error(`后台概览接口返回 ${overviewResponse.status}`);
    if (!eventsResponse.ok) throw new Error(`事件接口返回 ${eventsResponse.status}`);
    if (!predictionRunResponse.ok) throw new Error(`预测追踪接口返回 ${predictionRunResponse.status}`);
    setOverview((await overviewResponse.json()) as AdminOverview);
    setEventReview((await eventsResponse.json()) as EventReviewResponse);
    setPredictionRun((await predictionRunResponse.json()) as PredictionRunMonitor);
  }

  useEffect(() => {
    let active = true;

    async function run() {
      try {
        await loadAdminData(adminToken);
        if (active) {
          setAdminAccess("ready");
          setAuthError(null);
        }
        return true;
      } catch {
        if (active) {
          setOverview(null);
          setEventReview(null);
          setPredictionRun(null);
          setAdminAccess("locked");
        }
        return false;
      }
    }

    void run();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (adminAccess !== "ready") return undefined;
    const timer = window.setInterval(() => {
      void loadAdminData(adminToken);
    }, FORECAST_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [adminAccess, adminToken]);

  async function submitAdminLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminAccess("checking");
    setAuthError(null);
    try {
      await loadAdminData(adminToken);
      saveAdminToken(adminToken);
      setAdminAccess("ready");
    } catch {
      setOverview(null);
      setEventReview(null);
      setPredictionRun(null);
      setAdminAccess("locked");
      setAuthError("Token 不正确");
    }
  }

  function logoutAdmin() {
    saveAdminToken("");
    setOverview(null);
    setEventReview(null);
    setPredictionRun(null);
    setAuthError(null);
    setAdminAccess("locked");
  }

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

  if (adminAccess !== "ready") {
    return (
      <main className="admin-shell">
        <header className="admin-topbar">
          <div>
            <span>World Cup Ops</span>
            <h1>预测运营后台</h1>
          </div>
          <a href="/">返回预测页</a>
        </header>

        <section className="admin-login-panel">
          <article className="admin-card">
            <h2>后台 Token</h2>
            <form className="admin-login-form" onSubmit={submitAdminLogin}>
              <input
                value={adminToken}
                onChange={(event) => saveAdminToken(event.target.value)}
                aria-label="后台 token"
                placeholder="输入后台 Token"
                type="password"
                autoComplete="current-password"
              />
              <button type="submit" disabled={adminAccess === "checking"}>
                {adminAccess === "checking" ? "验证中" : "进入控制面板"}
              </button>
            </form>
            {authError ? <p className="admin-auth-error">{authError}</p> : null}
          </article>
        </section>
      </main>
    );
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
              placeholder="后台 Token"
              type="password"
            />
            <span>{overview?.authRequired ? "已通过 Token 验证" : "本地未启用 Token"}</span>
            <button type="button" onClick={logoutAdmin}>退出后台</button>
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
            <Metric label="多源确认" value={overview?.eventSummary.multiSource ?? 0} tone="green" />
            <Metric label="单源线索" value={overview?.eventSummary.singleSource ?? 0} tone="blue" />
            <Metric label="忽略" value={overview?.eventSummary.ignored ?? 0} tone="muted" />
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

        <article className="admin-card admin-card-wide">
          <h2>预测运行监管</h2>
          <PredictionRunPanel monitor={predictionRun} />
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

function PredictionRunPanel({ monitor }: { monitor: PredictionRunMonitor | null }) {
  if (!monitor) {
    return <p className="review-empty">预测运行追踪等待 API 连接</p>;
  }

  return (
    <div className="prediction-run-panel">
      <div className="run-head">
        <div>
          <span>{monitor.match.stage}</span>
          <strong>
            {monitor.match.homeCode} / {monitor.match.awayCode}
          </strong>
          <em>{monitor.match.status === "scheduled" ? "未开赛" : monitor.match.status}</em>
        </div>
        <div className="run-summary">
          <Metric label="已执行" value={monitor.summary.ranSteps} tone="green" />
          <Metric label="跳过" value={monitor.summary.skippedSteps} tone="muted" />
          <Metric label="待人工" value={monitor.summary.manualSteps} tone="gold" />
          <Metric label="介入点" value={monitor.summary.interventionPoints} tone="blue" />
        </div>
      </div>

      <div className="run-stage-list">
        {monitor.pipeline.map((stage) => (
          <section className="run-stage" key={stage.id}>
            <div className="run-stage-title">
              <strong>{stage.title}</strong>
              <span>{predictionRunStatusLabel(stage.status)}</span>
            </div>
            <div className="run-step-list">
              {stage.steps.map((step) => (
                <div className={`run-step ${predictionRunStatusTone(step.status)}`} key={step.id}>
                  <span>{predictionRunStatusLabel(step.status)}</span>
                  <strong>{step.label}</strong>
                  <p>{step.detail}</p>
                  <code>{step.functionName}</code>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>

      <div className="run-split">
        <div className="run-table">
          <strong>接口状态</strong>
          {monitor.interfaces.map((item) => (
            <div className="run-interface-row" key={`${item.method}-${item.path}`}>
              <code>{item.method}</code>
              <span>{item.path}</span>
              <em className={predictionRunStatusTone(item.status)}>{predictionRunStatusLabel(item.status)}</em>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
        <div className="run-table">
          <strong>人工介入</strong>
          {monitor.interventionPoints.map((item) => (
            <div className="run-intervention-row" key={item.endpoint}>
              <span>{item.label}</span>
              <code>{item.endpoint}</code>
              <small>{item.affects}</small>
            </div>
          ))}
        </div>
      </div>
    </div>
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
          <div className="champion-probability">
            <b>{team.tournament.champion}%</b>
            <em className={team.tournament.change >= 0 ? "green" : "red"}>{formatSignedPercent(team.tournament.change)}</em>
          </div>
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

function postMatchRootCauseLabel(value: string) {
  const labels: Record<string, string> = {
    large_score_tail_underestimated: "大比分尾部低估",
    score_matrix_truncated_tail: "比分矩阵覆盖不足",
    total_goals_underestimated: "总进球预期偏低",
    underdog_goal_tail_underestimated: "弱队进球尾部低估",
    normal_score_variance: "常规比分波动",
  };
  return labels[value] ?? "模型偏差待复盘";
}

function postMatchSeverityLabel(value?: string) {
  if (value === "high") return "需要校准";
  if (value === "medium") return "存在偏差";
  if (value === "low") return "偏差正常";
  return "复盘中";
}

function postMatchDirectionLabel(review?: PostMatchReview) {
  if (!review || typeof review.winnerMissed !== "boolean") return "方向待确认";
  return review.winnerMissed ? "方向偏离" : "方向命中";
}

function findFinishedMatch(matches: FinishedMatch[], home: TeamKey, away: TeamKey) {
  return matches.find((item) => item.homeTeam === home && item.awayTeam === away) ?? null;
}

function PostMatchReviewPage({ home, away }: { home: TeamKey; away: TeamKey }) {
  const [match, setMatch] = useState<FinishedMatch | null>(null);
  const [nextMatch, setNextMatch] = useState<PublicUpcomingMatch | null>(null);
  const [loadStatus, setLoadStatus] = useState<LoadStatus>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const orderId = useMemo(() => new URLSearchParams(window.location.search).get("orderId"), []);

  useEffect(() => {
    let active = true;

    async function loadPublicReview() {
      const response = await fetch(`${API_BASE_URL}/api/public-finished-matches?limit=72`, { cache: "no-store" });
      if (!response.ok) throw new Error(`完赛复盘接口返回 ${response.status}`);
      const payload = (await response.json()) as FinishedMatchesResponse;
      const found = findFinishedMatch(payload.items, home, away);
      if (!found) throw new Error("没有找到这场已结束比赛");
      if (!active) return;
      setMatch(found);
      setLoadStatus("ready");
    }

    async function loadPaidReview() {
      if (!orderId) return;
      const response = await fetch(
        `${API_BASE_URL}/api/finished-match-review?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&orderId=${encodeURIComponent(orderId)}`,
        { cache: "no-store" },
      );
      if (!active) return;
      if (!response.ok) {
        setMessage("赛前预测回看尚未解锁");
        return;
      }
      const payload = (await response.json()) as FinishedMatch;
      setMatch(payload);
      setMessage(null);
    }

    async function loadNextMatch() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/public-upcoming-matches?limit=1`, { cache: "no-store" });
        if (!response.ok) throw new Error(`下一场接口返回 ${response.status}`);
        const payload = (await response.json()) as PublicUpcomingMatchesResponse;
        if (!active) return;
        setNextMatch(payload.items[0] ?? null);
      } catch {
        if (!active) return;
        setNextMatch(buildStaticPublicUpcomingMatchesFallback().items[0] ?? null);
      }
    }

    async function run() {
      try {
        await loadPublicReview();
        await loadPaidReview();
      } catch (error) {
        if (!active) return;
        setLoadStatus("failed");
        setMessage(error instanceof Error ? error.message : "赛后复盘加载失败");
      }
      await loadNextMatch();
    }

    void run();
    return () => {
      active = false;
    };
  }, [home, away, orderId]);

  function goBack() {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/";
  }

  const review = match?.postMatchReview;
  const hasFullReview = Boolean(review?.predictedTopScore);
  const baselineReady = Boolean(review?.hasPredictionBaseline);
  const isBaselineMissing = review ? !review.hasPredictionBaseline : false;
  const rootCause = review?.rootCauses?.[0] ? postMatchRootCauseLabel(review.rootCauses[0]) : "等待赛前快照生成后复盘";
  const nextHref = nextMatch ? matchPagePath(nextMatch.homeTeam, nextMatch.awayTeam) : "/";
  const matchStage = match?.stage ?? "赛后复盘";
  const kickoff = match ? formatKickoffForUser(match.kickoff) : "加载中";
  const homeName = match?.homeName ?? home;
  const awayName = match?.awayName ?? away;
  const homeCode = match?.homeCode ?? home.slice(0, 3).toUpperCase();
  const awayCode = match?.awayCode ?? away.slice(0, 3).toUpperCase();

  return (
    <main className="postmatch-page-shell">
      <section className="postmatch-app" aria-label="已结束比赛复盘">
        <header className="postmatch-header">
          <button type="button" aria-label="返回" onClick={goBack}>
            <ArrowLeft size={25} strokeWidth={2.5} />
          </button>
          <div>
            <strong>赛后复盘</strong>
            <span>{matchStage}</span>
          </div>
        </header>

        <section className="postmatch-hero" aria-label="最终比分">
          <p>{kickoff}</p>
          <span className="postmatch-status">{match ? publicMatchStatusLabel(match.status) : "加载中"}</span>
          <div className="postmatch-scoreline">
            <div className="postmatch-team">
              <TeamFlag team={home} code={homeCode} />
              <span>{homeName}</span>
            </div>
            <strong>{match ? `${match.homeScore} - ${match.awayScore}` : "-- - --"}</strong>
            <div className="postmatch-team away">
              <TeamFlag team={away} code={awayCode} />
              <span>{awayName}</span>
            </div>
          </div>
        </section>

        <section className="postmatch-card postmatch-prediction-card" aria-label="赛前预测回看">
          <Target size={34} strokeWidth={2.2} />
          <div>
            <span>赛前最可能比分</span>
            {hasFullReview ? (
              <strong>
                {review?.predictedTopScore} · {formatProbabilityValue(review?.predictedTopProbability ?? 0)}
              </strong>
            ) : baselineReady ? (
              <strong>赛前预测回看已锁定</strong>
            ) : (
              <strong>赛前预测快照待生成</strong>
            )}
            <p>{hasFullReview ? "已读取本场赛前预测记录" : review?.message ?? "这场暂时只能展示真实赛果"}</p>
          </div>
          <Signal size={32} strokeWidth={2.1} />
        </section>

        <section className="postmatch-card postmatch-model-card" aria-label="模型复盘">
          <div className="postmatch-section-title">
            <ShieldCheck size={18} strokeWidth={2.4} />
            <span>模型复盘</span>
          </div>
          {loadStatus === "failed" ? (
            <div className="postmatch-review-copy muted">
              <strong>复盘加载失败</strong>
              <p>{message ?? "请稍后再试"}</p>
            </div>
          ) : hasFullReview ? (
            <div className="postmatch-review-copy">
              <strong>
                {postMatchDirectionLabel(review)}，{postMatchSeverityLabel(review?.severity)}
              </strong>
              <p>{review?.summary}</p>
            </div>
          ) : baselineReady ? (
            <div className="postmatch-review-copy locked">
              <strong>完整预测已锁定</strong>
              <p>{message ?? "解锁后可查看赛前比分预测、方向命中和误差复盘。"}</p>
            </div>
          ) : (
            <div className="postmatch-review-copy muted">
              <strong>真实赛果已锁定</strong>
              <p>{review?.message ?? match?.modelUseLabel ?? "比赛结果会进入后续路径权重。"}</p>
            </div>
          )}
        </section>

        <section className="postmatch-card postmatch-root-card" aria-label="误差归因">
          <div className="postmatch-section-title">
            <Signal size={18} strokeWidth={2.4} />
            <span>误差归因</span>
          </div>
          <strong>{hasFullReview ? rootCause : isBaselineMissing ? "赛前快照缺失" : "复盘内容已锁定"}</strong>
          <p>
            {hasFullReview
              ? `总进球误差 ${review?.totalGoalError ?? 0} 球，后续用于校准比分分布。`
              : isBaselineMissing
                ? "需要先保存每场赛前预测快照，才能做赛后误差归因。"
                : "解锁后查看模型偏差来源。"}
          </p>
        </section>

        <a className="postmatch-next-button" href={nextHref}>
          <Trophy size={22} strokeWidth={2.3} />
          <span>查看下一场未开赛</span>
          <ChevronRight size={24} strokeWidth={2.5} />
        </a>

        <footer className="postmatch-footer">
          <ShieldCheck size={15} strokeWidth={2.4} />
          <span>概率分析，不是投注建议</span>
        </footer>
      </section>
    </main>
  );
}

export default App;
