# Metaengine DevFabric Agent Guard — Always On

This rule is part of the Metaengine portable development fabric and applies to every Antigravity run in this workspace.

- `NO_CANONICAL_AUTHORITY`: never promote a checkpoint, change the active/champion policy, or write canonical cloud state.
- `PATCH_ONLY_OUTPUT`: work only inside the isolated candidate checkout; produce a patch/diff and verification evidence.
- `DETERMINISTIC_GATES_REQUIRED`: an AI opinion never overrides deterministic test, integrity, security, privacy, or zero-spend gates.
- `DO_NOT_ACCESS_CANONICAL_CREDENTIALS`: do not read, request, discover, print, or use Supabase service-role credentials, cloud tokens, `.env` secrets, OS keyrings, or credentials outside the workspace.
- Never run `git push`, publish/deploy commands, destructive cloud commands, or promotion commands.
- Do not access files outside the current Git/workspace root.
- Respect the task's allowed and forbidden paths. If the task is insufficiently scoped, stop and report the blocker rather than broadening access.
- Run the task's deterministic acceptance tests before returning a result.
