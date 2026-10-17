---
title: MyCount
layout: single
author_profile: true
---

[![MyCount Map](/pages/images/map-banner.png)]({% link pages/gallery.md %})

**MyCount** is a self-hosted analytics application that profiles website traffic across multiple sites within a domain. 

![Pie Chart Examples](/pages/images/pie-chart-data.png)

The application also includes a [marketing]({% link pages/gallery.md %}) interface that allows the user to log social media and other posts which aim to generate website traffic. This aims to correlate marketing activity with user engagement.

![Architecture](/pages/images/mycount-architecture.png)

This application works, because all of my sites use the same GitHub pages Jekyll theme which I control. The *HTTP POST* operation is embedded in a `mycount.js` that is part of the theme. Each site includes a site identifier in it's Jekyll configuration (`_config.yml`) file. This is picked up by the self-MyCount listener running on my network.

**MyCount** also leverages my [BMDynIP Dynamic DNS](https://bmdynip.osoyalce.com) and my[BMGeoIP GeoIP Database](https://bmgeoip.osoyalce.com) services which I also run on my network.

---

## Questions? Comments? Feedback?

If you found this project intersting or useful please give the [GitHub repo](https://github.com/NadimGhaznavi/mycount) a star.

Please contact me via email if you want provide feedback, notice any bugs, have feature requests or have any other questions.

---

## Links

- [MyCount Gallery]({% link pages/gallery.md %})
- [BMDynIP Dynamic DNS](https://bmdynip.osoyalce.com)
- [BMGeoIP GeoIP Database](https://bmgeoip.osoyalce.com)

**MyCount** is part of the [osoyalce.com](https://www.osoyalce.com/) site.


## Legacy Documentation

- [Installation and GeoIP updates]({% link pages/installation.md %})
- [Control server]({% link pages/control-server.md %})
- [Upgrading]({% link pages/upgrading.md %})
- [Deployment dependencies]({% link pages/deployment-dependencies.md %})
- [Uninstall]({% link pages/uninstall.md %})
- [Browser client and live example]({% link pages/client.md %})
- [What MyCount collects]({% link pages/collected-data.md %})
- [Data access]({% link pages/data-access.md %})
- [Coding guidelines]({% link pages/coding-guidelines.md %})
- [Release management]({% link pages/releases.md %})
- [Changelog]({% link CHANGELOG.md %})

