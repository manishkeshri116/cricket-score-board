let lastEvent = "";
let lastSpokenCommentary = "";
let audioReady = false;
let audioCtx = null;
let musicTimer = null;
let backgroundMusic = null;
let backgroundMusicStarted = false;
let crowdMusic = null;
let crowdMusicStarted = false;
let crowdMusicBaseVolume = 0.78;
let hindiCommentaryStream = null;
let hindiCommentaryStreamStarted = false;
let audienceTimer = null;
let audienceNoise = null;
let audienceGain = null;
let audienceChantTimer = null;
let audienceChantGain = null;
let crowdDuckTimer = null;
let crowdSyntheticBaseGain = 0.12;
let showSquadShowcase = false;
let showcaseMode = "squad";
let engagementVariant = 0;
let lastEngagementOver = 0;
let engagementTimer = null;
let latestScoreData = null;
let hindiVoice = null;
let lastMomentKey = "";
const announcedMilestones = new Set();

const ENGAGEMENT_SHOWCASE_DURATION = 35 * 1000;

const imageCache = new Map();
const realFallbackImages = {
  player: [
    "http://127.0.0.1:5001/player-placeholder/Player.svg"
  ],
  team: [
    "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?auto=format&fit=crop&w=220&q=80",
    "https://images.unsplash.com/photo-1512719994953-eabf50895df7?auto=format&fit=crop&w=220&q=80"
  ]
};

const teamThemes = [
  { keys: ["royal challengers bengaluru", "royal challengers bangalore", "rcb", "k"], primary: "#d71920", secondary: "#1b1313", accent: "#f4c430", score: "#ffe66d" },
  { keys: ["sunrisers hyderabad", "srh", "l"], primary: "#f26522", secondary: "#251408", accent: "#ffcc33", score: "#ffdd6e" },
  { keys: ["rajasthan royals", "rr", "m"], primary: "#ea1a85", secondary: "#1b1a44", accent: "#40c4ff", score: "#f8b5d9" },
  { keys: ["chennai super kings", "csk"], primary: "#f9cd05", secondary: "#133c8b", accent: "#00a0df", score: "#fff27a" },
  { keys: ["mumbai indians", "mi"], primary: "#005da0", secondary: "#061a33", accent: "#d1ab3e", score: "#7fd3ff" },
  { keys: ["delhi capitals", "dc", "h"], primary: "#ef1b2d", secondary: "#08285c", accent: "#4aa3ff", score: "#8fd0ff" },
  { keys: ["kolkata knight riders", "kkr"], primary: "#3a225d", secondary: "#130a24", accent: "#d4af37", score: "#f6d56b" },
  { keys: ["punjab kings", "pbks"], primary: "#d71920", secondary: "#2b1214", accent: "#cfd8dc", score: "#ff8a8a" },
  { keys: ["lucknow super giants", "lsg"], primary: "#00a7e1", secondary: "#082f49", accent: "#f28c28", score: "#94e7ff" },
  { keys: ["gujarat titans", "gt"], primary: "#1c3144", secondary: "#071420", accent: "#d8b46a", score: "#d8f3ff" }
];

