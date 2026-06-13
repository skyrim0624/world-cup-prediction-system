import { CSSProperties, PointerEvent, useEffect, useMemo, useRef, useState } from "react";

type TeamKey = "brazil" | "argentina" | "spain" | "france";
type Tone = "green" | "blue" | "gold" | "orange" | "red" | "muted";

type Team = {
  key: TeamKey;
  name: string;
  code: string;
  score?: number;
  favorite?: boolean;
  factors: Record<string, number>;
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

type LivePrediction = {
  scoreHome: number;
  scoreAway: number;
  minute: string;
  addedTime: number;
  homeWin: number;
  draw: number;
  awayWin: number;
  updatedAt: string;
  newsItems: NewsItem[];
};

const teams: Team[] = [
  {
    key: "brazil",
    name: "巴西",
    code: "BRA",
    score: 4,
    favorite: true,
    factors: { overall: 88, attack: 90, defense: 82, goalkeeper: 85, path: 76, squad: 84 },
  },
  {
    key: "argentina",
    name: "阿根廷",
    code: "ARG",
    score: 3,
    factors: { overall: 86, attack: 87, defense: 81, goalkeeper: 83, path: 72, squad: 82 },
  },
  {
    key: "spain",
    name: "西班牙",
    code: "ESP",
    factors: { overall: 91, attack: 88, defense: 86, goalkeeper: 84, path: 79, squad: 87 },
  },
  {
    key: "france",
    name: "法国",
    code: "FRA",
    factors: { overall: 90, attack: 89, defense: 87, goalkeeper: 86, path: 74, squad: 89 },
  },
];

const factorRows = [
  { key: "overall", label: "综合", value: 88, tone: "green" },
  { key: "attack", label: "进攻", value: 90, tone: "green" },
  { key: "defense", label: "防守", value: 82, tone: "green" },
  { key: "goalkeeper", label: "门将", value: 85, tone: "blue" },
  { key: "path", label: "路径", value: 76, tone: "gold" },
  { key: "squad", label: "阵容", value: 84, tone: "green" },
];

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
  { label: "市场舆论", value: 2, note: "赔率热度 / 媒体偏差" },
];

