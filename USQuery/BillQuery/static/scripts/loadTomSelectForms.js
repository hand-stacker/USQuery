document.addEventListener("DOMContentLoaded", function () {
    const selectElement = document.querySelector("#id_bill_subjects");

    if (selectElement) {
        new TomSelect(selectElement, {
            plugins: ["remove_button"],
            persist: false,
            create: false,
            maxItems: null,
            searchField: "text",
            closeAfterSelect: false,
        });
    }

    const selectElement2 = document.querySelector("#id_vote_subjects");

    if (selectElement2) {
        new TomSelect(selectElement2, {
            plugins: ["remove_button"],
            persist: false,
            create: false,
            maxItems: null,
            searchField: "text",
            closeAfterSelect: false,
        });
    }

    // Serialize vote subjects into a single comma-separated query param on submit
    const voteForm = document.getElementById("id_VoteForm");
    const voteHiddenId = "id_vote_subjects_csv";
    if (voteForm && selectElement2) {
        voteForm.addEventListener("submit", function (e) {
            const selected = Array.from(selectElement2.selectedOptions).map(opt => opt.value).filter(Boolean);
            // Remove any existing hidden if nothing selected
            const existingHidden = document.getElementById(voteHiddenId);
            if (selected.length === 0) {
                if (existingHidden) {
                    existingHidden.remove();
                }
                selectElement2.disabled = false;
                return;
            }
            selectElement2.disabled = true;

            // Reuse existing hidden input if present, otherwise create it
            let hidden = existingHidden;
            if (!hidden) {
                hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.id = voteHiddenId;
                hidden.name = "vote_subjects";
                voteForm.appendChild(hidden);
            }
            hidden.value = selected.join(",");
        });
    }

    // Serialize bill subjects into a single comma-separated query param on submit
    const billForm = document.getElementById("id_BillForm");
    const billHiddenId = "id_bill_subjects_csv";
    if (billForm && selectElement) {
        billForm.addEventListener("submit", function (e) {
            const selected = Array.from(selectElement.selectedOptions).map(opt => opt.value).filter(Boolean);
            // Remove any existing hidden if nothing selected
            const existingHidden = document.getElementById(billHiddenId);
            if (selected.length === 0) {
                if (existingHidden) {
                    existingHidden.remove();
                }
                selectElement.disabled = false;
                return;
            }
            selectElement.disabled = true;

            // Reuse existing hidden input if present, otherwise create it
            let hidden = existingHidden;
            if (!hidden) {
                hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.id = billHiddenId;
                hidden.name = "bill_subjects";
                billForm.appendChild(hidden);
            }
            hidden.value = selected.join(",");
        });
    }
});

