document.addEventListener("DOMContentLoaded", () => {
  // 1. Native WebSocket Connection
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  let socket = null;

  function initWebSocket() {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("Connected to BLACKBOX AI Real-time Event stream via native WebSocket.");
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("WebSocket event received:", data);

        if (data.type === "activity_feed_item") {
          addActivityFeedItem(data);
        } else if (data.type === "channel_pulse") {
          pulseChannelCard(data.channel);
        } else if (data.type === "agent_decision") {
          updateDecisionPanel(data);
        } else if (data.type === "ticket_update") {
          refreshMetrics();
        }
      } catch (err) {
        console.error("Error parsing WebSocket JSON:", err);
      }
    };

    socket.onclose = () => {
      setTimeout(initWebSocket, 3000);
    };
  }

  initWebSocket();

  // 2. Element References
  const toggleFounderMode = document.getElementById("toggle-founder-mode");
  const feedStream = document.getElementById("activity-feed-stream");
  const decInbound = document.getElementById("dec-inbound");
  const decIntent = document.getElementById("dec-intent");
  const decConfidenceVal = document.getElementById("dec-confidence-val");
  const decConfidenceFill = document.getElementById("dec-confidence-fill");
  const decActionsList = document.getElementById("dec-actions-list");

  // Toggle Founder Mode
  toggleFounderMode.addEventListener("change", async (e) => {
    const enabled = e.target.checked;
    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ founder_disappears_mode: enabled })
      });
      refreshMetrics();
    } catch (err) {
      console.error(err);
    }
  });

  // 3. UI Update Routines
  function addActivityFeedItem(item) {
    const div = document.createElement("div");
    div.className = "activity-item";

    let icon = "⚡";
    if (item.step_type === "THINKING") icon = "🧠";
    if (item.step_type === "TOOL") icon = "🛠️";
    if (item.step_type === "CASPIAN") icon = "📡";
    if (item.step_type === "SUCCESS") icon = "✅";

    div.innerHTML = `
      <span class="activity-time">${item.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      <span class="activity-icon">${icon}</span>
      <div class="activity-body">
        <span class="activity-title">${escapeHtml(item.title)}</span>
        <span class="activity-desc">${escapeHtml(item.details)}</span>
      </div>
    `;

    feedStream.insertBefore(div, feedStream.firstChild);
  }

  function pulseChannelCard(channelName) {
    if (!channelName) return;
    const card = document.getElementById(`channel-card-${channelName.toLowerCase()}`);
    const statusEl = document.getElementById(`status-${channelName.toLowerCase()}`);
    
    if (card) {
      card.classList.add("active-pulse");
      if (statusEl) statusEl.textContent = "Active Dispatch";
      
      setTimeout(() => {
        card.classList.remove("active-pulse");
        if (statusEl) statusEl.textContent = "Listening";
      }, 2500);
    }
  }

  function updateDecisionPanel(data) {
    if (decInbound) decInbound.textContent = `"${data.input_text}"`;
    if (decIntent) decIntent.textContent = `${data.intent} • Category: ${data.category}`;
    
    const conf = data.confidence || 96;
    if (decConfidenceVal) decConfidenceVal.textContent = `${conf}%`;
    if (decConfidenceFill) decConfidenceFill.style.width = `${conf}%`;

    if (decActionsList && data.actions) {
      decActionsList.innerHTML = data.actions.map(act => `
        <div class="check-item done">✓ ${escapeHtml(act)}</div>
      `).join('');
    }
  }

  async function refreshMetrics() {
    try {
      const [statsRes, settingsRes] = await Promise.all([
        fetch("/api/stats"),
        fetch("/api/settings")
      ]);
      if (statsRes.ok) {
        const stats = await statsRes.json();
        document.getElementById("kpi-actions").textContent = (stats.issues || 0) + 42;
        document.getElementById("kpi-saved").textContent = stats.opportunities || 5;
        document.getElementById("kpi-vendor").textContent = stats.delays || 2;
        document.getElementById("kpi-escalations").textContent = stats.risks || 3;
      }
      if (settingsRes.ok) {
        const settings = await settingsRes.json();
        toggleFounderMode.checked = settings.founder_disappears_mode === "1";
      }
    } catch (err) {
      console.error(err);
    }
  }

  // 4. Demo Trigger Handler
  window.triggerDemo = async function(type) {
    // Pulse channel card immediately based on trigger
    if (type === "support") pulseChannelCard("email");
    if (type === "blocker") pulseChannelCard("slack");
    if (type === "bug") pulseChannelCard("discord");
    if (type === "delay") pulseChannelCard("whatsapp");
    if (type === "briefing") pulseChannelCard("telegram");

    try {
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type })
      });
      if (res.ok) {
        refreshMetrics();
      }
    } catch (err) {
      console.error(err);
    }
  };

  function escapeHtml(text) {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initial Load
  refreshMetrics();
});
