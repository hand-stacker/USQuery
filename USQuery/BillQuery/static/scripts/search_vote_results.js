// search_vote_results.js - Display vote search results with proper client-side pagination

const ITEMS_PER_PAGE = 10;

// Global pagination state
let votesState = {
    currentPage: 0,
    data: [],
    totalPages: 0,
    totalResults: 0
};

let selectedSubjects = [];

// Initialize pagination state
function initializePagination() {
    // Parse JSON from script tags
    const votesScriptElement = document.getElementById('votes_json');
    const selectedSubjectsElement = document.getElementById('selected_subjects_json');
    
    votesState.data = votesScriptElement ? JSON.parse(votesScriptElement.textContent) : [];
    selectedSubjects = selectedSubjectsElement ? JSON.parse(selectedSubjectsElement.textContent) : [];
    
    // Calculate total pages based on ALL results (from server pagination context)
    votesState.totalResults = VOTES_TOTAL_RESULTS;
    votesState.totalPages = Math.ceil(VOTES_TOTAL_RESULTS / ITEMS_PER_PAGE);
    
    // Get current page from URL parameters, default to 1 (global page 1)
    const urlParams = new URLSearchParams(window.location.search);
    const serverPage = parseInt(urlParams.get('page')) || 1;
    
    // Convert server page (1-indexed, 50 items per page) to global page (0-indexed, 10 items per page)
    const firstItemIndex = (serverPage - 1) * 50;
    votesState.currentPage = Math.floor(firstItemIndex / ITEMS_PER_PAGE);
}

// Build vote URL
function getVoteURL(voteId) {
    return `/bill-query/vote/${voteId}`;
}

// Build bill URL from vote data
function getBillURL(vote) {
    if (!vote.bill_id || !vote.bill_type_url || !vote.bill_number) {
        return null;
    }
    // Extract congress from vote ID (first part before chamber bit)
    const congress = Math.floor(vote.vote_id / 10000000);
    return `/bill-query/bill/${congress}/${vote.bill_type_url}/${vote.bill_number}`;
}

// Update pagination button states based on current page
function updatePaginationButtons() {
    const firstBtn = document.getElementById('votes-first');
    const prevBtn = document.getElementById('votes-prev');
    const nextBtn = document.getElementById('votes-next');
    const lastBtn = document.getElementById('votes-last');
    
    const firstItem = document.getElementById('votes-first-item');
    const prevItem = document.getElementById('votes-prev-item');
    const nextItem = document.getElementById('votes-next-item');
    const lastItem = document.getElementById('votes-last-item');
    
    // Disable first/prev at start
    if (votesState.currentPage === 0) {
        firstBtn.disabled = true;
        prevBtn.disabled = true;
        firstItem.classList.add('disabled');
        prevItem.classList.add('disabled');
    } else {
        firstBtn.disabled = false;
        prevBtn.disabled = false;
        firstItem.classList.remove('disabled');
        prevItem.classList.remove('disabled');
    }
    
    // Disable next/last at end
    if (votesState.currentPage >= votesState.totalPages - 1) {
        nextBtn.disabled = true;
        lastBtn.disabled = true;
        nextItem.classList.add('disabled');
        lastItem.classList.add('disabled');
    } else {
        nextBtn.disabled = false;
        lastBtn.disabled = false;
        nextItem.classList.remove('disabled');
        lastItem.classList.remove('disabled');
    }
}

// Render votes for current page
function renderVotesPage() {
    const list = document.getElementById('votes-list');
    const empty = document.getElementById('votes-empty');
    const pagination = document.getElementById('votes-pagination');
    const pageInfo = document.getElementById('votes-page-info');

    if (votesState.data.length === 0 && votesState.totalResults === 0) {
        empty.classList.remove('d-none');
        list.innerHTML = '';
        pagination.classList.add('d-none');
        return;
    }

    empty.classList.add('d-none');
    pagination.classList.remove('d-none');

    // Calculate which votes to show based on global page number
    const start = votesState.currentPage * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    
    // Calculate which server page we need to be on
    const serverPageNeeded = Math.floor(start / 50) + 1;
    const currentServerPage = VOTES_CURRENT_SERVER_PAGE;
    
    // If we need a different server page, navigate to it
    if (serverPageNeeded !== currentServerPage) {
        // Build URL to the correct server page
        let newUrl = (VOTES_URL_PARAMS + `page=${serverPageNeeded}`).replaceAll("amp;", "");
        window.location.href = `?${newUrl}`;
        return;
    }
    
    // Now calculate position within current server page's data
    const positionInServerPage = start % 50;
    const positionEnd = positionInServerPage + ITEMS_PER_PAGE;
    const pageItems = votesState.data.slice(positionInServerPage, positionEnd);

    list.innerHTML = pageItems.map(vote => {
        const voteURL = getVoteURL(vote.vote_id);
        const billURL = getBillURL(vote);
        const voteDate = vote.date 
            ? new Date(vote.date).toLocaleDateString() 
            : 'N/A';
        const billDisplay = vote.bill_type_url && vote.bill_number
            ? `${vote.bill_type_url.toUpperCase()}-${vote.bill_number}`
            : 'Unknown';
        
        // Render matching subjects horizontally
        const subjectsHtml = vote.subjects && vote.subjects.length > 0
            ? `<div class="search-vote-subjects">
                <div class="subjects-scroll">
                    ${vote.subjects.map(subject => 
                        `<span class="subject-tag">${subject.name}</span>`
                    ).join('')}
                </div>
            </div>`
            : '';

        return `
            <div class="col-md-6 mb-4">
                <a href="${voteURL}" class="starred-item">
                    <div class="starred-vote-card">
                        <div class="starred-vote-date">${voteDate}</div>
                        <div class="starred-vote-bill-display">[${billDisplay}]-${vote.bill_title}</div>
                        <div class="starred-vote-question">${vote.question}</div>
                        <div class="starred-vote-result">
                            <span>Result:</span>
                            <span class="px-2 fw-bold">${vote.result}</span>
                        </div>
                        ${subjectsHtml}
                    </div>
                </a>
            </div>
        `;
    }).join('');

    // Update page info - show the GLOBAL page number
    pageInfo.textContent = `Page ${votesState.currentPage + 1} of ${votesState.totalPages}`;
    
    // Update button states
    updatePaginationButtons();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializePagination();
    
    // Render initial page
    renderVotesPage();

    // Handle pagination button clicks
    document.getElementById('votes-first').addEventListener('click', function() {
        votesState.currentPage = 0;
        renderVotesPage();
        window.scrollTo(0, 0);
    });

    document.getElementById('votes-prev').addEventListener('click', function() {
        if (votesState.currentPage > 0) {
            votesState.currentPage--;
            renderVotesPage();
            window.scrollTo(0, 0);
        }
    });

    document.getElementById('votes-next').addEventListener('click', function() {
        if (votesState.currentPage < votesState.totalPages - 1) {
            votesState.currentPage++;
            renderVotesPage();
            window.scrollTo(0, 0);
        }
    });

    document.getElementById('votes-last').addEventListener('click', function() {
        votesState.currentPage = votesState.totalPages - 1;
        renderVotesPage();
        window.scrollTo(0, 0);
    });
});