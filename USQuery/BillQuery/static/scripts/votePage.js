(function () {
    // ---- Tab switching ----
    var tabs = document.querySelectorAll('.vote-tab');
    var groups = document.querySelectorAll('[data-vote-group]');
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            tabs.forEach(function (t) { t.classList.remove('active'); });
            this.classList.add('active');
            var target = this.dataset.target;
            groups.forEach(function (g) {
                g.style.display = (target === 'all' || g.dataset.voteGroup === target) ? '' : 'none';
            });
        });
    });

    // ---- Member row transformation ----
    var PARTY_COLORS = {
        D: { bg: 'rgba(29,78,216,0.12)',   border: 'rgba(29,78,216,0.45)',   text: 'rgb(96,165,250)' },
        R: { bg: 'rgba(220,38,38,0.12)',   border: 'rgba(220,38,38,0.45)',   text: 'rgb(248,113,113)' },
        I: { bg: 'rgba(200,200,200,0.12)', border: 'rgba(200,200,200,0.45)', text: 'rgb(200,200,200)' },
        L: { bg: 'rgba(224,201,11,0.12)',  border: 'rgba(224,201,11,0.45)',  text: 'rgb(251,191,36)' },
        G: { bg: 'rgba(11,137,11,0.12)',   border: 'rgba(11,137,11,0.45)',   text: 'rgb(74,222,128)' }
    };
    var VOTE_BADGE_LABEL = { yeas: 'Yea', nays: 'Nay', pres: 'Present', novt: 'No Vote' };

    groups.forEach(function (group) {
        var voteType = group.dataset.voteGroup;
        var badgeLabel = VOTE_BADGE_LABEL[voteType];
        group.querySelectorAll('tr').forEach(function (row) {
            var link = row.querySelector('a');
            if (!link) return;
            var text = link.textContent.trim();
            var m = text.match(/^(.+?)\s*\[([A-Z])\]\s*\((.+?)\)$/);
            if (!m) return;
            var name = m[1].trim(), party = m[2], location = m[3];
            var words = name.split(/\s+/);
            var initials = (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase();
            var c = PARTY_COLORS[party] || PARTY_COLORS.I;
            var imgSrc = link.dataset.img;
            var hasImage = imgSrc && imgSrc !== 'empty';

            var avatarInner = hasImage
                ? '<img class="vote-member-avatar-img" data-src="' + imgSrc + '" alt="' + name + '">' +
                  '<span class="vote-member-avatar-initials">' + initials + '</span>'
                : initials;

            link.className = 'vote-member-row-inner text-decoration-none';
            link.innerHTML =
                '<div class="vote-member-avatar' + (hasImage ? ' vote-member-avatar--has-img' : '') +
                '" style="background:' + c.bg + ';border-color:' + c.border + ';color:' + c.text + '">' +
                avatarInner + '</div>' +
                '<div class="vote-member-info-wrap">' +
                '<div class="vote-member-name">' + name + '</div>' +
                '<div class="vote-member-sub">' + party + ' \xB7 ' + location + '</div>' +
                '</div>' +
                '<span class="vote-type-badge vote-type-badge--' + voteType + '">' + badgeLabel + '</span>';
            row.className = 'vote-member-row';
        });
    });

    // Initialize lazy loading for member avatar images
    if (typeof initializeLazyLoad === 'function') {
        initializeLazyLoad('.vote-member-list', {
            bufferPx: 500,
            onImageLoad: function (img) {
                var initSpan = img.nextElementSibling;
                if (initSpan) initSpan.style.display = 'none';
            },
            onImageError: function (img) {
                img.style.display = 'none';
            }
        });
    }

    // ---- Abstract State Map ----
    var mapEl = document.getElementById('state-map');
    var IS_HOUSE = mapEl && mapEl.dataset.isHouse === '1';
    var values = JSON.parse(document.getElementById('values').textContent);
    var geoids = JSON.parse(document.getElementById('geoids').textContent);

    var STATE_BY_IDX = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IN','IL','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'];
    var FIPS_TO_ABBR = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV','55':'WI','56':'WY','11':'DC'};
    var STATE_GRID = {AK:[0,5],ME:[11,0],VT:[10,0],NH:[11,1],WA:[0,0],MT:[2,0],ND:[3,0],MN:[4,0],WI:[5,0],MI:[6,0],NY:[9,0],OR:[0,1],ID:[2,1],WY:[3,1],SD:[4,1],IL:[5,1],IN:[6,1],OH:[7,1],PA:[8,1],MA:[10,1],CA:[0,2],NV:[1,2],UT:[2,2],CO:[3,2],NE:[4,2],IA:[5,2],KY:[6,2],WV:[7,2],VA:[8,2],NJ:[9,2],CT:[10,2],RI:[11,2],AZ:[1,3],NM:[2,3],KS:[4,3],MO:[5,3],TN:[6,3],NC:[7,3],SC:[8,3],MD:[9,3],DE:[10,3],TX:[3,4],OK:[4,4],AR:[5,4],MS:[6,4],AL:[7,4],GA:[8,4],DC:[9,4],LA:[5,5],FL:[9,5],HI:[1,6]};
    var VOTE_FILL   = ['rgba(239,68,68,0.18)','rgba(16,185,129,0.18)','rgba(245,158,11,0.18)','rgba(107,114,128,0.14)'];
    var VOTE_STROKE = ['#EF4444','#10B981','#F59E0B','#6B7280'];
    var stateColors = {};

    if (!IS_HOUSE) {
        for (var idx = 0; idx < 50; idx++) {
            var abbr = STATE_BY_IDX[idx];
            var counts = [values[0][idx], values[1][idx], values[2][idx], values[3][idx]];
            var tot = counts[0] + counts[1] + counts[2] + counts[3];
            if (tot === 0) {
                stateColors[abbr] = { fill: 'rgba(100,100,100,0.08)', stroke: 'rgba(150,150,150,0.28)' };
            } else {
                var mi = 0;
                for (var k = 1; k < 4; k++) { if (counts[k] > counts[mi]) mi = k; }
                stateColors[abbr] = { fill: VOTE_FILL[mi], stroke: VOTE_STROKE[mi] };
            }
        }
    } else {
        var stateCounts = {};
        for (var j = 0; j < geoids.length; j++) {
            if (!geoids[j]) continue;
            var fips = String(geoids[j]).slice(0, 2);
            var st = FIPS_TO_ABBR[fips];
            if (!st) continue;
            if (!stateCounts[st]) stateCounts[st] = [0, 0, 0, 0];
            stateCounts[st][values[j]]++;
        }
        Object.keys(stateCounts).forEach(function (ab) {
            var ct = stateCounts[ab];
            var mi2 = 0;
            for (var k = 1; k < 4; k++) { if (ct[k] > ct[mi2]) mi2 = k; }
            stateColors[ab] = { fill: VOTE_FILL[mi2], stroke: VOTE_STROKE[mi2] };
        });
    }

    var CELL = 32, TOTAL = 35;
    var W = 12 * TOTAL - 3, H = 7 * TOTAL - 3;
    var parts = ['<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" style="display:block;max-width:100%;height:auto">'];
    Object.keys(STATE_GRID).forEach(function (ab) {
        var pos = STATE_GRID[ab];
        var x = pos[0] * TOTAL, y = pos[1] * TOTAL;
        var c = stateColors[ab] || { fill: 'rgba(100,100,100,0.08)', stroke: 'rgba(150,150,150,0.28)' };
        parts.push(
            '<g><rect x="' + x + '" y="' + y + '" width="' + CELL + '" height="' + CELL + '" rx="4"' +
            ' fill="' + c.fill + '" stroke="' + c.stroke + '" stroke-width="1.5"/>' +
            '<text x="' + (x + 14) + '" y="' + (y + 15) + '" text-anchor="middle" dominant-baseline="middle"' +
            ' font-size="7.5" font-weight="600" fill="rgba(250,250,250,0.85)" font-family="monospace">' + ab + '</text></g>'
        );
    });
    parts.push('</svg>');
    mapEl.innerHTML = parts.join('');
}());
