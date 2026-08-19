// main.js — students will add JavaScript here as features are built

(function () {
    var DEMO_VIDEO_ID = "dQw4w9WgXcQ"; // placeholder — replace with real demo video

    var trigger = document.getElementById("seeHowItWorksBtn");
    var overlay = document.getElementById("demoModalOverlay");
    var closeBtn = document.getElementById("demoModalClose");
    var iframe = document.getElementById("demoModalIframe");

    if (!trigger || !overlay || !closeBtn || !iframe) return;

    function openModal(event) {
        event.preventDefault();
        iframe.src = "https://www.youtube.com/embed/" + DEMO_VIDEO_ID + "?autoplay=1";
        overlay.hidden = false;
    }

    function closeModal() {
        overlay.hidden = true;
        iframe.src = "about:blank";
    }

    trigger.addEventListener("click", openModal);
    closeBtn.addEventListener("click", closeModal);
    overlay.addEventListener("click", function (event) {
        if (event.target === overlay) closeModal();
    });
})();

(function () {
    var deleteForms = document.querySelectorAll(".profile-delete-form");
    if (!deleteForms.length) return;

    deleteForms.forEach(function (form) {
        form.addEventListener("submit", function (event) {
            var confirmed = confirm("Delete this expense? This cannot be undone.");
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });
})();
