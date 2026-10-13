// Keeps paired start_date / end_date inputs in order.
//
// Setting min/max on the native date pickers means the browser refuses the submit
// with its own message, so a backwards window never reaches the server. The forms
// validate the same rule server-side as well - a hand-built query string never
// passes through these inputs at all.
document.addEventListener("DOMContentLoaded", function () {
    const forms = document.querySelectorAll("form");

    forms.forEach(function (form) {
        const start = form.querySelector('input[name="start_date"]');
        const end = form.querySelector('input[name="end_date"]');

        if (!start || !end) {
            return;
        }

        function sync() {
            // An empty string clears the constraint, which is what we want while
            // either field is still blank (both are optional on the keyword forms).
            end.min = start.value || "";
            start.max = end.value || "";
        }

        start.addEventListener("change", sync);
        end.addEventListener("change", sync);
        sync();
    });
});
