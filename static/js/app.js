/**
 * ProcureAI - Minimal, Modern & Energetic Frontend Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
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

  // Nav Tabs
  const tabBtnWorkflow = document.getElementById('tab-btn-workflow');
  const tabBtnVi = document.getElementById('tab-btn-vi');
  const viewWorkflow = document.getElementById('view-workflow');
  const viewVi = document.getElementById('view-vi');
  const brandHome = document.getElementById('brand-home');

  // KPI Elements
  const kpiTotalRequests = document.getElementById('kpi-total-requests');
  const kpiPendingApprovals = document.getElementById('kpi-pending-approvals');
  const kpiCommittedSpend = document.getElementById('kpi-committed-spend');
  const kpiTotalSavings = document.getElementById('kpi-total-savings');

  // Workflow Pipeline Elements
  const cardsContainer = document.getElementById('procurement-cards-container');
  const pipelineCount = document.getElementById('pipeline-count');
  const searchInput = document.getElementById('search-input');
  const filterTabs = document.getElementById('status-filter-tabs');

  // Simulator Elements
  const simTabTelegram = document.getElementById('sim-tab-telegram');
  const simTabEmail = document.getElementById('sim-tab-email');
  const chatStream = document.getElementById('chat-stream');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const quickChips = document.querySelectorAll('.chip-btn');

  // Vendor Intelligence Elements
  const btnRunSampleAnalysis = document.getElementById('btn-run-sample-analysis');
  const btnTriggerNegotiationDemo = document.getElementById('btn-trigger-negotiation-demo');
  const btnViewComparisonReport = document.getElementById('btn-view-comparison-report');
  const btnViewNegotiationReport = document.getElementById('btn-view-negotiation-report');
  const scoringMatrixContainer = document.getElementById('scoring-matrix-container');
  const riskRadarContainer = document.getElementById('risk-radar-container');
  const riskCountBadge = document.getElementById('risk-count-badge');
  const negotiationsContainer = document.getElementById('negotiations-container');

  // Modals Elements
  const ticketModal = document.getElementById('ticket-modal');
  const createModal = document.getElementById('create-modal');
  const reportModal = document.getElementById('report-modal');
  const btnOpenCreateModal = document.getElementById('btn-open-create-modal');
  const btnCloseTicketModal = document.getElementById('btn-close-ticket-modal');
  const btnCloseCreateModal = document.getElementById('btn-close-create-modal');
  const btnCloseReportModal = document.getElementById('btn-close-report-modal');
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
    return (status || '').toLowerCase().replace(/\s+/g, '-');
  }

  // ---------------------------------------------------------
  // Tab Navigation
  // ---------------------------------------------------------
  function switchView(target) {
    if (target === 'view-workflow') {
      tabBtnWorkflow.classList.add('active');
      tabBtnVi.classList.remove('active');
      viewWorkflow.classList.add('active-view');
      viewVi.classList.remove('active-view');
    } else {
      tabBtnVi.classList.add('active');
      tabBtnWorkflow.classList.remove('active');
      viewVi.classList.add('active-view');
      viewWorkflow.classList.remove('active-view');
      fetchNegotiations();
    }
  }

  tabBtnWorkflow.addEventListener('click', () => switchView('view-workflow'));
  tabBtnVi.addEventListener('click', () => switchView('view-vi'));
  brandHome.addEventListener('click', () => switchView('view-workflow'));

  // ---------------------------------------------------------
  // Data Loaders
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
  // Render Clean Procurement Cards
  // ---------------------------------------------------------
  function renderCards(tickets) {
    pipelineCount.textContent = `${tickets.length} Ticket${tickets.length === 1 ? '' : 's'}`;

    if (!tickets || tickets.length === 0) {
      cardsContainer.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
          <div style="font-size: 2rem; margin-bottom: 6px;">📭</div>
          <div style="font-weight: 600; color: var(--text-secondary);">No procurement requests</div>
          <div style="font-size: 0.78rem; margin-top: 4px;">Use the AI Agent on the right or click "+ New Request" to create one.</div>
        </div>
      `;
      return;
    }

    cardsContainer.innerHTML = tickets.map(ticket => {
      const statusClass = getStatusClass(ticket.status);
      const isPending = ticket.status === 'Approval Pending';

      const specsHtml = (ticket.specifications || []).slice(0, 3).map(s => 
        `<span class="tag-pill">${escapeHtml(s)}</span>`
      ).join('');

      return `
        <div class="ticket-item" data-id="${ticket.id}">
          <div class="ticket-top-meta">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="ticket-code">${ticket.id}</span>
              <span class="tag-pill" style="text-transform: capitalize;">${ticket.channel}</span>
            </div>
            <span class="status-chip ${statusClass}">
              ● ${ticket.status}
            </span>
          </div>

          <div class="ticket-heading">${escapeHtml(ticket.title || `${ticket.quantity}x ${ticket.product}`)}</div>
          
          <div class="ticket-tags">
            <span class="tag-pill" style="color: var(--primary-light);">📦 ${ticket.quantity} Units</span>
            <span class="tag-pill">⏱️ ${ticket.delivery_days} Days</span>
            ${specsHtml}
          </div>

          <div class="quote-highlight-box">
            <div>
              <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Recommended Supplier</div>
              <div style="font-size: 0.88rem; font-weight: 700; color: var(--text-main); margin-top: 1px;">
                🏢 ${escapeHtml(ticket.recommended_vendor || 'Vendor Bids Pending')}
              </div>
            </div>
            <div style="text-align: right;">
              <div class="highlight-price">${formatINR(ticket.recommended_price || ticket.budget)}</div>
              <div style="font-size: 0.72rem; color: var(--text-muted);">Budget: ${formatINR(ticket.budget)}</div>
            </div>
          </div>

          <div class="ticket-action-bar">
            <span style="font-size: 0.75rem; color: var(--text-muted);">
              👤 ${escapeHtml(ticket.requester_name || 'Employee')}
            </span>

            <div style="display: flex; gap: 6px;">
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

    // Attach listeners
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
  // Sample Quotation Analysis & 4-Factor Scoring
  // ---------------------------------------------------------
  btnRunSampleAnalysis.addEventListener('click', async () => {
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

    scoringMatrixContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--primary-light);">Computing 4-Factor Weighted Model (40% Price, 25% Delivery, 20% Reliability, 15% Warranty)...</div>`;

    try {
      const res = await fetch('/quotes/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(samplePayload)
      });

      if (!res.ok) return;
      const data = await res.json();

      // Render 4-Factor Scoring Cards
      scoringMatrixContainer.innerHTML = data.scoring_results.map(s => `
        <div class="score-item-card" style="${s.is_recommended ? 'border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.05);' : ''}">
          <div class="score-top">
            <div>
              <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-main);">
                #${s.rank} ${escapeHtml(s.vendor)}
              </div>
              <div style="font-size: 0.74rem; color: var(--text-secondary); margin-top: 1px;">
                Quoted: <b style="color: #34d399;">${formatINR(s.quoted_price)}</b> • ${s.delivery_days} Days • ${s.warranty_years}-Yr Warranty
              </div>
            </div>
            <div class="score-large">${s.score}<span style="font-size: 0.72rem; color: var(--text-muted);">/100</span></div>
          </div>

          <div class="score-grid-4">
            <div class="sub-score-box">
              <div class="sub-score-label">Price (40%)</div>
              <div class="sub-score-value">${s.price_score}</div>
            </div>
            <div class="sub-score-box">
              <div class="sub-score-label">Delivery (25%)</div>
              <div class="sub-score-value">${s.delivery_score}</div>
            </div>
            <div class="sub-score-box">
              <div class="sub-score-label">Reliability (20%)</div>
              <div class="sub-score-value">${s.reliability_score}</div>
            </div>
            <div class="sub-score-box">
              <div class="sub-score-label">Warranty (15%)</div>
              <div class="sub-score-value">${s.warranty_score}</div>
            </div>
          </div>
        </div>
      `).join('');

      // Render Risk Alerts
      riskCountBadge.textContent = `${data.risk_alerts.length} Alert${data.risk_alerts.length === 1 ? '' : 's'}`;
      if (data.risk_alerts.length > 0) {
        riskRadarContainer.innerHTML = data.risk_alerts.map(alert => `
          <div class="risk-card risk-${alert.risk_level.toLowerCase()}">
            <div style="display: flex; justify-content: space-between; font-weight: 700;">
              <span>⚠️ ${escapeHtml(alert.vendor_name)}</span>
              <span>Level: ${alert.risk_level}</span>
            </div>
            <div style="font-weight: 600; margin-top: 2px;">${escapeHtml(alert.risk_factor)}</div>
            <div style="font-size: 0.75rem; margin-top: 2px;">${escapeHtml(alert.reason)}</div>
          </div>
        `).join('');
      } else {
        riskRadarContainer.innerHTML = `<div style="text-align: center; color: #34d399; padding: 14px;">✓ All quotes passed compliance checks.</div>`;
      }

    } catch (err) {
      console.error('Error analyzing quotes:', err);
    }
  });

  // ---------------------------------------------------------
  // Negotiation Action Trigger
  // ---------------------------------------------------------
  btnTriggerNegotiationDemo.addEventListener('click', async () => {
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
      negotiationsContainer.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 14px; font-size: 0.8rem;">No active negotiation rounds.</div>`;
      return;
    }

    negotiationsContainer.innerHTML = threads.map(t => `
      <div style="background: rgba(12, 17, 28, 0.5); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 12px 14px; margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="font-weight: 700; color: var(--text-main); font-size: 0.86rem;">
            🤝 ${escapeHtml(t.vendor_name)}
          </div>
          <span style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 0.7rem; font-weight: 700; padding: 2px 7px; border-radius: 9999px;">
            +${formatINR(t.savings_achieved)} Concession
          </span>
        </div>
        <div style="font-size: 0.74rem; color: var(--text-secondary); margin-top: 4px;">
          Initial: <strike>${formatINR(t.initial_price)}</strike> ➔ Improved: <b style="color: #34d399;">${formatINR(t.current_price)}</b>
        </div>
      </div>
    `).join('');
  }

  // ---------------------------------------------------------
  // Executive Reports Preview
  // ---------------------------------------------------------
  btnViewComparisonReport.addEventListener('click', async () => {
    try {
      const res = await fetch('/reports/comparison');
      if (!res.ok) return;
      const md = await res.text();
      document.getElementById('report-modal-title').textContent = 'Vendor Comparison Report';
      document.getElementById('report-modal-body').textContent = md;
      reportModal.classList.add('open');
    } catch (err) {
      console.error('Error fetching report:', err);
    }
  });

  btnViewNegotiationReport.addEventListener('click', async () => {
    try {
      const res = await fetch('/reports/negotiation');
      if (!res.ok) return;
      const md = await res.text();
      document.getElementById('report-modal-title').textContent = 'Negotiation Intelligence Report';
      document.getElementById('report-modal-body').textContent = md;
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

      const quotesHtml = (ticket.quotes || []).map(q => `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
          <td style="padding: 8px 10px; font-weight: 600;">
            ${q.is_recommended ? '⭐ ' : ''}${escapeHtml(q.vendor_name)}
          </td>
          <td style="padding: 8px 10px; color: #34d399; font-weight: 700;">${formatINR(q.price)}</td>
          <td style="padding: 8px 10px;">${q.delivery_days} Days</td>
          <td style="padding: 8px 10px;">${q.warranty_years} Yrs</td>
          <td style="padding: 8px 10px; color: #34d399;">${q.savings_percentage > 0 ? `+${q.savings_percentage}%` : 'Standard'}</td>
        </tr>
      `).join('');

      const content = document.getElementById('modal-ticket-content');
      content.innerHTML = `
        <div style="background: rgba(0,0,0,0.3); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); margin-bottom: 16px;">
          <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Executive Summary</div>
          <div style="font-size: 0.85rem; margin-top: 2px; color: var(--text-main);">${escapeHtml(ticket.summary || 'Summary unavailable')}</div>
        </div>

        <div style="font-weight: 700; font-size: 0.9rem; margin-bottom: 8px;">Vendor Bids Comparison</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-bottom: 16px;">
          <thead>
            <tr style="color: var(--text-muted); border-bottom: 1px solid var(--border-subtle); text-align: left;">
              <th style="padding: 6px 10px;">Vendor</th>
              <th style="padding: 6px 10px;">Quoted Price</th>
              <th style="padding: 6px 10px;">Timeline</th>
              <th style="padding: 6px 10px;">Warranty</th>
              <th style="padding: 6px 10px;">Savings</th>
            </tr>
          </thead>
          <tbody>
            ${quotesHtml || '<tr><td colspan="5">No vendor quotes recorded</td></tr>'}
          </tbody>
        </table>

        ${ticket.status === 'Approval Pending' ? `
          <div style="display: flex; gap: 10px; margin-top: 18px; border-top: 1px solid var(--border-subtle); padding-top: 16px;">
            <button class="btn btn-success btn-sm" style="flex: 1;" id="modal-btn-approve">
              ✓ Approve (${formatINR(ticket.recommended_price)})
            </button>
            <button class="btn btn-danger btn-sm" style="flex: 1;" id="modal-btn-reject">
              ✕ Reject
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
        body: JSON.stringify({ approver: 'Manager', channel: 'web' })
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
    chatInput.placeholder = "Type Email message...";
  });

  quickChips.forEach(chip => {
    chip.addEventListener('click', () => {
      chatInput.value = chip.dataset.text;
      chatInput.focus();
    });
  });

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = '';
    appendChatBubble('user', text);

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
          appendChatBubble('agent', data.reply);
        } else if (data.status === 'ticket_created') {
          const t = data.ticket;
          const msg = `
            🎉 <b>Procurement Created: <span style="color: var(--primary-light);">${t.id}</span></b><br>
            📦 <b>Item:</b> ${t.quantity}x ${t.product}<br>
            💰 <b>Budget:</b> ${formatINR(t.budget)}<br>
            🏢 <b>Recommended:</b> ${t.recommended_vendor} (${formatINR(t.recommended_price)})<br><br>
            <i>Approve or Reject?</i>
            <div style="display: flex; gap: 8px; margin-top: 8px;">
              <button class="btn btn-success btn-sm btn-sim-approve" data-id="${t.id}">Approve</button>
              <button class="btn btn-danger btn-sm btn-sim-reject" data-id="${t.id}">Reject</button>
            </div>
          `;
          appendChatBubble('agent', msg, true);

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
      appendChatBubble('agent', '⚠️ Error connecting to server.');
      console.error('Simulator error:', err);
    }
  });

  function appendChatBubble(sender, text, isHtml = false) {
    const bubble = document.createElement('div');
    bubble.className = `chat-msg ${sender}`;
    const tag = sender === 'agent' ? `<div style="font-size: 0.7rem; font-weight: 700; color: var(--primary-light); margin-bottom: 2px;">🤖 Caspian (${state.activeSimChannel.toUpperCase()})</div>` : '';

    bubble.innerHTML = `
      ${tag}
      <div>${isHtml ? text : escapeHtml(text).replace(/\n/g, '<br>')}</div>
    `;

    chatStream.appendChild(bubble);
    chatStream.scrollTop = chatStream.scrollHeight;
    return bubble;
  }

  // ---------------------------------------------------------
  // Filter & Search Controls
  // ---------------------------------------------------------
  filterTabs.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      filterTabs.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeStatusFilter = pill.dataset.status;
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

  // ---------------------------------------------------------
  // Create Modal
  // ---------------------------------------------------------
  btnOpenCreateModal.addEventListener('click', () => createModal.classList.add('open'));
  btnCloseCreateModal.addEventListener('click', () => createModal.classList.remove('open'));
  btnCancelCreate.addEventListener('click', () => createModal.classList.remove('open'));
  btnCloseTicketModal.addEventListener('click', () => ticketModal.classList.remove('open'));
  btnCloseReportModal.addEventListener('click', () => reportModal.classList.remove('open'));

  formCreateProcurement.addEventListener('submit', async (e) => {
    e.preventDefault();
    const product = document.getElementById('create-product').value;
    const quantity = parseInt(document.getElementById('create-quantity').value);
    const budget = parseFloat(document.getElementById('create-budget').value);
    const delivery_days = parseInt(document.getElementById('create-delivery').value);
    const channel = document.getElementById('create-channel').value;
    const specsRaw = document.getElementById('create-specs').value;

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

  // Initial Load & Auto-polling
  loadDashboardData();
  setInterval(loadDashboardData, 10000);
});
