---
title: What MyCount Collects
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

Static inventory of external data available through the current browser integration, incoming request, and all 14 GeoIP CSV fields. Optional values depend on browser support and GeoIP coverage; historical visits may lack newer fields.

Table and Column name the storage destinations. --- means no value is stored. Optional browser fields share the client_details JSON column; Details names each JSON key. Geographic values retained in both the reference dataset and visits list both destination tables.

| Source | Source Details | Table | Column | Details |
| --- | --- | --- | --- | --- |
| Browser | Date.getTimezoneOffset() | `page_views` | `client_details` | Optional browser details: JSON key `timezone_offset`. UTC minus local time, in minutes. |
| Browser | devicePixelRatio | `page_views` | `client_details` | Optional browser details: JSON key `pixel_ratio`. Device pixel ratio. |
| Browser | document.referrer | `page_views` | `referrer` | Full HTTP(S) referrer exposed by the browser, including any available path, query, and fragment. Browser referrer policy may limit it; empty becomes NULL. |
| Browser | innerHeight | `page_views` | `client_details` | Optional browser details: JSON key `viewport_height`. Viewport height. |
| Browser | innerWidth | `page_views` | `client_details` | Optional browser details: JSON key `viewport_width`. Viewport width. |
| Browser | Intl.DateTimeFormat().resolvedOptions().timeZone | `page_views` | `client_details` | Optional browser details: JSON key `timezone`. Browser timezone name; distinct from GeoIP timezone. |
| Browser | location.hash | --- | --- | Page fragment is available in the browser but excluded from the payload. |
| Browser | location.origin + location.pathname | `pages` | `url` | Required page origin and path; validated against the configured request origin. |
| Browser | location.search | `page_views` | `search` | Exact query string, including the leading ?. Empty string means no query; NULL means not supplied by an older client or historical visit. Stored separately from the page URL. |
| Browser | matchMedia(prefers-color-scheme) | `page_views` | `client_details` | Optional browser details: JSON key `color_scheme`. Dark, light, or no-preference. |
| Browser | matchMedia(prefers-reduced-motion) | `page_views` | `client_details` | Optional browser details: JSON key `reduced_motion`. Reduced-motion preference. |
| Browser | navigator.connection.downlink | `page_views` | `client_details` | Optional browser details: JSON key `connection_downlink`. Estimated downlink in Mbps. |
| Browser | navigator.connection.effectiveType | `page_views` | `client_details` | Optional browser details: JSON key `connection_effective_type`. Estimated connection class. |
| Browser | navigator.connection.rtt | `page_views` | `client_details` | Optional browser details: JSON key `connection_rtt`. Estimated round-trip time in milliseconds. |
| Browser | navigator.connection.saveData | `page_views` | `client_details` | Optional browser details: JSON key `save_data`. Reduced-data preference. |
| Browser | navigator.cookieEnabled | `page_views` | `client_details` | Optional browser details: JSON key `cookie_enabled`. Whether cookies are enabled; no cookie contents collected. |
| Browser | navigator.deviceMemory | `page_views` | `client_details` | Optional browser details: JSON key `device_memory`. Approximate reported device memory in GB. |
| Browser | navigator.doNotTrack | `page_views` | `client_details` | Optional browser details: JSON key `do_not_track`. Recognized Do Not Track value; recorded without disabling collection. |
| Browser | navigator.globalPrivacyControl | `page_views` | `client_details` | Optional browser details: JSON key `global_privacy_control`. Privacy preference flag; recorded without disabling collection. |
| Browser | navigator.hardwareConcurrency | `page_views` | `client_details` | Optional browser details: JSON key `hardware_concurrency`. Reported logical processor count. |
| Browser | navigator.languages | `page_view_languages` | `language_tag`, `preference_order` | Preferred language tags in browser-supplied preference order; the list may be empty. |
| Browser | navigator.maxTouchPoints | `page_views` | `client_details` | Optional browser details: JSON key `max_touch_points`. Maximum simultaneous touch points. |
| Browser | navigator.onLine | `page_views` | `client_details` | Optional browser details: JSON key `online`. Reported online status. |
| Browser | navigator.pdfViewerEnabled | `page_views` | `client_details` | Optional browser details: JSON key `pdf_viewer_enabled`. Built-in PDF viewer support. |
| Browser | navigator.platform | `page_views` | `client_details` | Optional browser details: JSON key `platform`. Reported platform. |
| Browser | navigator.userAgent | `page_views` | `user_agent` | User-agent string supplied in the payload. Empty strings become NULL. |
| Browser | navigator.vendor | `page_views` | `client_details` | Optional browser details: JSON key `vendor`. Reported browser vendor. |
| Browser | navigator.webdriver | `page_views` | `client_details` | Optional browser details: JSON key `webdriver`. Reported automation flag. |
| Browser | performance navigation entry.type | `page_views` | `client_details` | Optional browser details: JSON key `navigation_type`. Navigation type, such as navigate, reload, or back_forward. |
| Browser | screen.availHeight | `page_views` | `client_details` | Optional browser details: JSON key `available_height`. Available screen height. |
| Browser | screen.availWidth | `page_views` | `client_details` | Optional browser details: JSON key `available_width`. Available screen width. |
| Browser | screen.colorDepth | `page_views` | `client_details` | Optional browser details: JSON key `color_depth`. Screen color depth. |
| Browser | screen.height | `page_views` | `client_details` | Optional browser details: JSON key `screen_height`. Screen height. |
| Browser | screen.pixelDepth | `page_views` | `client_details` | Optional browser details: JSON key `pixel_depth`. Screen pixel depth. |
| Browser | screen.width | `page_views` | `client_details` | Optional browser details: JSON key `screen_width`. Screen width. |
| GeoIP CSV | accuracy | --- | --- | Upstream accuracy value; discarded during import, not interpreted by MyCount. |
| GeoIP CSV | city | `geoip_ranges`, `page_views` | `city_name` | City name; empty values become NULL. Copied into new visits as a nullable location snapshot; later dataset refreshes do not change historical visits. |
| GeoIP CSV | continent | --- | --- | Discarded during import. |
| GeoIP CSV | country | `geoip_ranges`, `page_views` | `country_name` | Full country name from the CSV; empty becomes NULL. Copied into new visits as a location snapshot. Existing records are backfilled from recognized ISO country codes without replacing stored names. |
| GeoIP CSV | country_code | `geoip_ranges`, `page_views` | `country_code` | Two-character country code; empty values become NULL. Copied into new visits as a nullable location snapshot; later dataset refreshes do not change historical visits. |
| GeoIP CSV | end_ip | `geoip_ranges` | `end_ip` | Range end, converted to a 16-byte binary value. |
| GeoIP CSV | ip_version | `geoip_ranges` | `ip_version` | IP family, 4 or 6. |
| GeoIP CSV | latitude | `geoip_ranges`, `page_views` | `latitude` | Approximate GeoIP latitude in degrees (-90 to 90); missing values remain NULL. Copied into new visits when available; existing ranges need a GeoIP refresh and historical visits are unchanged. |
| GeoIP CSV | longitude | `geoip_ranges`, `page_views` | `longitude` | Approximate GeoIP longitude in degrees (-180 to 180); missing values remain NULL. Copied into new visits when available; existing ranges need a GeoIP refresh and historical visits are unchanged. |
| GeoIP CSV | source | --- | --- | Upstream source value; discarded during import. |
| GeoIP CSV | start_ip | `geoip_ranges` | `start_ip` | Range start, converted to a 16-byte binary value. |
| GeoIP CSV | state | `geoip_ranges`, `page_views` | `region_name` | State/region name; empty values become NULL. Copied into new visits as a nullable location snapshot; later dataset refreshes do not change historical visits. |
| GeoIP CSV | timezone | `geoip_ranges`, `page_views` | `timezone` | GeoIP timezone, stored separately from the browser timezone in client_details. Empty values become NULL. Available after the next GeoIP refresh and copied into new visits; historical visits are unchanged. |
| GeoIP CSV | zip | `geoip_ranges`, `page_views` | `zip` | GeoIP ZIP/postal code, stored as text to preserve leading zeros. Empty values become NULL. Available after the next GeoIP refresh and copied into new visits; historical visits are unchanged. |
| Request | connection / trusted Caddy visitor header | `page_views` | `ip_address` | Full IPv4 or IPv6 address used for GeoIP lookup. Historical visits remain NULL; no hash is generated. |
| Request | Origin header | --- | --- | Checked against configured sites and the page URL; not stored as a separate field. |

See [Browser client]({% link pages/client.md %}) for setup and reporting, and
[Installation and GeoIP updates]({% link pages/installation.md %}) for the
reference-data import.
