# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to
the actual label strings used in this sub-system's tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the
corresponding label string from this table.

## Where the label goes

Appended to the ticket's front-matter `labels:` array, alongside any wayfinder type
label:

```yaml
labels: [wayfinder:grilling, ready-for-agent]
```

- Exactly one triage label at a time — replace, don't accumulate.
- `status:` is **not** a triage label. It is `open` | `closed` and tracks lifecycle
  only. Never encode triage state in `status`.
- `wontfix` closes the ticket: set the label **and** `status: closed`.

Edit the right-hand column to match whatever vocabulary you actually use.
