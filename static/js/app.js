/**
 * ProcureAI - Enterprise Procurement & Vendor Intelligence Frontend Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  const state = {
    procurements: [],
    negotiations: [],
    stats: null,
    activeStatusFilter: '',
    searchQuery: '',
    activeSimChannel: 'telegram',
    simSenderId: 'user_101',
    simSenderName: 'Sarah Chen (Lead)',
  };

  // Nav
  const tabNavWorkflow = document.getElementById('tab-nav-workflow');
  const tabNavVi = document.getElementById('tab-nav-vi');
  const viewWorkflow = document.getElementById('view-workflow');
  const viewVi = document.getElementById('view-vi');
  const navBrandHome = document.getElementById('nav-brand-home');

  // Metrics
  const kpiTotalRequests = document.getElementById('kpi-total-requests');
  const kpiPendingApprovals = document.getElementById('kpi-pending-approvals');
  const kpiCommittedSpend = document.getElementById('kpi-committed-spend');
  const kpiTotalSavings = document.getElementById('kpi-total-savings');

  // Pipeline Elements
  const ticketListContainer = document.getElementById('ticket-list-container');
  const ticketCountBadge = document.getElementById('ticket-count-badge');
  const searchQuery = document.getElementById('search-query');
  const filterTabs = document.getElementById('filter-tabs');

  // Channel Interface Elements
  const channelBtnTg = document.getElementById('channel-btn-tg');
  const channelBtnEmail = document.getElementById('channel-btn-email');
  const chatStream = document.getElementById('chat-stream');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const hintPills = document.querySelectorAll('.hint-pill');

  // Vendor Intelligence Elements
  const btnRunAnalysis = document.getElementById('btn-run-analysis');
  const btnRunNegotiation = document.getElementById('btn-run-negotiation');
  const btnOpenCompReport = document.getElementById('btn-open-comp-report');
  const btnOpenNegReport = document.getElementById('btn-open-neg-report');
  const scoringResultsContainer = document.getElementById('scoring-results-container');
  const riskAlertsContainer = document.getElementById('risk-alerts-container');
  const riskCountLabel = document.getElementById('risk-count-label');
  const negotiationsListContainer = document.getElementById('negotiations-list-container');

  // Modals Elements
  const ticketModal = document.getElementById('ticket-modal');
  const createModal = document.getElementById('create-modal');
  const reportModal = document.getElementById('report-modal');
  const btnOpenCreate = document.getElementById('btn-open-create');
  const btnCloseTicket = document.getElementById('btn-close-ticket');
  const btnCloseCreate = document.getElementById('btn-close-create');
  const btnCloseReport = document.getElementById('btn-close-report');
  const btnCancelCreate = document.getElementById('btn-cancel-create');
  const formCreate = document.getElementById('form-create');

  // ---------------------------------------------------------
  // Helper Formatters
  // ---------------------------------------------------------
  function formatINR(amount) {
    if (!amount && amount !== 0) return '₹0';
    if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(2)} Cr`;
    if (amount >= 100000) return `₹${(amount / 100000).toFixed(2)} Lakh`;
    return `₹${Number(amount).toLocaleString('en-IN')}`;
  }

  function getStatusBadgeClass(status) {
    const s = (status || '').toLowerCase();
    if (s.includes('pending')) return 'pending';
    if (s.includes('approved') || s.includes('completed')) return 'approved';
    if (s.includes('rejected')) return 'rejected';
    return 'open';
  }

  // ---------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------
  function setView(target) {
    if (target === 'view-workflow') {
      tabNavWorkflow.classList.add('active');
      tabNavVi.classList.remove('active');
      viewWorkflow.classList.add('active');
      viewVi.classList.remove('active');
    } else {
      tabNavVi.classList.add('active');
      tabNavWorkflow.classList.remove('active');
      viewVi.classList.add('active');
      viewWorkflow.classList.remove('active');
      fetchNegotiations();
    }
  }

  tabNavWorkflow.addEventListener('click', () => setView('view-workflow'));
  tabNavVi.addEventListener('click', () => setView('view-vi'));
  navBrandHome.addEventListener('click', () => setView('view-workflow'));

  // ---------------------------------------------------------
  // API Fetch Functions
  // ---------------------------------------------------------
  async function loadDashboard() {
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
      renderTickets(data);
    } catch (err) {
      console.error('Error fetching procurements:', err);
    }
  }

  async function fetchNegotiations() {
    try {
      const res = await fetch('/negotiations');
      if (!res.ok) return;
      const data = await res.json();
      state.negotiations = data;
      renderNegotiations(data);
    } catch (err) {
      console.error('Error fetching negotiations:', err);
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
  // Render Procurement Tickets
  // ---------------------------------------------------------
  function renderTickets(tickets) {
    ticketCountBadge.textContent = `${tickets.length} item${tickets.length === 1 ? '' : 's'}`;

    if (!tickets || tickets.length === 0) {
      ticketListContainer.innerHTML = `
        <div style="text-align: center; padding: 48px 20px; color: var(--text-muted);">
          <div style="font-weight: 500; color: var(--text-secondary); margin-bottom: 4px;">No procurement records found</div>
          <div style="font-size: 12px;">Create a new request or use the channel assistant to submit an order.</div>
        </div>
      `;
      return;
    }

    ticketListContainer.innerHTML = tickets.map(ticket => {
      const badgeClass = getStatusBadgeClass(ticket.status);
      const isPending = ticket.status === 'Approval Pending';

      const specsLine = (ticket.specifications || []).slice(0, 3).map(s => 
        `<span class="tag-badge" style="background: var(--bg-surface-raised); color: var(--text-secondary); border: 1px solid var(--border-subtle);">${escapeHtml(s)}</span>`
      ).join(' ');

      return `
        <div class="ticket-row" data-id="${ticket.id}">
          <div class="ticket-row-top">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="ticket-id">${ticket.id}</span>
              <span class="tag-badge" style="background: var(--bg-surface-raised); text-transform: capitalize; color: var(--text-secondary);">${ticket.channel}</span>
            </div>
            <span class="tag-badge ${badgeClass}">${ticket.status}</span>
          </div>

          <div class="ticket-title">${escapeHtml(ticket.title || `${ticket.quantity}x ${ticket.product}`)}</div>

          <div class="ticket-meta-line">
            <span>Quantity: <b>${ticket.quantity}</b></span>
            <span>Target Delivery: <b>${ticket.delivery_days} Days</b></span>
            ${specsLine}
          </div>

          <div class="ticket-quote-summary">
            <div>
              <span style="color: var(--text-muted);">Recommended Supplier:</span>
              <b style="color: var(--text-primary); margin-left: 4px;">${escapeHtml(ticket.recommended_vendor || 'Pending Evaluation')}</b>
            </div>
            <div>
              <span style="color: var(--text-muted); font-size: 11px;">Offer:</span>
              <b style="color: var(--success-text); margin-left: 4px; font-family: var(--font-mono);">${formatINR(ticket.recommended_price || ticket.budget)}</b>
              <span style="color: var(--text-muted); font-size: 11px; margin-left: 6px;">(Budget: ${formatINR(ticket.budget)})</span>
            </div>
          </div>

          <div class="ticket-row-bottom">
            <span style="font-size: 12px; color: var(--text-muted);">
              Requester: ${escapeHtml(ticket.requester_name || 'Staff')}
            </span>

            <div style="display: flex; gap: 6px;">
              <button class="btn btn-secondary btn-sm btn-ticket-details" data-id="${ticket.id}">
                Details
              </button>
              ${isPending ? `
                <button class="btn btn-success btn-sm btn-ticket-approve" data-id="${ticket.id}">
                  Approve
                </button>
                <button class="btn btn-danger btn-sm btn-ticket-reject" data-id="${ticket.id}">
                  Reject
                </button>
              ` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Attach listeners
    document.querySelectorAll('.btn-ticket-details').forEach(btn => {
      btn.addEventListener('click', () => openTicketModal(btn.dataset.id));
    });

    document.querySelectorAll('.btn-ticket-approve').forEach(btn => {
      btn.addEventListener('click', () => handleApproval(btn.dataset.id, 'approve'));
    });

    document.querySelectorAll('.btn-ticket-reject').forEach(btn => {
      btn.addEventListener('click', () => handleApproval(btn.dataset.id, 'reject'));
    });
  }

  // ---------------------------------------------------------
  // Quotation Scoring Execution
  // ---------------------------------------------------------
  btnRunAnalysis.addEventListener('click', async () => {
    const samplePayload = {
      product: "Laptop",
      quantity: 100,
      budget: 4500000.0,
      quotes: [
        {
          vendor_name: "Dell Partner (Enterprise Solutions)",
          price: 4150000.0,
          delivery_days: 7,
          warranty_years: 3,
          vendor_rating: 4.8,
          reliability_score: 96.0,
        },
        {
          vendor_name: "HP Commercial Direct",
          price: 4320000.0,
          delivery_days: 9,
          warranty_years: 3,
          vendor_rating: 4.6,
          reliability_score: 92.0,
        },
        {
          vendor_name: "Lenovo Premier Solutions",
          price: 4400000.0,
          delivery_days: 8,
          warranty_years: 3,
          vendor_rating: 4.5,
          reliability_score: 90.0,
        },
        {
          vendor_name: "TechNova Global Ltd (Risk Outlier)",
          price: 2800000.0,
          delivery_days: 16,
          warranty_years: 1,
          vendor_rating: 3.6,
          reliability_score: 72.0,
        }
      ]
    };

    scoringResultsContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--primary-text); font-size: 13px;">Computing 4-Factor Weighted Model...</div>`;

    try {
      const res = await fetch('/quotes/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(samplePayload)
      });

      if (!res.ok) return;
      const data = await res.json();

      // Render 4-Factor Scoring Cards
      scoringResultsContainer.innerHTML = data.scoring_results.map(s => `
        <div class="vendor-score-row" style="${s.is_recommended ? 'border-color: rgba(16, 185, 129, 0.4);' : ''}">
          <div class="vendor-score-top">
            <div>
              <div style="font-weight: 600; font-size: 13px; color: var(--text-primary);">
                #${s.rank} ${escapeHtml(s.vendor)}
                ${s.is_recommended ? '<span class="tag-badge approved" style="margin-left: 6px;">Top Ranked</span>' : ''}
              </div>
              <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
                Quoted: <b style="color: var(--success-text); font-family: var(--font-mono);">${formatINR(s.quoted_price)}</b> • ${s.delivery_days} Days Lead Time • ${s.warranty_years}-Year Warranty
              </div>
            </div>
            <div class="score-badge">${s.score}<span style="font-size: 11px; color: var(--text-muted);">/100</span></div>
          </div>

          <div class="score-sub-grid">
            <div class="score-cell">
              <div class="score-cell-label">Price (40%)</div>
              <div class="score-cell-val">${s.price_score}</div>
            </div>
            <div class="score-cell">
              <div class="score-cell-label">Delivery (25%)</div>
              <div class="score-cell-val">${s.delivery_score}</div>
            </div>
            <div class="score-cell">
              <div class="score-cell-label">Reliability (20%)</div>
              <div class="score-cell-val">${s.reliability_score}</div>
            </div>
            <div class="score-cell">
              <div class="score-cell-label">Warranty (15%)</div>
              <div class="score-cell-val">${s.warranty_score}</div>
            </div>
          </div>
        </div>
      `).join('');

      // Render Risk Alerts
      riskCountLabel.textContent = `${data.risk_alerts.length} alert${data.risk_alerts.length === 1 ? '' : 's'}`;
      if (data.risk_alerts.length > 0) {
        riskAlertsContainer.innerHTML = data.risk_alerts.map(alert => `
          <div class="risk-alert-box ${alert.risk_level.toLowerCase()}">
            <div style="display: flex; justify-content: space-between; font-weight: 600;">
              <span>${escapeHtml(alert.vendor_name)}</span>
              <span>Level: ${alert.risk_level}</span>
            </div>
            <div style="font-weight: 500; margin-top: 2px;">${escapeHtml(alert.risk_factor)}</div>
            <div style="margin-top: 2px; opacity: 0.9;">${escapeHtml(alert.reason)}</div>
          </div>
        `).join('');
      } else {
        riskAlertsContainer.innerHTML = `<div style="text-align: center; color: var(--success-text); padding: 14px; font-size: 12px;">Zero compliance flags identified.</div>`;
      }

    } catch (err) {
      console.error('Error analyzing quotes:', err);
    }
  });

  // ---------------------------------------------------------
  // Negotiation Action
  // ---------------------------------------------------------
  btnRunNegotiation.addEventListener('click', async () => {
    try {
      const payload = {
        procurement_id: "PROC-2026-001",
        vendor_name: "Dell Partner (Enterprise Solutions)",
        initial_price: 4400000.0,
        competing_lower_price: 4200000.0,
        target_discount_percentage: 5.5,
        product_name: "Laptop",
        quantity: 100
      };

      const res = await fetch('/vendors/negotiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        await fetchNegotiations();
        await fetchStats();
      }
    } catch (err) {
      console.error('Error launching negotiation:', err);
    }
  });

  function renderNegotiations(threads) {
    if (!threads || threads.length === 0) {
      negotiationsListContainer.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 14px; font-size: 12px;">No active negotiations.</div>`;
      return;
    }

    negotiationsListContainer.innerHTML = threads.map(t => `
      <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="font-weight: 600; color: var(--text-primary); font-size: 13px;">
            ${escapeHtml(t.vendor_name)}
          </div>
          <span class="tag-badge approved">
            +${formatINR(t.savings_achieved)} Concession
          </span>
        </div>
        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
          Initial Quote: <strike>${formatINR(t.initial_price)}</strike> ➔ Conceded: <b style="color: var(--success-text); font-family: var(--font-mono);">${formatINR(t.current_price)}</b>
        </div>
      </div>
    `).join('');
  }

  // ---------------------------------------------------------
  // Reports
  // ---------------------------------------------------------
  btnOpenCompReport.addEventListener('click', async () => {
    try {
      const res = await fetch('/reports/comparison');
      if (!res.ok) return;
      const md = await res.text();
      document.getElementById('report-modal-heading').textContent = 'Vendor Comparison Report';
      document.getElementById('report-modal-content').textContent = md;
      reportModal.classList.add('open');
    } catch (err) {
      console.error('Error fetching report:', err);
    }
  });

  btnOpenNegReport.addEventListener('click', async () => {
    try {
      const res = await fetch('/reports/negotiation');
      if (!res.ok) return;
      const md = await res.text();
      document.getElementById('report-modal-heading').textContent = 'Negotiation Intelligence Report';
      document.getElementById('report-modal-content').textContent = md;
      reportModal.classList.add('open');
    } catch (err) {
      console.error('Error fetching report:', err);
    }
  });

  // ---------------------------------------------------------
  // Ticket Details Modal
  // ---------------------------------------------------------
  async function openTicketModal(ticketId) {
    try {
      const res = await fetch(`/procurement/${ticketId}`);
      if (!res.ok) return;
      const ticket = await res.json();

      document.getElementById('modal-ticket-id').textContent = ticket.id;
      document.getElementById('modal-ticket-title').textContent = ticket.title;

      const quotesRows = (ticket.quotes || []).map(q => `
        <tr style="border-bottom: 1px solid var(--border-subtle);">
          <td style="padding: 8px 10px; font-weight: 500;">
            ${escapeHtml(q.vendor_name)} ${q.is_recommended ? '<span class="tag-badge approved" style="margin-left: 4px;">Top Pick</span>' : ''}
          </td>
          <td style="padding: 8px 10px; color: var(--success-text); font-family: var(--font-mono);">${formatINR(q.price)}</td>
          <td style="padding: 8px 10px;">${q.delivery_days} Days</td>
          <td style="padding: 8px 10px;">${q.warranty_years} Yrs</td>
          <td style="padding: 8px 10px; color: var(--success-text);">${q.savings_percentage > 0 ? `+${q.savings_percentage}%` : 'Standard'}</td>
        </tr>
      `).join('');

      const content = document.getElementById('modal-ticket-body');
      content.innerHTML = `
        <div style="background: var(--bg-surface); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); margin-bottom: 16px;">
          <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Executive Summary</div>
          <div style="font-size: 13px; margin-top: 2px; color: var(--text-primary);">${escapeHtml(ticket.summary || 'Summary unavailable')}</div>
        </div>

        <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px;">Vendor Quotations Matrix</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 16px;">
          <thead>
            <tr style="color: var(--text-muted); border-bottom: 1px solid var(--border-subtle); text-align: left;">
              <th style="padding: 6px 10px;">Supplier</th>
              <th style="padding: 6px 10px;">Quoted Price</th>
              <th style="padding: 6px 10px;">Delivery</th>
              <th style="padding: 6px 10px;">Warranty</th>
              <th style="padding: 6px 10px;">Savings</th>
            </tr>
          </thead>
          <tbody>
            ${quotesRows || '<tr><td colspan="5" style="padding: 8px 10px; color: var(--text-muted);">No quotes on file</td></tr>'}
          </tbody>
        </table>

        ${ticket.status === 'Approval Pending' ? `
          <div style="display: flex; gap: 8px; margin-top: 16px; border-top: 1px solid var(--border-subtle); padding-top: 14px;">
            <button class="btn btn-success btn-sm" style="flex: 1;" id="modal-action-approve">
              Approve (${formatINR(ticket.recommended_price)})
            </button>
            <button class="btn btn-danger btn-sm" style="flex: 1;" id="modal-action-reject">
              Reject Request
            </button>
          </div>
        ` : ''}
      `;

      if (ticket.status === 'Approval Pending') {
        document.getElementById('modal-action-approve')?.addEventListener('click', async () => {
          await handleApproval(ticket.id, 'approve');
          ticketModal.classList.remove('open');
        });
        document.getElementById('modal-action-reject')?.addEventListener('click', async () => {
          await handleApproval(ticket.id, 'reject');
          ticketModal.classList.remove('open');
        });
      }

      ticketModal.classList.add('open');
    } catch (err) {
      console.error('Error loading ticket modal:', err);
    }
  }

  // ---------------------------------------------------------
  // Approval Action
  // ---------------------------------------------------------
  async function handleApproval(ticketId, action) {
    try {
      const endpoint = action === 'approve' ? `/procurement/${ticketId}/approve` : `/procurement/${ticketId}/reject`;
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approver: 'Authorized Manager', channel: 'web' })
      });
      if (res.ok) {
        await loadDashboard();
        appendChatMsg('agent', `Order ${ticketId} has been ${action === 'approve' ? 'APPROVED' : 'REJECTED'}.`);
      }
    } catch (err) {
      console.error('Error in approval action:', err);
    }
  }

  // ---------------------------------------------------------
  // Channel Interface Simulator
  // ---------------------------------------------------------
  channelBtnTg.addEventListener('click', () => {
    state.activeSimChannel = 'telegram';
    channelBtnTg.classList.add('active');
    channelBtnEmail.classList.remove('active');
    chatInput.placeholder = "Enter Telegram message...";
  });

  channelBtnEmail.addEventListener('click', () => {
    state.activeSimChannel = 'email';
    channelBtnEmail.classList.add('active');
    channelBtnTg.classList.remove('active');
    chatInput.placeholder = "Enter Email requirement...";
  });

  hintPills.forEach(pill => {
    pill.addEventListener('click', () => {
      chatInput.value = pill.dataset.text;
      chatInput.focus();
    });
  });

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = '';
    appendChatMsg('user', text);

    try {
      const res = await fetch('/api/channels/simulate-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: state.activeSimChannel,
          sender_id: state.simSenderId,
          sender_name: state.simSenderName,
          text: text,
        })
      });

      if (res.ok) {
        const data = await res.json();
        
        if (data.status === 'in_progress') {
          appendChatMsg('agent', data.reply);
        } else if (data.status === 'ticket_created') {
          const t = data.ticket;
          const msg = `
            <b>Procurement Ticket Generated: ${t.id}</b><br>
            • Item: ${t.quantity}x ${t.product}<br>
            • Budget: ${formatINR(t.budget)}<br>
            • Recommended: ${t.recommended_vendor} (${formatINR(t.recommended_price)})<br><br>
            <i>Authorize this procurement?</i>
            <div style="display: flex; gap: 6px; margin-top: 8px;">
              <button class="btn btn-success btn-sm btn-sim-appr" data-id="${t.id}">Approve</button>
              <button class="btn btn-danger btn-sm btn-sim-rej" data-id="${t.id}">Reject</button>
            </div>
          `;
          appendChatMsg('agent', msg, true);

          setTimeout(() => {
            document.querySelectorAll('.btn-sim-appr').forEach(b => {
              b.onclick = () => {
                chatInput.value = `APPROVE ${b.dataset.id}`;
                chatForm.dispatchEvent(new Event('submit'));
              };
            });
            document.querySelectorAll('.btn-sim-rej').forEach(b => {
              b.onclick = () => {
                chatInput.value = `REJECT ${b.dataset.id}`;
                chatForm.dispatchEvent(new Event('submit'));
              };
            });
          }, 100);

          await loadDashboard();
        } else if (data.status === 'approval_processed') {
          appendChatMsg('agent', data.reply);
          await loadDashboard();
        } else {
          appendChatMsg('agent', data.reply || 'Request received.');
        }
      }
    } catch (err) {
      appendChatMsg('agent', 'Connection error to procurement service.');
    }
  });

  function appendChatMsg(sender, text, isHtml = false) {
    const el = document.createElement('div');
    el.className = `chat-entry ${sender}`;
    const header = sender === 'agent' ? `<div style="font-size: 11px; font-weight: 600; color: var(--primary-text); margin-bottom: 2px;">Procurement Assistant (${state.activeSimChannel.toUpperCase()})</div>` : '';

    el.innerHTML = `${header}<div>${isHtml ? text : escapeHtml(text).replace(/\n/g, '<br>')}</div>`;
    chatStream.appendChild(el);
    chatStream.scrollTop = chatStream.scrollHeight;
    return el;
  }

  // ---------------------------------------------------------
  // Filters & Search
  // ---------------------------------------------------------
  filterTabs.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      filterTabs.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      state.activeStatusFilter = chip.dataset.status;
      fetchProcurements();
    });
  });

  let debounceTimer = null;
  searchQuery.addEventListener('input', (e) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.searchQuery = e.target.value.trim();
      fetchProcurements();
    }, 200);
  });

  // ---------------------------------------------------------
  // Create Modal
  // ---------------------------------------------------------
  btnOpenCreate.addEventListener('click', () => createModal.classList.add('open'));
  btnCloseCreate.addEventListener('click', () => createModal.classList.remove('open'));
  btnCancelCreate.addEventListener('click', () => createModal.classList.remove('open'));
  btnCloseTicket.addEventListener('click', () => ticketModal.classList.remove('open'));
  btnCloseReport.addEventListener('click', () => reportModal.classList.remove('open'));

  formCreate.addEventListener('submit', async (e) => {
    e.preventDefault();
    const product = document.getElementById('inp-product').value;
    const quantity = parseInt(document.getElementById('inp-qty').value);
    const budget = parseFloat(document.getElementById('inp-budget').value);
    const delivery_days = parseInt(document.getElementById('inp-delivery').value);
    const channel = document.getElementById('inp-channel').value;
    const specsRaw = document.getElementById('inp-specs').value;

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
        })
      });

      if (res.ok) {
        formCreate.reset();
        createModal.classList.remove('open');
        await loadDashboard();
      }
    } catch (err) {
      console.error('Error creating ticket:', err);
    }
  });

  // Close modals on backdrop click
  window.addEventListener('click', (e) => {
    if (e.target === ticketModal) ticketModal.classList.remove('open');
    if (e.target === createModal) createModal.classList.remove('open');
    if (e.target === reportModal) reportModal.classList.remove('open');
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

  // Init
  loadDashboard();
  setInterval(loadDashboard, 10000);
});
