// Bill timeline (status pipeline) renderer: not included in the public snapshot.
(function () {
    'use strict';
    var el = document.getElementById('pipeline_data');
    if (el && el.parentElement) {
        el.parentElement.setAttribute('data-pipeline', 'unavailable');
    }
})();
