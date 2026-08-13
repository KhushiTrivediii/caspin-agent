document.addEventListener("DOMContentLoaded", () => {
  // 1. Tab Bar Navigation
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(targetId).classList.add("active");

      // Re-render graph if graph tab selected
      if (targetId === "tab-graph") {
        fetchGraph();
      }
    });
  });

  // 2. Native WebSocket Connection
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  let socket = null;

  function initWebSocket() {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("Connected to BLACKBOX AI Real-time Event stream via native WebSocket.");
      showToast("System Online", "Native Caspian WebSocket connected.", "success");
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log("WebSocket event received:", message);
        
        if (message.type === "ticket_update") {
          showToast("Operations Update", `Ticket ${message.ticket_id} updated: ${message.status}.`, "info");
          refreshDashboard();
        } else if (message.type === "sla_breach_alert") {
          showToast("⚠️ SLA Breach Alert", `Ticket ${message.ticket_id} unassigned. Escalating to founder.`, "danger");
          refreshDashboard();
        }
      } catch (err) {
        console.error("Error parsing WebSocket JSON:", err);
      }
    };

    socket.onclose = () => {
      console.log("WebSocket disconnected. Reconnecting in 3s...");
      setTimeout(initWebSocket, 3000);
    };

    socket.onerror = (err) => {
      console.error("WebSocket error:", err);
    };
  }

  initWebSocket();

  // 3. UI Element References
  const toggleFounderMode = document.getElementById("toggle-founder-mode");
  const logsContainer = document.getElementById("logs-stream-container");
  const ticketsTbody = document.getElementById("tickets-tbody");
  const ticketModal = document.getElementById("ticket-modal");
  const modalTicketId = document.getElementById("modal-ticket-id");
  const modalTicketBody = document.getElementById("modal-ticket-body");
  const btnCloseModal = document.getElementById("btn-close-modal");

  // Toggle Founder Mode
  toggleFounderMode.addEventListener("change", async (e) => {
    const enabled = e.target.checked;
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ founder_disappears_mode: enabled })
      });
      if (res.ok) {
        showToast(
          "Mode Toggle", 
          `Founder Disappears Mode is now ${enabled ? 'ENABLED' : 'DISABLED'}.`,
          enabled ? "success" : "info"
        );
        refreshDashboard();
      }
    } catch (err) {
      console.error("Failed to toggle settings:", err);
    }
  });

  // Modal handlers
  btnCloseModal.addEventListener("click", () => {
    ticketModal.style.display = "none";
  });
  window.onclick = (e) => {
    if (e.target === ticketModal) {
      ticketModal.style.display = "none";
    }
  };

  // 4. Data Refresh Routines
  async function refreshDashboard() {
    await Promise.all([
      fetchStats(),
      fetchTickets(),
      fetchLogs(),
      fetchSettings()
    ]);
  }

  async function fetchSettings() {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const settings = await res.json();
        toggleFounderMode.checked = settings.founder_disappears_mode === "1";
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function fetchStats() {
    try {
      const res = await fetch("/api/stats");
      if (!res.ok) return;
      const stats = await res.json();
      document.getElementById("kpi-opps").textContent = stats.opportunities || 0;
      document.getElementById("kpi-risks").textContent = stats.risks || 0;
      document.getElementById("kpi-issues").textContent = stats.issues || 0;
      document.getElementById("kpi-delays").textContent = stats.delays || 0;
    } catch (err) {
      console.error(err);
    }
  }

  async function fetchTickets() {
    try {
      const res = await fetch("/api/tickets");
      if (!res.ok) return;
      const tickets = await res.json();
      renderTickets(tickets);
    } catch (err) {
      console.error("Error fetching tickets:", err);
    }
  }

  async function fetchLogs() {
    try {
      const res = await fetch("/api/logs");
      if (!res.ok) return;
      const logs = await res.json();
      renderLogs(logs);
    } catch (err) {
      console.error("Error fetching logs:", err);
    }
  }

  async function fetchGraph() {
    try {
      const res = await fetch("/api/graph");
      if (!res.ok) return;
      const graph = await res.json();
      renderCircularGraph(graph);
    } catch (err) {
      console.error("Error fetching graph:", err);
    }
  }

  // 5. Render Functions
  function renderTickets(tickets) {
    if (!tickets || tickets.length === 0) {
      ticketsTbody.innerHTML = `<tr><td colspan="5" class="table-empty">No active tickets found.</td></tr>`;
      return;
    }

    ticketsTbody.innerHTML = tickets.map(t => {
      let statusClass = "tag-open";
      if (t.status === "Escalated") statusClass = "tag-escalated";
      if (t.status === "Resolved") statusClass = "tag-resolved";

      return `
        <tr onclick="openTicketDetails('${t.id}')">
          <td style="font-family: var(--font-mono); font-weight: 600; color: var(--accent);">${t.id}</td>
          <td><span style="font-size: 11px; opacity: 0.85;">${t.category}</span></td>
          <td style="font-weight: 500;">${escapeHtml(t.title)}</td>
          <td><span style="font-size: 11px; font-family: var(--font-mono);">${t.assigned_to || 'Unassigned'}</span></td>
          <td><span class="tag ${statusClass}">${t.status}</span></td>
        </tr>
      `;
    }).join('');
  }

  function renderLogs(logs) {
    if (!logs || logs.length === 0) {
      logsContainer.innerHTML = `<div class="feed-empty">Ready for operational communications...</div>`;
      return;
    }

    logsContainer.innerHTML = logs.map(msg => {
      const isAgent = msg.sender === "blackbox_ai";
      const badgeClass = `badge-${msg.channel.toLowerCase()}`;
      const timeStr = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

      return `
        <div class="feed-item" style="border-left: 3px solid ${isAgent ? 'var(--accent)' : 'var(--border)'}">
          <div class="feed-meta">
            <div>
              <span class="badge ${badgeClass}">${msg.channel}</span>
              <span class="feed-sender">${escapeHtml(msg.sender)}</span>
            </div>
            <span class="feed-time">${timeStr}</span>
          </div>
          <div class="feed-text">${escapeHtml(msg.text)}</div>
        </div>
      `;
    }).join('');

    logsContainer.scrollTop = logsContainer.scrollHeight;
  }

  // 6. Circular Memory Graph Renderer
  function renderCircularGraph(graph) {
    const svg = document.getElementById("memory-graph-svg");
    svg.innerHTML = ''; // Clear SVG

    if (!graph.nodes || graph.nodes.length === 0) return;

    const container = svg.parentElement;
    const width = container.clientWidth || 500;
    const height = container.clientHeight || 350;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;

    // Calculate node coordinates evenly around a circle
    const positions = {};
    const total = graph.nodes.length;

    graph.nodes.forEach((node, i) => {
      const angle = (i / total) * 2 * Math.PI - (Math.PI / 2);
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      
      let color = "var(--accent)";
      if (node.label === "Customer") color = "var(--color-email)";
      if (node.label === "Vendor") color = "var(--color-whatsapp)";
      if (node.label === "TeamMember") color = "var(--color-slack)";
      if (node.label === "Lead") color = "var(--warning)";

      positions[node.id] = { x, y, color, label: node.properties.name || node.id };
    });

    // Draw Edges
    graph.edges.forEach(edge => {
      const p1 = positions[edge.source];
      const p2 = positions[edge.target];
      if (p1 && p2) {
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", p1.x);
        line.setAttribute("y1", p1.y);
        line.setAttribute("x2", p2.x);
        line.setAttribute("y2", p2.y);
        line.setAttribute("class", "graph-link");
        svg.appendChild(line);
      }
    });

    // Draw Nodes
    Object.keys(positions).forEach(id => {
      const p = positions[id];
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "graph-node");

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", p.x);
      circle.setAttribute("cy", p.y);
      circle.setAttribute("r", 8);
      circle.setAttribute("fill", p.color);
      circle.setAttribute("stroke", "var(--bg-panel)");
      group.appendChild(circle);

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", p.x);
      text.setAttribute("y", p.y - 12);
      text.setAttribute("text-anchor", "middle");
      text.textContent = p.label.substring(0, 15);
      group.appendChild(text);

      svg.appendChild(group);
    });
  }

  // 7. Modal Ticket Details View
  window.openTicketDetails = async function(ticketId) {
    try {
      const [ticketRes, auditRes] = await Promise.all([
        fetch(`/api/ticket/${ticketId}`),
        fetch(`/api/ticket/${ticketId}/audit`)
      ]);
      if (!ticketRes.ok) return;

      const ticket = await ticketRes.json();
      const auditLogs = await auditRes.json();

      let auditHtml = (auditLogs || []).map(log => {
        const time = new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        return `
          <div style="border-left: 2px solid var(--border); padding-left: 10px; margin-bottom: 8px;">
            <div style="font-weight: 600; color: var(--text-primary); font-size: 11px;">
              ${escapeHtml(log.action)} &bull; ${time}
            </div>
            <div style="color: var(--text-muted); font-size: 10px;">
              Actor: ${escapeHtml(log.actor)} | ${escapeHtml(log.details)}
            </div>
          </div>
        `;
      }).join('');

      modalTicketId.textContent = ticket.id;
      modalTicketBody.innerHTML = `
        <div style="background: var(--bg-input); border: 1px solid var(--border); padding: 12px; border-radius: var(--radius); margin-bottom: 16px;">
          <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Category</div>
          <div style="font-weight: 600; font-size: 12px; color: var(--accent); margin-top: 2px;">${ticket.category}</div>
          <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; margin-top: 10px;">Description</div>
          <div style="color: var(--text-primary); margin-top: 2px; font-size: 12px;">${escapeHtml(ticket.description)}</div>
          <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; margin-top: 10px;">Assignee</div>
          <div style="font-weight: 500; font-family: var(--font-mono); margin-top: 2px;">${ticket.assigned_to || 'Unassigned'}</div>
        </div>

        <div style="font-weight: 600; margin-bottom: 10px; color: var(--text-primary); font-size: 12px;">Audit Timeline</div>
        <div style="max-height: 150px; overflow-y: auto;">
          ${auditHtml || '<div style="color: var(--text-muted); font-size: 11px;">No audit steps recorded yet.</div>'}
        </div>
      `;

      ticketModal.style.display = "flex";
    } catch (err) {
      console.error(err);
    }
  };

  // 8. Simulation Trigger Handler
  window.triggerSimulation = async function(type) {
    try {
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type })
      });
      if (res.ok) {
        showToast("Event Dispatched", `${type} trigger handled autonomously.`, "success");
        refreshDashboard();
      } else {
        const err = await res.json();
        showToast("Error", err.detail || "Trigger failed.", "danger");
      }
    } catch (err) {
      console.error(err);
      showToast("Connection Error", "API simulation endpoint unreachable.", "danger");
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

  function showToast(title, message, type = 'info') {
    const toast = document.createElement("div");
    toast.style.position = "fixed";
    toast.style.bottom = "20px";
    toast.style.right = "20px";
    toast.style.background = "var(--bg-panel)";
    toast.style.border = "1px solid var(--border)";
    
    let accent = "var(--accent)";
    if (type === "success") accent = "var(--success)";
    if (type === "danger") accent = "var(--danger)";
    
    toast.style.borderLeft = `4px solid ${accent}`;
    toast.style.padding = "10px 16px";
    toast.style.borderRadius = "var(--radius)";
    toast.style.color = "var(--text-primary)";
    toast.style.zIndex = "2000";
    toast.style.fontSize = "12px";

    toast.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 2px;">${escapeHtml(title)}</div>
      <div style="color: var(--text-secondary);">${escapeHtml(message)}</div>
    `;

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }

  // Initial Data Fetch
  refreshDashboard();
});
