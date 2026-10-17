---
title: Adding a New Site
layout: single
author_profile: true
---

Adding a new site to the **MyCount** application is simple.

## Install the Custom Minimal Mistakes Theme

Copy and customize the [_config.yml](https://github.com/NadimGhaznavi/mycount/blob/main/_config.yml) for your GitHub pages site. Pay particular attention to the *mycount* section which supplies the site identifier.

```yaml
mycount:
  endpoint: "https://count.osoyalce.com/count"
```
## Whitelist the New Site

The **MyCount** application enforces a CORS whitelist. 

- Sites must be in the `/opt/prod/mycount/mycount/constants/DMyCount.py` file.

### Restart Services

The services should be restarted after changing this file:

```sh
sudo systemctl restart mycount-control
sudo systemctl restart mycount-router
```
