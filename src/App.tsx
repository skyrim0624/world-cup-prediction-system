import { CSSProperties, PointerEvent, useEffect, useMemo, useRef, useState } from "react";

type TeamKey = string;
type Tone = "green" | "blue" | "gold" | "orange" | "red" | "muted";
type PlateKey = "strength" | "form" | "path" | "squad" | "margin";
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

type DragState = {
  key: string;
  startX: number;
  startY: number;
  baseX: number;
  baseY: number;
};

type NewsItem = {
  title: string;
  detail: string;
  impact: string;
  tone: Tone;
  time: string;
};

type ScoreOutcome = {
  score: string;
  probability: number;
  note: string;
  tone: Tone;
};

type ScenarioImpact = {
  label: string;
  probability: number;
  title: string;
  details: string[];
  championShift: string;
  tone: Tone;
};

type MatchPrediction = {
  stage: string;
  kickoff: string;
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
  modelMeta?: {
    engine: string;
    simulationCount: number;
    lockedResults: number;
    dataset?: {
      source: string;
      teamCount: number;
      fixtureCount: number;
      eventCount: number;
    };
    events?: {
      watched: number;
      applied: number;
      ignored: number;
    };
    factorImpacts?: FactorImpactMap;
  };
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
    key: "netherlands",
    name: "荷兰",
    code: "NED",
    factors: { strength: 82, form: 83, path: 69, squad: 80, margin: 83 },
    tournament: { champion: 7.1, final: 15.8, semifinal: 28.6, quarterfinal: 51.9, change: -0.3 },
  },
];

const factorRows = [
  { key: "strength", label: "实力盘", tone: "green" },
  { key: "form", label: "状态盘", tone: "blue" },
  { key: "path", label: "路径盘", tone: "gold" },
  { key: "squad", label: "人员盘", tone: "green" },
  { key: "margin", label: "边际盘", tone: "orange" },
] satisfies Array<{ key: PlateKey; label: string; tone: Tone }>;

