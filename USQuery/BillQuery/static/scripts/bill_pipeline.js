(function () {
    const dataEl = document.getElementById('pipeline_data');
    if (!dataEl) return;

    const { status_code: sc, origin, outer, conf_in_history: confHist, veto_in_history: vetoHist, passed } =
        JSON.parse(dataEl.textContent);

    const isConf = sc >= 50 && sc <= 59;
    const isVeto = sc >= 70 && sc <= 79;

    function dot(c) {
        return `<div class="pipeline-dot pipeline-dot--${c}"></div>`;
    }

    function step(c, title, label) {
        return `<div class="pipeline-step"><span class="pipeline-section-title">${title}</span>${dot(c)}<span class="pipeline-label pipeline-label--${c}">${label}</span></div>`;
    }

    function mstep(title, items) {
        const rows = items.map(([c, t]) =>
            `<div class="pipeline-multi-item">${dot(c)}<span class="pipeline-multi-label pipeline-multi-label--${c}">${t}</span></div>`
        ).join('');
        return `<div class="pipeline-step pipeline-step--multi"><span class="pipeline-section-title">${title}</span>${rows}</div>`;
    }

    function conn(done) {
        return `<div class="pipeline-connector${done ? ' pipeline-connector--done' : ''}"></div>`;
    }

    const parts = [];

    // Introduced
    const ic = sc === 9 ? 'red' : sc >= 0 ? 'green' : 'gray';
    const il = sc === 9 ? 'Expired' : 'Introduced';
    parts.push(step(ic, 'Intro', il));
    parts.push(conn(sc >= 10));

    if (isConf || confHist) {
        let items;
        if (sc === 50) {
            items = [['blue', `${origin}: Awaiting Report`], ['blue', `${outer}: Awaiting Report`]];
        } else if (sc >= 51 && sc <= 53) {
            items = [['blue', `${origin}: Considering Report`], ['blue', `${outer}: Considering Report`]];
        } else if (sc === 54) {
            items = [['green', `${origin}: Passed`], ['blue', `${outer}: Considering Report`]];
        } else if (sc === 59) {
            items = [['red', 'Expired in Conference'], ['red', 'Expired in Conference']];
        } else {
            items = [['green', `${origin}: Passed`], ['green', `${outer}: Passed`]];
        }
        parts.push(mstep('Conference', items));
        parts.push(conn(sc >= 60 || isVeto));

    } else {
        // Origin chamber
        let oc, ol;
        if (sc < 10)                     { oc = 'gray';  ol = '...'; }
        else if (sc === 10)              { oc = 'blue';  ol = 'In Committee'; }
        else if (sc === 19)              { oc = 'red';   ol = 'Expired in Committee'; }
        else if (sc === 20)              { oc = 'blue';  ol = `Reported to ${origin}`; }
        else if (sc === 28)              { oc = 'red';   ol = 'Expired on Floor'; }
        else if (sc === 21)              { oc = 'green'; ol = `Amended, awaiting ${outer}`; }
        else if (sc === 22)              { oc = 'green'; ol = 'Passed amended bill'; }
        else if (sc === 25)              { oc = 'green'; ol = 'Passed'; }
        else if (sc === 27 || sc === 29) { oc = 'green'; ol = 'Expired after Passed'; }
        else if (sc === 41)              { oc = 'blue';  ol = 'Received Amended Bill'; }
        else                             { oc = 'green'; ol = 'Passed'; }
        parts.push(step(oc, origin, ol));
        // connector is done only if origin completed AND bill reached outer (27-29 = expired before outer)
        parts.push(conn((sc >= 21 && sc < 27) || sc >= 30));

        // Outer chamber
        let xc, xl;
        if (sc === 27 || sc === 28 || sc === 29) { xc = 'gray';  xl = '...'; }
        else if (sc === 21)                      { xc = 'blue';  xl = 'Received Amended Bill'; }
        else if (sc < 30)                        { xc = 'gray';  xl = `In ${outer}`; }
        else if (sc === 30)                      { xc = 'blue';  xl = 'In Committee'; }
        else if (sc === 39)                      { xc = 'red';   xl = 'Expired in Committee'; }
        else if (sc === 40)                      { xc = 'blue';  xl = `Reported to ${outer}`; }
        else if (sc === 41)                      { xc = 'green'; xl = `Amended, awaiting ${origin}`; }
        else if (sc === 42)                      { xc = 'green'; xl = 'Passed amended bill'; }
        else if (sc === 45)                      { xc = 'green'; xl = 'Passed'; }
        else if (sc === 47 || sc === 49)         { xc = 'green'; xl = 'Expired after Passed'; }
        else if (sc === 48)                      { xc = 'red';   xl = 'Expired on Floor'; }
        else if (sc >= 60 || isVeto)             { xc = 'green'; xl = 'Passed'; }
        else                                     { xc = 'gray';  xl = '...'; }
        parts.push(step(xc, outer, xl));
        parts.push(conn(sc >= 60 || isVeto));
    }

    // Presidential Action
    if (isVeto || vetoHist) {
        let vitems;
        if (sc === 75 || (passed && vetoHist)) {
            vitems = [
                ['green', `Override passed in ${origin}`],
                ['green', `Override passed in ${outer}`],
                ['green', 'Veto overridden'],
            ];
        } else if (sc === 71) {
            vitems = [
                ['green', `Override passed in ${origin}`],
                ['gray', outer],
                ['red', 'Vetoed'],
            ];
        } else if (sc === 72) {
            vitems = [
                ['gray', origin],
                ['green', `Override passed in ${outer}`],
                ['red', 'Vetoed'],
            ];
        } else if (sc === 76) {
            vitems = [
                ['red', `Override failed in ${origin}`],
                ['gray', outer],
                ['red', 'Vetoed'],
            ];
        } else if (sc === 77) {
            vitems = [
                ['gray', origin],
                ['red', `Override failed in ${outer}`],
                ['red', 'Vetoed'],
            ];
        } else {
            vitems = [['gray', origin], ['gray', outer], ['red', 'Vetoed']];
        }
        parts.push(mstep('Pres. Veto', vitems));
    } else {
        let pc, pl;
        if (sc === 49)      { pc = 'gray';  pl = 'Expired Before Enrollment'; }
        else if (sc === 60) { pc = 'blue';  pl = 'Enrolled'; }
        else if (sc === 61) { pc = 'green'; pl = 'Became Law w/ Signature'; }
        else if (sc === 62) { pc = 'green'; pl = 'Became Law w/o Signature'; }
        else if (sc === 63) { pc = 'green'; pl = 'Became Law over Veto'; }
        else if (sc === 69) { pc = 'red';   pl = 'Pocket Vetoed'; }
        else                { pc = 'gray';  pl = '...'; }
        parts.push(step(pc, 'Pres. Act.', pl));
    }

    const container = document.getElementById('bill-status-pipeline');
    if (container) {
        container.innerHTML = `<div class="status-pipeline">${parts.join('')}</div>`;
    }
})();
