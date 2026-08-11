/**
 * Enterprise AI Procurement Agent - Frontend Application Logic
 * Integrates with Caspian SDK Backend API, Channel Simulator, and Real-Time Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    procurements: [],
    stats: null,
    activeStatusFilter: '',
    searchQuery: '',
    activeSimChannel: 'telegram',
    simSenderId: 'user_101',
    simSenderName: 'Sarah Chen (Lead)',
  };

  // DOM Elements
  const kpiTotalRequests = document.getElementById('kpi-total-requests');
  const kpiPendingApprovals = document.getElementById('kpi-pending-approvals');
  const kpiCommittedSpend = document.getElementById('kpi-committed-spend');
  const kpiTotalSavings = document.getElementById('kpi-total-savings');
  const cardsContainer = document.getElementById('procurement-cards-container');
  const pipelineCount = document.getElementById('pipeline-count');
  const searchInput = document.getElementById('search-input');
  const filterTabs = document.getElementById('status-filter-tabs');
  const btnRefresh = document.getElementById('btn-refresh-dashboard');

  // Simulator Elements
  const simTabTelegram = document.getElementById('sim-tab-telegram');
  const simTabEmail = document.getElementById('sim-tab-email');
  const chatStream = document.getElementById('chat-stream');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const quickPromptBtns = document.querySelectorAll('.quick-prompt-btn');

  // Modals Elements
  const ticketModal = document.getElementById('ticket-modal');
  const createModal = document.getElementById('create-modal');
  const btnOpenCreateModal = document.getElementById('btn-open-create-modal');
  const btnCloseTicketModal = document.getElementById('btn-close-ticket-modal');
  const btnCloseCreateModal = document.getElementById('btn-close-create-modal');
  const btnCancelCreate = document.getElementById('btn-cancel-create');
  const formCreateProcurement = document.getElementById('form-create-procurement');

  // ---------------------------------------------------------
  // Helper Formatters
  // ---------------------------------------------------------
  function formatINR(amount) {
    if (!amount && amount !== 0) return '₹0';
    if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(2)} Cr`;
    if (amount >= 100000) return `₹${(amount / 100000).toFixed(2)} Lakh`;
    return `₹${Number(amount).toLocaleString('en-IN')}`;
  }

  function getStatusClass(status) {
    const s = (status || '').toLowerCase().replace(/\s+/g, '-');
    return s;
  }

  function getChannelIcon(channel) {
    if (channel === 'telegram') return '✈️ Telegram';
    if (channel === 'email') return '✉️ Email';
    return '🌐 Web';
  }

  // ---------------------------------------------------------
  // API Fetch Functions
  // ---------------------------------------------------------
  async function loadDashboardData() {
    await Promise.all([fetchStats(), fetchProcurements()]);
  }

  async function fetchStats() {
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) return;
      const data = await res.json();
      state.stats = data;
      renderKPIs(data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  }

  async function fetchProcurements() {
    try {
      let url = '/procurements';
      const params = new URLSearchParams();
      if (state.activeStatusFilter) params.append('status', state.activeStatusFilter);
      if (state.searchQuery) params.append('search', state.searchQuery);
      
      const qs = params.toString();
      if (qs) url += `?${qs}`;

      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      state.procurements = data;
      renderCards(data);
    } catch (err) {
      console.error('Error fetching procurements:', err);
    }
  }

  // ---------------------------------------------------------
  // Render KPI Metrics
  // ---------------------------------------------------------
  function renderKPIs(stats) {
    if (!stats) return;
    kpiTotalRequests.textContent = stats.total_requests;
    kpiPendingApprovals.textContent = stats.pending_approvals;
    kpiCommittedSpend.textContent = formatINR(stats.total_spend_committed);
    kpiTotalSavings.textContent = formatINR(stats.total_savings);
  }

  // ---------------------------------------------------------
  // Render Procurement Cards
  // ---------------------------------------------------------
  function renderCards(tickets) {
    pipelineCount.textContent = `${tickets.length} Ticket${tickets.length === 1 ? '' : 's'}`;

    if (!tickets || tickets.length === 0) {
      cardsContainer.innerHTML = `
        <div style="text-align: center; padding: 48px 20px; color: var(--text-muted);">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">📭</div>
          <div style="font-weight: 600; color: var(--text-secondary);">No procurement requests found</div>
          <div style="font-size: 0.8rem; margin-top: 4px;">Use the Channel Simulator on the right or click "New Request" to create one.</div>
        </div>
      `;
      return;
    }

    cardsContainer.innerHTML = tickets.map(ticket => {
      const statusClass = getStatusClass(ticket.status);
      const isPending = ticket.status === 'Approval Pending';
      const isApproved = ticket.status === 'Approved' || ticket.status === 'Completed';

      const specsHtml = (ticket.specifications || []).slice(0, 3).map(s => 
        `<span class="spec-pill">${escapeHtml(s)}</span>`
      ).join('');

      return `
        <div class="procurement-card" data-id="${ticket.id}">
          <div class="card-top">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="ticket-id-badge">${ticket.id}</span>
              <span class="channel-tag ${ticket.channel}">${getChannelIcon(ticket.channel)}</span>
            </div>
            <span class="status-badge ${statusClass}">
              ● ${ticket.status}
            </span>
          </div>

          <div class="card-title">${escapeHtml(ticket.title || `${ticket.quantity}x ${ticket.product}`)}</div>
          
          <div class="specs-pills">
            <span class="spec-pill" style="color: var(--primary-light);">📦 ${ticket.quantity} Units</span>
            <span class="spec-pill">⏱️ ${ticket.delivery_days} Days</span>
            ${specsHtml}
          </div>

          <div class="offer-box">
            <div class="vendor-info">
              <span class="vendor-label">Recommended Vendor</span>
              <span class="vendor-name">
                🏢 ${escapeHtml(ticket.recommended_vendor || 'Searching bids...')}
              </span>
            </div>
            <div class="price-details">
              <div class="quoted-price">${formatINR(ticket.recommended_price || ticket.budget)}</div>
              <div class="budget-strike">Budget: ${formatINR(ticket.budget)}</div>
            </div>
          </div>

          <div class="card-footer">
            <div class="requester-meta">
              👤 ${escapeHtml(ticket.requester_name || 'Requester')}
            </div>

            <div class="card-actions">
              <button class="btn btn-glass btn-sm btn-view-details" data-id="${ticket.id}">
                Details
              </button>
              ${isPending ? `
                <button class="btn btn-success btn-sm btn-approve" data-id="${ticket.id}">
                  ✓ Approve
                </button>
                <button class="btn btn-danger btn-sm btn-reject" data-id="${ticket.id}">
                  ✕ Reject
                </button>
              ` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Attach button event listeners
    document.querySelectorAll('.btn-view-details').forEach(btn => {
      btn.addEventListener('click', () => openTicketModal(btn.dataset.id));
    });

    document.querySelectorAll('.btn-approve').forEach(btn => {
      btn.addEventListener('click', () => handleApprovalAction(btn.dataset.id, 'approve'));
    });

    document.querySelectorAll('.btn-reject').forEach(btn => {
      btn.addEventListener('click', () => handleApprovalAction(btn.dataset.id, 'reject'));
    });
  }

  // ---------------------------------------------------------
  // Ticket Details Modal
  // ---------------------------------------------------------
  async function openTicketModal(ticketId) {
    try {
      const res = await fetch(`/procurement/${ticketId}`);
      if (!res.ok) return;
      const ticket = await res.json();

      // Fetch audit logs
      const auditRes = await fetch(`/api/audit-logs/${ticketId}`);
      const auditLogs = auditRes.ok ? await auditRes.json() : [];

      document.getElementById('modal-ticket-id').textContent = ticket.id;
      document.getElementById('modal-ticket-title').textContent = ticket.title;

      const quotesHtml = (ticket.quotes || []).map(q => `
        <tr class="${q.is_recommended ? 'recommended' : ''}">
          <td style="font-weight: 600;">
            ${q.is_recommended ? '⭐ ' : ''}${escapeHtml(q.vendor_name)}
            ${q.is_recommended ? '<span style="font-size: 0.68rem; color: #34d399; display: block;">Top Recommendation</span>' : ''}
          </td>
          <td style="color: #34d399; font-weight: 700;">${formatINR(q.price)}</td>
          <td>${q.delivery_days} Days</td>
          <td>⭐ ${q.rating} / 5.0</td>
          <td style="color: #34d399;">${q.savings_percentage > 0 ? `+${q.savings_percentage}%` : 'Standard'}</td>
        </tr>
      `).join('');

      const timelineHtml = (auditLogs || []).map(log => `
        <div class="timeline-item">
          <div class="timeline-dot"></div>
          <div class="timeline-title">${escapeHtml(log.action)} (${escapeHtml(log.stage)})</div>
          <div class="timeline-meta">By ${escapeHtml(log.actor)} • ${new Date(log.timestamp).toLocaleTimeString()}</div>
        </div>
      `).join('');

      const structuredJsonString = JSON.stringify({
        product: ticket.product,
        quantity: ticket.quantity,
        budget: ticket.budget,
        delivery_days: ticket.delivery_days,
        specifications: ticket.specifications
      }, null, 2);

      const content = document.getElementById('modal-ticket-content');
      content.innerHTML = `
        <div style="display: flex; gap: 8px; margin-bottom: 16px;">
          <span class="status-badge ${getStatusClass(ticket.status)}">● ${ticket.status}</span>
          <span class="channel-tag ${ticket.channel}">${getChannelIcon(ticket.channel)}</span>
        </div>

        <div style="background: rgba(0,0,0,0.3); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-glass); margin-bottom: 18px;">
          <div style="font-size: 0.78rem; color: var(--text-muted); text-transform: uppercase;">Executive Summary</div>
          <div style="font-size: 0.85rem; margin-top: 4px; color: var(--text-main);">${escapeHtml(ticket.summary || 'Summary unavailable')}</div>
        </div>

        <h4 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 8px;">Vendor Bids & Quotation Matrix</h4>
        <table class="quote-table">
          <thead>
            <tr>
              <th>Vendor</th>
              <th>Quoted Price</th>
              <th>Timeline</th>
              <th>Rating</th>
              <th>Savings</th>
            </tr>
          </thead>
          <tbody>
            ${quotesHtml || '<tr><td colspan="5">No vendor quotes recorded</td></tr>'}
          </tbody>
        </table>

        <h4 style="font-size: 0.95rem; font-weight: 700; margin: 18px 0 8px 0;">Structured JSON Payload</h4>
        <pre style="background: #060911; border: 1px solid var(--border-glass); padding: 12px; border-radius: 8px; font-family: var(--font-mono); font-size: 0.76rem; color: #38bdf8; overflow-x: auto;">${structuredJsonString}</pre>

        <h4 style="font-size: 0.95rem; font-weight: 700; margin: 18px 0 8px 0;">Workflow Audit Trail</h4>
        <div class="timeline">
          ${timelineHtml || '<div class="timeline-meta">No audit logs yet.</div>'}
        </div>

        ${ticket.status === 'Approval Pending' ? `
          <div style="display: flex; gap: 12px; margin-top: 20px; border-top: 1px solid var(--border-glass); padding-top: 16px;">
            <button class="btn btn-success" style="flex: 1;" id="modal-btn-approve">
              ✓ Authorize & Approve (${formatINR(ticket.recommended_price)})
            </button>
            <button class="btn btn-danger" style="flex: 1;" id="modal-btn-reject">
              ✕ Reject Request
            </button>
          </div>
        ` : ''}
      `;

      if (ticket.status === 'Approval Pending') {
        document.getElementById('modal-btn-approve')?.addEventListener('click', async () => {
          await handleApprovalAction(ticket.id, 'approve');
          ticketModal.classList.remove('open');
        });
        document.getElementById('modal-btn-reject')?.addEventListener('click', async () => {
          await handleApprovalAction(ticket.id, 'reject');
          ticketModal.classList.remove('open');
        });
      }

      ticketModal.classList.add('open');
    } catch (err) {
      console.error('Error loading ticket modal:', err);
    }
  }

  // ---------------------------------------------------------
  // Handle Approval / Rejection API Actions
  // ---------------------------------------------------------
  async function handleApprovalAction(ticketId, action) {
    try {
      const endpoint = action === 'approve' ? `/procurement/${ticketId}/approve` : `/procurement/${ticketId}/reject`;
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approver: 'Dashboard Manager', channel: 'web' })
      });
      if (res.ok) {
        await loadDashboardData();
        appendChatBubble('agent', `⚡ Action processed: Ticket ${ticketId} has been ${action === 'approve' ? 'APPROVED' : 'REJECTED'}.`);
      }
    } catch (err) {
      console.error('Error handling approval action:', err);
    }
  }

  // ---------------------------------------------------------
  // Channel Simulator Interaction
  // ---------------------------------------------------------
  simTabTelegram.addEventListener('click', () => {
    state.activeSimChannel = 'telegram';
    simTabTelegram.classList.add('active', 'telegram');
    simTabEmail.classList.remove('active', 'email');
    chatInput.placeholder = "Type Telegram message (e.g. 'Need 100 laptops.')...";
  });

  simTabEmail.addEventListener('click', () => {
    state.activeSimChannel = 'email';
    simTabEmail.classList.add('active', 'email');
    simTabTelegram.classList.remove('active', 'telegram');
    chatInput.placeholder = "Type Email body (e.g. 'Procure 50 server racks...')...";
  });

  quickPromptBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      chatInput.value = btn.dataset.text;
      chatInput.focus();
    });
  });

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = '';
    appendChatBubble('user', text);

    // Show temporary typing indicator
    const typingBubble = appendTypingIndicator();

    try {
      const res = await fetch('/api/channels/simulate-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: state.activeSimChannel,
          sender_id: state.simSenderId,
          sender_name: state.simSenderName,
          text: text,
          subject: state.activeSimChannel === 'email' ? 'Procurement Request Inquiry' : null
        })
      });

      typingBubble.remove();

      if (res.ok) {
        const data = await res.json();
        
        if (data.status === 'in_progress') {
          appendChatBubble('agent', data.reply);
        } else if (data.status === 'ticket_created') {
          const t = data.ticket;
          const msg = `
            🎉 <b>Procurement Ticket Created: <span style="color: var(--primary-light);">${t.id}</span></b><br><br>
            📦 <b>Item:</b> ${t.quantity}x ${t.product}<br>
            💰 <b>Budget:</b> ${formatINR(t.budget)}<br>
            🚚 <b>Delivery:</b> ${t.delivery_days} Days<br>
            🏢 <b>Recommended Vendor:</b> ${t.recommended_vendor} (${formatINR(t.recommended_price)})<br><br>
            <i>Approve or Reject?</i>
            <div style="display: flex; gap: 8px; margin-top: 10px;">
              <button class="btn btn-success btn-sm btn-sim-approve" data-id="${t.id}">Approve</button>
              <button class="btn btn-danger btn-sm btn-sim-reject" data-id="${t.id}">Reject</button>
            </div>
          `;
          appendChatBubble('agent', msg, true);

          // Attach simulated button actions
          setTimeout(() => {
            document.querySelectorAll('.btn-sim-approve').forEach(b => {
              b.onclick = () => {
                chatInput.value = `APPROVE ${b.dataset.id}`;
                chatForm.dispatchEvent(new Event('submit'));
              };
            });
            document.querySelectorAll('.btn-sim-reject').forEach(b => {
              b.onclick = () => {
                chatInput.value = `REJECT ${b.dataset.id}`;
                chatForm.dispatchEvent(new Event('submit'));
              };
            });
          }, 100);

          await loadDashboardData();
        } else if (data.status === 'approval_processed') {
          appendChatBubble('agent', data.reply);
          await loadDashboardData();
        } else {
          appendChatBubble('agent', data.reply || 'Message processed.');
        }
      }
    } catch (err) {
      typingBubble.remove();
      appendChatBubble('agent', '⚠️ Error communicating with agent server.');
      console.error('Simulator error:', err);
    }
  });

  function appendChatBubble(sender, text, isHtml = false) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const tag = sender === 'agent' ? `<div class="agent-tag">🤖 Caspian Agent (${state.activeSimChannel.toUpperCase()})</div>` : '';

    bubble.innerHTML = `
      ${tag}
      <div>${isHtml ? text : escapeHtml(text).replace(/\n/g, '<br>')}</div>
      <div class="bubble-time">${timeStr}</div>
    `;

    chatStream.appendChild(bubble);
    chatStream.scrollTop = chatStream.scrollHeight;
    return bubble;
  }

  function appendTypingIndicator() {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble agent';
    bubble.innerHTML = `
      <div class="agent-tag">🤖 Caspian Agent thinking...</div>
      <div style="display: flex; gap: 4px; padding: 4px 0;">
        <span style="animation: pulse 1s infinite;">●</span>
        <span style="animation: pulse 1s infinite 0.2s;">●</span>
        <span style="animation: pulse 1s infinite 0.4s;">●</span>
      </div>
    `;
    chatStream.appendChild(bubble);
    chatStream.scrollTop = chatStream.scrollHeight;
    return bubble;
  }

  // ---------------------------------------------------------
  // Filter & Search Controls
  // ---------------------------------------------------------
  filterTabs.querySelectorAll('.filter-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.activeStatusFilter = tab.dataset.status;
      fetchProcurements();
    });
  });

  let searchDebounce = null;
  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.searchQuery = e.target.value.trim();
      fetchProcurements();
    }, 250);
  });

  btnRefresh.addEventListener('click', () => {
    loadDashboardData();
  });

  // ---------------------------------------------------------
  // Create Modal
  // ---------------------------------------------------------
  btnOpenCreateModal.addEventListener('click', () => createModal.classList.add('open'));
  btnCloseCreateModal.addEventListener('click', () => createModal.classList.remove('open'));
  btnCancelCreate.addEventListener('click', () => createModal.classList.remove('open'));
  btnCloseTicketModal.addEventListener('click', () => ticketModal.classList.remove('open'));

  formCreateProcurement.addEventListener('submit', async (e) => {
    e.preventDefault();
    const product = document.getElementById('create-product').value;
    const quantity = parseInt(document.getElementById('create-quantity').value);
    const budget = parseFloat(document.getElementById('create-budget').value);
    const delivery_days = parseInt(document.getElementById('create-delivery').value);
    const channel = document.getElementById('create-channel').value;
    const specsRaw = document.getElementById('create-specs').value;
    const requester_name = document.getElementById('create-requester').value || 'Employee';

    const specifications = specsRaw ? specsRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

    try {
      const res = await fetch('/procurement', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product,
          quantity,
          budget,
          delivery_days,
          channel,
          specifications,
          requester_name,
        })
      });

      if (res.ok) {
        formCreateProcurement.reset();
        createModal.classList.remove('open');
        await loadDashboardData();
      }
    } catch (err) {
      console.error('Error creating procurement:', err);
    }
  });

  // Close modals on backdrop click
  window.addEventListener('click', (e) => {
    if (e.target === ticketModal) ticketModal.classList.remove('open');
    if (e.target === createModal) createModal.classList.remove('open');
  });

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Initial Load & Auto-polling
  loadDashboardData();
  setInterval(loadDashboardData, 10000);
});
