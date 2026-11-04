@AGENTS.md

## Claude Code

Additions for Claude Code only; everything shared is in AGENTS.md (imported above, loaded once whichever "Project instructions" setting you use).

- **Start sessions with `just claude` from blokky-cli** (`cd ../blokky-cli && just claude`): it adds this repo as a directory and loads these instructions. Working mainly here, `just claude` in this repo does the reverse (adds `../blokky-cli`). Settings in an added directory's `.claude/` don't apply; only the starting repo's do.
- **If this repo was added with `--add-dir`**, its `@AGENTS.md` import may not be expanded (Claude Code treats it as an external import that needs approval). In that case, read `../blokky-specs/AGENTS.md` with the Read tool before changing files in this repo.
- **Subagents and worktrees** (brief §0.2): when work can be parallelized, give each subagent its own git worktree and branch, explicit file ownership, and its own PR. Shared files belong to the main agent (see AGENTS.md). Don't fan out before the language spec draft is merged.
- **Sandbox:** `.claude/settings.json` enables the Bash sandbox with a small network allowlist. Commit signing, `gh` and network beyond the allowlist may need to run outside the sandbox as separate calls (for example `git commit -s -F <file>` on its own, not chained); follow your user-level setup for that.
- **Check what loads:** `claude -p --permission-mode plan "list the instruction files in your context"` from the repo root.
