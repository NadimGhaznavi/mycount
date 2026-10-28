# Development guidance

Read and follow [Coding Guidelines](pages/coding-guidelines.md) before making
development changes in this repository. That document is the canonical guide
for MyCount's development style, code organization, interfaces, data access,
configuration validation, and refactoring practices.

Apply these guidelines to new and modified code. Keep changes focused on the
requested task; existing code that predates the guidelines is not a reason to
expand the scope into an unrelated refactor.

## BMForge guidance

MyCount attaches selected, pinned BMForge skills under `.agents/skills/`.
The coding guidelines above remain authoritative. Apply BMForge practices to
the requested work within MyCount's existing architecture; attaching a skill
does not authorize refactoring, replacing infrastructure, changing dependencies,
or imposing the greenfield project baseline.

Read the relevant skill and only the references needed for the task:

- [RCA](.agents/skills/bmforge-rca/SKILL.md): production evidence collection and
  local investigation; remote access requires authorization for that host.
- [HTTP](.agents/skills/bmforge-http/SKILL.md): request boundaries, server
  lifecycle, health checks, and accessible presentation.
- [Database](.agents/skills/bmforge-db-server/SKILL.md): domain data access,
  transactions, and resource ownership.
- [Visualization](.agents/skills/bmforge-visualization/SKILL.md): browser charts,
  maps, and safe presentation of data.

Use the pinned [engineering contract](.agents/skills/bmforge-rca/references/engineering-contract.md)
and [class responsibilities](.agents/skills/bmforge-rca/references/classification.md)
alongside MyCount's guidelines. Existing code is not evidence of compliance with
a BMForge component specification; do not add provenance markers merely because
the skill is installed.

Before first using a pinned skill in a work session, verify its local integrity:

```sh
python3 -B .agents/bmforge/verify.py
```

This check uses no Git commands or network access. The upstream manager invokes
Git even for `check`; leave its commands and upstream-source maintenance to the
project owner, as required by the coding guidelines. Report integrity failures
or unavailable update checks. Never replace pinned skills or apply updates
without direct user approval.
