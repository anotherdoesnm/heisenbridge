// IRC voice widget: bridges an IRCv3 `^voice` channel (obby.world/voice) into a
// Matrix room. The bridge relays the `+obsidianirc/rtc` TAGMSG envelopes; this
// page does the WebRTC part and talks to the SFU the IRC server points at.

const logEl = document.getElementById("log");
const statusEl = document.getElementById("status");
const whoEl = document.getElementById("who");
const joinBtn = document.getElementById("join");
const leaveBtn = document.getElementById("leave");
const micBtn = document.getElementById("mic");
const membersEl = document.getElementById("members");

const ROOM_ID = new URLSearchParams(location.search).get("roomId") || "";

function log(...parts) {
  logEl.textContent += parts.map(String).join(" ") + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

function setStatus(text) {
  statusEl.textContent = text;
}

/* ---------------- Matrix widget API (MSC1236) ---------------- */

let nextRequestId = 1;
const pendingRequests = new Map();

window.addEventListener("message", (event) => {
  const data = event.data;
  if (!data || typeof data !== "object") return;
  if (data.api !== "toWidget") return;
  if (data.response && data.requestId && pendingRequests.has(data.requestId)) {
    const { resolve, reject } = pendingRequests.get(data.requestId);
    pendingRequests.delete(data.requestId);
    if (data.response.error) reject(new Error(JSON.stringify(data.response.error)));
    else resolve(data.response);
  }
});

function widgetRequest(action, data) {
  const requestId = "ircvoice-" + nextRequestId++;
  return new Promise((resolve, reject) => {
    pendingRequests.set(requestId, { resolve, reject });
    window.parent.postMessage({ api: "fromWidget", action, data, requestId }, "*");
    setTimeout(() => {
      if (pendingRequests.delete(requestId)) reject(new Error("widget request timed out: " + action));
    }, 15000);
  });
}

async function sendState(type, stateKey, content) {
  return widgetRequest("send_event", { type, state_key: stateKey, content });
}

/* ---------------- bridge socket ---------------- */

let socket = null;
let joined = false;
let channel = null;
let nick = null;

function connect() {
  const scheme = location.protocol === "https:" ? "wss://" : "ws://";
  socket = new WebSocket(scheme + location.host + "/voice/ws");
  socket.addEventListener("open", () => setStatus("handshaking…"));
  socket.addEventListener("close", () => {
    setStatus("disconnected");
    joined = false;
    updateButtons();
  });
  socket.addEventListener("error", () => setStatus("socket error"));
  socket.addEventListener("message", (event) => onBridgeMessage(JSON.parse(event.data)));
}

async function onBridgeMessage(msg) {
  if (msg.action === "ready") {
    nick = msg.nick;
    channel = msg.channel;
    whoEl.textContent = `${msg.network} · ${nick || "?"}`;
    setStatus("ready");
    joinBtn.disabled = false;
    return;
  }

  if (msg.action === "signal") {
    let payload;
    try {
      payload = JSON.parse(msg.payload);
    } catch (e) {
      log("bad payload", msg.payload);
      return;
    }
    handleSignal(payload, msg.from);
    return;
  }

  if (msg.action === "error") {
    log("bridge error:", msg.message);
    setStatus("error: " + msg.message);
    return;
  }
}

/* ---------------- signalling ---------------- */

function handleSignal(payload, from) {
  log("<<", payload.type, from || "", payload.member || "");
  if (payload.type === "joined") {
    onSfuJoined(payload);
  } else if (payload.type === "presence") {
    renderMembers(payload);
  }
}

function onSfuJoined(payload) {
  log("SFU turn:", JSON.stringify(payload.turn || {}).slice(0, 120));
  log("mode:", payload.mode, "role:", payload.role, "streamers:", JSON.stringify(payload.streamers || []));
  setStatus("in call (media not wired up yet)");
  updateButtons();
}

function renderMembers(payload) {
  const li = document.createElement("li");
  li.textContent = `${payload.member} — ${payload.state}${payload.role ? " (" + payload.role + ")" : ""}`;
  membersEl.appendChild(li);
}

function sendSignal(envelope) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({ action: "signal", payload: JSON.stringify(envelope) }));
}

/* ---------------- UI ---------------- */

function updateButtons() {
  joinBtn.disabled = joined || !socket;
  leaveBtn.disabled = !joined;
  micBtn.disabled = !joined;
  micBtn.classList.toggle("on", joined);
  micBtn.textContent = joined ? "Mic: on" : "Mic: off";
}

joinBtn.addEventListener("click", () => {
  joined = true;
  membersEl.innerHTML = "";
  setStatus("joining…");
  updateButtons();
  socket.send(JSON.stringify({ action: "join" }));
});

leaveBtn.addEventListener("click", () => {
  joined = false;
  setStatus("left");
  membersEl.innerHTML = "";
  updateButtons();
  socket.send(JSON.stringify({ action: "leave" }));
});

micBtn.addEventListener("click", () => {
  sendSignal({ type: "mic", state: micBtn.classList.contains("on") ? "off" : "on" });
});

async function main() {
  if (!ROOM_ID) {
    setStatus("missing roomId in the widget URL");
    return;
  }

  connect();
  socket.addEventListener("open", async () => {
    const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
    socket.send(JSON.stringify({ action: "handshake", nonce, room_id: ROOM_ID }));
    try {
      await sendState("com.obby.rtc.session", "", { nonce });
    } catch (e) {
      log("handshake state event failed:", e.message);
      setStatus("handshake failed");
    }
  });
}

main();