const weightFactors = [
  { label: "基础实力", value: 22, note: "Elo / SPI / 长期评级" },
  { label: "攻防质量", value: 16, note: "xG / 射门质量 / 防守压制" },
  { label: "晋级路径", value: 16, note: "小组名次 / 半区难度" },
  { label: "阵容健康", value: 12, note: "伤病 / 停赛 / 替补深度" },
  { label: "主帅凝聚", value: 10, note: "临场调整 / 更衣室秩序" },
  { label: "关键人物", value: 8, note: "核心球员影响与可替代性" },
  { label: "战术克制", value: 6, note: "高压 / 低位 / 反击适配" },
  { label: "定位球门将", value: 5, note: "定位球 / 点球 / 门将" },
  { label: "旅程气候", value: 3, note: "飞行 / 时区 / 高温高原" },
  { label: "市场舆论", value: 2, note: "市场热度 / 媒体偏差" },
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

const sourceWeights = [
  { level: "S", value: "1.00", label: "官方", tone: "green" },
  { level: "A", value: "0.70", label: "顶级媒体", tone: "green" },
  { level: "B", value: "0.40", label: "随队记者", tone: "gold" },
  { level: "C", value: "0.20", label: "普通媒体", tone: "orange" },
  { level: "D", value: "0.00", label: "传闻", tone: "red" },
];

const INTERACTIVE_SIMULATION_COUNT = 1200;
const FORECAST_REFRESH_MS = 15000;
const API_BASE_URL = import.meta.env.DEV ? "http://127.0.0.1:8000" : "";

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

function plateImpact(teamKey: TeamKey, plateKey: PlateKey, impacts?: FactorImpactMap) {
  const teamImpacts = impacts?.[teamKey];
  if (!teamImpacts) return 0;
  if (plateKey === "form") return ((teamImpacts.attack ?? 0) + (teamImpacts.defense ?? 0)) / 2;
  if (plateKey === "margin") return ((teamImpacts.goalkeeper ?? 0) + (teamImpacts.defense ?? 0)) / 2;
  if (plateKey === "path") return teamImpacts.path ?? 0;
  if (plateKey === "squad") return teamImpacts.squad ?? 0;
  return 0;
}

function App() {
  const [selectedTeam, setSelectedTeam] = useState<TeamKey>("brazil");
  const [layoutUnlocked, setLayoutUnlocked] = useState(false);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [forecastTick, setForecastTick] = useState(0);
  const [apiPrediction, setApiPrediction] = useState<MatchPrediction | null>(null);
  const [dataMode, setDataMode] = useState<"api" | "demo">("demo");
  const dragRef = useRef<DragState | null>(null);
  const lastTapRef = useRef(0);

  const teamsData = apiPrediction?.teams?.length ? apiPrediction.teams : teams;
  const selected = useMemo(() => teamsData.find((team) => team.key === selectedTeam) ?? teamsData[0], [selectedTeam, teamsData]);
  const fallbackPrediction = useMemo(() => buildFallbackPrediction(forecastTick), [forecastTick]);
  const matchPrediction = apiPrediction ?? fallbackPrediction;
  const homeTeam = teamsData.find((team) => team.key === matchPrediction.homeTeam) ?? teamsData[0];
  const awayTeam = teamsData.find((team) => team.key === matchPrediction.awayTeam) ?? teamsData[1];
  const dataModeLabel = dataMode === "api" ? "真实模型" : "演示动态";
  const championBoard = [...teamsData].sort((left, right) => right.tournament.champion - left.tournament.champion);
  const modelSummary = matchPrediction.modelMeta
    ? `${matchPrediction.modelMeta.simulationCount.toLocaleString("zh-CN")} 次模拟 · 已锁定 ${matchPrediction.modelMeta.lockedResults} 场赛果 · 事件 ${matchPrediction.modelMeta.events?.applied ?? 0} 入模 / ${matchPrediction.modelMeta.events?.ignored ?? 0} 忽略`
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

    loadPrediction();
    const timer = window.setInterval(() => {
      setForecastTick((value) => value + 1);
      loadPrediction();
    }, FORECAST_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  function toggleLayoutLock() {
    setLayoutUnlocked((value) => !value);
  }

  function handleTouchToggle() {
    const now = Date.now();
    if (now - lastTapRef.current < 320) {
      toggleLayoutLock();
    }
    lastTapRef.current = now;
  }

  function startDrag(key: string, event: PointerEvent<HTMLElement>) {
    if (!layoutUnlocked) return;
    const current = positions[key] ?? { x: 0, y: 0 };
    dragRef.current = {
      key,
      startX: event.clientX,
      startY: event.clientY,
      baseX: current.x,
      baseY: current.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDrag(event: PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    setPositions((current) => ({
      ...current,
      [drag.key]: {
        x: drag.baseX + event.clientX - drag.startX,
        y: drag.baseY + event.clientY - drag.startY,
      },
    }));
  }

  function endDrag(event: PointerEvent<HTMLElement>) {
    if (dragRef.current) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
  }

  return (
    <main className="console-shell" onDoubleClick={toggleLayoutLock} onTouchEnd={handleTouchToggle}>
      <div className="ambient-grid" />
      <header className="topbar">
        <div className="brand">
          <span className="signal-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>世界杯预测终端</span>
        </div>
        <button className="menu-button" aria-label="打开菜单">
          <span />
          <span />
          <span />
        </button>
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
            <b>预测更新 {formatUpdateTime(matchPrediction.updatedAt)}</b>
          </div>
        </div>
        <MiniPitch side="right" />
      </section>

      <div className="module-grid">
        <DraggablePanel
          id="match"
          className="wide"
          title="赛前胜平负概率"
          position={positions.match}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
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
            <span className="chevron">›</span>
          </div>
          <div className="analysis-list">
            {matchPrediction.analysis.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </DraggablePanel>

        <DraggablePanel
          id="scores"
          title="最可能比分"
          position={positions.scores}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="score-outcome-list">
            {matchPrediction.scoreOutcomes.map((outcome) => (
              <article className={`score-outcome ${outcome.tone}`} key={outcome.score}>
                <strong>{outcome.score}</strong>
                <div>
                  <b>{outcome.probability.toFixed(1)}%</b>
                  <span>{outcome.note}</span>
                </div>
              </article>
            ))}
          </div>
        </DraggablePanel>

        <DraggablePanel
          id="teams"
          title="选择球队"
          position={positions.teams}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="team-list">
            {teamsData.map((team) => (
              <button
                className={`team-row ${selectedTeam === team.key ? "selected" : ""}`}
                key={team.key}
                onClick={() => setSelectedTeam(team.key)}
              >
                <TeamFlag team={team.key} code={team.code} />
                <span>{team.name}</span>
                <span className="star">{selectedTeam === team.key ? "★" : "☆"}</span>
              </button>
            ))}
          </div>
        </DraggablePanel>

        <DraggablePanel
          id="impact"
          className="wide"
          title="整届概率传导"
          position={positions.impact}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <ScenarioImpactList scenarios={matchPrediction.scenarioImpacts} />
        </DraggablePanel>

        <DraggablePanel
          id="champion"
          title="冠军概率榜"
          position={positions.champion}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <ChampionBoard teams={championBoard} />
        </DraggablePanel>

        <DraggablePanel
          id="news"
          title="新闻影响"
          position={positions.news}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="news-list">
            {matchPrediction.newsItems.map((item) => (
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
        </DraggablePanel>

        <DraggablePanel
          id="sources"
          title="来源权重"
          position={positions.sources}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="source-list">
            {sourceWeights.map((source) => (
              <div className={`source-row ${source.tone}`} key={source.level}>
                <span className="source-level">{source.level}</span>
                <strong>{source.value}</strong>
                <SegmentBar value={Number(source.value) * 100} tone={source.tone} />
                <span>{source.label}</span>
              </div>
            ))}
          </div>
        </DraggablePanel>

        <DraggablePanel
          id="layers"
          className="wide"
          title="三层模型"
          position={positions.layers}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="layer-grid">
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
        </DraggablePanel>

        <DraggablePanel
          id="factors"
          className="wide"
          title={`五大盘面 · ${selected.name}`}
          position={positions.factors}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="factor-grid">
            {factorRows.map((factor) => (
              <FactorBar
                key={factor.key}
                label={factor.label}
                value={selected.factors[factor.key] ?? 0}
                impact={plateImpact(selected.key, factor.key, matchPrediction.modelMeta?.factorImpacts)}
                tone={factor.tone}
              />
            ))}
          </div>
        </DraggablePanel>

        <DraggablePanel
          id="weights"
          className="wide"
          title="预测权重因子"
          position={positions.weights}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="weight-grid">
            {weightFactors.map((factor) => (
              <article className="weight-card" key={factor.label}>
                <div>
                  <strong>{factor.label}</strong>
                  <span>{factor.note}</span>
                </div>
                <b>{factor.value}</b>
                <SegmentBar value={factor.value * 4} tone={factor.value >= 12 ? "green" : factor.value >= 6 ? "gold" : "orange"} />
              </article>
            ))}
          </div>
        </DraggablePanel>
      </div>

      <button className={`move-hint ${layoutUnlocked ? "active" : ""}`} onClick={toggleLayoutLock}>
        <span>⌖</span>
        {layoutUnlocked ? "模块已解锁" : "双击移动模块"}
      </button>
    </main>
  );
}

function DraggablePanel({
  id,
  title,
  className = "",
  position,
  layoutUnlocked,
  children,
  onPointerDown,
  onPointerMove,
  onPointerUp,
}: {
  id: string;
  title: string;
  className?: string;
  position?: { x: number; y: number };
  layoutUnlocked: boolean;
  children: React.ReactNode;
  onPointerDown: (key: string, event: PointerEvent<HTMLElement>) => void;
  onPointerMove: (event: PointerEvent<HTMLElement>) => void;
  onPointerUp: (event: PointerEvent<HTMLElement>) => void;
}) {
  const style = {
    transform: position ? `translate(${position.x}px, ${position.y}px)` : undefined,
    cursor: layoutUnlocked ? "grab" : undefined,
  } satisfies CSSProperties;

  return (
    <section
      className={`console-panel ${className}`}
      style={style}
      onPointerDown={(event) => onPointerDown(id, event)}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <h2>{title}</h2>
      {children}
    </section>
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

function FactorBar({ label, value, impact, tone }: { label: string; value: number; impact: number; tone: string }) {
  return (
    <div className="factor-row">
      <span className={`factor-icon ${tone}`} />
      <strong>{label}</strong>
      <div className="bar-track">
        <i className={tone} style={{ width: `${value}%` }} />
      </div>
      <b>{value}</b>
      <em className={impact > 0 ? "green" : impact < 0 ? "red" : "muted"}>{formatSignedNumber(impact)}</em>
    </div>
  );
}

export default App;
