# Controlling Zoo Design Studio from Claude Code in VS Code

This guide describes a practical setup for using **Claude Code in VS Code** to create, edit, inspect, and validate CAD models through **Zoo MCP**, while keeping **Zoo Design Studio** open for visual inspection and manual editing.

> Status: installed and wired up in this repository. Claude reaches Zoo MCP and
> can validate KCL offline, but real engine execution is currently blocked by an
> account-side authentication failure. See [Section 6](#6-verify-the-setup) for
> exactly what is verified working and what is not.

## Architecture

Claude does **not** directly remote-control the Zoo Design Studio GUI.

Instead, the workflow is:

```text
             VS Code
                │
                ▼
          Claude Code
                │
                │ MCP
                ▼
         ┌──────────────┐
         │   Zoo MCP    │
         │  uvx zoo-mcp │
         └──────┬───────┘
                │
                ▼
       Zoo CAD / KCL Engine
                │
      execute / inspect / render
                │
                ▼
       local .kcl project
             ▲       ▲
             │       │
       Claude edits  │
                     │
            Zoo Design Studio
            visual inspection
```

Claude edits the project's KCL files and uses Zoo MCP to execute, inspect, and validate the CAD model. Zoo Design Studio can be opened on the same project directory so the design remains visible and editable interactively.

**Caveat on the shared directory.** Design Studio and Claude communicate only through the files on disk; there is no live link between them. Zoo documents a reload action and supports editing KCL in an external editor, but automatic filesystem watching is not guaranteed. Assume you may need to reload the project in Design Studio after Claude edits it, and avoid leaving unsaved GUI changes in Design Studio while Claude is writing to the same files — whichever writes last wins.

---

## 1. Create a Zoo API token

Create a Zoo developer/API token.

Zoo MCP expects the token in the environment variable:

```text
ZOO_API_TOKEN
```

Zoo documentation:

- https://docs.zoo.dev/account/developer
- https://docs.zoo.dev/docs/developer-tools/mcp

In this repository the token already exists, untracked, at `secrets/zoo.env`.
Both `secrets/` and `*.env` are listed in `.gitignore`, so it is never committed.
Reuse that file as the source of truth rather than pasting the token into a
second location.

---

## 2. Install `uv` / `uvx`

Zoo's official MCP server is launched with `uvx`, which ships with `uv`.

On Windows, install `uv` with:

```powershell
winget install --id=astral-sh.uv -e
```

Verify the installation:

```powershell
uvx --version
```

Do **not** try to smoke-test the server by running `uvx zoo-mcp` on its own.
Zoo MCP is a stdio server: it prints a couple of startup log lines, then blocks
forever waiting for JSON-RPC on standard input. It does not handle `--help`
either, so it looks like a hang rather than a successful test. `uvx --version`
is the only check worth doing by hand; the server itself is tested end-to-end in
[Section 6](#6-verify-the-setup).

Note also that the server starts **successfully with no token at all** — the
token is only needed once a tool call reaches the Zoo engine. Startup is
therefore not evidence that authentication works.

Official Zoo MCP repository:

- https://github.com/KittyCAD/mcp

---

## 3. Choose one of two configurations

Sections 3 and 4 are **mutually exclusive alternatives**, not consecutive steps.

| | Option A — user-scope server | Option B — project `.mcp.json` |
|---|---|---|
| Token stored | in plaintext in `~/.claude.json` | in a Windows user environment variable |
| Committable | no | yes |
| Applies to | every project | this repository |

**Option B is recommended, and is what this repository uses.** Option A is
documented only because it is the quickest way to try Zoo MCP once.

### Option A — quick, single-machine, token in Claude's config

```powershell
claude mcp add --scope user --env ZOO_API_TOKEN=YOUR_ZOO_TOKEN --transport stdio zoo -- uvx zoo-mcp
```

This writes the token **in plaintext** into `~/.claude.json`. If you later move
to Option B, remove this entry first, otherwise the plaintext copy stays behind
and the user-scope server shadows the project one:

```powershell
claude mcp remove --scope user zoo
```

---

## 4. Option B (recommended): keep the token out of the repository

### 4.1 Persist the token as a user environment variable

```powershell
setx ZOO_API_TOKEN "YOUR_ZOO_TOKEN"
```

`setx` writes the value for future processes only. **Fully restart VS Code**
afterwards so Claude Code — and therefore the MCP server it spawns — inherits
the variable. Until you do, Claude Code reports the server as connected but
`claude mcp list` warns `Missing environment variables: ZOO_API_TOKEN`.

To avoid putting the token on a command line, set it from the existing secrets
file instead:

```powershell
$tok = (Select-String -Path 'secrets\zoo.env' -Pattern '^ZOO_API_TOKEN=(.*)$').Matches[0].Groups[1].Value.Trim()
[Environment]::SetEnvironmentVariable('ZOO_API_TOKEN', $tok, 'User')
```

### 4.2 Create `.mcp.json`

At the root of the CAD repository:

```json
{
  "mcpServers": {
    "zoo": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "zoo-mcp"
      ],
      "env": {
        "ZOO_API_TOKEN": "${ZOO_API_TOKEN}"
      }
    }
  }
}
```

Claude Code expands `${VAR}` and `${VAR:-default}` inside `command`, `args`,
`env`, `url` and `headers`, so the token is resolved at launch and never stored
in the file. This configuration is safe to commit.

The key **must** be `mcpServers`. VS Code's own MCP configuration uses `servers`
instead; a file with that key is silently useless to Claude Code, which reports
`Missing "mcpServers" — found "servers" instead`. Note that Claude Code also
picks up `.mcp.json` files in parent directories, so a stale one in your home
directory will produce a standing parse error unrelated to this project.

### 4.3 Approve the server

A project-scope server starts at `⏸ Pending approval` and exposes no tools until
it is approved. Approving it interactively means simply running `claude` in the
project and accepting the prompt.

To approve it without the prompt, add to `~/.claude/settings.json`:

```json
{
  "enabledMcpjsonServers": [
    "zoo"
  ]
}
```

**The scope of this setting matters.** The same key in the project's own
`.claude/settings.json` is *ignored while the folder is untrusted* — a
deliberate safeguard, so that a cloned repository cannot approve its own
servers. This repository is currently untrusted
(`hasTrustDialogAccepted: false` in `~/.claude.json`), which is why the approval
above lives in user settings. Approvals that always apply are user settings,
administrator-managed settings, and `--settings`. Once you accept the folder
trust prompt, the project-scope setting takes effect and the user-scope entry
can be removed.

Claude Code MCP documentation:

- https://code.claude.com/docs/en/mcp

---

## 5. Use the same project directory in VS Code and Zoo Design Studio

This repository's actual layout:

```text
bipedal/
├── .mcp.json              # Zoo MCP server, committed
├── .claude/settings.json  # project-scope MCP approval
├── project.toml           # Zoo Design Studio project file
├── main.kcl               # top-level assembly
├── parameters.kcl         # shared named dimensions
├── torso.kcl
├── hip_carrier.kcl
├── pitch_yoke.kcl
├── thigh.kcl
├── knee_module.kcl
├── shin.kcl
├── foot.kcl
├── actuator.kcl
├── payload_envelopes.kcl
├── pose_check.kcl
├── knee_limit_check.kcl
├── knee_prelimit_check.kcl
├── docs/
├── reference/             # vendor geometry, tracked on purpose
└── secrets/               # ZOO_API_TOKEN, untracked
```

`project.toml` is what marks the directory as a Design Studio project; do not
delete it. Design Studio projects are filesystem-based and `.kcl` files are
plain-text parametric CAD source.

Open this directory in both VS Code and Zoo Design Studio.

**Design Studio's project browser defaults to
`~/Documents/zoo-design-studio-projects/`.** A repository kept anywhere else —
such as this one — will not appear in that list. Either change the project
directory in Design Studio's settings, or open the folder directly.

If the Zoo CLI is installed, the current directory can be opened with:

```powershell
zoo app .
```

The CLI is a **separate install from the desktop app** and is not present on
this machine. Design Studio itself is installed at
`C:\Program Files\Zoo Design Studio\Zoo Design Studio.exe`, and can be pointed
at the project directly:

```powershell
& "C:\Program Files\Zoo Design Studio\Zoo Design Studio.exe" .
```

Zoo CLI documentation:

- https://zoo.dev/docs/developer-tools/cli/manual/zoo_app

---

## 6. Verify the setup

Check the server from the VS Code integrated terminal:

```powershell
claude mcp list
```

A correct setup reports:

```text
zoo: uvx zoo-mcp - ✔ Connected
```

If it reports `⏸ Pending approval`, revisit section 4.3. If it reports
`Missing environment variables: ZOO_API_TOKEN`, the token is persisted but this
VS Code process predates it — restart VS Code.

Because the server starts fine without credentials, a green "Connected" does not
prove the token authenticates. Confirm the token separately:

```powershell
curl -H "Authorization: Bearer $env:ZOO_API_TOKEN" https://api.zoo.dev/user
```

A valid token returns HTTP 200 and your account details.

### 6.1 What is verified working on this machine

| Check | Result |
|---|---|
| `uvx zoo-mcp` resolves and starts | yes |
| `claude mcp list` reports the server | `zoo: uvx zoo-mcp - ✔ Connected` |
| Tools exposed to Claude | yes, e.g. `mcp__zoo__execute_kcl` |
| Token reaches the server process | yes, 40 chars |
| Token valid over the REST API | yes, HTTP 200 from `/user` |
| KCL parses (`kcl.parse`) | yes, `main.kcl` OK |
| Offline validation (`mock_execute`) | yes, `main.kcl` OK |
| Real engine execution | **no — see 6.2** |

### 6.2 Known blocker: the modeling engine rejects the token

Real geometry execution currently fails. The KCL itself is fine — it parses and
mock-executes — but as soon as a tool needs the Zoo engine, the websocket
returns:

```text
error_code: auth_token_missing
message: Please send `{ headers: { Authorization: "Bearer <token>" } }` over this websocket.
```

This is **not** a misconfiguration of Claude Code, Zoo MCP, or `.mcp.json`. The
same rejection reproduces outside Claude entirely:

- with the token confirmed present in the engine process (40 characters),
- calling `kcl.execute_code` directly from Python, bypassing MCP,
- and from a raw `curl` websocket upgrade, which returns
  `HTTP/1.1 101 Switching Protocols` and *then* the same `auth_token_missing`,
- both with the `Authorization` header and with the in-band
  `{"headers": {"Authorization": "Bearer ..."}}` message the error text asks for.

So the token authenticates against `api.zoo.dev` over REST but is not accepted
by the modeling engine. The token itself is a well-formed API token
(`api-` prefix, listed as `is_valid: true` on the account), which points at an
account entitlement rather than the token or the setup — this is a free account
created 2026-08-22. Resolve it on the Zoo side: check the plan/subscription on
the account, or ask Zoo support why an otherwise valid API token gets
`auth_token_missing` from `wss://api.zoo.dev/ws/modeling/commands`.

### 6.3 What Claude can still do meanwhile

Everything that does not touch the engine works today, which is more than it
sounds:

- `mcp__zoo__mock_execute_kcl` runs the full KCL interpreter without the engine,
  so it catches genuine semantic errors — bad arguments, type errors, unresolved
  imports, broken sketch constraints — not merely syntax.
- KCL parsing, formatting, and linting are local.
- Design Studio itself signs in separately from this token, so visual inspection
  is unaffected.

Until the engine is available, prefer mock execution in the working loop below
and treat step 4 as "validate as far as offline execution allows".


Inside Claude Code, `/mcp` inspects MCP servers and lets you reconnect or
enable/disable them.

Finally, exercise the engine with a non-destructive prompt:

```text
Use the Zoo MCP tools to inspect this CAD project.

Execute the current main.kcl and tell me whether it builds correctly.

Do not modify anything yet.
```

Then try a simple change:

```text
Change the diameter of the mounting holes to 4 mm.

Update the KCL, execute it with Zoo MCP, and verify that the model
still builds successfully.
```

The important point is that Claude should use the Zoo MCP tools to validate the design rather than merely editing KCL and assuming the result is correct.

---

## 7. Recommended working loop

A good development loop is:

1. Describe the desired CAD change to Claude Code.
2. Claude inspects the existing KCL.
3. Claude edits the relevant `.kcl` files.
4. Claude executes/validates the model through Zoo MCP.
5. Claude fixes any KCL or geometry errors it encounters.
6. Reload the project in Zoo Design Studio and inspect the resulting geometry.
7. Make any manual visual adjustments if useful, and save them.
8. Ask Claude to continue from the updated project state.
9. Commit validated milestones to Git.

This gives Claude access to the actual CAD execution environment while retaining Zoo Design Studio as the interactive visual interface.

---

## 8. Suggested `CLAUDE.md` instructions

For a CAD repository, it is useful to tell Claude explicitly how Zoo should be
used. This repository has a `CLAUDE.md`, but it currently covers reporting style
only and says nothing about Zoo or CAD. The following is a starting point to add
to it.

```markdown
# CAD Development Instructions

This repository is a Zoo Design Studio / KCL project.

## Zoo MCP

Zoo MCP is available to Claude.

When modifying CAD:

1. Inspect the existing KCL before making structural changes.
2. Preserve parametric dimensions wherever practical.
3. Use Zoo MCP to execute and validate KCL changes.
4. Do not assume syntactically plausible KCL is valid.
5. Resolve execution or geometry errors before declaring a change complete.
6. Prefer reusable functions/components over duplicated geometry.
7. Keep important mechanical dimensions exposed as named parameters.
8. Avoid destructive rewrites unless they materially simplify the model.
9. Summarize dimensional or structural changes after each substantial edit.
10. Do not commit changes unless explicitly asked.
```

For a robotics project, additional instructions can cover:

- actuator envelopes
- joint axes
- bearing clearances
- bolt sizes
- print tolerances
- carbon-fibre plate thickness
- cable routing
- mass estimates
- symmetry requirements
- manufacturability constraints

---

## 9. Git workflow

Because KCL is text-based, the CAD project works well with Git.

A typical workflow is:

```powershell
git status
git diff
```

after Claude has modified the model.

Once the model has been visually inspected and validated through Zoo MCP:

```powershell
git add .
git commit -m "Refine hip actuator mounting geometry"
```

`git add .` is safe here because `secrets/` and `*.env` are gitignored, but
confirm with `git status` before staging if you have added new credential files.

This makes it easy to experiment aggressively while retaining known-good CAD states.

---

## Result

With this setup, the division of responsibilities is roughly:

| Component | Role |
|---|---|
| Claude Code | Reasoning, design changes, KCL editing |
| Zoo MCP | CAD execution, inspection and validation |
| Zoo CAD engine | Geometry generation |
| Zoo Design Studio | Interactive visual inspection/editing |
| Git | Version control and rollback |
| VS Code | Main development environment |

The key advantage is that Claude can work against the **actual Zoo CAD engine** rather than merely generating KCL source code without validating the resulting geometry.
