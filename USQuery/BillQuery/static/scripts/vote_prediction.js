(function () {
    'use strict';

    // ── Read initial state from template JSON script tags ──────────────────────
    function readJSON(id) { return JSON.parse(document.getElementById(id).textContent); }

    const billId            = readJSON('vp_bill_id');
    const initialPredState  = readJSON('vp_pred_state');   // 'empty'|'ready'|'error'
    const userTier          = readJSON('vp_user_tier');    // 'guest'|'free'|'plus'|'premium'
    const initialCredits    = readJSON('vp_pred_credits'); // int or null
    const creditLimit       = readJSON('vp_pred_credit_limit') || 10; // daily allowance (Plus 10, Plus Pro 30)
    const memberUnlocked    = readJSON('vp_member_unlocked'); // bool
    const initialHouseDist  = readJSON('vp_house_dist');   // {voteCount: freq} or null
    const initialSenateDist = readJSON('vp_senate_dist');  // {voteCount: freq} or null

    const HOUSE_THRESHOLD   = 218;
    const SENATE_THRESHOLD  = 51;

    // ── Component state ────────────────────────────────────────────────────────
    const state = {
        phase:         initialPredState,   // 'empty'|'generating'|'ready'|'error'
        memberPhase:   'locked',           // 'locked'|'revealing'|'unlocked'
        budget:        initialCredits,
        houseDist:     initialHouseDist,
        senateDist:    initialSenateDist,
        houseMembers:  null,
        senateMembers: null,
        errorDetail:   null,
    };

    // Determine initial member phase
    if (initialPredState === 'ready') {
        if (userTier === 'premium' || memberUnlocked) {
            state.memberPhase = 'revealing'; // will auto-fetch immediately
        }
    }

    let fetchingMembers = false;
    let genInterval     = null;

    // ── Utilities ──────────────────────────────────────────────────────────────
    function getCsrf() {
        const c = document.cookie.split(';').map(s => s.trim()).find(s => s.startsWith('csrftoken='));
        return c ? c.split('=')[1] : '';
    }

    function escHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Probability → oklch gradient color (orange → green)
    function probColor(p) {
        const h = 42 + Math.max(0, Math.min(1, p)) * 120;
        return `oklch(0.74 0.135 ${h.toFixed(1)})`;
    }

    // ── Distribution statistics ────────────────────────────────────────────────
    function distStats(dist, threshold) {
        if (!dist) return null;
        const entries = Object.entries(dist)
            .map(([k, v]) => [parseInt(k), v])
            .sort((a, b) => a[0] - b[0]);
        if (!entries.length) return null;

        const total   = entries.reduce((s, [, v]) => s + v, 0);
        const maxCount = Math.max(...entries.map(([, v]) => v));
        let passCount  = 0, cumul = 0, pi = 0;
        const targets  = [0.05, 0.5, 0.95];
        const pcts     = {};

        for (const [k, v] of entries) {
            if (k >= threshold) passCount += v;
        }
        for (const [k, v] of entries) {
            cumul += v;
            while (pi < targets.length && cumul / total >= targets[pi]) {
                pcts[targets[pi]] = k; pi++;
            }
        }
        return {
            total, maxCount, passProb: passCount / total,
            median: pcts[0.5]  ?? entries[Math.floor(entries.length / 2)][0],
            p5:     pcts[0.05] ?? entries[0][0],
            p95:    pcts[0.95] ?? entries[entries.length - 1][0],
            minVotes: entries[0][0],
            maxVotes: entries[entries.length - 1][0],
            threshold,
        };
    }

    // ── SVG Histogram ──────────────────────────────────────────────────────────
    function buildHistSVG(dist, threshold, chamber) {
        const entries = Object.entries(dist)
            .map(([k, v]) => ({ x: parseInt(k), y: v }))
            .sort((a, b) => a.x - b.x);
        if (!entries.length) return '';

        const total  = entries.reduce((s, e) => s + e.y, 0);
        const maxY   = Math.max(...entries.map(e => e.y));
        const minX   = entries[0].x;
        const maxX   = entries[entries.length - 1].x;

        const W = 600, H = 230, padL = 52, padR = 16, padT = 16, padB = 34;
        const cW = W - padL - padR, cH = H - padT - padB;
        const n  = maxX - minX + 1;
        const bw = cW / n;

        // Y-axis gridlines (5 levels)
        let grid = '', ylbls = '';
        for (let i = 0; i <= 4; i++) {
            const frac = i / 4;
            const yp   = padT + cH * (1 - frac);
            const spct = ((maxY * frac / total) * 100).toFixed(1);
            grid  += `<line x1="${padL}" y1="${yp.toFixed(1)}" x2="${W - padR}" y2="${yp.toFixed(1)}" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>`;
            ylbls += `<text x="${padL - 5}" y="${(yp + 3.5).toFixed(1)}" text-anchor="end" fill="rgba(255,255,255,0.28)" font-size="9" font-family="monospace">${spct}%</text>`;
        }

        // Bars
        let bars = '';
        for (const { x, y } of entries) {
            const h    = (y / maxY) * cH;
            const bx   = padL + (x - minX) * bw;
            const by   = padT + cH - h;
            const fill = x >= threshold ? '#2ea87e' : '#e8833a';
            const pct  = (y / total * 100).toFixed(1);
            bars += `<rect class="vp-hist-bar" x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${Math.max(1, bw - 0.5).toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="${fill}" fill-opacity="0.72"><title>${x} Yes votes · ${pct}% of simulations</title></rect>`;
        }

        // X-axis labels (every 5 votes, auto-stepped for dense ranges)
        const xRange = maxX - minX;
        const step   = xRange > 60 ? 10 : 5;
        let xlbls    = '';
        const first  = Math.ceil(minX / step) * step;
        for (let x = first; x <= maxX; x += step) {
            const cx = padL + (x - minX + 0.5) * bw;
            xlbls += `<text x="${cx.toFixed(1)}" y="${H - 7}" text-anchor="middle" fill="rgba(255,255,255,0.28)" font-size="9.5" font-family="monospace">${x}</text>`;
        }

        // Threshold dashed line
        const tx = padL + (threshold - minX) * bw;
        const showT = threshold >= minX && threshold <= maxX + 1;
        const threshSVG = showT ? `<line x1="${tx.toFixed(1)}" y1="${padT}" x2="${tx.toFixed(1)}" y2="${(padT + cH).toFixed(1)}" stroke="#d29922" stroke-width="1.5" stroke-dasharray="5,3"/><text x="${(tx + 5).toFixed(1)}" y="${padT + 14}" fill="#d29922" font-size="9" font-family="monospace">${threshold} to pass</text>` : '';

        const chamberLabel = chamber === 'house'
            ? 'PREDICTED HOUSE FLOOR VOTE · YES COUNT'
            : 'PREDICTED SENATE FLOOR VOTE · YES COUNT';

        return `<div class="vp-hist-wrapper">
            <div class="vp-hist-header">
                <span class="vp-hist-title">${chamberLabel}</span>
                <div class="vp-hist-legend">
                    <span class="vp-legend-dot" style="background:#2ea87e88"></span><span>Passes</span>
                    <span class="vp-legend-dot" style="background:#e8833a88"></span><span>Fails</span>
                </div>
            </div>
            <svg viewBox="0 0 ${W} ${H}" class="vp-hist-svg" style="width:100%;height:auto;overflow:visible">${grid}${ylbls}${bars}${threshSVG}${xlbls}</svg>
        </div>`;
    }

    // ── Pass summary stats row ─────────────────────────────────────────────────
    function buildPassSummary(houseSt, senateSt) {
        function block(st, chamberName) {
            if (!st) return '';
            const pct     = (st.passProb * 100).toFixed(1);
            const color   = probColor(st.passProb);
            const likely  = st.passProb >= 0.5;
            const pillClr = likely ? '#2ea87e' : '#e8833a';
            const pillTxt = likely ? 'Likely to Pass' : 'Likely to Fail';
            return `<div class="vp-pass-block">
                <div class="vp-chamber-label">${chamberName}</div>
                <div class="vp-pass-row">
                    <div class="vp-stat-card vp-stat-card--main">
                        <div class="vp-stat-label">PASSAGE PROBABILITY</div>
                        <div class="vp-stat-big" style="color:${color}">${pct}%</div>
                        <span class="vp-stat-pill" style="background:${pillClr}22;color:${pillClr};border:1px solid ${pillClr}44">${pillTxt}</span>
                    </div>
                    <div class="vp-stat-card">
                        <div class="vp-stat-label">MEDIAN YES</div>
                        <div class="vp-stat-val">${st.median}</div>
                    </div>
                    <div class="vp-stat-card">
                        <div class="vp-stat-label">90% RANGE</div>
                        <div class="vp-stat-val">${st.p5}–${st.p95}</div>
                    </div>
                    <div class="vp-stat-card vp-stat-card--amber">
                        <div class="vp-stat-label">NEEDED TO PASS</div>
                        <div class="vp-stat-val">${st.threshold}</div>
                    </div>
                </div>
            </div>`;
        }
        return `<div class="vp-summary-section">${block(houseSt, 'HOUSE')}${block(senateSt, 'SENATE')}</div>`;
    }

    // ── Credit meter (Plus) ────────────────────────────────────────────────────
    function buildCreditMeter() {
        const budget = state.budget ?? 0;
        const total  = creditLimit;
        const used   = total - budget;
        let segs = '';
        for (let i = 0; i < total; i++) {
            let color;
            if (i < used)        color = '#21262d';
            else if (budget <= 0) color = '#f85149';
            else if (budget <= 3) color = '#d29922';
            else                  color = '#2ea87e';
            segs += `<span class="vp-credit-seg" style="background:${color}"></span>`;
        }
        const hint = budget <= 0
            ? 'Daily limit reached. Resets at midnight ET.'
            : 'Each generation or member reveal uses 1 credit.';
        return `<div class="vp-credit-meter">
            <div class="vp-credit-header">
                <span class="vp-credit-label">DAILY PREDICTION CREDITS</span>
                <span class="vp-credit-count">${budget} of ${total} left</span>
            </div>
            <div class="vp-credit-segs">${segs}</div>
            <div class="vp-credit-hint">${hint}</div>
        </div>`;
    }

    // ── Empty state ────────────────────────────────────────────────────────────
    const sparkIcon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#7d8590" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>`;
    const lockIcon  = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;

    function renderEmptyState() {
        const budget   = state.budget ?? 0;
        const disabled = budget <= 0 ? ' disabled' : '';
        let cta = '';

        if (userTier === 'guest') {
            cta = `<div class="vp-cta-group">
                <a href="/login/" class="vp-btn vp-btn--primary">${lockIcon}&ensp;Log in to generate a prediction</a>
                <a href="/register/" class="vp-btn vp-btn--ghost">Create an account</a>
            </div>`;
        } else if (userTier === 'free') {
            cta = `<div class="vp-upsell-box">&#9888;&ensp;Vote predictions are a Plus &amp; Premium feature. Upgrade to access AI-powered vote simulations.</div>
            <div class="vp-cta-group">
                <a href="/plans/" class="vp-btn vp-btn--primary">Upgrade to Plus</a>
                <a href="/plans/" class="vp-btn vp-btn--ghost">Compare plans</a>
            </div>`;
        } else if (userTier === 'plus') {
            cta = `<button class="vp-btn vp-btn--primary vp-btn--full" id="vp-generate-btn"${disabled}>${budget <= 0 ? 'Daily limit reached — resets at midnight ET' : 'Request a prediction'}</button>
            ${buildCreditMeter()}`;
        } else {
            cta = `<button class="vp-btn vp-btn--primary vp-btn--full" id="vp-generate-btn">Request a prediction</button>
            <div class="vp-premium-note"><span class="vp-badge vp-badge--premium">Premium</span>&ensp;Unlimited generations</div>`;
        }

        return `<div class="vp-empty">
            <div class="vp-empty-icon">${sparkIcon}</div>
            <div class="vp-empty-title">AI Vote Prediction</div>
            <div class="vp-empty-desc">Monte-Carlo simulation forecasting the bill's likelihood of passage and how each member is expected to vote.</div>
            ${cta}
        </div>`;
    }

    // ── Generating state ───────────────────────────────────────────────────────
    function renderGenerating() {
        return `<div class="vp-generating">
            <svg class="vp-spinner" width="26" height="26" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="11" stroke="#21262d" stroke-width="2.5"/><path d="M13 2a11 11 0 0 1 11 11" stroke="#388bfd" stroke-width="2.5" stroke-linecap="round"/></svg>
            <div class="vp-gen-title">Simulating floor votes…</div>
            <div class="vp-gen-count" id="vp-gen-count">0 / 1,000</div>
            <div class="vp-gen-progress"><div class="vp-gen-bar"></div></div>
            <div class="vp-hist-shimmer"></div>
        </div>`;
    }

    // ── Member row ─────────────────────────────────────────────────────────────
    function buildMemberRow(m, rank) {
        const partyColor = { D: '#388bfd', R: '#f85149', I: '#a371f7' }[m.party] || '#7d8590';
        const pct        = (m.prob * 100).toFixed(1);
        const barColor   = probColor(m.prob);
        const district   = m.district != null ? `-${m.district}` : '';
        return `<div class="vp-member-row">
            <span class="vp-member-rank">${rank}</span>
            <div class="vp-member-info">
                <span class="vp-member-name">${escHtml(m.name)}</span>
                <span class="vp-member-meta" style="color:${partyColor}">${m.party} · ${m.state}${district}</span>
            </div>
            <div class="vp-member-bar-track">
                <div class="vp-member-bar-fill" style="width:${pct}%;background:${barColor}"></div>
            </div>
            <span class="vp-member-pct" style="color:${barColor}">${pct}%</span>
        </div>`;
    }

    // ── Unlocked member list ───────────────────────────────────────────────────
    function buildUnlockedList(members, chamberId) {
        let rows = '';
        members.forEach((m, i) => { rows += buildMemberRow(m, i + 1); });
        return `<div class="vp-member-toolbar">
            <input class="vp-member-search" type="text" placeholder="Search name or state…" data-chamber="${chamberId}" id="vp-search-${chamberId}"/>
            <div class="vp-party-filters">
                <button class="vp-party-btn active" data-party="all" data-chamber="${chamberId}">All</button>
                <button class="vp-party-btn" data-party="D" data-chamber="${chamberId}" style="color:#388bfd">Dem</button>
                <button class="vp-party-btn" data-party="R" data-chamber="${chamberId}" style="color:#f85149">Rep</button>
            </div>
            <span class="vp-member-count" id="vp-count-${chamberId}">${members.length} members</span>
        </div>
        <div class="vp-member-header-row">
            <span style="width:22px;text-align:right">#</span>
            <span style="flex:1;min-width:0">MEMBER</span>
            <span style="flex:1;min-width:0;text-align:right;padding-right:8px">P(VOTES YES)</span>
        </div>
        <div class="vp-member-list" id="vp-member-list-${chamberId}" data-chamber="${chamberId}">${rows}</div>`;
    }

    // ── Blurred placeholder list ───────────────────────────────────────────────
    function buildBlurredList() {
        const names    = ['Alexander Johnson', 'Barbara Williams', 'Charles Davis', 'Diana Martinez', 'Edward Brown', 'Frances Wilson', 'George Anderson', 'Helen Thomas', 'Irving Jackson', 'Jennifer White', 'Kevin Harris', 'Lisa Thompson', 'Michael Garcia', 'Nancy Rodriguez', 'Oliver Lewis', 'Patricia Lee', 'Robert Walker', 'Sandra Hall', 'Thomas Allen', 'Victoria Young', 'William King', 'Yvonne Wright', 'Zachary Scott', 'Amanda Green', 'Brandon Adams'];
        const parties  = ['D','R','R','D','R','D','R','D','R','D','R','D','R','D','R','D','R','D','R','D','R','D','R','D','R'];
        const states   = ['TX','CA','FL','NY','PA','OH','GA','NC','MI','AZ','WA','MA','TN','IN','MO','MD','WI','CO','MN','SC','AL','LA','KY','OR','OK'];
        let rows = '';
        // Use a deterministic pseudo-random sequence so the placeholder looks natural
        const seed = (i) => ((i * 1664525 + 1013904223) & 0x7fffffff) / 0x7fffffff;
        for (let i = 0; i < names.length; i++) {
            const prob = 0.25 + seed(i) * 0.55;
            const pct  = (prob * 100).toFixed(1);
            const pc   = { D: '#388bfd', R: '#f85149', I: '#a371f7' }[parties[i]];
            rows += `<div class="vp-member-row">
                <span class="vp-member-rank">${i+1}</span>
                <div class="vp-member-info">
                    <span class="vp-member-name">${names[i]}</span>
                    <span class="vp-member-meta" style="color:${pc}">${parties[i]} · ${states[i]}</span>
                </div>
                <div class="vp-member-bar-track"><div class="vp-member-bar-fill" style="width:${pct}%;background:${probColor(prob)}"></div></div>
                <span class="vp-member-pct" style="color:${probColor(prob)}">${pct}%</span>
            </div>`;
        }
        return `<div class="vp-member-list" style="pointer-events:none;user-select:none">${rows}</div>`;
    }

    // ── Locked overlay ─────────────────────────────────────────────────────────
    function buildLockedOverlay() {
        const budget   = state.budget ?? 0;
        const disabled = budget <= 0 ? ' disabled' : '';
        let inner = '';

        if (userTier === 'plus') {
            inner = `<div class="vp-lock-badge vp-lock-badge--blue">${lockIcon}</div>
                <div class="vp-lock-title">Per-Member Predictions</div>
                <div class="vp-lock-desc">See each legislator's probability of voting Yes.</div>
                <button class="vp-btn vp-btn--primary" id="vp-reveal-btn"${disabled}>${budget <= 0 ? 'Daily limit reached — resets at midnight ET' : 'Reveal per-member predictions · 1 credit'}</button>
                ${budget > 0 ? `<div class="vp-lock-hint">${budget} of ${creditLimit} credits left today</div>` : ''}
                <div class="vp-lock-disclaimer">Once revealed, accessible for 24 hours without additional credits.</div>`;
        } else if (userTier === 'free') {
            inner = `<div class="vp-lock-badge vp-lock-badge--amber">${lockIcon}</div>
                <div class="vp-lock-title">Available on Plus &amp; Premium</div>
                <div class="vp-lock-desc">Per-member vote probabilities require a Plus or Premium plan.</div>
                <div class="vp-cta-group"><a href="/plans/" class="vp-btn vp-btn--primary">Upgrade to Plus</a><a href="/plans/" class="vp-btn vp-btn--ghost">Compare plans</a></div>`;
        } else {
            inner = `<div class="vp-lock-badge vp-lock-badge--amber">${lockIcon}</div>
                <div class="vp-lock-title">Log in to unlock</div>
                <div class="vp-lock-desc">Per-member vote probabilities require a Plus or Premium plan.</div>
                <div class="vp-cta-group"><a href="/login/" class="vp-btn vp-btn--primary">Log in</a><a href="/plans/" class="vp-btn vp-btn--ghost">See plans</a></div>`;
        }
        return `<div class="vp-locked-overlay">${inner}</div>`;
    }

    // ── Revealing overlay ──────────────────────────────────────────────────────
    function buildRevealingOverlay() {
        return `<div class="vp-locked-overlay vp-locked-overlay--dim">
            <svg class="vp-spinner" width="22" height="22" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="11" stroke="#21262d" stroke-width="2.5"/><path d="M13 2a11 11 0 0 1 11 11" stroke="#388bfd" stroke-width="2.5" stroke-linecap="round"/></svg>
            <div class="vp-lock-title">Loading members…</div>
        </div>`;
    }

    // ── Members section ────────────────────────────────────────────────────────
    function buildMembersSection() {
        const phase  = state.memberPhase;
        const premiumBadge = userTier === 'premium'
            ? `<span class="vp-badge vp-badge--premium">Premium · Unlimited</span>` : '';
        const subLbl = phase === 'unlocked'
            ? `<span class="vp-members-sub">Sorted by P(votes Yes), high → low</span>` : '';

        let houseBlock, senateBlock;

        if (phase === 'unlocked' && state.houseMembers) {
            houseBlock  = buildUnlockedList(state.houseMembers, 'house');
            senateBlock = buildUnlockedList(state.senateMembers || [], 'senate');
        } else if (phase === 'revealing') {
            houseBlock  = `<div class="vp-member-locked">${buildBlurredList()}${buildRevealingOverlay()}</div>`;
            senateBlock = '';
        } else {
            houseBlock  = `<div class="vp-member-locked">${buildBlurredList()}${buildLockedOverlay()}</div>`;
            senateBlock = '';
        }

        const senateSection = (phase === 'unlocked' || phase === 'revealing') ? `
            <div class="vp-members-chamber">
                <div class="vp-chamber-sub-label">SENATE</div>
                ${senateBlock}
            </div>` : '';

        return `<div class="vp-members-section">
            <div class="vp-members-header">
                <span class="vp-section-label">PER-MEMBER PREDICTIONS</span>
                ${premiumBadge}${subLbl}
            </div>
            <div class="vp-members-chamber">
                <div class="vp-chamber-sub-label">HOUSE OF REPRESENTATIVES</div>
                ${houseBlock}
            </div>
            ${senateSection}
        </div>`;
    }

    // ── Ready state ────────────────────────────────────────────────────────────
    function renderReady() {
        const houseSt  = distStats(state.houseDist,  HOUSE_THRESHOLD);
        const senateSt = distStats(state.senateDist, SENATE_THRESHOLD);

        const creditMeter = (userTier === 'plus' && state.memberPhase !== 'unlocked')
            ? buildCreditMeter() : '';

        return `<div class="vp-ready">
            ${buildPassSummary(houseSt, senateSt)}
            <div class="vp-histograms">
                ${buildHistSVG(state.houseDist,  HOUSE_THRESHOLD,  'house')}
                ${buildHistSVG(state.senateDist, SENATE_THRESHOLD, 'senate')}
            </div>
            <div class="vp-divider"></div>
            ${creditMeter}
            ${buildMembersSection()}
        </div>`;
    }

    // ── Error state ────────────────────────────────────────────────────────────
    function renderError() {
        const fallback = "We couldn't generate a prediction for this bill. This may be because the bill text or subject list is not yet available from the Congress API.";
        const desc = state.errorDetail
            ? String(state.errorDetail).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            : fallback;
        return `<div class="vp-empty">
            <div class="vp-empty-icon"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#f85149" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>
            <div class="vp-empty-title">Prediction Unavailable</div>
            <div class="vp-empty-desc">${desc}</div>
        </div>`;
    }

    // ── Render dispatcher ──────────────────────────────────────────────────────
    function render() {
        const el = document.getElementById('vp-content');
        if (!el) return;
        switch (state.phase) {
            case 'empty':      el.innerHTML = renderEmptyState();  break;
            case 'generating': el.innerHTML = renderGenerating();  break;
            case 'ready':      el.innerHTML = renderReady();       break;
            case 'error':      el.innerHTML = renderError();       break;
            default:           el.innerHTML = renderEmptyState();
        }
        if (state.phase === 'generating') startGenCounter();
    }

    // ── Generate prediction ────────────────────────────────────────────────────
    function generate() {
        if (state.phase === 'generating') return;
        state.phase = 'generating';
        render();

        fetch(`/bill/prediction/generate/${billId}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
        })
        .then(r => r.json())
        .then(data => {
            stopGenCounter();
            if (data.success) {
                state.phase      = 'ready';
                state.houseDist  = data.house_dist;
                state.senateDist = data.senate_dist;
                if (data.credits_remaining !== null && data.credits_remaining !== undefined) {
                    state.budget = data.credits_remaining;
                }
                state.memberPhase = data.member_reveal_unlocked ? 'revealing' : 'locked';
                render();
                if (state.memberPhase === 'revealing') fetchMembers();
            } else {
                state.phase = 'error';
                state.errorDetail = data.detail || null;
                render();
            }
        })
        .catch(() => { stopGenCounter(); state.phase = 'error'; state.errorDetail = null; render(); });
    }

    // ── Fetch per-member predictions ───────────────────────────────────────────
    function fetchMembers() {
        if (fetchingMembers) return;
        fetchingMembers = true;
        state.memberPhase = 'revealing';
        render();
        // btw you wont be able to fetch the members prediction without the proper
        // credentials coder ;)
        fetch(`/bill/prediction/members/${billId}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
        })
        .then(r => r.json())
        .then(data => {
            fetchingMembers = false;
            if (data.success) {
                state.houseMembers  = data.members_house;
                state.senateMembers = data.members_senate;
                state.memberPhase   = 'unlocked';
                if (data.credits_remaining !== null && data.credits_remaining !== undefined) {
                    state.budget = data.credits_remaining;
                }
            } else {
                state.memberPhase = 'locked';
            }
            render();
        })
        .catch(() => { fetchingMembers = false; state.memberPhase = 'locked'; render(); });
    }

    // ── Counter animation ──────────────────────────────────────────────────────
    function startGenCounter() {
        let n = 0;
        genInterval = setInterval(() => {
            n = Math.min(900, n + Math.floor(Math.random() * 60 + 20));
            const el = document.getElementById('vp-gen-count');
            if (el) el.textContent = n.toLocaleString() + ' / 1,000';
        }, 150);
    }

    function stopGenCounter() {
        clearInterval(genInterval);
        genInterval = null;
        const el = document.getElementById('vp-gen-count');
        if (el) el.textContent = '1,000 / 1,000';
    }

    // ── Filter members ─────────────────────────────────────────────────────────
    function filterMembers(chamber) {
        const members = chamber === 'house' ? state.houseMembers : state.senateMembers;
        if (!members) return;
        const card    = document.getElementById('vote-prediction-card');
        const listEl  = card && card.querySelector(`#vp-member-list-${chamber}`);
        const countEl = card && card.querySelector(`#vp-count-${chamber}`);
        if (!listEl) return;

        const query    = card.querySelector(`#vp-search-${chamber}`)?.value.toLowerCase() || '';
        const party    = card.querySelector(`.vp-party-btn.active[data-chamber="${chamber}"]`)?.dataset.party || 'all';

        let filtered = members;
        if (query)          filtered = filtered.filter(m => m.name.toLowerCase().includes(query) || m.state.toLowerCase().includes(query));
        if (party !== 'all') filtered = filtered.filter(m => m.party === party);

        let rows = '';
        filtered.forEach((m, i) => { rows += buildMemberRow(m, i + 1); });
        listEl.innerHTML = rows;
        if (countEl) countEl.textContent = `${filtered.length} members`;
    }

    // ── Event delegation (attach once to stable container) ────────────────────
    function initHandlers() {
        const card = document.getElementById('vote-prediction-card');
        if (!card) return;

        card.addEventListener('click', function (e) {
            const btn = e.target.closest('button');
            if (!btn) return;

            if (btn.id === 'vp-generate-btn' && !btn.disabled) {
                e.preventDefault();
                generate();
            } else if (btn.id === 'vp-reveal-btn' && !btn.disabled) {
                e.preventDefault();
                fetchMembers();
            } else if (btn.classList.contains('vp-party-btn')) {
                const chamber = btn.dataset.chamber;
                card.querySelectorAll(`.vp-party-btn[data-chamber="${chamber}"]`)
                    .forEach(b => b.classList.toggle('active', b === btn));
                filterMembers(chamber);
            }
        });

        card.addEventListener('input', function (e) {
            const input = e.target.closest('.vp-member-search');
            if (input) filterMembers(input.dataset.chamber);
        });
    }

    // ── Init ───────────────────────────────────────────────────────────────────
    render();
    initHandlers();

    // Auto-fetch members for authorized users who already have a prediction
    if (state.phase === 'ready' && state.memberPhase === 'revealing') {
        fetchMembers();
    }

})();