function normalizeTeamText(value = "") {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function themeForTeam(name = "", fkey = "") {
  const normalizedName = normalizeTeamText(name);
  const normalizedFkey = normalizeTeamText(fkey);
  const nameTokens = normalizedName.split(" ").filter(Boolean);
  const matchesLongName = theme => theme.keys.some(key => {
    const normalizedKey = normalizeTeamText(key);
    return normalizedKey.length > 3 && normalizedName.includes(normalizedKey);
  });
  const matchesKey = theme => theme.keys.some(key => {
    const normalizedKey = normalizeTeamText(key);
    if (!normalizedKey) return false;

    if (normalizedKey.length <= 3) {
      return normalizedFkey === normalizedKey || nameTokens.includes(normalizedKey);
    }

    return normalizedName.includes(normalizedKey) || normalizedFkey === normalizedKey;
  });

  return teamThemes.find(matchesLongName) || teamThemes.find(matchesKey) || {
    primary: "#f4a020",
    secondary: "#12343b",
    accent: "#00ffff",
    score: "#00ff78"
  };
}

function firstImageUrl(value) {
  const list = Array.isArray(value) ? value : [value];
  return list.find(src => src && /^https?:\/\//.test(src)) || "";
}

function readableTextColor(hex = "#000000") {
  const clean = String(hex || "").replace("#", "").trim();
  if (!/^[0-9a-f]{6}$/i.test(clean)) return "#050505";
  const r = parseInt(clean.slice(0, 2), 16) / 255;
  const g = parseInt(clean.slice(2, 4), 16) / 255;
  const b = parseInt(clean.slice(4, 6), 16) / 255;
  const luminance = [r, g, b].map(value => (
    value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  )).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
  return luminance > 0.48 ? "#050505" : "#ffffff";
}

function applyBattingTheme(data) {
  const box = document.getElementById("box");
  if (!box) return;

  const theme = themeForTeam(data.battingTeam || data.team1 || "", data.battingTeamFkey || data.team1Fkey || "");
  const logoUrl = firstImageUrl(data.battingTeamImgCandidates || data.battingTeamImg || data.team1ImgCandidates || data.team1Img);
  [box, document.documentElement].forEach(target => {
    target.style.setProperty("--team-primary", theme.primary);
    target.style.setProperty("--team-secondary", theme.secondary);
    target.style.setProperty("--team-accent", theme.accent);
    target.style.setProperty("--team-score", theme.score);
    target.style.setProperty("--team-glow", `${theme.primary}66`);
    target.style.setProperty("--team-on-primary", readableTextColor(theme.primary));
    target.style.setProperty("--team-on-accent", readableTextColor(theme.accent));
    target.style.setProperty("--team-logo", logoUrl ? `url("${logoUrl.replace(/"/g, '\\"')}")` : "none");
  });
}

function applyBowlingTheme(data) {
  const bowlerCard = document.querySelector(".bowler-card");
  if (!bowlerCard) return;

  const theme = themeForTeam(data.bowlingTeam || data.team2 || "", data.bowlingTeamFkey || data.team2Fkey || "");
  bowlerCard.style.setProperty("--bowler-team-primary", theme.primary);
  bowlerCard.style.setProperty("--bowler-team-secondary", theme.secondary);
  bowlerCard.style.setProperty("--bowler-team-accent", theme.accent);
  bowlerCard.style.setProperty("--bowler-team-score", theme.score);
  bowlerCard.style.setProperty("--bowler-team-glow", `${theme.primary}66`);
  bowlerCard.style.setProperty("--bowler-team-on-primary", readableTextColor(theme.primary));
  bowlerCard.style.setProperty("--bowler-team-on-accent", readableTextColor(theme.accent));
}

function pickRealFallback(name, type = "player") {
  if (type === "player") {
    return `http://127.0.0.1:5001/player-placeholder/${encodeURIComponent(name || "Player")}.svg`;
  }

  const key = `${type}:${name || "cricket"}`;
  const list = realFallbackImages[type] || realFallbackImages.player;

  if (!imageCache.has(key)) {
    let hash = 0;
    for (const ch of key) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    imageCache.set(key, list[hash % list.length]);
  }

  return imageCache.get(key);
}

function setImageWithFallback(id, url, name, type = "player") {
  const el = document.getElementById(id);
  setImageElementFallback(el, url, name, type);
}

function setImageElementFallback(el, url, name, type = "player") {
  const fallback = pickRealFallback(name, type);
  const urls = (Array.isArray(url) ? url : [url]).filter(src => src && /^https?:\/\//.test(src));
  let index = 0;

  if (!urls.length) {
    if (type === "team") {
      el.removeAttribute("src");
      el.alt = `${name || "Team"} logo not available`;
      el.style.visibility = "hidden";
      return;
    }

    el.style.visibility = "visible";
    el.src = fallback;
    return;
  }

  el.onerror = () => {
    index += 1;
    if (urls[index]) {
      el.src = urls[index];
    } else {
      el.onerror = null;
      if (type === "team") {
        el.removeAttribute("src");
        el.alt = `${name || "Team"} logo not available`;
        el.style.visibility = "hidden";
        return;
      }
      el.style.visibility = "visible";
      el.src = fallback;
    }
  };

  el.style.visibility = "visible";
  el.src = urls[index];
}

function initAudio() {
  if (audioReady) return;

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  audioCtx.resume();
  audioReady = true;
  document.getElementById("soundToggle").classList.add("enabled");
  document.getElementById("soundToggle").setAttribute("aria-pressed", "true");
  startApiBackgroundMusic();
  startCrowdMusic();
  startHindiCommentaryStream();
  startBackgroundMusic();
  startAudienceAmbience();
  loadHindiVoice();
}

function loadHindiVoice() {
  if (!("speechSynthesis" in window)) return;

  const voices = window.speechSynthesis.getVoices();
  hindiVoice = voices.find(voice => voice.lang === "hi-IN")
    || voices.find(voice => voice.lang && voice.lang.toLowerCase().startsWith("hi"))
    || voices.find(voice => /hindi|india/i.test(voice.name))
    || voices[0]
    || null;
}

if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = loadHindiVoice;
}

async function startApiBackgroundMusic() {
  if (backgroundMusicStarted) return;
  backgroundMusicStarted = true;

  try {
    const res = await fetch("http://127.0.0.1:5001/audio-config");
    const config = await res.json();

    if (!config.backgroundMusicUrl) return;

    backgroundMusic = new Audio(config.backgroundMusicUrl);
    backgroundMusic.loop = true;
    backgroundMusic.volume = config.backgroundVolume ?? 0.18;
    backgroundMusic.crossOrigin = "anonymous";

    await backgroundMusic.play();
  } catch (error) {
    console.log("BACKGROUND MUSIC ERROR:", error);
  }
}

async function startCrowdMusic() {
  if (crowdMusicStarted) return;
  crowdMusicStarted = true;

  try {
    const res = await fetch("http://127.0.0.1:5001/audio-config");
    const config = await res.json();

    if (!config.crowdMusicUrl) return;

    crowdMusic = new Audio(config.crowdMusicUrl);
    crowdMusic.loop = true;
    crowdMusicBaseVolume = config.crowdVolume ?? 0.78;
    crowdMusic.volume = crowdMusicBaseVolume;
    crowdMusic.crossOrigin = "anonymous";

    await crowdMusic.play();
  } catch (error) {
    console.log("CROWD MUSIC ERROR:", error);
  }
}

async function startHindiCommentaryStream() {
  if (hindiCommentaryStreamStarted) return;
  hindiCommentaryStreamStarted = true;

  try {
    const res = await fetch("http://127.0.0.1:5001/audio-config");
    const config = await res.json();

    if (!config.hindiCommentaryStreamUrl) return;

    hindiCommentaryStream = new Audio(config.hindiCommentaryStreamUrl);
    hindiCommentaryStream.loop = false;
    hindiCommentaryStream.volume = config.hindiCommentaryVolume ?? 0.9;
    hindiCommentaryStream.crossOrigin = "anonymous";

    await hindiCommentaryStream.play();
  } catch (error) {
    console.log("HINDI COMMENTARY STREAM ERROR:", error);
  }
}

function tone(freq, duration, delay = 0, gainValue = 0.06, type = "sine") {
  if (!audioReady || !audioCtx) return;

  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  const start = audioCtx.currentTime + delay;
  const end = start + duration;

  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(gainValue, start + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, end);

  osc.connect(gain).connect(audioCtx.destination);
  osc.start(start);
  osc.stop(end + 0.02);
}

function startBackgroundMusic() {
  if (musicTimer) return;

  const loop = () => {
    [196, 247, 294, 247].forEach((freq, i) => tone(freq, 0.18, i * 0.22, 0.006, "triangle"));
  };

  loop();
  musicTimer = setInterval(loop, 1800);
}

function startAudienceAmbience() {
  if (audienceTimer || !audioReady || !audioCtx) return;

  const bufferSize = audioCtx.sampleRate * 2;
  const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
  const data = buffer.getChannelData(0);

  for (let i = 0; i < bufferSize; i += 1) {
    data[i] = (Math.random() * 2 - 1) * 0.22;
  }

  audienceNoise = audioCtx.createBufferSource();
  const upperNoise = audioCtx.createBufferSource();
  const lowpass = audioCtx.createBiquadFilter();
  const highpass = audioCtx.createBiquadFilter();
  const upperBand = audioCtx.createBiquadFilter();
  const upperGain = audioCtx.createGain();
  const crowdMaster = audioCtx.createGain();
  const crowdCompressor = audioCtx.createDynamicsCompressor();
  audienceGain = audioCtx.createGain();
  audienceChantGain = audioCtx.createGain();

  audienceNoise.buffer = buffer;
  audienceNoise.loop = true;
  upperNoise.buffer = buffer;
  upperNoise.loop = true;
  lowpass.type = "lowpass";
  lowpass.frequency.value = 1250;
  highpass.type = "highpass";
  highpass.frequency.value = 90;
  upperBand.type = "bandpass";
  upperBand.frequency.value = 2300;
  upperBand.Q.value = 0.7;
  upperGain.gain.value = 0.052;
  crowdMaster.gain.value = 1.55;
  crowdCompressor.threshold.value = -24;
  crowdCompressor.knee.value = 18;
  crowdCompressor.ratio.value = 4;
  crowdCompressor.attack.value = 0.01;
  crowdCompressor.release.value = 0.24;
  audienceGain.gain.value = crowdSyntheticBaseGain;
  audienceChantGain.gain.value = 0.0001;

  audienceNoise
    .connect(highpass)
    .connect(lowpass)
    .connect(audienceGain)
    .connect(crowdMaster);
  upperNoise
    .connect(upperBand)
    .connect(upperGain)
    .connect(crowdMaster);
  crowdMaster
    .connect(crowdCompressor)
    .connect(audioCtx.destination);

  [164, 196, 246].forEach((freq, index) => {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sawtooth";
    osc.frequency.value = freq;
    gain.gain.value = index === 0 ? 0.015 : 0.009;
    osc.connect(gain).connect(audienceChantGain).connect(crowdMaster);
    osc.start();
  });

  audienceNoise.start();
  upperNoise.start();

  audienceTimer = setInterval(() => {
    if (!audienceGain || !audioCtx) return;
    const now = audioCtx.currentTime;
    const next = 0.095 + Math.random() * 0.07;
    audienceGain.gain.cancelScheduledValues(now);
    audienceGain.gain.setValueAtTime(audienceGain.gain.value, now);
    audienceGain.gain.linearRampToValueAtTime(next, now + 0.8);
  }, 900);

  audienceChantTimer = setInterval(() => {
    if (!audienceChantGain || !audioCtx) return;
    const now = audioCtx.currentTime;
    audienceChantGain.gain.cancelScheduledValues(now);
    audienceChantGain.gain.setValueAtTime(0.0001, now);
    audienceChantGain.gain.linearRampToValueAtTime(0.072, now + 0.45);
    audienceChantGain.gain.linearRampToValueAtTime(0.026, now + 1.4);
    audienceChantGain.gain.exponentialRampToValueAtTime(0.0001, now + 2.6);
  }, 5200 + Math.random() * 1800);
}

function setMediaVolume(audio, target, duration = 260) {
  if (!audio) return;
  const start = audio.volume;
  const startTime = performance.now();
  const tick = now => {
    const progress = Math.min(1, (now - startTime) / duration);
    audio.volume = start + (target - start) * progress;
    if (progress < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function duckCrowdForCommentary(duration = 3600) {
  if (crowdDuckTimer) clearTimeout(crowdDuckTimer);
  setMediaVolume(crowdMusic, Math.min(0.18, crowdMusicBaseVolume * 0.24), 220);
  setMediaVolume(backgroundMusic, 0.04, 220);

  if (audienceGain && audioCtx) {
    const now = audioCtx.currentTime;
    audienceGain.gain.cancelScheduledValues(now);
    audienceGain.gain.setValueAtTime(audienceGain.gain.value, now);
    audienceGain.gain.linearRampToValueAtTime(0.024, now + 0.18);
  }
  if (audienceChantGain && audioCtx) {
    const now = audioCtx.currentTime;
    audienceChantGain.gain.cancelScheduledValues(now);
    audienceChantGain.gain.setValueAtTime(Math.min(audienceChantGain.gain.value, 0.006), now);
  }

  crowdDuckTimer = setTimeout(() => {
    setMediaVolume(crowdMusic, crowdMusicBaseVolume, 650);
    setMediaVolume(backgroundMusic, 0.18, 650);
    if (audienceGain && audioCtx) {
      const now = audioCtx.currentTime;
      audienceGain.gain.cancelScheduledValues(now);
      audienceGain.gain.setValueAtTime(audienceGain.gain.value, now);
      audienceGain.gain.linearRampToValueAtTime(crowdSyntheticBaseGain, now + 0.65);
    }
  }, duration);
}

function playEventSound(eventName) {
  if (!audioReady) return;

  if (eventName === "FOUR") {
    [392, 523, 659].forEach((freq, i) => tone(freq, 0.13, i * 0.08, 0.08, "square"));
    audienceCheer(0.22, 1.4);
  } else if (eventName === "SIX") {
    [330, 494, 660, 880].forEach((freq, i) => tone(freq, 0.16, i * 0.07, 0.09, "sawtooth"));
    audienceCheer(0.34, 2.0);
  } else if (eventName === "WICKET") {
    [220, 165, 110].forEach((freq, i) => tone(freq, 0.22, i * 0.12, 0.09, "triangle"));
    audienceCheer(0.38, 2.3);
  } else if (eventName === "RUNOUT") {
    [520, 260, 520, 180].forEach((freq, i) => tone(freq, 0.12, i * 0.08, 0.085, "square"));
    audienceCheer(0.3, 1.8);
  } else if (["LBWCHECK", "RUNOUTCHECK", "DRS"].includes(eventName)) {
    [620, 620, 420].forEach((freq, i) => tone(freq, 0.1, i * 0.16, 0.075, "square"));
    audienceCheer(0.18, 1.1);
  } else if (eventName === "WIDE") {
    tone(150, 0.12, 0, 0.08, "square");
    tone(150, 0.12, 0.18, 0.08, "square");
    audienceCheer(0.14, 0.8);
  }
}

function parseScoreParts(score) {
  const match = String(score || "").match(/(\d+)\s*\/\s*(\d+)/);
  return {
    runs: match ? Number(match[1]) : 0,
    wickets: match ? Number(match[2]) : 0
  };
}

function overToBalls(over) {
  const [overs = "0", balls = "0"] = String(over || "0.0").split(".");
  return (Number(overs) || 0) * 6 + (Number(balls) || 0);
}

function completedOvers(over) {
  return Math.floor(overToBalls(over) / 6);
}

function chaseLine(data) {
  const target = Number(data.target || 0);
  if (!target) return "";

  const { runs, wickets } = parseScoreParts(data.score);
  const balls = overToBalls(data.over);
  const totalBalls = target > 0 && balls <= 120 ? 120 : 300;
  const ballsLeft = Math.max(0, totalBalls - balls);
  const runsNeeded = Math.max(0, target - runs);
  const wicketsLeft = Math.max(0, 10 - wickets);

  if (!ballsLeft) {
    if (runsNeeded <= 0) return `लक्ष्य ${target} पूरा, मैच बल्लेबाजी टीम ने जीत लिया।`;
    if (runsNeeded === 1) return `लक्ष्य ${target}, ओवर खत्म, मैच बराबरी पर।`;
    return `लक्ष्य ${target}, ओवर खत्म, ${runsNeeded - 1} रन से पीछे रह गए।`;
  }

  const rrr = (runsNeeded / ballsLeft * 6).toFixed(2);
  const pressure = runsNeeded > ballsLeft * 1.8
    ? "दबाव अब बल्लेबाजी टीम पर साफ दिख रहा है।"
    : runsNeeded <= ballsLeft
      ? "मैच अभी बल्लेबाजी टीम के नियंत्रण में है।"
      : "";

  return `लक्ष्य ${target}, ${runsNeeded} रन चाहिए ${ballsLeft} गेंदों में, ${wicketsLeft} विकेट बाकी। जरूरी रन रेट ${rrr}। ${pressure}`;
}

function chaseState(data) {
  const isChase = Boolean(Number(data.target || 0)) && !data.inningsBreak;
  const target = isChase ? Number(data.target || 0) : 0;
  const { runs, wickets } = parseScoreParts(data.score);
  const balls = overToBalls(data.over);
  const totalBalls = Number(data.inningsLimitBalls || 0) || (balls <= 120 ? 120 : 300);
  const ballsLeft = Math.max(0, totalBalls - balls);
  const runsNeeded = target ? Math.max(0, target - runs) : 0;
  const wicketsLeft = Math.max(0, 10 - wickets);
  const rrr = target && ballsLeft ? runsNeeded / ballsLeft * 6 : 0;
  const crr = Number(data.rr || 0);
  const pressure = !target
    ? "BUILDING"
    : runsNeeded <= 0
      ? "CHASED"
      : rrr >= 13 || runsNeeded > ballsLeft * 2
        ? "HIGH"
        : rrr >= 9
          ? "MEDIUM"
          : "LOW";

  return { target, runs, wickets, ballsLeft, runsNeeded, wicketsLeft, rrr, crr, pressure, isChase };
}

function targetDisplayText(data) {
  const isChase = Boolean(Number(data.target || 0)) && !data.inningsBreak;
  if (data.target && !isChase) {
    return `Target ${data.target}`;
  }
  const state = chaseState(data);
  if (!state.target) return "--";
  if (state.runsNeeded <= 0) return `Target ${state.target} | Chased`;
  if (state.ballsLeft <= 0) {
    return state.runsNeeded === 1
      ? `Target ${state.target} | Match tied`
      : `Target ${state.target} | Short by ${state.runsNeeded - 1}`;
  }
  if (overToBalls(data.over) >= 30) {
    return `Target ${state.target} | Need ${state.runsNeeded} in ${state.ballsLeft} balls | RRR ${state.rrr.toFixed(2)}`;
  }
  return String(state.target);
}

function chaseEquationText(data) {
  const state = chaseState(data);
  if (!state.target) return "";
  if (state.runsNeeded <= 0) return `${data.battingTeam || "Team"} chased it`;
  if (state.ballsLeft <= 0) {
    return state.runsNeeded === 1
      ? "Match tied"
      : `Innings over | Short by ${state.runsNeeded - 1}`;
  }
  return `Need ${state.runsNeeded} runs in ${state.ballsLeft} balls`;
}

function partnershipText(data) {
  const existing = String(data.partnership || "").trim();
  if (existing && existing !== "--") return existing;

  const batters = uniqueBatterStats(data.batsmenStats || []).slice(0, 2);
  if (!batters.length) return "0(0)";

  const runs = batters.reduce((sum, player) => sum + Number(player.runs || 0), 0);
  const balls = batters.reduce((sum, player) => sum + Number(player.balls || 0), 0);
  return `${runs}(${balls})`;
}

function parseWinPercent(value) {
  const match = String(value || "").match(/(\d+(?:\.\d+)?)\s*%/);
  if (!match) return 50;
  return Math.max(0, Math.min(100, Number(match[1])));
}

function clampPercent(value) {
  return Math.max(1, Math.min(99, Math.round(value)));
}

function frontendWinPercent(data) {
  if (data.matchResult) {
    const battingWon = data.battingTeam && String(data.matchResult).toLowerCase().includes(String(data.battingTeam).toLowerCase());
    return battingWon ? 100 : 0;
  }

  const state = chaseState(data);
  const { runs, wickets } = parseScoreParts(data.score);
  const balls = overToBalls(data.over);
  const wicketsLeft = Math.max(0, 10 - wickets);

  if (state.target) {
    if (state.runsNeeded <= 0) return 100;
    if (state.ballsLeft <= 0) return state.runsNeeded === 1 ? 50 : 0;

    const reqPerBall = state.runsNeeded / state.ballsLeft;
    const currentPerBall = balls ? runs / balls : 0;
    const rateEdge = (currentPerBall - reqPerBall) * 38;
    const wicketEdge = (wicketsLeft - 5) * 4.5;
    const ballPressure = state.ballsLeft <= 24 ? -Math.max(0, reqPerBall - 1) * 12 : 0;
    return clampPercent(50 + rateEdge + wicketEdge + ballPressure);
  }

  if (!balls) return 50;
  const totalBalls = Number(data.inningsLimitBalls || 0) || (balls <= 120 ? 120 : 300);
  const projected = runs / balls * totalBalls;
  const parScore = totalBalls <= 120 ? 175 : 285;
  const wicketPenalty = wickets * 4;
  return clampPercent(50 + (projected - parScore) * 0.22 - wicketPenalty);
}

function frontendWinText(data) {
  const percent = frontendWinPercent(data);
  const batting = data.battingTeam || "Batting";
  const bowling = data.bowlingTeam || "Bowling";
  return `${batting} ${percent}% | ${bowling} ${100 - percent}%`;
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function matchWinnerText(data) {
  if (data.winnerTeam) return String(data.winnerTeam).trim();

  const result = String(data.matchResult || "").trim();
  if (!result || /(?:match\s+tied|no\s+result|abandoned|called\s+off)/i.test(result)) return "";

  const teams = [...new Set([
    data.team1,
    data.team2,
    data.battingTeam,
    data.bowlingTeam
  ].filter(Boolean))];
  const resultLower = result.toLowerCase();
  const exactWinner = teams.find(team => {
    const pattern = new RegExp(`\\b${escapeRegExp(team)}\\b\\s+(?:won|wins|win|beat|beats|defeated|defeats)\\b`, "i");
    return pattern.test(result);
  });
  if (exactWinner) return exactWinner;

  const direct = result.match(/^(.+?)\s+(?:won|wins|win|beat|beats|defeated|defeats)\b/i);
  if (direct) return direct[1].replace(/^[^A-Za-z0-9]+/, "").trim();

  const namedWinner = teams.find(team => {
    const pattern = new RegExp(`\\b${escapeRegExp(team)}\\b`, "i");
    return pattern.test(result);
  });
  if (namedWinner) return namedWinner;

  const winChance = String(data.winChance || "");
  const chanceWinner = teams.find(team => {
    const pattern = new RegExp(`${escapeRegExp(team)}\\s+100\\s*%`, "i");
    return pattern.test(winChance);
  });
  if (chanceWinner) return chanceWinner;

  if (/match\s+closed|match\s+end|match\s+finished|innings\s+over/i.test(result)) {
    const state = chaseState(data);
    if (state.target && state.runsNeeded <= 0) return data.battingTeam || data.team2 || "";
    if (state.target && state.ballsLeft <= 0 && state.runsNeeded > 1) return data.bowlingTeam || data.team1 || "";
  }

  const state = chaseState(data);
  if (state.target && state.runsNeeded <= 0) return data.battingTeam || data.team2 || "";
  if (state.target && state.ballsLeft <= 0 && state.runsNeeded > 1) return data.bowlingTeam || data.team1 || "";

  if (resultLower.includes("won")) return result.split(/\s+won\b/i)[0].trim();
  return "";
}

function recentBallList(data) {
  const balls = [];
  (data.recentOvers || []).slice().reverse().forEach(over => {
    (over.balls || []).forEach(ball => balls.push(ball));
  });
  (data.thisOver || []).forEach(ball => balls.push(ball));
  return balls.filter(Boolean).slice(-5);
}

function runTextHindi(lastRuns) {
  const value = String(lastRuns || "").toUpperCase();
  if (value === "0") return "डॉट बॉल";
  if (value === "1") return "एक रन";
  if (value === "2") return "दो रन";
  if (value === "3") return "तीन रन";
  if (/^\d+\+\d+$/.test(value)) return `${value.split("+").reduce((sum, part) => sum + Number(part), 0)} रन, फील्डिंग में चूक का फायदा`;
  if (/^\d+$/.test(value)) return `${value} रन`;
  return "";
}

function cleanCommentaryText(value = "") {
  return String(value)
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function shortHindiFromCommentary(data) {
  const raw = cleanCommentaryText(data.commentaryText || "");
  if (!raw) return "";

  const text = raw
    .replace(/\b(?:that's|that is|this is)\b/gi, "")
    .replace(/\b(?:what a|brilliant|excellent|superb|lovely)\b/gi, "")
    .replace(/\b(?:in the end|at the end of it|as a result)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  const lower = text.toLowerCase();
  const striker = data.lastBatter || data.striker || "बल्लेबाज";
  const bowler = data.lastBowler || (data.bowlerStats && data.bowlerStats.name) || data.bowler || "गेंदबाज";
  const scoreLine = `${data.score || ""}, ओवर ${data.over || ""}`;
  const chase = chaseLine(data);
  let line = "";

  if (/\bsix\b|maximum|over the rope|into the stands/i.test(text) || data.event === "SIX") {
    line = `छक्का! ${striker} ने बड़ा शॉट लगाया।`;
  } else if (/\bfour\b|boundary|finds the fence|to the fence/i.test(text) || data.event === "FOUR") {
    line = `चौका! ${striker} ने बाउंड्री निकाली।`;
  } else if (/wicket|bowled|caught|lbw|out\b/i.test(text) || data.event === "WICKET") {
    line = `विकेट! ${bowler} ने सफलता दिलाई। ${data.lastWicket || ""}`;
  } else if (/run\s*-?\s*out/i.test(text) || data.event === "RUNOUT") {
    line = `रन आउट! फील्डिंग ने मौका बना दिया। ${data.lastWicket || ""}`;
  } else if (/wide/i.test(text) || data.event === "WIDE") {
    line = `वाइड गेंद। ${bowler} लाइन से भटके।`;
  } else if (/no\s*ball/i.test(text) || data.event === "NOBALL") {
    line = `नो बॉल। बल्लेबाजी टीम को अतिरिक्त रन।`;
  } else if (/review|drs|third umpire|upstairs|checking|lbw check/i.test(text)) {
    line = `रिव्यू चल रहा है। ${data.reviewPlayer || striker} फैसले के इंतजार में।`;
  } else if (/\bno run\b|dot ball|defended|leaves it/i.test(lower) || String(data.lastBallRuns) === "0") {
    line = `डॉट बॉल। ${striker} ने ${bowler} को संभलकर खेला।`;
  } else {
    const runText = runTextHindi(data.lastBallRuns);
    line = runText
      ? `${runText}। ${striker} ने ${bowler} को खेला।`
      : text.split(/[.!?]/).find(Boolean) || text;
  }

  line = line.replace(/\s+/g, " ").trim();
  if (line.length > 130) line = `${line.slice(0, 127).trim()}...`;
  return `${line} स्कोर ${scoreLine}। ${chase}`.replace(/\s+/g, " ").trim();
}

function hindiCommentaryText(data) {
  const eventName = data.event || "";
  const striker = data.lastBatter || data.striker || (data.batsmenStats && data.batsmenStats[0] && data.batsmenStats[0].name) || "बल्लेबाज";
  const bowler = data.lastBowler || (data.bowlerStats && data.bowlerStats.name ? data.bowlerStats.name : (data.bowler || "गेंदबाज"));
  const scoreLine = `${data.battingTeam || data.team2 || "टीम"} ${data.score || ""}, ओवर ${data.over || ""}`;
  const lastRuns = String(data.lastBallRuns || "").toUpperCase();
  const chase = chaseLine(data);
  const commentaryLine = shortHindiFromCommentary(data);

  if (data.matchResult) return `मैच खत्म। ${data.matchResult}`;
  if (data.inningsBreak) return `पहली पारी खत्म। इनिंग्स ब्रेक। ${data.inningsBreakText || ""}`;
  if (commentaryLine) return commentaryLine;
  if (eventName === "FOUR") return `चौका! ${striker} ने गैप ढूंढा और गेंद सीधा बाउंड्री के पार। स्कोर ${scoreLine}। ${chase}`;
  if (eventName === "SIX") return `छक्का! ${striker} ने पूरी ताकत से शॉट लगाया, गेंद सीमा रेखा के बाहर। स्कोर ${scoreLine}। ${chase}`;
  if (eventName === "WICKET") return `विकेट! ${bowler} ने बड़ा झटका दिया। ${data.lastWicket || ""}। स्कोर ${scoreLine}।`;
  if (eventName === "RUNOUT") return `रन आउट! कमाल की फील्डिंग, बल्लेबाज क्रीज से बाहर। ${data.lastWicket || ""}।`;
  if (eventName === "LBWCHECK") return `एल बी डब्ल्यू चेक चल रहा है। ${data.reviewPlayer || striker} फैसले के इंतजार में। स्कोर ${scoreLine}।`;
  if (eventName === "RUNOUTCHECK") return `रन आउट चेक तीसरे अंपायर के पास। ${data.reviewPlayer || striker} क्रीज के करीब। स्कोर ${scoreLine}।`;
  if (eventName === "DRS") return `डी आर एस रिव्यू लिया गया है। ${data.reviewPlayer || striker} पर फैसला आने वाला है। स्कोर ${scoreLine}।`;
  if (eventName === "WIDE") return `वाइड गेंद। ${bowler} लाइन से भटके, बल्लेबाजी टीम को अतिरिक्त रन। स्कोर ${scoreLine}। ${chase}`;
  if (eventName === "NOBALL") return `नो बॉल! बल्लेबाजी टीम को फ्री हिट का मौका मिल सकता है। स्कोर ${scoreLine}। ${chase}`;

  const runText = runTextHindi(lastRuns);
  if (runText) {
    const dotPressure = lastRuns === "0" && data.target ? "ये गेंद दबाव बढ़ाएगी।" : "";
    return `${runText}। ${striker} ने खेला ${bowler} को। स्कोर ${scoreLine}। ${dotPressure} ${chase}`;
  }
  if (data.ticker && data.ticker !== "Match in progress...") return `${data.ticker}. स्कोर ${scoreLine}`;

  return "";
}

function speakHindiCommentary(data) {
  if (!audioReady || !("speechSynthesis" in window)) return;

  const text = hindiCommentaryText(data);
  const spokenKey = `${text}|${data.score || ""}|${data.over || ""}`;
  if (!text || spokenKey === lastSpokenCommentary) return;

  lastSpokenCommentary = spokenKey;
  window.speechSynthesis.cancel();
  duckCrowdForCommentary(Math.max(3200, Math.min(6800, text.length * 55)));

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "hi-IN";
  utterance.rate = 0.92;
  utterance.pitch = 1.0;
  utterance.volume = 1;
  utterance.onend = () => duckCrowdForCommentary(900);
  if (hindiVoice) utterance.voice = hindiVoice;

  window.speechSynthesis.speak(utterance);
}

function audienceCheer(level, duration) {
  if (!audienceGain || !audioCtx) return;

  const now = audioCtx.currentTime;
  audienceGain.gain.cancelScheduledValues(now);
  audienceGain.gain.setValueAtTime(audienceGain.gain.value, now);
  audienceGain.gain.linearRampToValueAtTime(level, now + 0.08);
    audienceGain.gain.exponentialRampToValueAtTime(0.034, now + duration);
}

function triggerEventEffect(eventName) {
  const box = document.getElementById("box");
  const overlay = document.getElementById("eventOverlay");
  const labels = {
    FOUR: "FOUR",
    SIX: "SIX",
    WICKET: "WICKET",
    RUNOUT: "RUN OUT",
    LBWCHECK: "LBW CHECK",
    RUNOUTCHECK: "RUN OUT CHECK",
    DRS: "DRS REVIEW",
    WIDE: "WIDE"
  };

  if (!labels[eventName]) return;

  box.classList.remove("event-four", "event-six", "event-wicket", "event-runout", "event-lbwcheck", "event-runoutcheck", "event-drs", "event-wide");
  overlay.className = "event-overlay";
  void box.offsetWidth;

  const eventClass = eventName.toLowerCase();
  box.classList.add(`event-${eventClass}`);
  overlay.textContent = labels[eventName];
  overlay.classList.add("show", `event-${eventClass}`);
  playEventSound(eventName);

  setTimeout(() => {
    box.classList.remove(`event-${eventClass}`);
    overlay.className = "event-overlay";
    overlay.textContent = "";
  }, 1200);
}

function showMoment(title, subtitle, tone = "") {
  const overlay = document.getElementById("momentOverlay");
  if (!overlay) return;

  overlay.className = "moment-overlay";
  overlay.innerHTML = "";

  const panel = document.createElement("div");
  panel.className = `moment-panel ${tone}`.trim();

  const titleEl = document.createElement("strong");
  titleEl.textContent = title;

  const subEl = document.createElement("span");
  subEl.textContent = subtitle || "";

  panel.append(titleEl, subEl);
  overlay.appendChild(panel);
  void overlay.offsetWidth;
  overlay.classList.add("show");

  setTimeout(() => {
    overlay.className = "moment-overlay";
    overlay.innerHTML = "";
  }, 2800);
}

function checkBroadcastMoments(data) {
  if (data.matchResult || data.inningsBreak) return;

  if (data.event === "WICKET" && data.lastWicket) {
    const key = `wicket:${data.lastWicket}`;
    if (key !== lastMomentKey) {
      lastMomentKey = key;
      showMoment("WICKET", data.lastWicket, "wicket");
    }
  }

  if (["LBWCHECK", "RUNOUTCHECK", "DRS"].includes(data.event) && (data.reviewText || data.ticker)) {
    const key = `review:${data.event}:${data.reviewText || data.ticker}`;
    if (key !== lastMomentKey) {
      lastMomentKey = key;
      showMoment(data.reviewEvent || "REVIEW", data.reviewPlayer || data.reviewText || data.ticker, "review");
    }
  }

  (data.batsmenStats || []).forEach(player => {
    [50, 100].forEach(mark => {
      if ((player.runs || 0) >= mark) {
        const key = `bat:${player.name}:${mark}`;
        if (!announcedMilestones.has(key)) {
          announcedMilestones.add(key);
          showMoment(`${mark} FOR ${String(player.name || "").toUpperCase()}`, `${player.runs} from ${player.balls} balls`, "bat");
        }
      }
    });
  });

  const partnership = partnershipText(data);
  const partnershipRuns = Number(String(partnership).match(/^(\d+)/)?.[1] || 0);
  [50, 100, 150].forEach(mark => {
    if (partnershipRuns >= mark) {
      const key = `partnership:${mark}:${data.battingTeam || ""}`;
      if (!announcedMilestones.has(key)) {
        announcedMilestones.add(key);
        showMoment(`${mark} PARTNERSHIP`, partnership, "partnership");
      }
    }
  });

  if (data.bowlerStats && (data.bowlerStats.wickets || 0) >= 5) {
    const key = `five:${data.bowlerStats.name}`;
    if (!announcedMilestones.has(key)) {
      announcedMilestones.add(key);
      showMoment("FIVE-WICKET HAUL", `${data.bowlerStats.name} ${data.bowlerStats.runs}/${data.bowlerStats.wickets}`, "wicket");
    }
  }
}

function renderPlayerList(data) {
  const list = document.getElementById("playerList");
  const players = [];
  const seen = new Set();

  const addPlayer = player => {
    const name = player.name || "";
    const key = name.toLowerCase();
    if (!name || seen.has(key)) return;
    seen.add(key);
    players.push(player);
  };

  (data.batsmenStats || []).forEach(player => {
    addPlayer({
      role: "BAT",
      name: player.name,
      line: `${player.runs} (${player.balls}) | SR ${player.sr}`,
      img: player.imgCandidates || player.img
    });
  });

  if (data.bowlerStats && data.bowlerStats.name) {
    addPlayer({
      role: "BOWL",
      name: data.bowlerStats.name,
      line: `${data.bowlerStats.overs} | ${data.bowlerStats.runs}/${data.bowlerStats.wickets}`,
      img: data.bowlerStats.imgCandidates || data.bowlerStats.img
    });
  }

  if (!players.length) {
    (data.squadPlayers || []).slice(0, 6).forEach(player => {
      addPlayer({
        role: player.role || "PLAYER",
        name: player.name,
        line: player.role || "PLAYER",
        img: player.imgCandidates || player.img
      });
    });
  }

  list.innerHTML = "";
  players.forEach((player, index) => {
    const item = document.createElement("div");
    item.className = "player-list-item";
    item.style.animationDelay = `${index * 90}ms`;

    const img = document.createElement("img");
    img.alt = player.name || "Cricket player";
    setImageElementFallback(img, player.img, player.name);

    const role = document.createElement("span");
    role.className = "player-list-role";
    role.textContent = player.role;

    const copy = document.createElement("span");
    copy.className = "player-list-copy";

    const name = document.createElement("strong");
    name.textContent = player.name || "--";

    const line = document.createElement("small");
    line.textContent = player.line || "--";

    copy.append(name, line);
    item.append(img, role, copy);
    list.appendChild(item);
  });
}

function renderSquadShowcase(data) {
  const stage = document.getElementById("playerStage");
  const cards = document.getElementById("playerCards");
  const showcase = document.getElementById("squadShowcase");
  const players = (data.squadPlayers || []).slice(0, 11);
  const shouldShow = showSquadShowcase && (showcaseMode === "engagement" || players.length > 0);

  stage.classList.toggle("show-squad", shouldShow);
  cards.setAttribute("aria-hidden", shouldShow ? "true" : "false");
  showcase.innerHTML = "";

  if (shouldShow && showcaseMode === "engagement") {
    renderEngagementShowcase(showcase, data);
    return;
  }

  if (!players.length) return;

  const title = document.createElement("div");
  title.className = "squad-title";
  title.textContent = `${data.team2 || "Team"} Player Showcase`;
  showcase.appendChild(title);

  const grid = document.createElement("div");
  grid.className = "squad-grid";

  players.forEach((player, index) => {
    const item = document.createElement("div");
    item.className = "squad-player";
    item.style.animationDelay = `${index * 80}ms`;

    const img = document.createElement("img");
    img.alt = player.name || "Player";
    setImageElementFallback(img, player.imgCandidates || player.img, player.name);

    const name = document.createElement("strong");
    name.textContent = player.name || "--";

    const role = document.createElement("span");
    role.textContent = player.role || "PLAYER";

    item.append(img, name, role);
    grid.appendChild(item);
  });

  showcase.appendChild(grid);
}

function renderEngagementShowcase(showcase, data) {
  const batters = uniqueBatterStats(data.batsmenStats || []);
  const striker = batters.find(player => player.isStriker) || batters[0] || {};
  const support = batters.find(player => player.name && player.name !== striker.name) || batters[1] || {};
  const bowler = data.bowlerStats || {};
  const recent = data.recentOvers && data.recentOvers[0];
  const chase = chaseLine(data);
  const activeNames = [striker.name, support.name, bowler.name].filter(Boolean).join("  |  ");
  const playerLine = activeNames || `${data.battingTeam || data.team2 || "LIVE"} ${data.score || "--"} (${data.over || "--"})`;
  const variants = ["pulse", "team-batting", "batter", "team-bowling", "chase", "team-all", "over", "bowler", "spotlight"];
  const variant = variants[engagementVariant % variants.length];

  const teamSquad = teamName => {
    const name = String(teamName || "").toLowerCase();
    if (name && String(data.team1 || "").toLowerCase() === name) return data.team1Squad || [];
    if (name && String(data.team2 || "").toLowerCase() === name) return data.team2Squad || [];
    return [];
  };

  const battingSquad = teamSquad(data.battingTeam);
  const bowlingSquad = teamSquad(data.bowlingTeam);
  const combinedSquad = [...battingSquad.slice(0, 6), ...bowlingSquad.slice(0, 6)];

  const panel = document.createElement("div");
  panel.className = `engagement-panel variant-${variant}`;

  const title = document.createElement("div");
  title.className = "engagement-title";
  const titles = {
    pulse: "MATCH PULSE",
    batter: "BATTER WATCH",
    chase: data.target ? "CHASE EQUATION" : "MOMENTUM CHECK",
    over: "OVER RECAP",
    bowler: "BOWLER PRESSURE",
    spotlight: "PLAYER SPOTLIGHT",
    "team-batting": `${data.battingTeam || "Batting"} XI`,
    "team-bowling": `${data.bowlingTeam || "Bowling"} XI`,
    "team-all": "PLAYING XI"
  };
  title.innerHTML = `<span>${titles[variant]}</span><strong>${playerLine}</strong>`;

  const grid = document.createElement("div");
  grid.className = "engagement-grid";

  const makeCard = (label, main, sub, tone = "") => {
    const card = document.createElement("div");
    card.className = `engagement-card ${tone}`.trim();

    const labelEl = document.createElement("span");
    labelEl.textContent = label;

    const mainEl = document.createElement("strong");
    mainEl.textContent = main || "--";

    const subEl = document.createElement("small");
    subEl.textContent = sub || "";

    card.append(labelEl, mainEl, subEl);
    return card;
  };

  const renderPlayerTiles = (players, label) => {
    grid.className = "engagement-grid player-tiles";
    const list = players.length ? players.slice(0, 12) : [
      striker && striker.name ? { ...striker, role: "BAT" } : null,
      support && support.name ? { ...support, role: "BAT" } : null,
      bowler && bowler.name ? { ...bowler, role: "BOWL" } : null
    ].filter(Boolean);

    list.forEach((player, index) => {
      const tile = document.createElement("div");
      tile.className = "engagement-player-tile";
      tile.style.animationDelay = `${index * 55}ms`;

      const img = document.createElement("img");
      img.alt = player.name || "Player";
      setImageElementFallback(img, player.imgCandidates || player.img, player.name);

      const name = document.createElement("strong");
      name.textContent = player.name || "--";

      const role = document.createElement("span");
      role.textContent = player.role || label || "PLAYER";

      tile.append(img, name, role);
      grid.appendChild(tile);
    });
  };

  if (variant === "team-batting") {
    renderPlayerTiles(battingSquad, "BAT");
  } else if (variant === "team-bowling") {
    renderPlayerTiles(bowlingSquad, "BOWL");
  } else if (variant === "team-all") {
    renderPlayerTiles(combinedSquad, "XI");
  } else if (variant === "batter") {
    grid.append(
      makeCard("ON STRIKE", striker.name, striker.name ? `${striker.runs} off ${striker.balls}` : "--", "bat"),
      makeCard("STRIKE RATE", striker.sr ? `${striker.sr}` : "--", `${striker.fours || 0} fours, ${striker.sixes || 0} sixes`, "bat"),
      makeCard("PARTNERSHIP", partnershipText(data), support.name ? `With ${support.name}` : "Building stand"),
      makeCard("NEXT STORY", support.name || "Non striker", support.name ? `${support.runs}(${support.balls})` : "--")
    );
  } else if (variant === "chase") {
    grid.append(
      makeCard("TARGET", data.target || "Set the platform", data.target ? chase : "First innings tempo"),
      makeCard("ON STRIKE", striker.name, striker.name ? `${striker.runs}(${striker.balls})  SR ${striker.sr}` : "--", "bat"),
      makeCard("NON STRIKER", support.name || "--", support.name ? `${support.runs}(${support.balls})` : "--", "bat"),
      makeCard("BOWLER", bowler.name || "--", bowler.name ? `${bowler.overs}  ${bowler.runs}/${bowler.wickets}` : "--", "bowl")
    );
  } else if (variant === "over") {
    const balls = recent && recent.balls ? recent.balls : data.thisOver || [];
    grid.append(
      makeCard("RECENT OVER", recent ? recent.label : "THIS OVER", balls.length ? balls.join("  ") : "Waiting", "bat"),
      makeCard("BATTER", data.lastBatter || striker.name || "--", data.lastBallRuns ? `Last ball ${data.lastBallRuns}` : "Waiting"),
      makeCard("BOWLER", data.lastBowler || bowler.name || "--", bowler.name ? `${bowler.overs || "--"}  ${bowler.runs ?? "--"}/${bowler.wickets ?? "--"}` : "", "bowl"),
      makeCard("PAIR", striker.name && support.name ? `${striker.name} / ${support.name}` : partnershipText(data), `P'ship ${partnershipText(data)}`)
    );
  } else if (variant === "bowler") {
    grid.append(
      makeCard("BOWLER", bowler.name || "--", bowler.overs ? `${bowler.overs} overs` : "", "bowl"),
      makeCard("FIGURES", bowler.name ? `${bowler.runs}/${bowler.wickets}` : "--", bowler.economy ? `Economy ${bowler.economy}` : "", "bowl"),
      makeCard("DISCIPLINE", `WD ${bowler.wides ?? 0}  NB ${bowler.noballs ?? 0}`, "Extras watch"),
      makeCard("MATCHUP", striker.name || "Batter", data.lastBowler ? `Facing ${data.lastBowler}` : "Next ball coming")
    );
  } else if (variant === "spotlight") {
    const players = [
      striker && striker.name ? { ...striker, kind: "bat" } : null,
      support && support.name ? { ...support, kind: "bat" } : null,
      bowler && bowler.name ? { ...bowler, kind: "bowl" } : null
    ].filter(Boolean);
    const pick = players[engagementVariant % Math.max(1, players.length)] || striker || {};
    const impactLine = pick.kind === "bowl"
      ? `${pick.runs ?? "--"}/${pick.wickets ?? "--"} in ${pick.overs || "--"}`
      : `${pick.runs ?? "--"}(${pick.balls ?? "--"})`;
    grid.append(
      makeCard("SPOTLIGHT", pick.name || "Live player", impactLine, pick.kind === "bowl" ? "bowl" : "bat"),
      makeCard("ROLE", pick.isStriker ? "On strike" : pick.kind === "bowl" ? "Bowling spell" : "Key player", ""),
      makeCard("IMPACT", pick.sr ? `SR ${pick.sr}` : pick.economy ? `Econ ${pick.economy}` : "Watch this phase"),
      makeCard("TEAM", data.battingTeam || data.team2 || "--", data.venue || "")
    );
  } else {
    grid.append(
      makeCard("ON STRIKE", striker.name, striker.name ? `${striker.runs}(${striker.balls})  SR ${striker.sr}` : "--", "bat"),
      makeCard("NON STRIKER", support.name, support.name ? `${support.runs}(${support.balls})` : "--", "bat"),
      makeCard("BOWLER", bowler.name, bowler.name ? `${bowler.overs} overs  ${bowler.runs}/${bowler.wickets}` : "--", "bowl"),
      makeCard("PARTNERSHIP", partnershipText(data), chase || frontendWinText(data) || "Match building")
    );
  }

  const overStrip = document.createElement("div");
  overStrip.className = "engagement-over";
  const balls = recent && recent.balls ? recent.balls : data.thisOver || [];
  overStrip.innerHTML = `<span>${recent ? recent.label : "THIS OVER"}</span><strong>${balls.length ? balls.join("  ") : "Waiting for next ball"}</strong>`;

  panel.append(title, grid, overStrip);
  showcase.appendChild(panel);
}

function maybeTriggerEngagementShowcase(data) {
  if (data.matchResult || data.inningsBreak) return;

  const overCount = completedOvers(data.over);
  if (!overCount || overCount % 2 !== 0 || overCount === lastEngagementOver) return;

  lastEngagementOver = overCount;
  engagementVariant += 1;
  showcaseMode = "engagement";
  showSquadShowcase = true;
  renderSquadShowcase(data);

  clearTimeout(engagementTimer);
  engagementTimer = setTimeout(() => {
    showSquadShowcase = false;
    if (latestScoreData) renderSquadShowcase(latestScoreData);
  }, ENGAGEMENT_SHOWCASE_DURATION);
}

function ballTotal(ball) {
  const value = String(ball).toUpperCase();
  if (value === "WD" || value === "NB") return 1;
  if (value === "W") return 0;

  const number = parseInt(value.replace(/\D/g, ""), 10);
  return Number.isNaN(number) ? 0 : number;
}

function decorateBall(el, ball) {
  const value = String(ball).toUpperCase();

  if (value === "4" || value === "4B") el.classList.add("four");
  if (value === "6" || value === "6B") el.classList.add("six");
  if (value === "W") el.classList.add("wicket");
  if (value === "WD" || value === "NB") el.classList.add("wide");
}

function renderOverHistory(data) {
  const container = document.getElementById("overHistory");
  const overs = data.recentOvers && data.recentOvers.length
    ? data.recentOvers
    : [{ label: "THIS OVER", balls: data.thisOver || [] }];

  container.innerHTML = "";

  overs.forEach(over => {
    const section = document.createElement("div");
    section.className = "over-section";
    if (over.current) section.classList.add("current-over");

    const label = document.createElement("span");
    label.className = "over-label";
    label.textContent = `${over.label || "OVER"}:`;

    const balls = document.createElement("div");
    balls.className = "balls";

    (over.balls || []).forEach(ball => {
      const el = document.createElement("span");
      el.className = "ball";
      el.textContent = ball;
      decorateBall(el, ball);
      balls.appendChild(el);
    });

    const total = document.createElement("span");
    total.className = "over-total";
    total.textContent = `= ${over.total ?? (over.balls || []).reduce((sum, ball) => sum + ballTotal(ball), 0)}`;

    section.append(label, balls, total);
    container.appendChild(section);
  });
}

function addTickerItem(container, label, value, tone = "") {
  if (!value) return;

  const item = document.createElement("div");
  item.className = "ticker-item";
  if (tone) item.classList.add(tone);

  const labelEl = document.createElement("span");
  labelEl.className = "ticker-label";
  labelEl.textContent = label;

  const valueEl = document.createElement("strong");
  valueEl.className = "ticker-value";
  valueEl.textContent = value;

  item.append(labelEl, valueEl);
  container.appendChild(item);
}

function renderTicker(data) {
  const ticker = document.getElementById("ticker");
  const batters = (data.batsmenStats || [])
    .map(player => `${player.name} ${player.runs}(${player.balls})`)
    .join("  |  ");
  const bowler = data.bowlerStats && data.bowlerStats.name
    ? `${data.bowlerStats.name} ${data.bowlerStats.overs}-${data.bowlerStats.runs}/${data.bowlerStats.wickets}`
    : "";
  const over = data.recentOvers && data.recentOvers[0]
    ? `${data.recentOvers[0].label}: ${(data.recentOvers[0].balls || []).join(" ")}`
    : "";
  const chaseEquation = chaseEquationText(data);

  ticker.innerHTML = "";
  const liveLabel = data.matchResult ? "RESULT" : data.inningsBreak ? "BREAK" : "LIVE";
  addTickerItem(ticker, liveLabel, data.matchResult || data.inningsBreakText || data.ticker || "Match in progress", "ticker-main");
  if (data.reviewText) addTickerItem(ticker, "REVIEW", data.reviewText);
  if (chaseEquation) addTickerItem(ticker, "CHASE", chaseEquation);
  if (over) addTickerItem(ticker, "OVER", over);
  if (data.lastWicket) addTickerItem(ticker, "LAST WICKET", data.lastWicket);
  if (!chaseEquation && !over && !data.lastWicket) {
    addTickerItem(ticker, "MATCH", `${data.battingTeam || "Batting"} ${data.score || "--"} (${data.over || "--"})`);
  }
}

function renderBroadcastStrip(data) {
  const state = chaseState(data);
  const equationEl = document.getElementById("equationText");
  const pressureCard = document.getElementById("pressureCard");
  const pressureEl = document.getElementById("pressureText");
  const winFill = document.getElementById("winFill");
  const winLeft = document.getElementById("winMeterLeft");
  const winRight = document.getElementById("winMeterRight");

  if (state.target) {
    const chaseEquation = chaseEquationText(data);
    equationEl.textContent = state.ballsLeft > 0 && state.runsNeeded > 0
      ? `${chaseEquation} | RRR ${state.rrr.toFixed(2)}`
      : chaseEquation;
  } else {
    equationEl.textContent = `CRR ${data.rr || "--"} | ${data.score || "--"} in ${data.over || "--"}`;
  }

  pressureCard.classList.remove("pressure-low", "pressure-medium", "pressure-high", "pressure-chased", "pressure-building");
  pressureCard.classList.add(`pressure-${String(state.pressure).toLowerCase()}`);
  pressureEl.textContent = state.pressure;

  const percent = frontendWinPercent(data);
  winFill.style.width = `${percent}%`;
  winLeft.textContent = data.battingTeam || "Batting";
  winRight.textContent = data.bowlingTeam || "Bowling";
}

function renderMatchEnd(data) {
  const overlay = document.getElementById("matchEndOverlay");

  if (!data.matchResult && !data.inningsBreak) {
    overlay.classList.remove("show");
    overlay.innerHTML = "";
    return;
  }

  overlay.innerHTML = "";

  const panel = document.createElement("div");
  panel.className = "match-end-panel";
  if (data.matchResult) panel.classList.add("winner-panel");

  const title = document.createElement("span");
  title.className = "match-end-title";
  title.textContent = data.matchResult ? "MATCH END" : "INNINGS BREAK";

  const result = document.createElement("strong");
  result.className = "match-end-result";
  result.textContent = data.matchResult || data.inningsBreakText || "Second innings coming up";

  const winnerName = matchWinnerText(data);
  const winner = document.createElement("span");
  winner.className = "match-end-winner";
  winner.textContent = winnerName ? `WINNER: ${winnerName}` : "";

  const score = document.createElement("span");
  score.className = "match-end-score";
  score.textContent = `${data.team || ""}  |  ${data.score || ""} (${data.over || ""})`;

  if (data.matchResult) {
    const confetti = document.createElement("div");
    confetti.className = "winner-confetti";
    for (let i = 0; i < 18; i += 1) {
      const piece = document.createElement("i");
      piece.style.setProperty("--delay", `${(i % 6) * 0.12}s`);
      piece.style.setProperty("--x", `${(i - 9) * 18}px`);
      confetti.appendChild(piece);
    }
    panel.append(confetti);
  }

  panel.append(title, result);
  if (winnerName) panel.appendChild(winner);
  panel.appendChild(score);
  overlay.appendChild(panel);
  overlay.classList.add("show");
}

function formatBatterScore(player) {
  return {
    main: `${player.runs}`,
    stats: [
      ["BALLS", player.balls],
      ["SR", player.sr],
      ["4s", player.fours ?? 0],
      ["6s", player.sixes ?? 0]
    ]
  };
}

function setRichScore(id, main, stats) {
  const el = document.getElementById(id);
  el.textContent = "";

  const mainEl = document.createElement("span");
  mainEl.className = "score-main";
  mainEl.textContent = main || "--";

  const statsEl = document.createElement("span");
  statsEl.className = "score-stats";

  (stats || []).forEach(([label, value]) => {
    const item = document.createElement("span");
    item.className = "score-stat";

    const labelEl = document.createElement("small");
    labelEl.textContent = label;

    const valueEl = document.createElement("b");
    valueEl.textContent = value ?? "--";

    item.append(labelEl, valueEl);
    statsEl.appendChild(item);
  });

  el.append(mainEl, statsEl);
}

function samePlayerName(left, right) {
  const clean = value => String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const a = clean(left);
  const b = clean(right);
  if (!a || !b) return false;
  if (a === b || a.includes(b) || b.includes(a)) return true;

  const aParts = a.split(" ");
  const bParts = b.split(" ");
  return aParts.length >= 2
    && bParts.length >= 2
    && aParts[aParts.length - 1] === bParts[bParts.length - 1]
    && aParts[0][0] === bParts[0][0];
}

function uniqueBatterStats(players) {
  const unique = [];
  (players || []).forEach(player => {
    if (!player || !player.name) return;
    if (unique.some(existing => samePlayerName(existing.name, player.name))) return;
    unique.push(player);
  });
  return unique.slice(0, 2);
}

function updateStrikerIndicator(data, b1, b2) {
  const card1 = document.getElementById("batsman1Card");
  const card2 = document.getElementById("batsman2Card");
  const badge1 = document.getElementById("batsman1StrikeState");
  const badge2 = document.getElementById("batsman2StrikeState");
  const striker = data.striker || "";
  const nonStriker = data.nonStriker || "";
  const b1Striker = Boolean((b1 && b1.isStriker) || samePlayerName(striker, b1 && b1.name));
  const b2Striker = Boolean((b2 && b2.isStriker) || samePlayerName(striker, b2 && b2.name));
  const b1NonStriker = Boolean((b1 && b1.isNonStriker) || samePlayerName(nonStriker, b1 && b1.name) || (!b1Striker && b1 && (b2Striker || !striker)));
  const b2NonStriker = Boolean((b2 && b2.isNonStriker) || samePlayerName(nonStriker, b2 && b2.name) || (!b2Striker && b2 && (b1Striker || !striker)));

  card1.classList.toggle("is-striker", b1Striker);
  card2.classList.toggle("is-striker", b2Striker);
  card1.classList.toggle("is-non-striker", b1NonStriker);
  card2.classList.toggle("is-non-striker", b2NonStriker);
  badge1.textContent = b1Striker ? "ON STRIKE" : "NON STRIKER";
  badge2.textContent = b2Striker ? "ON STRIKE" : "NON STRIKER";
}

document.getElementById("soundToggle").addEventListener("click", initAudio);

async function fetchScore() {
  try {
    const res = await fetch("http://127.0.0.1:5001/score");
    const data = await res.json();
    latestScoreData = data;
    applyBattingTheme(data);
    applyBowlingTheme(data);

    // BASIC
    document.getElementById("score").innerText = data.score || "";
    document.getElementById("overs").innerText = data.over || "";
    document.getElementById("currentOverBox").innerText = data.over || "--";
    document.getElementById("rr").innerText = data.rr || "";
    document.getElementById("winChance").innerText = frontendWinText(data);
    document.getElementById("target").innerText = targetDisplayText(data);
    document.getElementById("venueBar").innerText = data.venue || "";

    // TEAMS + LOGO
    const battingTeam = data.battingTeam || data.team1 || "";
    const bowlingTeam = data.bowlingTeam || data.team2 || "";
    document.getElementById("team1").innerText = battingTeam;
    document.getElementById("team2").innerText = bowlingTeam;

    const battingImg = data.battingTeamImgCandidates || data.battingTeamImg || data.team1ImgCandidates || data.team1Img || (data.team1Fkey ? `https://cricketvectors.akamaized.net/cricketimages/Teams/${data.team1Fkey}.png` : "");
    const bowlingImg = data.bowlingTeamImgCandidates || data.bowlingTeamImg || data.team2ImgCandidates || data.team2Img || (data.team2Fkey ? `https://cricketvectors.akamaized.net/cricketimages/Teams/${data.team2Fkey}.png` : "");
    setImageWithFallback("team1Logo", battingImg, battingTeam, "team");
    setImageWithFallback("team2Logo", bowlingImg, bowlingTeam, "team");

    // PARTNERSHIP
    document.getElementById("partnership").innerText = partnershipText(data);
    renderBroadcastStrip(data);

    // BATSMEN
    if (data.batsmenStats && data.batsmenStats.length > 0) {
      const batters = uniqueBatterStats(data.batsmenStats);
      const b1 = batters[0];
      const b2 = batters[1];

      if (b1) {
        document.getElementById("batsman1").innerText = b1.name;
        const score = formatBatterScore(b1);
        setRichScore("batsman1Score", score.main, score.stats);

        setImageWithFallback("batsman1Img", b1.imgCandidates || b1.img, b1.name);
      }

      if (b2) {
        document.getElementById("batsman2").innerText = b2.name;
        const score = formatBatterScore(b2);
        setRichScore("batsman2Score", score.main, score.stats);

        setImageWithFallback("batsman2Img", b2.imgCandidates || b2.img, b2.name);
      } else {
        document.getElementById("batsman2").innerText = "--";
        setRichScore("batsman2Score", "--", []);
      }

      updateStrikerIndicator(data, b1, b2);
    }

    // BOWLER
    if (data.bowlerStats && data.bowlerStats.name) {
      const b = data.bowlerStats;

      document.getElementById("bowler").innerText = b.name;
      setRichScore("bowlerScore", `${b.runs}/${b.wickets}`, [
        ["OVERS", b.overs],
        ["ECON", b.economy],
        ["WD", b.wides ?? 0],
        ["NB", b.noballs ?? 0]
      ]);

      setImageWithFallback("bowlerImg", b.imgCandidates || b.img, b.name);
    }

    renderPlayerList(data);
    maybeTriggerEngagementShowcase(data);
    renderSquadShowcase(data);

    renderOverHistory(data);
    renderMatchEnd(data);

    // LAST WICKET
    document.getElementById("lastWicket").innerText = data.lastWicket || "--";

    renderTicker(data);
    checkBroadcastMoments(data);

    const eventKey = `${data.event || ""}|${data.score || ""}|${data.over || ""}|${data.ticker || ""}`;
    if (data.event && eventKey !== lastEvent) {
      triggerEventEffect(data.event);
      lastEvent = eventKey;
    }
    speakHindiCommentary(data);

  } catch (e) {
    console.log("ERROR:", e);
  }
}

// AUTO REFRESH
setInterval(fetchScore, 2000);
fetchScore();
