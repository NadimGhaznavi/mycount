/* Include once per page using a deferred script with data-endpoint. */
(() => {
    "use strict";

    const script = document.currentScript;
    const endpointValue = script.dataset.endpoint;
    if (!endpointValue) {
        return;
    }

    const endpoint = new URL(endpointValue);
    if (endpoint.protocol !== "https:" || endpoint.username || endpoint.password) {
        throw new Error("MyCount requires an HTTPS endpoint without credentials.");
    }
    const site = script.dataset.site;
    if (!site) {
        throw new Error("MyCount requires a data-site label.");
    }

    const payload = {
        schema_version: 1,
        event: "page_view",
        site,
        url: window.location.origin + window.location.pathname,
        languages: Array.from(navigator.languages),
        user_agent: navigator.userAgent,
    };

    fetch(endpoint.href, {
        method: "POST",
        mode: "cors",
        credentials: "omit",
        referrerPolicy: "no-referrer",
        redirect: "error",
        cache: "no-store",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    }).then((response) => {
        if (!response.ok) {
            console.warn(`MyCount collection failed (HTTP ${response.status}).`);
        }
    }).catch(() => {
        // Do not log the payload or retry a request that may have been received.
        console.warn("MyCount collection failed. Check the endpoint and CORS configuration.");
    });
})();
