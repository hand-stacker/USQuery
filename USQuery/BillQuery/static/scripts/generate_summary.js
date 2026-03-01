// Expects a button with id="generate-summary" and data-endpoint attribute
// that contains the POST endpoint URL for summary generation.
// Uses the CSRF cookie named 'csrftoken'.

(function () {
    'use strict';
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    document.addEventListener('DOMContentLoaded', function () {
        const btn = document.getElementById('generate-summary');
        if (!btn) return;

        const endpoint = btn.getAttribute('data-endpoint');
        if (!endpoint) return;

        const summaryContainer = document.getElementById('bill-summary');

        btn.addEventListener('click', async function () {
            btn.disabled = true;
            const originalText = btn.innerText;
            btn.innerText = 'Generating...';

            try {
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'Accept': 'application/json'
                    }
                });

                if (!resp.ok) {
                    let errText = await resp.text();
                    throw new Error(`Server returned ${resp.status}: ${errText}`);
                }

                const data = await resp.json();
                if (data.status === 'ok') {
                    if (summaryContainer) summaryContainer.innerHTML = data.summary || '';
                    // hide the button after success
                    btn.style.display = 'none';
                } else {
                    // show error message to user
                    alert('Error generating summary: ' + (data.message || 'Unknown error'));
                    btn.disabled = false;
                    btn.innerText = originalText;
                }
            } catch (err) {
                console.error('Error generating summary:', err);
                alert('Failed to generate summary. Log in or try again later.');
                btn.disabled = false;
                btn.innerText = originalText;
            }
        });
    });
})();