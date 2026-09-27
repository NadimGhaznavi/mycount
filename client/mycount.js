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

    // Keep only the referring origin; paths and query strings can contain private data.
    let referrer = null;
    if (document.referrer) {
        try {
            const address = new URL(document.referrer);
            if (address.protocol === "https:" || address.protocol === "http:") {
                referrer = address.origin;
            }
        } catch (error) {
            if (!(error instanceof TypeError)) throw error;
        }
    }
    const connection = navigator.connection;
    const navigation = window.performance?.getEntriesByType?.("navigation")[0];
    const media = (query) => window.matchMedia ? window.matchMedia(query).matches : null;
    const dark = media("(prefers-color-scheme: dark)");
    const light = media("(prefers-color-scheme: light)");
    const doNotTrack = navigator.doNotTrack;
    const payload = {
        schema_version: 1,
        event: "page_view",
        site,
        url: window.location.origin + window.location.pathname,
        languages: Array.from(navigator.languages),
        user_agent: navigator.userAgent,
        referrer,
        client_details: {
            screen_width: window.screen?.width,
            screen_height: window.screen?.height,
            available_width: window.screen?.availWidth,
            available_height: window.screen?.availHeight,
            color_depth: window.screen?.colorDepth,
            pixel_depth: window.screen?.pixelDepth,
            viewport_width: window.innerWidth,
            viewport_height: window.innerHeight,
            pixel_ratio: window.devicePixelRatio,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            timezone_offset: new Date().getTimezoneOffset(),
            platform: navigator.platform,
            vendor: navigator.vendor,
            cookie_enabled: navigator.cookieEnabled,
            online: navigator.onLine,
            pdf_viewer_enabled: navigator.pdfViewerEnabled,
            hardware_concurrency: navigator.hardwareConcurrency,
            device_memory: navigator.deviceMemory,
            max_touch_points: navigator.maxTouchPoints,
            webdriver: navigator.webdriver,
            do_not_track: ["0", "1", "yes", "no", "unspecified"].includes(doNotTrack) ? doNotTrack : null,
            global_privacy_control: navigator.globalPrivacyControl,
            color_scheme: dark === null ? null : dark ? "dark" : light ? "light" : "no-preference",
            reduced_motion: media("(prefers-reduced-motion: reduce)"),
            connection_effective_type: connection?.effectiveType,
            connection_downlink: connection?.downlink,
            connection_rtt: connection?.rtt,
            save_data: connection?.saveData,
            navigation_type: navigation?.type,
        },
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
