const $ = (id) => document.getElementById(id);
const logEl = $("log"), statusEl = $("status"), whoEl = $("who");
const joinBtn = $("join"), leaveBtn = $("leave"), micBtn = $("mic");
const membersEl = $("members"), audioEl = $("audio");
const q = new URLSearchParams(location.search);
const ROOM_ID = q.get("roomId") || "", TOKEN = q.get("token") || "";

let socket = null, pc = null, localStream = null, joined = false, micOn = false, channel = null;
const members = new Map(), chunks = new Map();

const log = (...a) => { logEl.textContent += a.map(String).join(" ") + "\n"; logEl.scrollTop = logEl.scrollHeight; };
const setStatus = (t) => { statusEl.textContent = t; };
const send = (env) => { if (socket && socket.readyState === 1) socket.send(JSON.stringify({ action: "signal", payload: JSON.stringify(env) })); };

function renderMembers() {
  membersEl.innerHTML = "";
  for (const [nick, m] of members) {
    const li = document.createElement("li");
    li.textContent = nick + (m.mic ? " 🎤" : " 🔇") + (m.speaking ? " · говорит" : "");
    membersEl.appendChild(li);
  }
}

function applyPresence(e) {
  if (!e.member) return;
  if (e.state === "left" || e.state === "gone") { members.delete(e.member); return renderMembers(); }
  const m = members.get(e.member) || { mic: false, speaking: false };
  if (e.kind === "mic") m.mic = e.state === "on";
  else if (e.kind === "speaking") m.speaking = e.state === "speaking";
  else if (e.state === "joined") m.mic = true;
  members.set(e.member, m);
  renderMembers();
}

async function onJoined(env) {
  const t = env.turn || {};
  const iceServers = t.urls ? [{ urls: t.urls, username: t.username, credential: t.password }] : [];
  log("turn:", (t.urls || []).length + " url(s), mode:", env.mode);

  pc = new RTCPeerConnection({ iceServers });
  pc.onicecandidate = (e) => e.candidate && send({ type: "ice", candidate: e.candidate });
  pc.ontrack = (e) => { log("track:", e.track.kind); audioEl.srcObject = e.streams[0]; audioEl.play().catch(() => {}); };
  pc.onconnectionstatechange = () => { log("pc:", pc.connectionState); if (pc.connectionState === "connected") setStatus("в звонке"); };

  pc.addTransceiver("audio", { direction: "recvonly" });

  if (env.mode !== "stream") {
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localStream.getAudioTracks().forEach((tr) => { tr.enabled = false; pc.addTrack(tr, localStream); });
      log("микрофон есть (выключен)");
    } catch (e) {
      log("без микрофона:", e.message);
    }
  }

  try {
    const offer = await pc.createOffer({ offerToReceiveAudio: true });
    log("offer:", offer.sdp.length, "bytes");
    await pc.setLocalDescription(offer);
    send({ type: "offer", sdp: offer.sdp });
    log("offer отправлен");
    setStatus("подключаюсь к SFU…");
  } catch (e) {
    log("ошибка оффера:", e.name, e.message);
    setStatus("ошибка оффера");
  }
}

function onEnvelope(env) {
  log("<<", env.type, env.member || "");
  if (env.type === "chunk") {
    const acc = (chunks.get(env.id) || "") + (env.sdp || "");
    chunks.set(env.id, acc);
    if (!env.last) return;
    chunks.delete(env.id);
    return onEnvelope({ type: env.of || "answer", sdp: acc });
  }
  if (env.type === "joined") return onJoined(env);
  if (env.type === "presence") return applyPresence(env);
  if (!pc) return;
  if (env.type === "answer") {
    pc.setRemoteDescription({ type: "answer", sdp: env.sdp }).catch((e) => log("sdp:", e.message));
  } else if (env.type === "ice" && env.candidate) {
    pc.addIceCandidate(env.candidate).catch(() => {});
  }
}

function connect() {
  const scheme = location.protocol === "https:" ? "wss://" : "ws://";
  socket = new WebSocket(scheme + location.host + "/voice/ws");
  socket.onopen = () => { setStatus("handshaking…"); socket.send(JSON.stringify({ action: "handshake", room_id: ROOM_ID, token: TOKEN })); };
  socket.onclose = () => { setStatus("disconnected"); joined = false; update(); };
  socket.onerror = () => setStatus("socket error");
  socket.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.action === "ready") { channel = m.channel; whoEl.textContent = m.network + " · " + (m.nick || "?"); setStatus("ready"); joinBtn.disabled = false; return; }
    if (m.action === "signal") return onEnvelope(JSON.parse(m.payload));
    if (m.action === "error") { log("bridge:", m.message); setStatus("error: " + m.message); }
  };
}

const update = () => { joinBtn.disabled = joined || !socket; leaveBtn.disabled = !joined; micBtn.disabled = !joined; };

joinBtn.onclick = () => {
  joined = true; members.clear(); renderMembers(); setStatus("joining " + channel); update();
  socket.send(JSON.stringify({ action: "join", channel }));
};

leaveBtn.onclick = () => {
  joined = false;
  if (pc) { pc.close(); pc = null; }
  if (localStream) { localStream.getTracks().forEach((t) => t.stop()); localStream = null; }
  audioEl.srcObject = null; setStatus("left"); update();
  socket.send(JSON.stringify({ action: "leave" }));
};

micBtn.onclick = () => {
  if (!localStream) return;
  micOn = !micOn;
  localStream.getAudioTracks().forEach((t) => (t.enabled = micOn));
  micBtn.textContent = micOn ? "Mic: on" : "Mic: off";
  micBtn.classList.toggle("on", micOn);
  send({ type: "mic", state: micOn ? "on" : "off" });
};

if (!ROOM_ID || !TOKEN) setStatus("widget URL is missing roomId or token");
else { update(); connect(); }
