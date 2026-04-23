/**
 * Member Image Modal - Reusable modal for member profile images
 * Handles normalized square images with popup functionality
 */

(function() {
    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMemberImageModal);
    } else {
        initMemberImageModal();
    }

    function initMemberImageModal() {
        const imageContainer = document.querySelector('.member-image-container');
        const memberImage = document.querySelector('.member-image-normalized');
        const modal = document.getElementById('memberImageModal');
        const modalImage = document.getElementById('modalImage');

        if (!imageContainer || !memberImage || !modal) {
            return;
        }

        // Open modal on image click
        imageContainer.addEventListener('click', function() {
            const fullSrc = memberImage.getAttribute('data-full-src');
            modalImage.src = fullSrc || memberImage.src;
            
            // Use Bootstrap modal if available
            if (typeof bootstrap !== 'undefined') {
                const bsModal = new bootstrap.Modal(modal);
                bsModal.show();
            }
        });

        // Prevent event bubbling if clicked inside modal
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                if (typeof bootstrap !== 'undefined') {
                    bootstrap.Modal.getInstance(modal)?.hide();
                }
            }
        });
    }
})();