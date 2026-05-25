# Internal Git repo

The lab machines can use a shared bare repo for SSH-based push and pull without relying on GitHub availability.

Current internal repo:

```text
/home/workspace/git/mybank.git
```

Recommended remotes on the Mac worktree:

```bash
git remote add origin git@github.com:kalingod/mybank.git
git remote add internal exp2:/home/workspace/git/mybank.git
```

Recommended `internal` remote on experiment machines:

```bash
git remote add internal /home/workspace/git/mybank.git
```

Typical sync flow from the Mac worktree:

```bash
git push origin main
git push internal main
```

Typical sync flow on an experiment machine:

```bash
cd /home/workspace/mybank
git pull internal main --ff-only
```

Use GitHub as the collaboration source of record. Use `internal` for fast lab-machine rollout, especially when a machine cannot reach GitHub SSH or needs to avoid public-network dependency.
