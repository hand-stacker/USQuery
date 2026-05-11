(function () {
    // Fallback client IDs and endpoints (override with your production values if needed)
    const FALLBACK_GOOGLE_CLIENT_ID = '1069290177302-8u4ljfiouf9pkiffe8okobr75dbi13lc.apps.googleusercontent.com';
    const FALLBACK_APPLE_CLIENT_ID = '';
    const FALLBACK_GOOGLE_URL = '/oauth/google/';
    const FALLBACK_APPLE_URL = '/oauth/apple/';
    const FALLBACK_REGISTER_URL = '/register/';

    function getConfig() {
        var el = document.getElementById("registerOAuthConfig");
        var googleClientId = "";
        var appleClientId = "";
        var googleUrl = "";
        var appleUrl = "";
        var registerUrl = "/register/";

        if (el) {
            googleClientId = el.dataset.googleClientId || "";
            appleClientId = el.dataset.appleClientId || "";
            googleUrl = el.dataset.googleUrl || "";
            appleUrl = el.dataset.appleUrl || "";
            registerUrl = el.dataset.registerUrl || "/register/";
        }

        // Use fallback if template didn't provide values
        if (!googleClientId) googleClientId = FALLBACK_GOOGLE_CLIENT_ID;
        if (!appleClientId) appleClientId = FALLBACK_APPLE_CLIENT_ID;
        if (!googleUrl) googleUrl = FALLBACK_GOOGLE_URL;
        if (!appleUrl) appleUrl = FALLBACK_APPLE_URL;
        if (!registerUrl) registerUrl = FALLBACK_REGISTER_URL;

        return {
            googleClientId: googleClientId,
            appleClientId: appleClientId,
            googleUrl: googleUrl,
            appleUrl: appleUrl,
            registerUrl: registerUrl
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
        var googleClientId = config.googleClientId;
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
                use_fedcm_for_prompt: false,
                use_fedcm_for_button: false,
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
                    shape: "pill",
                    ux_mode: "popup"
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

        var maxAttempts = 40;
        var attempts = 0;

        function tryInitApple() {
            if (!window.AppleID || !window.AppleID.auth) {
                attempts += 1;
                if (attempts >= maxAttempts) return;
                window.setTimeout(tryInitApple, 250);
                return;
            }

            AppleID.auth.init({
                clientId: config.appleClientId,
                scope: "name email",
                redirectURI: window.location.protocol + "//" + window.location.host + config.appleUrl,
                usePopup: true
            });

            var btn = document.getElementById("appleBtn");
            if (btn) {
                btn.classList.remove("oauth-btn--hidden");
                btn.addEventListener("click", function () {
                    AppleID.auth.signIn();
                });
            }

            document.addEventListener("AppleIDSignInOnSuccess", async function (event) {
                try {
                    var auth = event.detail.authorization || {};
                    var idToken = auth.id_token || auth.idToken;
                    var user = event.detail.user || {};
                    var email = user.email || "";

                    if (!idToken) throw new Error("Apple did not return an identity token.");

                    var out = await postForm(config.appleUrl, { identity_token: idToken, email: email });
                    window.location.assign(out.redirect || "/");
                } catch (e) {
                    showOAuthError(e.message || "Apple sign-in failed.");
                }
            });

            document.addEventListener("AppleIDSignInOnFailure", function (event) {
                var error = event.detail && event.detail.error;
                if (error && error !== "popup_closed_by_user") {
                    showOAuthError(error);
                }
            });
        }

        tryInitApple();
    }

    function boot() {
        var config = getConfig();
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
