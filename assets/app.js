// 讀心猜拳 AI — 瀏覽器端
// 1. 打開 Mac 鏡頭  2. 把畫面傳給 UNO Q 辨識  3. 顯示遊戲結果
import { FilesetResolver, HandLandmarker } from './libs/mediapipe/vision_bundle.mjs';

const socket = io({ transports: ['websocket', 'polling'] });

const $ = (id) => document.getElementById(id);
const EMOJI = { rock: '✊', paper: '🖐', scissors: '✌️' };
const NAME = { rock: '石頭', paper: '布', scissors: '剪刀' };
const METHOD = { 'markov-2': '二階馬可夫', 'markov-1': '一階馬可夫', frequency: '出拳頻率', random: '隨機（還在學）' };

const video = $('video');
const overlay = $('overlay');
const octx = overlay.getContext('2d');

let connected = false;
let cameraOn = false;

// ---------------------------------------------------------------- 連線
socket.on('connect', () => { connected = true; if (cameraOn) setStatus('已就緒：按空白鍵開始', 'ok'); });
socket.on('disconnect', () => { connected = false; setStatus('與 UNO Q 斷線，重新連線中…', 'bad'); });
socket.on('status', (s) => { if (cameraOn) setStatus('已就緒：按空白鍵開始', 'ok'); });

function setStatus(text, cls) {
  const el = $('status');
  el.textContent = text;
  el.className = 'status ' + (cls || '');
}

// ---------------------------------------------------------------- 鏡頭 → 手部關節 → UNO Q
let landmarker = null;
let lastSent = 0;
let inflight = false;

async function startCamera() {
  try {
    setStatus('載入手部偵測模型…');
    const vision = await FilesetResolver.forVisionTasks(new URL('libs/mediapipe/wasm', location.href).href);
    const opts = (delegate) => ({
      baseOptions: { modelAssetPath: 'models/hand_landmarker.task', delegate },
      runningMode: 'VIDEO',
      numHands: 1,
    });
    try {
      landmarker = await HandLandmarker.createFromOptions(vision, opts('GPU'));
    } catch (e) {
      landmarker = await HandLandmarker.createFromOptions(vision, opts('CPU'));
    }
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    video.srcObject = stream;
    await video.play();
    cameraOn = true;
    setStatus(connected ? '已就緒：按空白鍵開始' : '連線 UNO Q 中…', connected ? 'ok' : '');
    requestAnimationFrame(detectLoop);
  } catch (e) {
    console.error(e);
    setStatus('無法開啟鏡頭或模型（' + (e.name || e) + '），可以先用按鈕出拳', 'bad');
  }
}

function detectLoop() {
  if (!cameraOn) return;
  if (video.readyState >= 2) {
    const t0 = performance.now();
    const res = landmarker.detectForVideo(video, t0);
    const ms = Math.round(performance.now() - t0);
    const pts = res.landmarks && res.landmarks.length ? res.landmarks[0].map((p) => [+p.x.toFixed(4), +p.y.toFixed(4)]) : [];
    drawHand(pts);
    $('live-ms').textContent = `瀏覽器偵測 ${ms} ms`;
    // 每 80ms 把關節座標傳給 UNO Q 判斷（不是傳整張畫面，資料量小很多）
    if (connected && !inflight && t0 - lastSent > 80) {
      lastSent = t0;
      inflight = true;
      socket.emit('landmarks', { landmarks: pts, aspect: video.videoWidth / video.videoHeight || 4 / 3 });
      setTimeout(() => { inflight = false; }, 1000);
    }
  }
  requestAnimationFrame(detectLoop);
}

socket.on('landmarks_response', (r) => {
  inflight = false;
  $('live-gesture').textContent = r.move ? `${EMOJI[r.move]} ${NAME[r.move]}`
    : (Object.keys(r.fingers || {}).length ? '不是猜拳手勢' : '沒看到手');
  $('board-us').textContent = `UNO Q 判斷 ${r.us} µs`;
});

