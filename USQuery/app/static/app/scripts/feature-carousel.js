/**
 * Feature Carousel - Uses SimpleCarousel utility
 */

(function() {
    // Initialize carousel on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCarousel);
    } else {
        initCarousel();
    }
    
    function initCarousel() {
        // Check if SimpleCarousel class exists and initialize
        if (typeof SimpleCarousel !== 'undefined') {
            window.featureCarousel = new SimpleCarousel('.feature-carousel', {
                autoAdvanceInterval: 6000,
                pauseOnHover: true
            });
        }
    }
})();