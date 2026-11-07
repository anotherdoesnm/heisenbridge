// IRC voice widget: joins an obby `^voice` / `$stream` channel through the bridge
// and does WebRTC against the SFU the IRC server points at.

const $ = (id) => document.getElementById(id);
const logEl = $("log"), statusEl = $("status"), whoEl = $("who");
const joinBtn = $("join"), leaveBtn = $("leave"), micBtn = $("mic");
const membersEl = $("members"), audioEl = $("audio"), modeSel = $("mode");

const p = new URLSearchParams(location.search);
const ROOM_ID = p.get("roomId") || "";
const TOKEN = p.get("token") || "";

let socket = null, pc = null, localStream = null;
let channel = null, joined = false, micOn = false;
const members = new Map();

function log(...a) { logEl.textContent += a.map(String).join(" ") + "\n"; logEl.scrollTop = logEl.scrollHeight; }
function setStatus(t) { statusEl.textContent = t; }

/* ---------- members ---------- */

function renderMembers() {
  membersEl.innerHTML = "";
  for (const [nick, m] of members) {
    const li = document.createElement("li");
    li.textContent = nick + (m.mic ? " 🎤" : " 🔇") + (m.speaking ? " · говорит" : "");
    membersEl.appendChild(li);
  }
}

function applyPresence(e) {
  const nick = e.member;
  if (!nick) return;
  if (e.state === "left" || e.state === "gone") { members.delete(nick); renderMembers(); return; }
  const m = members.get(nick) || { mic: false, speaking: false };
  if (e.kind === "mic") m.mic = e.state === "on";
  else if (e.kind === "speaking") m.speaking = e.state === "speaking";
  else if (e.state === "joined") m.mic = true;
  members.set(nick, m);
  renderMembers();
}

/* ---------- signalling ---------- */

function send(env) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({ action: "signal", payload: JSON.stringify(env) }));
}

const chunkBuf = new Map();

function onEnvelope(env) {
  log("<<", env.type, env.member || "");
  if (env.type === "chunk") {
    const id = env.id;
    const acc = chunkBuf.get(id) || "";
    chunkBuf.set(id, acc + (env.sdp || ""));
    if (env.last) {
      const sdp = chunkBuf.get(id);
      chunkBuf.delete(id);
      onEnvelope({ type: env.of || "answer", sdp });
    }
    return;
  }
  if (env.type === "joined") return onJoined(env);
  if (env.type === "presence") return applyPresence(env);
  if (!pc) return;
  if (env.type === "answer") pc.setRemoteDescription({ type: "answer", sdp: env.sdp }).catch((e) => log("sdp:", e.message));
  else if (env.type === "ice" && env.candidate) pc.addIceCandidate(env.candidate).catch(() => {});
}

async function onJoined(env) {
  const turn = env.turn || {};
  const iceServers = turn.urls ? [{ urls: turn.urls, username: turn.username, credential: turn.password }] : [];
  log("turn:", (turn.urls || []).join(",") || "none", "mode:", env.mode);

  pc = new RTCPeerConnection({ iceServers });
  pc.onicecandidate = (e) => e.candidate && send({ type: "ice", candidate: e.candidate });
  pc.ontrack = (e) => { audioEl.srcObject = e.streams[0]; audioEl.play().catch(() => {}); };
  pc.onconnectionstatechange = () => {
    log("pc:", pc.connectionState);
    if (pc.connectionState === "connected") setStatus("в звонке");
  };

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    localStream.getAudioTracks().forEach((t) => { t.enabled = false; pc.addTrack(t, localStream); });
    log("микрофон получен (выключен)");
  } catch (e) {
    log("без микрофона:", e.message);
  }

  const offer = await pc.createOffer({ offerToReceiveAudio: true });
  await pc.setLocalDescription(offer);
  send({ type: "offer", sdp: offer.sdp });
  setStatus("подключаюсь к SFU…");
}

function toggleMic() {
  if (!localStream) return;
  micOn = !micOn;
  localStream.getAudioTracks().forEach((t) => (t.enabled = micOn));
  micBtn.textContent = micOn ? "Mic: on" : "Mic: off";
  micBtn.classList.toggle("on", micOn);
  send({ type: "mic", state: micOn ? "on" : "off" });
}

/* ---------- socket ---------- */

function connect() {
  const scheme = location.protocol === "https:" ? "wss://" : "ws://";
  socket = new WebSocket(scheme + location.host + "/voice/ws");
  socket.onopen = () => {
    setStatus("handshaking…");
    socket.send(JSON.stringify({ action: "handshake", room_id: ROOM_ID, token: TOKEN }));
  };
  socket.onclose = () => { setStatus("disconnected"); joined = false; update(); };
  socket.onerror = () => setStatus("socket error");
  socket.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.action === "ready") {
      channel = msg.channel;
      whoEl.textContent = `${msg.network} · ${msg.nick || "?"}`;
      setStatus("ready");
      joinBtn.disabled = false;
      return;
    }
    if (msg.action === "signal") return onEnvelope(JSON.parse(msg.payload));
    if (msg.action === "error") { log("bridge:", msg.message); setStatus("error: " + msg.message); }
  };
}

function update() {
  joinBtn.disabled = joined || !socket;
  leaveBtn.disabled = !joined;
  micBtn.disabled = !joined;
}

joinBtn.onclick = () => {
  const target = modeSel.value + channel.replace(/^[\^$]/, "");
  joined = true;
  members.clear();
  renderMembers();
  setStatus("joining… " + target);
  update();
  socket.send(JSON.stringify({ action: "join", channel: target }));
};

leaveBtn.onclick = () => {
  joined = false;
  if (pc) { pc.close(); pc = null; }
  if (localStream) { localStream.getTracks().forEach((t) => t.stop()); localStream = null; }
  audioEl.srcObject = null;
  setStatus("left");
  update();
  socket.send(JSON.stringify({ action: "leave" }));
};

micBtn.onclick = toggleMic;

if (!ROOM_ID || !TOKEN) {
  setStatus("widget URL is missing roomId or token");
} else {
  update();
  connect();
}