const modelLayers = [
  {
    layer: "一层模型",
    title: "底层概率引擎",
    points: ["Elo 实力评分", "Dixon-Coles 单场比分", "50,000 次蒙特卡洛"],
    metric: "基础概率",
  },
  {
    layer: "二层模型",
    title: "事件与新闻修正",
    points: ["赛果锁定", "伤病停赛", "来源权威等级"],
    metric: "短期修正",
  },
  {
    layer: "三层模型",
    title: "产品解释盘面",
    points: ["实力盘", "状态盘", "路径盘", "人员盘 / 边际盘"],
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

const fallbackNewsItems: NewsItem[] = [
  { title: "官方伤病", detail: "核心球员腿筋存疑", impact: "高影响", tone: "red", time: "1 小时前" },
  { title: "训练消息", detail: "球队今日进行轻量训练", impact: "中影响", tone: "gold", time: "3 小时前" },
  { title: "传闻忽略", detail: "转会传闻，与比赛无关", impact: "已忽略", tone: "muted", time: "5 小时前" },
];

function buildFallbackPrediction(tick: number): LivePrediction {
  const homeDrift = [0, 1, -1, 2, 0, -2][tick % 6];
  const drawDrift = [0, -1, 1, -1, 0, 1][tick % 6];
  const homeWin = 58 + homeDrift;
  const draw = 15 + drawDrift;
  const awayWin = 100 - homeWin - draw;

  return {
    scoreHome: 4,
    scoreAway: 3,
    minute: "90:00",
    addedTime: 6 + (tick % 2),
    homeWin,
    draw,
    awayWin,
    updatedAt: new Date().toISOString(),
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

function App() {
  const [selectedTeam, setSelectedTeam] = useState<TeamKey>("brazil");
  const [layoutUnlocked, setLayoutUnlocked] = useState(false);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [liveTick, setLiveTick] = useState(0);
  const [apiPrediction, setApiPrediction] = useState<LivePrediction | null>(null);
  const [dataMode, setDataMode] = useState<"api" | "demo">("demo");
  const dragRef = useRef<DragState | null>(null);
  const lastTapRef = useRef(0);

  const selected = useMemo(() => teams.find((team) => team.key === selectedTeam) ?? teams[0], [selectedTeam]);
  const fallbackPrediction = useMemo(() => buildFallbackPrediction(liveTick), [liveTick]);
  const livePrediction = apiPrediction ?? fallbackPrediction;
  const dataModeLabel = dataMode === "api" ? "真实接口" : "演示动态";

  useEffect(() => {
    let active = true;

    async function loadPrediction() {
      try {
        const response = await fetch("/api/live-prediction", { cache: "no-store" });
        if (!response.ok) throw new Error(`预测接口返回 ${response.status}`);
        const data = (await response.json()) as LivePrediction;
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
      setLiveTick((value) => value + 1);
      loadPrediction();
    }, 5000);

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

      <section className="scoreboard" aria-label="比赛记分牌">
        <MiniPitch side="left" />
        <div className="score-strip">
          <div className="score-team home-team">
            <TeamFlag team="brazil" />
            <span className="team-code">BRA</span>
          </div>
          <strong className="score-value">{livePrediction.scoreHome}</strong>
          <span className="score-separator">-</span>
          <strong className="score-value">{livePrediction.scoreAway}</strong>
          <div className="score-team away-team">
            <span className="team-code">ARG</span>
            <TeamFlag team="argentina" />
          </div>
          <div className="match-clock">
            <span>{livePrediction.minute}</span>
            <em>+{livePrediction.addedTime}</em>
          </div>
        </div>
        <MiniPitch side="right" />
      </section>

      <div className="module-grid">
        <DraggablePanel
          id="win"
          className="wide"
          title="实时胜平负概率"
          position={positions.win}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="probability-row">
            <Probability label="主胜" value={livePrediction.homeWin} tone="green" />
            <Probability label="平局" value={livePrediction.draw} tone="gold" />
            <Probability label="客胜" value={livePrediction.awayWin} tone="blue" />
          </div>
          <div className="engine-line">
            <span className="ai-badge">AI</span>
            <span className="engine-copy">
              <strong>Elo + Dixon-Coles + 蒙特卡洛</strong>
              <small>
                数据源：{dataModeLabel} · 更新 {formatUpdateTime(livePrediction.updatedAt)}
              </small>
            </span>
            <span className="chevron">›</span>
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
            {teams.map((team) => (
              <button
                className={`team-row ${selectedTeam === team.key ? "selected" : ""}`}
                key={team.key}
                onClick={() => setSelectedTeam(team.key)}
              >
                <TeamFlag team={team.key} />
                <span>{team.name}</span>
                <span className="star">{selectedTeam === team.key ? "★" : "☆"}</span>
              </button>
            ))}
          </div>
        </DraggablePanel>

        <DraggablePanel
          id="path"
          className="wide"
          title="晋级路径模拟"
          position={positions.path}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <PathSimulation />
        </DraggablePanel>

        <DraggablePanel
          id="news"
          title="新闻风险"
          position={positions.news}
          layoutUnlocked={layoutUnlocked}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
        >
          <div className="news-list">
            {livePrediction.newsItems.map((item) => (
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
          title={`模型因子 · ${selected.name}`}
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
                value={selected.factors[factor.key] ?? factor.value}
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

function TeamFlag({ team }: { team: TeamKey }) {
  return <span className={`flag flag-${team}`} aria-hidden="true" />;
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

function PathSimulation() {
  const columns = [
    ["小组赛", "▣▣▢▣", "▣▢▣▣", "▣▣▣▢", "▣▢▢▣"],
    ["16 强", "▣▣▨▣", "▣▨▣▢", "▣▣▨▣"],
    ["8 强", "▣▨▣▥", "▣▣▥▢"],
    ["半决赛", "▥▣▨▥"],
    ["决赛", "🏆"],
  ];

  return (
    <div className="path-preview">
      {columns.map((column) => (
        <div className="path-column" key={column[0]}>
          <span>{column[0]}</span>
          {column.slice(1).map((node, index) => (
            <b key={`${node}-${index}`}>{node}</b>
          ))}
        </div>
      ))}
      <div className="path-legend">
        <span className="legend-green">高机会</span>
        <span className="legend-gold">中机会</span>
        <span className="legend-orange">低机会</span>
        <span className="legend-red">极低</span>
        <span className="legend-gray">淘汰</span>
      </div>
    </div>
  );
}

function FactorBar({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="factor-row">
      <span className={`factor-icon ${tone}`} />
      <strong>{label}</strong>
      <div className="bar-track">
        <i className={tone} style={{ width: `${value}%` }} />
      </div>
      <b>{value}</b>
    </div>
  );
}

export default App;
