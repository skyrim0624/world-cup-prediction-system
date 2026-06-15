import { Fragment, FormEvent, useEffect, useMemo, useState, type CSSProperties } from "react";
import { CalendarDays, Newspaper, Target, Trophy, type LucideIcon } from "lucide-react";

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
  scenarioImpacts: ScenarioImpact[];
  creatorTopics?: CreatorTopic[];
  analysis: string[];
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
const SINGLE_MATCH_ROUTE_PREFIX = "/match/";

const USER_SCREENS: { key: UserScreenKey; hash: string; label: string; Icon: LucideIcon }[] = [
  { key: "forecast", hash: "forecast", label: "预测", Icon: Target },
  { key: "matches", hash: "matches", label: "赛程", Icon: CalendarDays },
  { key: "board", hash: "board", label: "榜单", Icon: Trophy },
  { key: "news", hash: "news", label: "新闻", Icon: Newspaper },
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
  const [upcomingMatches, setUpcomingMatches] = useState<UpcomingMatchesResponse | null>(() => buildStaticUpcomingMatchesFallback());
  const [upcomingMatchesStatus, setUpcomingMatchesStatus] = useState<LoadStatus>("loading");
  const [activeScreen, setActiveScreen] = useState<UserScreenKey>(() => userScreenFromHash());
  const referenceDate = useMemo(() => new Date(), [forecastTick]);

  const teamsData = apiPrediction?.teams?.length ? apiPrediction.teams : teams;
  const fallbackPrediction = useMemo(() => buildFallbackPrediction(referenceDate), [referenceDate]);
  const validApiPrediction = apiPrediction && isUpcomingMatch(apiPrediction, referenceDate) ? apiPrediction : null;
  const matchPrediction = validApiPrediction ?? fallbackPrediction;
  const homeTeam = teamsData.find((team) => team.key === matchPrediction.homeTeam) ?? teamsData[0];
  const awayTeam = teamsData.find((team) => team.key === matchPrediction.awayTeam) ?? teamsData[1];
  const championBoard = [...teamsData].sort((left, right) => right.tournament.champion - left.tournament.champion);
  const topScore = matchPrediction.scoreOutcomes[0];
  const goalMarkets = matchPrediction.goalMarkets?.length ? matchPrediction.goalMarkets : goalMarketsFallback();
  const predictionOutcomes = [
    { label: `${homeTeam.name}胜`, value: matchPrediction.homeWin, tone: "green" as Tone },
    { label: "平局", value: matchPrediction.draw, tone: "gold" as Tone },
    { label: `${awayTeam.name}胜`, value: matchPrediction.awayWin, tone: "blue" as Tone },
  ].sort((left, right) => right.value - left.value);
  const primaryOutcome = predictionOutcomes[0];
  const secondaryOutcomes = predictionOutcomes.slice(1);
  const upcomingMatchItems = useMemo(() => filterUpcomingMatches(upcomingMatches?.items ?? [], referenceDate), [upcomingMatches, referenceDate]);
  const focusedPredictionMatch = predictionToUpcomingMatch(matchPrediction, homeTeam, awayTeam);
  const focusedUpcomingMatch = isUpcomingMatch(focusedPredictionMatch, referenceDate) ? focusedPredictionMatch : null;

  useEffect(() => {
    let active = true;

    async function loadPrediction() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/match-prediction?simulations=${INTERACTIVE_SIMULATION_COUNT}&useSnapshot=true`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`预测接口返回 ${response.status}`);
        const data = (await response.json()) as MatchPrediction;
        if (!active) return;
        setApiPrediction(data);
      } catch {
        if (!active) return;
        setApiPrediction(null);
      }
    }

    async function loadUpcomingMatches() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/upcoming-matches?limit=12`, { cache: "no-store" });
        if (!response.ok) throw new Error(`未开赛赛程接口返回 ${response.status}`);
        const data = (await response.json()) as UpcomingMatchesResponse;
        if (!active) return;
        const items = filterUpcomingMatches(data.items);
        setUpcomingMatches({ ...data, count: items.length, items });
        setUpcomingMatchesStatus("ready");
      } catch {
        if (!active) return;
        setUpcomingMatches(buildStaticUpcomingMatchesFallback());
        setUpcomingMatchesStatus("failed");
      }
    }

    async function loadHomeData() {
      // NOTE: Cloudflare Python Worker 冷启动时并发请求容易超 CPU，公开页按顺序读取快照和赛程。
      await loadPrediction();
      await loadUpcomingMatches();
    }

    void loadHomeData();
    const timer = window.setInterval(() => {
      setForecastTick((value) => value + 1);
      void loadHomeData();
    }, FORECAST_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    function syncScreenFromLocation() {
      setActiveScreen(userScreenFromHash());
    }

    window.addEventListener("hashchange", syncScreenFromLocation);
    window.addEventListener("popstate", syncScreenFromLocation);
    return () => {
      window.removeEventListener("hashchange", syncScreenFromLocation);
      window.removeEventListener("popstate", syncScreenFromLocation);
    };
  }, []);

  function openMatchPage(match: UpcomingMatch) {
    window.location.href = matchPagePath(match.homeTeam, match.awayTeam);
  }

  function openScreen(screenKey: UserScreenKey) {
    const screen = USER_SCREENS.find((item) => item.key === screenKey);
    if (!screen) return;
    setActiveScreen(screenKey);
    window.history.pushState(null, "", `${window.location.pathname}${window.location.search}#${screen.hash}`);
  }

  return (
    <main className="console-shell user-page-shell">
      <div className="ambient-grid" />
      <header className="topbar portal-topbar">
        <div className="brand portal-brand">
          <span>世界杯预测</span>
          <small>{formatUpdateTime(matchPrediction.updatedAt)} 更新</small>
        </div>
      </header>

      <section className="app-screen" aria-labelledby="active-screen-title">
        <div className="app-screen-head">
          <h1 id="active-screen-title">
            {activeScreen === "forecast" ? "今日重点预测" : activeScreen === "matches" ? "未开赛比赛" : activeScreen === "board" ? "概率榜单" : "新闻与方法"}
          </h1>
        </div>

        {activeScreen === "forecast" ? (
          <div className="app-screen-stack forecast-screen">
            <section className="console-panel app-hero-card">
              <a className="app-match-summary" href={matchPagePath(matchPrediction.homeTeam, matchPrediction.awayTeam)}>
                <span>{matchPrediction.stage}</span>
                <div className="app-match-teams">
                  <span>
                    <TeamFlag team={homeTeam.key} code={homeTeam.code} />
                    <b>{homeTeam.code}</b>
                  </span>
                  <strong>VS</strong>
                  <span>
                    <TeamFlag team={awayTeam.key} code={awayTeam.code} />
                    <b>{awayTeam.code}</b>
                  </span>
                </div>
                <small>{formatKickoffForUser(matchPrediction.kickoff)}</small>
              </a>
              <div className="app-prediction-focus">
                <div className={`app-main-outcome ${primaryOutcome.tone}`}>
                  <span>主判断</span>
                  <strong>{primaryOutcome.label}</strong>
                  <b>{primaryOutcome.value}%</b>
                </div>
                <div className="app-score-chip">
                  <span>最可能比分</span>
                  <strong>{topScore?.score ?? "--"}</strong>
                  <em>{topScore ? `${topScore.probability.toFixed(1)}%` : "生成中"}</em>
                </div>
              </div>
              <div className="app-supporting-probs" aria-label="其它赛果概率">
                {secondaryOutcomes.map((outcome) => (
                  <article className={outcome.tone} key={outcome.label}>
                    <span>{outcome.label}</span>
                    <strong>{outcome.value}%</strong>
                  </article>
                ))}
              </div>
              <CompactScoreList outcomes={matchPrediction.scoreOutcomes.slice(0, 3)} />
              <div className="analysis-list compact-analysis">
                {matchPrediction.analysis.slice(0, 2).map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
              <div className="app-mini-market">
                <div className="section-title">
                  <span>进球概率</span>
                </div>
                <GoalMarketPanel markets={goalMarkets.slice(0, 2)} compact />
              </div>
            </section>
          </div>
        ) : null}

        {activeScreen === "matches" ? (
          <div className="app-screen-stack">
            <section className="console-panel">
              <UpcomingMatchesPanel
                matches={upcomingMatchItems}
                status={upcomingMatchesStatus}
                fallbackMatch={focusedUpcomingMatch}
                onSelect={openMatchPage}
              />
            </section>
          </div>
        ) : null}

        {activeScreen === "board" ? (
          <div className="app-screen-stack">
            <section className="console-panel portal-standing-card">
              <div className="section-title">
                <span>冠军概率榜</span>
              </div>
              <ChampionBoard teams={championBoard.slice(0, 5)} />
            </section>
          </div>
        ) : null}

        {activeScreen === "news" ? (
          <div className="app-screen-stack">
            <section className="console-panel">
              <div className="section-title">
                <span>新闻影响摘要</span>
              </div>
              <div className="news-list">
                {matchPrediction.newsItems.slice(0, 3).map((item) => (
                  <article className={`news-item ${item.tone}`} key={item.title}>
                    <span className="news-icon">{item.tone === "red" ? "+" : item.tone === "gold" ? "!" : "?"}</span>
                    <div>
                      <strong>{item.title}</strong>
                      <p>{userNewsDetail(item.detail)}</p>
                      <small>{item.time}</small>
                    </div>
                    <em>{userNewsImpactLabel(item.impact)}</em>
                  </article>
                ))}
              </div>
            </section>
            <section className="console-panel">
              <div className="section-title">
                <span>判断依据</span>
              </div>
              <UserMethodPanel />
            </section>
          </div>
        ) : null}

      </section>

      <nav className="app-bottom-nav" aria-label="预测功能导航">
        {USER_SCREENS.map(({ key, label, Icon }) => (
          <button type="button" className={activeScreen === key ? "active" : ""} aria-current={activeScreen === key ? "page" : undefined} key={key} onClick={() => openScreen(key)}>
            <Icon aria-hidden="true" size={20} strokeWidth={2.4} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </main>
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

function UpcomingMatchesPanel({
  matches,
  status,
  fallbackMatch,
  onSelect,
}: {
  matches: UpcomingMatch[];
  status: LoadStatus;
  fallbackMatch: UpcomingMatch | null;
  onSelect: (match: UpcomingMatch) => void;
}) {
  const displayMatches = matches.length ? matches : status !== "ready" && fallbackMatch ? [fallbackMatch] : [];

  if (displayMatches.length === 0 && status === "loading") {
    return <p className="review-empty">赛程加载中</p>;
  }

  if (displayMatches.length === 0 && status === "failed") {
    return <p className="review-empty">赛程接口连接失败，等待自动刷新</p>;
  }

  if (displayMatches.length === 0) {
    return <p className="review-empty">暂无未开赛比赛</p>;
  }

  return (
    <div className="upcoming-list">
      {displayMatches.map((match) => {
        const key = `${match.homeTeam}-${match.awayTeam}`;
        return (
          <button className="upcoming-row" key={`${key}-${match.kickoff}`} onClick={() => onSelect(match)}>
            <div className="upcoming-teams">
              <span>
                <TeamFlag team={match.homeTeam} code={match.homeCode} />
                <em>{match.homeCode}</em>
              </span>
              <b>VS</b>
              <span>
                <TeamFlag team={match.awayTeam} code={match.awayCode} />
                <em>{match.awayCode}</em>
              </span>
            </div>
            <div className="upcoming-copy">
              <strong>
                {match.homeName} / {match.awayName}
              </strong>
              <small>
                {[match.stage, formatKickoffForUser(match.kickoff), `最可能 ${match.topScore.score} / ${match.topScore.probability.toFixed(1)}%`].filter(Boolean).join(" · ")}
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

function SingleMatchPage({ home, away }: { home: TeamKey; away: TeamKey }) {
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

    loadDetail();
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
  const detailScoreMatrix = detail ? (detail.scoreMatrix?.length ? detail.scoreMatrix : scoreMatrixFallbackFromOutcomes(detail.scoreOutcomes)) : [];
  const detailGoalMarkets = detail?.goalMarkets?.length ? detail.goalMarkets : goalMarketsFallback();
  const detailFairPrices = detail?.fairPrices?.length
    ? detail.fairPrices
    : [
        { label: `${homeName}胜`, probability: detail?.homeWin ?? 0, fairDecimal: detail?.homeWin ? Number((100 / detail.homeWin).toFixed(2)) : 0, note: "90 分钟模型公平概率", tone: "green" as Tone },
        { label: "平局", probability: detail?.draw ?? 0, fairDecimal: detail?.draw ? Number((100 / detail.draw).toFixed(2)) : 0, note: "90 分钟模型公平概率", tone: "gold" as Tone },
        { label: `${awayName}胜`, probability: detail?.awayWin ?? 0, fairDecimal: detail?.awayWin ? Number((100 / detail.awayWin).toFixed(2)) : 0, note: "90 分钟模型公平概率", tone: "blue" as Tone },
      ];
  const detailCreatorTopics = detail?.creatorTopics?.length
    ? detail.creatorTopics
    : creatorTopicsFallback(homeName, awayName, detail?.scoreOutcomes[0]?.score);

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
            <span>{detail ? formatKickoffForUser(detail.kickoff) : "加载中"}</span>
            <em>{detail?.status ?? "待载入"}</em>
          </div>
          <div className="match-meta">
            <span>{detail?.stage ?? "单场预测"}</span>
            {detail ? <b>预测更新 {formatUpdateTime(detail.updatedAt)}</b> : null}
          </div>
        </div>
        <MiniPitch side="right" />
      </section>

      <div className="module-grid">
        <section className="console-panel wide">
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
          <h2>比分预测</h2>
          {detail ? (
            <div className="score-outcome-list">
              {detail.scoreOutcomes.slice(0, 3).map((outcome) => (
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
        </section>

        <section className="console-panel wide">
          <h2>单场预测细节</h2>
          {detail ? (
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
              <div className="match-detail-splits">
                <FairPricePanel prices={detailFairPrices} />
                <GoalMarketPanel markets={detailGoalMarkets} compact />
              </div>
              <ScoreMatrix cells={detailScoreMatrix} />
              <div className="analysis-list">
                {detail.analysis.map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
              <ScenarioImpactList scenarios={detail.scenarioImpacts} />
              <CreatorTopicsPanel topics={detailCreatorTopics} />
            </div>
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

export default App;
