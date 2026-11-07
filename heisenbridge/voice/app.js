const $ = (id) => document.getElementById(id);
const logEl = $("log"), statusEl = $("status"), whoEl = $("who");
const joinBtn = $("join"), leaveBtn = $("leave"), micBtn = $("mic");
const membersEl = $("members"), audioEl = $("audio");
const q = new URLSearchParams(location.search);
const ROOM_ID = q.get("roomId") || "", TOKEN = q.get("token") || "";

let socket = null, pc = null, localStream = null, joined = false, micOn = false, channel = null;
const members = new Map();

const log = (...a) => { logEl.textContent += a.map(String).join(" ") + "\n"; logEl.scrollTop = logEl.scrollHeight; };
const setStatus = (t) => { statusEl.textContent = t; };
const emit = (env) => {
  if (socket && socket.readyState === 1) socket.send(JSON.stringify({ action: "signal", payload: JSON.stringify(env) }));
};

// IRC client tags have a hard size limit, so a large SDP is split into parts
// that share an id; the SFU reassembles them by seq/total.
const CHUNK = 1500;

const send = (env) => {
  if (!env.sdp) return emit(env);
  const parts = [];
  for (let i = 0; i < env.sdp.length; i += CHUNK) parts.push(env.sdp.slice(i, i + CHUNK));
  if (parts.length < 2) return emit(env);
  const id = "c" + Math.random().toString(36).slice(2);
  parts.forEach((sdp, seq) => emit({ ...env, sdp, id, seq, total: parts.length }));
};

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
  const iceServers = [{ urls: "stun:stun.l.google.com:19302" }];
  if (t.urls) iceServers.push({ urls: t.urls, username: t.username, credential: t.password });
  log("turn:", (t.urls || []).length + " url(s), mode:", env.mode);
  for (const m of env.members || []) members.set(m, members.get(m) || { mic: false, speaking: false });
  renderMembers();

  pc = new RTCPeerConnection({ iceServers });
  pc.onicecandidate = (e) => {
    if (!e.candidate) return;
    send({
      type: "ice",
      cand: e.candidate.candidate,
      mid: e.candidate.sdpMid ?? undefined,
      mlineidx: e.candidate.sdpMLineIndex ?? undefined,
    });
  };
  pc.ontrack = (e) => { log("track:", e.track.kind); audioEl.srcObject = e.streams[0]; audioEl.play().catch(() => {}); };
  pc.onconnectionstatechange = () => {
    log("pc:", pc.connectionState);
    if (pc.connectionState === "connected") setStatus("в звонке");
  };

  if (env.mode !== "stream") {
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localStream.getAudioTracks().forEach((tr) => { tr.enabled = false; pc.addTrack(tr, localStream); });
      log("микрофон есть (выключен)");
    } catch (e) {
      log("без микрофона:", e.message);
    }
  }

  // a client that publishes nothing must still offer m-lines, or the SFU
  // rejects the session; a captured mic already provides the audio m-line
  if (!localStream) pc.addTransceiver("audio", { direction: "recvonly" });
  pc.addTransceiver("video", { direction: "recvonly" });

  try {
    const offer = await pc.createOffer();
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

const inbound = new Map();
const pendingIce = [];

function flushIce() {
  while (pendingIce.length) pc.addIceCandidate(pendingIce.shift()).catch(() => {});
}

function onEnvelope(env) {
  if (env.id && env.total > 1 && env.seq !== undefined) {
    const slot = inbound.get(env.id) || { base: { ...env, sdp: undefined }, parts: new Array(env.total), filled: 0 };
    if (slot.parts[env.seq] === undefined) slot.filled++;
    slot.parts[env.seq] = env.sdp || "";
    inbound.set(env.id, slot);
    if (slot.filled < slot.total) return;
    inbound.delete(env.id);
    env = { ...slot.base, sdp: slot.parts.join("") };
  }

  log("<<", env.type, env.member || "");
  if (env.type === "joined") return onJoined(env);
  if (env.type === "presence") return applyPresence(env);
  if (!pc) return;
  if (env.type === "answer") {
    pc.setRemoteDescription({ type: "answer", sdp: env.sdp })
      .then(() => { log("answer применён"); flushIce(); })
      .catch((e) => log("sdp:", e.message));
  } else if (env.type === "ice" && env.cand) {
    const cand = { candidate: env.cand, sdpMid: env.mid, sdpMLineIndex: env.mlineidx };
    if (pc.remoteDescription) pc.addIceCandidate(cand).catch((e) => log("ice:", e.message));
    else pendingIce.push(cand);
  }
}

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
    const m = JSON.parse(ev.data);
    if (m.action === "ready") {
      channel = m.channel;
      whoEl.textContent = m.network + " · " + (m.nick || "?");
      setStatus("ready");
      joinBtn.disabled = false;
      return;
    }
    if (m.action === "signal") return onEnvelope(JSON.parse(m.payload));
    if (m.action === "error") { log("bridge:", m.message); setStatus("error: " + m.message); }
  };
}

const update = () => { joinBtn.disabled = joined || !socket; leaveBtn.disabled = !joined; micBtn.disabled = !joined; };

joinBtn.onclick = () => {
  joined = true;
  members.clear();
  renderMembers();
  setStatus("joining " + channel);
  update();
  socket.send(JSON.stringify({ action: "join", channel }));
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

micBtn.onclick = () => {
  if (!localStream) return;
  micOn = !micOn;
  localStream.getAudioTracks().forEach((t) => (t.enabled = micOn));
  micBtn.textContent = micOn ? "Mic: on" : "Mic: off";
  micBtn.classList.toggle("on", micOn);
  send({ type: "mic", state: micOn ? "on" : "off" });
};

if (!ROOM_ID || !TOKEN) {
  setStatus("widget URL is missing roomId or token");
} else {
  update();
  connect();
}
