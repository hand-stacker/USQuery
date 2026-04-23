/**
 * Bill Details Carousel Tab Switcher
 * Handles navigation between sponsor, subjects, and related bills tabs
 */

document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('.carousel-tab');
    const panes = document.querySelectorAll('.carousel-pane');

    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');

            // Remove active class from all tabs and panes
            tabs.forEach(t => t.classList.remove('active'));
            panes.forEach(p => p.classList.remove('active'));

            // Add active class to clicked tab and corresponding pane
            this.classList.add('active');
            const targetPane = document.getElementById(`carousel-${targetTab}`);
            if (targetPane) {
                targetPane.classList.add('active');
            }
        });
    });
});