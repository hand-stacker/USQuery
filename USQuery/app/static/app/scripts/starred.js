// starred.js - Handle starring/unstarring bills and members

const ENDPOINT = '/';

// Helper to read a cookie value (used to get CSRF token)
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// GraphQL query/mutation helper
async function APIRequest(path, variables = {}) {

    // Build headers and include CSRF token. Send variables in the POST body.
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') || '',
        'CSRFToken': getCookie('csrftoken') || '',
    };

    const response = await fetch(ENDPOINT + path, {
        method: 'POST',
        credentials: 'same-origin',
        headers,
        body: JSON.stringify(variables || {}),
    });

    const result = await response.json();

    if (result.errors) {
        throw new Error(result.errors[0].message);
    }
    if (result.error) {
        throw new Error(result.error.__all__[0]);
    }
    return result.status;
}

// Star/unstar bill
async function toggleStarBill(billId) {
    const btn = document.getElementById('star-bill-btn');
    const isStarred = btn.classList.contains('starred');

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin star-btn-spinner"></i><span>Loading...</span>';

    try {
        const path = isStarred ? 'unstar-item/' : 'star-item/';
        const result = await APIRequest(path, { "bill_id" : billId });

        // Update button state
        if (result == 'starred') {
            btn.classList.add('starred');
            btn.innerHTML = '<i class="fas fa-star"></i><span>Unstar</span>';
        } else if (result == 'unstarred') {
            btn.classList.remove('starred');
            btn.innerHTML = '<i class="far fa-star"></i><span>Star</span>';
        } else {
            throw new Error('Unexpected response from server. Please log in and try again.');
        }

    } catch (error) {
        if (error.message && (error.message.includes('Authentication required') || error.message.includes('Session expired'))) {
            window.location.href = '/login/';
            return;
        }
        alert('Error: ' + (error.message || String(error)));
        // Reset button to previous state
        const isStarred = btn.classList.contains('starred');
        btn.innerHTML = isStarred 
            ? '<i class="fas fa-star"></i><span>Unstar</span>'
            : '<i class="far fa-star"></i><span>Star</span>';
    } finally {
        btn.disabled = false;
    }
}

// Star/unstar membership
async function toggleStarMembership(membershipId) {
    const btn = document.getElementById('star-member-btn');
    const isStarred = btn.classList.contains('starred');

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin star-btn-spinner"></i><span>Loading...</span>';

    try {
        const path = isStarred ? 'unstar-item/' : 'star-item/';
        const result = await APIRequest(path, { 'membership_id' : membershipId });

        // Update button state
        if (result == 'starred') {
            btn.classList.add('starred');
            btn.innerHTML = '<i class="fas fa-star"></i><span>Unstar</span>';
        } else if (result == 'unstarred') {
            btn.classList.remove('starred');
            btn.innerHTML = '<i class="far fa-star"></i><span>Star</span>';
        } else {
            throw new Error('Unexpected response from server. Please log in and try again.');
        }

    } catch (error) {
        if (error.message && (error.message.includes('Authentication required') || error.message.includes('Session expired'))) {
            window.location.href = '/login/';
            return;
        }
        alert('Error: ' + (error.message || String(error)));
        // Reset button to previous state
        const isStarred = btn.classList.contains('starred');
        btn.innerHTML = isStarred 
            ? '<i class="fas fa-star"></i><span>Unstar</span>'
            : '<i class="far fa-star"></i><span>Star</span>';
    } finally {
        btn.disabled = false;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    const starBtn = document.getElementById('star-bill-btn');
    if (starBtn) {
        const billId = parseInt(starBtn.dataset.billId);

        starBtn.addEventListener('click', function() {
            if (!loggedIn) {
                alert('You must be logged in to star bills. Redirecting to login...');
                window.location.href = '/login/';
                return;
            }
            toggleStarBill(billId);
        });
    }

    const starMemberBtn = document.getElementById('star-member-btn');
    if (starMemberBtn) {
        const membershipId = parseInt(starMemberBtn.dataset.membershipId);

        starMemberBtn.addEventListener('click', function() {
            if (!loggedIn) {
                alert('You must be logged in to star members. Redirecting to login...');
                window.location.href = '/login/';
                return;
            }
            toggleStarMembership(membershipId);
        });
    }
});