// 手部 21 個關節的連線
const LINKS = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],
  [9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];

function drawHand(pts) {
  overlay.width = overlay.clientWidth; overlay.height = overlay.clientHeight;
  octx.clearRect(0, 0, overlay.width, overlay.height);
  if (!pts.length) return;
  const W = overlay.width, H = overlay.height;
  octx.strokeStyle = '#3fb950'; octx.lineWidth = 3;
  for (const [a, b] of LINKS) {
    octx.beginPath();
    octx.moveTo(pts[a][0] * W, pts[a][1] * H);
    octx.lineTo(pts[b][0] * W, pts[b][1] * H);
    octx.stroke();
  }
  octx.fillStyle = '#ffffff';
  for (const [x, y] of pts) { octx.beginPath(); octx.arc(x * W, y * H, 4, 0, Math.PI * 2); octx.fill(); }
}

// ---------------------------------------------------------------- 遊戲
$('start').onclick = startRound;
$('reset').onclick = () => socket.emit('reset', {});
document.addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); startRound(); }
  const keyMove = { Digit1: 'rock', Digit2: 'scissors', Digit3: 'paper' }[e.code];
  if (keyMove) socket.emit('manual_move', { move: keyMove });
});
document.querySelectorAll('[data-move]').forEach((b) => {
  b.onclick = () => socket.emit('manual_move', { move: b.dataset.move });
});

function startRound() {
  if ($('start').disabled) return;
  socket.emit('start_round', {});
}

socket.on('round_start', () => {
  $('start').disabled = true;
  $('result').textContent = '';
  $('ai-move').textContent = '🔒';
  $('ai-move').title = 'UNO Q 已經決定好要出什麼了';
});

socket.on('countdown', ({ n }) => { $('countdown').textContent = n; });

socket.on('round_result', (r) => {
  $('start').disabled = false;
  setTimeout(() => { $('countdown').textContent = ''; }, 400);
  if (r.error) { $('result').textContent = r.error; $('ai-move').textContent = '🤖'; return; }

  $('ai-move').textContent = EMOJI[r.ai];
  $('result').innerHTML = `${EMOJI[r.player]} vs ${EMOJI[r.ai]}<br>` +
    ({ player: '🎉 你贏了！', ai: '😈 UNO Q 贏了！', draw: '🤝 平手' }[r.winner]);
  $('pred').textContent = r.predicted ? `${EMOJI[r.predicted]} ${NAME[r.predicted]} ${r.hit ? '✅ 猜中' : '❌'}` : '（還在觀察你）';
  $('prob').textContent = r.predicted ? Math.round(r.prob * 100) + '%' : '—';
  $('method').textContent = METHOD[r.method] || r.method;
  updateScore(r.score);
  renderHistory(r.rounds || []);
  $('ai-rate').textContent = Math.round(r.ai_win_rate * 100) + '%';
});

socket.on('reset_done', (r) => {
  updateScore(r.score);
  renderHistory(r.rounds || []);
  $('result').textContent = '';
  $('ai-move').textContent = '🤖';
  ['pred', 'prob', 'method', 'hit-rate', 'ai-rate'].forEach((id) => { $(id).textContent = '—'; });
});

function updateScore(s) {
  $('s-player').textContent = s.player;
  $('s-ai').textContent = s.ai;
  $('s-draw').textContent = s.draw;
}

function renderHistory(rounds) {
  $('history').innerHTML = rounds.map((r, i) =>
    `<div class="round ${r.winner}">#${i + 1} ${EMOJI[r.player]} vs ${EMOJI[r.ai]}${r.hit ? ' 🎯' : ''}</div>`).join('');
  const guessed = rounds.filter((r) => r.predicted);
  if (guessed.length) {
    const hits = guessed.filter((r) => r.hit).length;
    $('hit-rate').textContent = `${Math.round((hits / guessed.length) * 100)}%（${hits}/${guessed.length}）`;
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

startCamera();
