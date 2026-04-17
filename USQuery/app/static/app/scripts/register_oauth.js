(function () {
    function getConfig() {
        var el = document.getElementById("registerOAuthConfig");
        if (!el) return null;
        return {
            googleClientId: el.dataset.googleClientId || "",
            appleClientId: el.dataset.appleClientId || "",
            googleUrl: el.dataset.googleUrl || "",
            appleUrl: el.dataset.appleUrl || "",
            registerUrl: el.dataset.registerUrl || "/register/"
        };
    }

    function showOAuthError(msg) {
        var el = document.getElementById("oauthError");
        if (!el) return;
        el.textContent = msg || "OAuth sign-in failed.";
        el.style.display = "block";
    }

    function getCsrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : "";
    }

    async function postForm(url, data) {
        var formBody = new URLSearchParams();
        Object.keys(data || {}).forEach(function (k) {
            if (data[k] !== undefined && data[k] !== null) {
                formBody.append(k, data[k]);
            }
        });

        var resp = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-CSRFToken": getCsrfToken(),
                "X-Requested-With": "XMLHttpRequest"
            },
            body: formBody.toString(),
            credentials: "same-origin"
        });

        var payload = null;
        try {
            payload = await resp.json();
        } catch (e) {
            payload = null;
        }

        if (!resp.ok) {
            var detail = (payload && (payload.detail || payload.error))
                ? (payload.detail || payload.error)
                : ("Request failed (" + resp.status + ")");
            throw new Error(detail);
        }

        return payload || {};
    }

    function initGoogle(config) {
        if (!config.googleClientId || !config.googleUrl) return;
        var rawClientId = String(config.googleClientId || "");
        var googleClientId = rawClientId
            .split(",")[0]
            .trim()
            .replace(/^["']+|["']+$/g, "");

        var host = document.getElementById("googleBtnHost");
        var fallback = document.getElementById("googleFallbackBtn");
        var maxAttempts = 40; // ~10 seconds at 250ms interval
        var attempts = 0;
        var googleInitialized = false;
        var fallbackBound = false;

        function bindFallbackIfNeeded(message) {
            if (!fallback || fallbackBound) return;
            fallback.classList.remove("oauth-btn--hidden");
            fallback.addEventListener("click", function () {
                showOAuthError(message || "Google Sign-In is not available right now. Please refresh and try again.");
            });
            fallbackBound = true;
        }

        function isGoogleReady() {
            return !!(window.google && window.google.accounts && window.google.accounts.id);
        }

        function tryInitGoogle() {
            if (googleInitialized) return;

            if (!isGoogleReady()) {
                attempts += 1;
                if (attempts >= maxAttempts) {
                    bindFallbackIfNeeded(
                        "Google Sign-In script did not load. Check that no extension/network policy is blocking accounts.google.com, then refresh."
                    );
                    return;
                }
                window.setTimeout(tryInitGoogle, 250);
                return;
            }

            googleInitialized = true;
            window.google.accounts.id.initialize({
                client_id: googleClientId,
                // Avoid browser-specific FedCM transform flow issues that can show a blank popup.
                use_fedcm_for_prompt: false,
                itp_support: true,
                auto_select: false,
                cancel_on_tap_outside: true,
                callback: async function (resp) {
                    try {
                        var out = await postForm(config.googleUrl, { id_token: resp.credential });
                        window.location.assign(out.redirect || "/");
                    } catch (e) {
                        showOAuthError(e.message);
                    }
                }
            });

            if (host) {
                window.google.accounts.id.renderButton(host, {
                    theme: "outline",
                    size: "large",
                    width: host.offsetWidth || 360,
                    text: "continue_with",
                    shape: "pill"
                });
                if (fallback) fallback.classList.add("oauth-btn--hidden");
            } else {
                bindFallbackIfNeeded("Unable to render Google button. Please refresh and try again.");
            }
        }

        tryInitGoogle();
    }

    function initApple(config) {
        if (!config.appleClientId || !config.appleUrl) return;
        var appleBtn = document.getElementById("appleBtn");
        if (!appleBtn) return;

        appleBtn.addEventListener("click", async function (ev) {
            ev.preventDefault();

            if (!window.AppleID || !window.AppleID.auth) {
                showOAuthError("Apple Sign in JS SDK failed to load.");
                return;
            }

            try {
                window.AppleID.auth.init({
                    clientId: config.appleClientId,
                    scope: "name email",
                    redirectURI: window.location.origin + config.registerUrl,
                    usePopup: true
                });

                var resp = await window.AppleID.auth.signIn();
                var idToken = (resp && resp.authorization && (resp.authorization.id_token || resp.authorization.idToken))
                    || resp.id_token
                    || resp.idToken;
                var email = (resp && resp.user && resp.user.email) || "";

                if (!idToken) throw new Error("Apple did not return an identity token.");

                var out = await postForm(config.appleUrl, { identity_token: idToken, email: email });
                window.location.assign(out.redirect || "/");
            } catch (e) {
                var msg = (e && e.error) ? e.error : ((e && e.message) ? e.message : "Apple sign-in failed.");
                showOAuthError(msg);
            }
        });
    }

    function boot() {
        var config = getConfig();
        if (!config) return;

        initGoogle(config);
        initApple(config);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            window.setTimeout(boot, 0);
        });
    } else {
        window.setTimeout(boot, 0);
    }
})();
