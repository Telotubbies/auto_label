# Area 7 — Workspace admin: people, money, keys, audit, integrations, publishing

Method: 28 public pages fetched on 2026-11-17 — `docs.roboflow.com/llms.txt` (index), 24 docs pages under `/platform/workspaces/`, `/platform/enterprise-features/`, `/platform/billing-and-plans/`, `/reference/authentication/`, `/datasets/universe/`, plus `roboflow.com/pricing` and `roboflow.com/credits`. Screen names, button labels and microcopy below are mine; a Roboflow label appears only in parentheses as a source tag. Not opened: the Slack/Twilio block pages, Workspace Announcements, Organizations, Recommended Access Setup, Purchase a Plan, Purchase Prepaid Credits, Billing Folders, Usage Projection, project-folders permissions, Trash-adjacent changelog entries, support-access page, Trust Center, any authenticated app screen.

Settings menu order as observed from page references (this is the spine our redesign should mirror): Team Members · API Keys · Plan & Billing · Credit Usage · Trash · Audit Logs · SSO · Auth Groups · Branding · Datasources · Credentials · Project Settings · Delete Workspace · Account.

---

## Team and membership

### F7.1 Member roster with seat accounting (RF: *Team Members*)
- **What the user does:** sees everyone who can enter the workspace, their role, and how many of the plan's seats are spent.
- **Flow:** 1. Click the workspace name, then **Settings** → **Team Members** (`[loading]` skeleton rows while the roster resolves). 2. Roster lists each member with avatar, name, email, role, and a `⋯` row menu. 3. Header shows seats used / seats allowed. 4. `[empty]` "Only you so far" with the invite control as the only filled element. 5. `[error: roster failed to load — retry]`. 6. `⋯` menu offers **Change role**, **Remove from workspace**; on your own row, **Leave workspace**.
- **Why it is easy:** the roster is the same page as invites, pending invites and seat count, so "who is in, who is waiting, how many are left" is one screen and never a separate report.
- **Gates:** seat count depends on plan; pending invites consume a seat because the spot is reserved.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/settings/Settings.tsx`, `apps/backend/app/routers/workspaces.py`

### F7.2 Bulk email invite with per-batch role (RF: *Invite via Email*)
- **What the user does:** pastes several addresses at once and picks the role they all get.
- **Flow:** 1. **Settings → Team Members** → **Invite**. 2. Dialog holds one address field (comma-separated accepted) and a role dropdown. 3. Click **Send invites**. 4. `[error: not enough seats left — remove a member or upgrade]` blocks the send before any mail leaves. 5. `[error: address already a member]` names the offending address, keeps the rest of the field intact. 6. `[loading]` per-row "Sending…" then the addresses move into the pending list (F7.3). 7. `[empty]` role dropdown defaults to the workspace default role (F7.8).
- **Why it is easy:** one dialog covers a whole onboarding batch, and the seat check happens before the send so half the team is never invited.
- **Gates:** "can manage team members" (Admin by default); seat limit; who can invite is Admin-only unless a custom role grants it.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members/invite-a-team-member.md
- **LabelDesk hook points:** `apps/backend/app/routers/workspaces.py`

### F7.3 Pending invitation list with resend and cancel (RF: *pending invites*)
- **What the user does:** watches invitations that have not been accepted and rescues stale ones.
- **Flow:** 1. Same page, section under the roster listing email, role, sent date, and status. 2. Row actions **Resend** and **Cancel**. 3. Unaccepted email invites die after 3 days; the row stays visible as expired. 4. `[error: invite expired]` on the recipient's link offers "ask your admin to resend".
- **Why it is easy:** expiry is a visible state with a one-click fix rather than a silent failure the admin learns about from a confused teammate.
- **Gates:** Admin.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members/invite-a-team-member.md

### F7.4 Role-locked permanent invite link (RF: *Invite via Link*)
- **What the user does:** copies a join URL that already carries a role, for a batch of contractors.
- **Flow:** 1. **Team Members** → **Invite link** → pick role → **Copy link** (one URL per role). 2. Recipient opens it while signed in and joins at that role. 3. The link is static for the workspace and cannot be regenerated or expired from the UI — the docs warn about it in a red callout.
- **Why it is easy:** zero-friction onboarding for a known group; the cost is that the link is forever, which our design should fix with a rotate/expire control.
- **Gates:** Admin; seat limit still applies at join time.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members/invite-a-team-member.md

### F7.5 Same-domain join request with admin approval (RF: *Allow Same Domain*)
- **What the user does:** lets colleagues with the company email domain find the workspace and ask to join, without an invite.
- **Flow:** 1. **Team Members** → **Domain access** toggle (only offered when the workspace was created through a Google-verified email). 2. A colleague signs up → a workspace list appears at account creation → **Request to join**. 3. Admin approves in either **Team Members** (choose role, or decline) or the **Notifications** bell panel (same two actions inline). 4. Admin also gets a confirmation email when someone actually joins. 5. `[empty]` "No requests" in the bell panel.
- **Why it is easy:** two approval surfaces — the roster and the notification tray — so an admin working anywhere in the app can clear the queue.
- **Gates:** Admin; domain must be verified; role chosen at approval time, not requested by the joiner.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members/invite-a-team-member.md

### F7.6 Change a member's role, with self-change blocked (RF: *Change Role*)
- **What the user does:** promotes a labeler to reviewer, or narrows an admin.
- **Flow:** 1. **Team Members** → `⋯` on the row → **Change role**. 2. Dialog with a role dropdown → **Save**. 3. `[error: you cannot change your own role — ask another admin]` is enforced, not just warned.
- **Why it is easy:** the role is edited in place from the roster; the self-demotion guard prevents an admin from locking themselves out.
- **Gates:** Admin; the workspace creator's role is honorific and cannot be reassigned.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members/change-a-team-member-role.md, https://docs.roboflow.com/platform/enterprise-features/role-based-access-control.md

### F7.7 Remove a member / leave, with last-admin guard (RF: *Remove From Workspace*)
- **What the user does:** revokes someone's access, or leaves a client workspace.
- **Flow:** 1. **Team Members** → `⋯` → **Remove from workspace** → confirm **Yes, remove**. 2. On your own row: **Leave workspace** → **Yes, leave**. 3. `[error: you are the last admin — promote someone first]` blocks the leave. 4. `[empty]` after removal the row disappears immediately and the seat count drops by one.
- **Why it is easy:** leaving is on your own row where you would look, and the guard is phrased as an action ("promote someone first") not a dead end.
- **Gates:** Admin for removals; last-admin rule is per workspace, not per role.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members/remove-a-team-member.md

### F7.8 Workspace default role for new joiners (RF: *Default Role*)
- **What the user does:** sets what a person gets when they arrive by SSO or by domain request rather than by a role-pinned invite.
- **Flow:** 1. **Team Members → Roles** tab, **Default role** card at the top. 2. Dropdown → selection applies immediately to all future joins (no save button).
- **Why it is easy:** one obvious control that removes a per-invite decision; it is also the safety net that stops SSO strangers becoming admins once custom roles exist.
- **Gates:** Admin; custom roles are a select-Enterprise feature.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/role-based-access-control.md

### F7.9 Built-in role matrix as a readable table (RF: *Default Roles*)
- **What the user does:** checks what a labeler or reviewer is allowed to do before assigning.
- **Flow:** 1. **Team Members → Roles** tab. 2. Three system roles — Admin, Reviewer, Labeler — shown as a permission table with rows for labeling, reviewing, assigning, managing members, uploading/deleting/exporting data, training, workflows, deploying, viewing keys, viewing credit usage, managing billing. 3. System roles are not editable; custom roles use the same table shape with per-permission checkboxes.
- **Why it is easy:** the table is the mental model — same rows for system and custom roles, so "what am I about to grant" is answered by the same artifact.
- **Gates:** without role management every user must be an Admin; the Reviewer/Labeler split ships with the Teams add-on or Enterprise.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/role-based-access-control.md
- **LabelDesk hook points:** `apps/backend/app/routers/rbac.py`, `apps/frontend/src/features/settings/Settings.tsx`

### F7.10 Custom roles built from grouped permissions (RF: *Custom Roles*)
- **What the user does:** builds a role that can label and view but not export, for outsourced teams.
- **Flow:** 1. **Team Members → Roles** → **+ New role**. 2. Dialog: **Role name**; **Start from** an existing role + **Copy permissions**; then a permission grid grouped Data / Labeling / Models / Workflows & deployment / Workspace & admin, each resource a row with View, Create, Edit, Delete, Other columns. 3. Hover a checkbox → tooltip explaining the grant. **Select all** / **Clear all** per section. 4. **Grant all folder access** checkbox. 5. **Create role**. Dialog closes only on Create or Cancel — edits are not lost by a stray click outside. 6. `⋯` on a role row → **Edit role** / **Delete role**; deleting a role that still has members warns and asks for reassignment first.
- **Why it is easy:** copy-from + tooltips + explicit save/cancel make a 60-checkbox matrix survivable; the "dialog never closes on outside click" detail is the single best small touch in the whole admin surface.
- **Gates:** select Enterprise customers only; system roles are read-only; folder permissions are a further Enterprise gate.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/role-based-access-control.md

### F7.11 Folder-scoped access plus named auth groups (RF: *Folder Permissions / Auth Groups*)
- **What the user does:** limits a contractor to one project folder, and groups people by team so a folder can be granted to a group.
- **Flow:** 1. **Settings → Auth groups** (appears only once folder permissions exist) → **Create auth group** → name it and list the identity-provider group names it maps to. 2. Members carry a **Manual** or **SSO** badge; SSO badges are rechecked at every sign-in. 3. On a project folder card: **Set permissions** → pick roles/groups. 4. Folder card menu also carries **Folder usage** and **API keys** (F7.32).
- **Why it is easy:** the split "a role says what you may do, a group says where" is legible on one screen; it beats per-project membership editing.
- **Gates:** Enterprise; SSO needed for the automatic badge path.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/single-sign-on-sso.md, https://docs.roboflow.com/reference/authentication/authentication/scoped-api-keys.md

---

## Billing and usage

### F7.12 One billing home for plan, packs and add-ons (RF: *Plan & Billing*)
- **What the user does:** sees the current plan, swaps the monthly credit pack, and buys an add-on, without a sales call.
- **Flow:** 1. **Settings → Plan & Billing**. 2. Plan card with current tier and cycle; pack selector as a vertical list of "credits/month → $/month → effective $/credit" rows; the Free Tier row is the baseline and packs add on top of it (10 included +10 = 20 total, $39/mo; scaling to +490 → 500 credits, $1,399/mo). 3. **Add-ons** block with **Add Teams** (F7.24). 4. **Go to portal** for payment and invoices (F7.23). 5. **Cancel plan** (F7.22). 6. `[empty]` on Free Tier the pack list is the primary call to action, priced per credit so the volume discount is visible while choosing. 7. `[error: card declined — update card]` returns the user to the same card, add-on not applied.
- **Why it is easy:** the pack list shows three numbers per row (credits, dollars, rate) so the discount curve is discoverable without a calculator tab.
- **Gates:** managing billing is an Admin permission in the role matrix; USD only; card only for packs, ACH/custom invoicing on Enterprise.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans.md, https://roboflow.com/pricing

### F7.13 Credit burn-down chart with cumulative / daily toggle (RF: *Usage Chart*)
- **What the user does:** answers "are we going to run out this cycle" in one look.
- **Flow:** 1. **Settings → Credit usage**. 2. Header: link to "how credits work", **Audit log** button, and the current plan cycle. 3. Chart defaults to cumulative (bar = total spent this cycle); toggle off for per-day bars that expose spikes. 4. Date range: plan cycle, or explicit dates. 5. **Display by** credits or dollars (dollars use the workspace's own per-credit price, which can differ per plan or contract). 6. `[empty]` chart shows an empty axis with "no usage in this range". 7. `[loading]` chart skeleton, filters still interactive.
- **Why it is easy:** cumulative-first is the right default for a limit, and the daily toggle is one click away for the "what happened on Tuesday" question — the same chart answers both without a second page.
- **Gates:** viewing credit usage is a permission; the free tier cannot exceed 10 credits anyway.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/view-credit-usage.md

### F7.14 Attribution filters: by key, folder and member (RF: *Attribution*)
- **What the user does:** finds out which camera fleet, project folder or person burned the credits.
- **Flow:** 1. Same page → **Attribution** filter → segment **API keys** / **Folders** / **Members**. 2. Folders render as a collapsible tree with a checkbox per node; deselecting a parent excludes its direct usage and keeps the children — roll-up is the default, not a mode. 3. Members list shows spend per person plus a synthetic **Workspace usage (no member)** row for storage, background jobs and plain API-key traffic. 4. An auth-group dropdown narrows the member list. 5. **Usage type** filter is a two-level drill-down that only lists categories that actually recorded usage. 6. `[empty]` a filter segment with no data is hidden rather than shown as zero.
- **Why it is easy:** hiding zero-usage categories keeps the filter honest; the explicit "no member" bucket prevents the classic mistake of assuming the member list sums to the total.
- **Gates:** folder attribution needs Billing Folders (Enterprise); key and member attribution are on the standard page.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/view-credit-usage.md

### F7.15 Cycle breakdown plus a limits meter (RF: *Current Cycle Breakdown*)
- **What the user does:** sees spend split by feature and by Dataset / Train / Deploy, and how close the workspace is to its caps.
- **Flow:** 1. Same page, **Current cycle** section: summary by feature, then three stacked groups. 2. Bottom of page: meters for **team members** and **projects** against plan limits. 3. `[error: at limit]` the meter turns to a distinct state and the invite / create-project buttons explain why they are disabled.
- **Why it is easy:** usage and plan limits live on one page, so "we are out of seats" and "we are out of credits" are not two different support tickets.
- **Gates:** Core is 20 projects; team seats follow the plan (unlimited admins, with the Teams add-on capping non-admins at 10).
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/view-credit-usage.md, https://roboflow.com/pricing

### F7.16 Forward projection with saved scenarios (RF: *Usage Projection*)
- **What the user does:** models next month's bill before committing to a bigger pack.
- **Flow:** 1. **Credit usage → Projection** tab. 2. Two headline numbers: projected credits and projected extra credits beyond the included allowance. 3. **Customize assumptions** → choose horizon (this cycle end, next cycle end, 3 months, 1 year, custom date), choose the historical basis period, then edit per-feature rates for "what if we double inference" modelling. 4. **Save** a scenario, **share** by link, or **publish** it publicly.
- **Why it is easy:** projections are named, savable objects rather than a throwaway number, so a finance conversation can reopen the same scenario a week later.
- **Gates:** Admin-ish (usage visibility); publishing a projection makes cost assumptions public — worth a warning we should add.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/view-credit-usage.md

### F7.17 Consumption audit log, distinct from the security audit log (RF: *Credit Consumption Audit Log*)
- **What the user does:** reconciles a surprise charge down to the feature and the minute.
- **Flow:** 1. **Credit usage** → **Audit log**. 2. Pick a date range → **Search**. 3. Rows show timestamp, feature, credits. 4. `[empty]` "no credit usage in this range".
- **Why it is easy:** it is deliberately separate from the security audit log and reachable from the billing surface, which is where the question is actually asked.
- **Gates:** nothing stated beyond usage visibility.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/view-credit-usage.md

### F7.18 Training cost estimator before spending (RF: *Training Cost Estimator*)
- **What the user does:** predicts runtime and credits for a planned run.
- **Flow:** 1. **Credit usage** → bottom of page → expand **Training cost estimator**. 2. Inputs: model type, epoch count, dataset shape. 3. Output: expected duration and credit cost. 4. `[empty]` estimator stays collapsed; it is a disclosure, not a page.
- **Why it is easy:** the estimate is co-located with the burn-down, so a user can see the projected hit against the remaining allowance in the same viewport.
- **Gates:** none stated.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/view-credit-usage.md

### F7.19 Prepaid credit purchase with volume price shown (RF: *Prepaid Credits*)
- **What the user does:** buys a one-off block so a launch week does not hit the flex rate.
- **Flow:** 1. Warning banner or Plan & Billing → **Buy prepaid credits**. 2. Purchase screen shows the workspace's current price and volume discount, then quantity → checkout. 3. Prepaid credits are spent only after included credits and expire one year after purchase; balance is verifiable on the plan page. 4. `[error: payment declined]` inline, no partial credit grant.
- **Why it is easy:** the buyer sees their own discounted rate in the same screen as the quantity, so the "is this cheaper than on-demand" comparison is not a separate research task.
- **Gates:** card required; starting at $4/credit vs $6 on-demand per the pricing page.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans.md, https://roboflow.com/pricing

### F7.20 Flex (on-demand) billing with an explicit spend cap (RF: *Flex Billing*)
- **What the user does:** decides whether the workspace may auto-spend past its allowance, and caps the damage.
- **Flow:** 1. **Plan & Billing → Flex billing** card. 2. Toggle on → confirm **Enable**; a default cap of $100/month applies ($1,200/year on annual plans). Buying a first paid pack also turns it on with that default. 3. **Monthly spending cap** checkbox + amount, saved by **Save cap**, Enter, or clicking outside the field. Entering `0` disables flex after a confirm. 4. Clearing the cap → **Remove cap** confirm warns that spend becomes unlimited. 5. Disable flex → dialog warns that in-flight training and deployments stop when credits run out.
- **Why it is easy:** the cap saves on blur — three ways to commit the same edit — and the disable dialog names the real consequence (running jobs stop) rather than a generic warning.
- **Gates:** Free Tier has no flex; payment method must exist; flex is billed monthly even on annual plans.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/enable-or-disable-flex-billing.md

### F7.21 Three-stage "you are spending" notices (RF: *80% / at-cap / consuming*)
- **What the user does:** gets warned inside the working app, not by email.
- **Flow:** 1. At 80% of included credits: a banner in the workspace with the percentage and a link offering credit options sized to the plan and recent usage. 2. At 80% of the flex cap: a warning with the percentage and two actions — raise cap, buy prepaid. 3. At the cap: a notice saying credit-requiring actions are blocked until cap raise, prepaid purchase, or the next cycle. 4. While flex is being consumed: an informational notice recommending prepaid for a lower rate. 5. `[error: out of credits]` credit-requiring actions fail with a pointer to the same options.
- **Why it is easy:** the 80% warning links to an option that is already sized to observed usage, so the user does not have to guess which pack to buy mid-task.
- **Gates:** none to see the banner; acting on it is Admin for purchases.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans.md, https://docs.roboflow.com/platform/billing-and-plans/enable-or-disable-flex-billing.md, https://roboflow.com/credits

### F7.22 Cancel plan with an explicit end state (RF: *Cancel Plan*)
- **What the user does:** stops paying and knows exactly what survives.
- **Flow:** 1. **Plan & Billing → Cancel plan**. 2. Confirmation screen. 3. Success screen states the downgrade took effect. 4. The post-cancel rules are spelled out: access continues to cycle end, then the workspace drops to the Free Tier (unlimited users, private projects, 10 credits/month); unused included credits are forfeited; one final flex invoice; prepaid credits survive until expiry; no on-demand billing on Free, so work stops when credits run out.
- **Why it is easy:** the confirmation screen doubles as the "what happens next" page, and every sentence is about data or access rather than sentiment.
- **Gates:** billing permission.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/cancel-a-plan.md

### F7.23 Billing portal: card, billing details, invoice history (RF: *Billing Portal*)
- **What the user does:** updates the card, changes the billing email/address/tax ID, downloads a past invoice.
- **Flow:** 1. **Plan & Billing → Go to portal** (leaves the app into a hosted billing UI). 2. **Add payment method** → details → **Add**, with a "make default" checkbox before submit. 3. **Update information** → edit fields → **Save**. 4. Invoice list: click an invoice to open; **View more** for older; search icon to find one; per invoice **download invoice**, **download receipt**, or view payment detail.
- **Why it is easy:** the invoice row offers invoice, receipt and payment detail as three separate downloads, which matches how finance teams actually file things.
- **Gates:** billing permission; hosted surface means our own design cannot control its styling — plan for either an embedded payment provider portal or an in-app invoices table.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/billing-portal.md

### F7.24 Teams add-on: buy, and what turns off on cancel (RF: *Teams Add-On*)
- **What the user does:** adds labeler/reviewer roles and self-serve SSO to a cheap workspace.
- **Flow:** 1. **Plan & Billing → Add-ons → Add Teams**. 2. Checkout (card only; bank-account payers must add a card first). If a bank verification step appears, follow it; a declined charge means Teams is not added and an **Update card** action is offered. 3. On success return to Plan & Billing. 4. **Cancel Teams**: stays on until period end. 5. On expiry: every member becomes an Admin, SSO turns off (sign-in falls back to emailed links), and Review mode, annotation insights and workflow version history turn off. 6. `[error: more than 10 non-admin members — make some admins or remove them first]` blocks the purchase.
- **Why it is easy:** the downgrade consequences are documented as a list, so a buyer can see the trap before opting in — and the seat precondition is a pre-flight check, not a post-payment failure.
- **Gates:** any paid workspace; unlimited admins + up to 10 non-admins; not sold in the EU region.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans/teams-add-on.md, https://roboflow.com/pricing

---

## API keys and sign-in

### F7.25 Key table whose badges carry the state (RF: *API Keys*)
- **What the user does:** audits every credential in the workspace at a glance.
- **Flow:** 1. **Settings → API Keys** (`[error: you do not have permission to view workspace keys]` for a non-admin). 2. Table columns: name, badges, created by/when, masked value with reveal and copy, rotation status, `⋯` actions (**Edit**, **Protect**, **Roll**, **Disable**, **Revoke**). 3. Badges: Default, In use, Protected, Disabled (hover shows the reason), Full access / Scoped, Rotate by / Due in / Due today / Overdue / No rotation date, New. 4. Device-created keys replace the row actions with a **View device** button. 5. Table can be filtered to only keys due for rotation. 6. `[empty]` explanatory block plus **Generate new key**.
- **Why it is easy:** every risk state (protected, disabled, overdue, in use, new) is a badge on the row, so an admin can scan one table instead of opening each key.
- **Gates:** "View workspace API keys" permission; Advanced keys adds disable, default and rotation.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/manage-api-keys-in-the-dashboard.md
- **LabelDesk hook points:** `apps/backend/app/routers/workspaces.py` (`/keys`, `/keys/{kid}`), `apps/frontend/src/features/settings/Settings.tsx`

### F7.26 Create a key with a one-time reveal (RF: *Generate New Key*)
- **What the user does:** mints a credential for a new CI job or camera gateway.
- **Flow:** 1. **Generate new key** → **Key name** (docs recommend naming after the consumer: "ci-pipeline", "line-3-camera-gateway") → **Create API key**. 2. A "Key created" dialog shows the value once; the copy instructs storing it in a secret manager or an uncommitted env file. 3. Afterwards members with copy permission can reveal it from the table; the API and CLI never return it again. 4. Optional (Advanced): custom metadata, set-as-default, rotation due date, owners, per-section permissions. 5. `[error: no permission to create a key]`.
- **Why it is easy:** one dialog, one name, one reveal, and the naming advice is placed at the moment the name is typed.
- **Gates:** create-key permission; folder-scoped creation needs access to that folder.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/manage-api-keys-in-the-dashboard.md

### F7.27 Rename, protect, disable, revoke — four different strengths (RF: *Protect / Disable / Revoke*)
- **What the user does:** picks the least destructive action that solves the problem.
- **Flow:** 1. **Edit** → rename → **Save** (value unchanged). 2. Shield icon → confirm: a protected key cannot be disabled, revoked, rolled or re-permissioned from dashboard, API, CLI or MCP; unprotecting is dashboard-only. 3. Pause icon → confirm: consumers get auth errors immediately, value unchanged, play icon restores. 4. Trash icon → confirm: permanent and immediate; the last workspace key cannot be revoked from the table. 5. A key backing a dedicated deployment needs an extra dependency acknowledgement, and the deployment pauses within minutes.
- **Why it is easy:** the ladder rename → disable → revoke is visible as three icons on one row, so an operator under pressure has a reversible option next to the irreversible one.
- **Gates:** update-key permission for rename/protect/disable, revoke-key for revoke; disable requires Advanced keys; protected keys resist automation by design.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/manage-api-keys-in-the-dashboard.md

### F7.28 Atomic roll (rotate) with a dependency warning (RF: *Roll*)
- **What the user does:** swaps a leaked or aged key in one step, keeping name, scopes, folders, metadata and disabled state.
- **Flow:** 1. **Roll** icon → dialog lists what is known to depend on the key: dedicated deployments, billing folders, edge devices, workspace default, recent billed usage in the last 30 days. 2. If anything is listed (or the check could not complete) the confirm button stays disabled until **"I understand what depends on this key"** is ticked. 3. **Roll this key** → row highlights, marked **New**, new value copied. 4. Deployments migrate automatically; if one cannot move, the roll fails with "the key was not rolled", the old key stays live, and a same-named replacement may already exist — check the list before retrying. 5. Watch consumer logs for 401/403: rejected calls on a revoked key are not recorded on the platform side.
- **Why it is easy:** the hard part of rotation is knowing the blast radius, and the dialog answers it before the action instead of after. The alternative path — create a second key, migrate one consumer at a time, revoke the old — is documented as a first-class choice for planned rotations.
- **Gates:** create-key + revoke-key permissions; protected keys must be unprotected first; last key cannot be revoked.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/rotate-api-keys.md, https://docs.roboflow.com/reference/authentication/authentication/manage-api-keys-in-the-dashboard.md

### F7.29 Per-key permission scoping with silent 404s (RF: *Scoped Keys*)
- **What the user does:** gives an edge device inference rights and nothing else.
- **Flow:** 1. In the create dialog, **Key permissions** is grouped by section (Workspace, Projects, Workflows, Images, Models and inference, API keys); everything is preselected except key management. 2. Untick, or **Deselect all** then pick a few. 3. Change later by clicking the **Scoped / Full access** badge on the row. 4. A request needing an absent permission returns 404, as if the route did not exist. 5. From API/CLI a key can also be scoped by role name.
- **Why it is easy:** default-deny on key management means a leaked key cannot mint more keys, and 404-instead-of-403 avoids leaking which endpoints exist.
- **Gates:** Advanced keys, an Enterprise add-on; locked dialogs otherwise.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/scoped-api-keys.md

### F7.30 Folder keys scoped to one project folder (RF: *Folder API Keys*)
- **What the user does:** issues one key per site or production line so a leak or rotation affects one folder.
- **Flow:** 1. Project folder card → **API keys** → **Generate new key**; or **Settings → API Keys → Folder API keys** → pick a folder. 2. Both surfaces show the same table and the same row actions as workspace keys. 3. A folder key cannot be the workspace default, and its usage is attributed to that folder. 4. `[error: no write access to this folder]` hides the entry from the folder menu.
- **Why it is easy:** the credential lives next to the thing it protects, so the team running a site can rotate their own key without an admin round-trip.
- **Gates:** Advanced keys; folder write access plus key permissions.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/scoped-api-keys.md

### F7.31 Key metadata and named owners (RF: *Custom Metadata / Owners*)
- **What the user does:** records who is responsible for a key and what it serves, so rotation does not become archaeology.
- **Flow:** 1. Under **Custom metadata** in create/edit: **Add field**, up to 20 key/value pairs (`owner=platform-team`, `env=prod`, `cost-center=4711`), keys ≤100 chars, values ≤500. 2. Once any key has metadata, a **Metadata** column appears in the table. 3. **Owners** field takes members who can roll the key; leaving it empty emails everyone who can.
- **Why it is easy:** metadata is optional and column-adaptive — zero cost until used, then a column appears — which is how you get adoption without a migration.
- **Gates:** Advanced keys; owners must have verified email or IdP-confirmed address.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/scoped-api-keys.md, https://docs.roboflow.com/reference/authentication/authentication/rotate-api-keys.md

### F7.32 Rotation due dates and one reminder per date (RF: *Rotation Reminders*)
- **What the user does:** puts an expiry culture on keys without enforcing expiry.
- **Flow:** 1. Set **Rotation due date** at create or edit; **Suggest one year** fills a date a year out; clearing it stops reminders. 2. One email per recipient, on a day from 15 days before the due date through the due day, only while the key is active. 3. Table shows **Rotate by**, then **Due in** from 30 days out, **Due today**, **Overdue**. 4. Rolling moves the date forward by the same interval, capped at a year. 5. `[empty]` keys with no date show **No rotation date** and are excluded from the due filter.
- **Why it is easy:** the date is advisory — nothing breaks on it — which is why teams actually set one; and the badge ladder makes the due filter a one-click triage.
- **Gates:** Advanced keys; a disabled key through the reminder window gets no mail; a billing-restricted workspace gets none.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/rotate-api-keys.md

### F7.33 Default key vs. "in use" fallback, surfaced in the UI (RF: *Default and In Use Keys*)
- **What the user does:** controls which credential the product itself spends under.
- **Flow:** 1. **Set as default for this workspace** in create/edit → **Default** badge. 2. Default must keep workspace:read, project:read, version:read, image:read, model:infer, workflow:read; those are added and locked. 3. With no default, the app falls back to a full-access key, else the oldest enabled key with those permissions, and the row shows **In use**. 4. If no key qualifies, the table shows a warning; an admin gets one auto-created on next need, a non-admin has app-run actions fail (running models, previewing workflows, auto-labeling, evaluation, dataset export).
- **Why it is easy:** the invisible fallback is made visible as a badge, which is the difference between "which key do I disable" and an outage.
- **Gates:** Advanced keys; a folder key cannot be default; default is dashboard-only, not API.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/manage-api-keys-in-the-dashboard.md

### F7.34 Public non-secret key for browser/edge inference (RF: *Publishable Key*)
- **What the user does:** embeds inference in a web page or device without shipping a secret.
- **Flow:** 1. Read the workspace's publishable key from the auth docs / key page instead of minting one. 2. It is derived from the workspace ID (`rf_<workspaceId>`), inference- and weight-download-only, and cannot be rotated or revoked. 3. `[error: rejected]` management endpoints refuse it as a credential.
- **Why it is easy:** "safe to embed" is a distinct credential type rather than a scoped private key, so developers stop pasting secrets into frontend bundles.
- **Gates:** tied to workspace existence; nothing to rotate means it must stay low-privilege forever.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication.md

### F7.35 Self-serve SSO setup with DNS proof (RF: *Single Sign-On*)
- **What the user does:** connects the company IdP without a support ticket.
- **Flow:** 1. **Settings → Team members → SSO** tab → **Enable single sign-on**. 2. **Domain verification** → **Verify domain** opens an admin portal in a new tab; add the email domain and publish the TXT record. **Verify another domain** for more. 3. Back on the tab each domain reads **Pending**, **Verified** or **Failed**. 4. With at least one verified domain, **Set up SSO** → choose the identity provider and follow its steps in the portal. 5. The SSO card reads **Active** when the connection works; **Manage SSO** changes it later. 6. Sign-in page carries **Continue with SSO** next to Google, GitHub and email; an unconfigured domain shows an inline error. 7. `[empty]` before setup, both cards are unelevated placeholders.
- **Why it is easy:** the DNS state machine (Pending / Verified / Failed) is shown per domain on the same tab that starts the setup, so a failed verification has a visible home.
- **Gates:** Teams add-on or Enterprise; "Manage single sign-on" permission; domain TXT control required.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/single-sign-on-sso.md

### F7.36 OAuth sign-in for third-party apps (RF: *Sign in with Roboflow*)
- **What the user does:** grants an external tool scoped access without handing over a workspace key.
- **Flow:** 1. App sends the user through an OAuth 2.1 authorization-code + PKCE redirect. 2. User signs in and consents. 3. Usage made with the resulting token is attributed to that member in credit usage; OAuth tokens can read and control video jobs but cannot start them. 4. OAuth app create/update/revoke, client-secret rotation, install and consent events are all audit-logged.
- **Why it is easy:** per-user tokens make spend attributable to a person, which plain workspace keys cannot do.
- **Gates:** developer-side registration; scope list per app; some operations deliberately denied to OAuth.
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication.md, https://docs.roboflow.com/platform/enterprise-features/audit-logs-and-siem-export.md

### F7.37 CLI/SDK auth handshake (RF: *Install and Set Up the CLI*)
- **What the user does:** authenticates a laptop and pins a default workspace.
- **Flow:** 1. Install the CLI, run its auth step with a key, set a default workspace, enable shell completion. 2. Auth failures surface as errors from the same commands (`roboflow workspace plan`, `roboflow workspace usage`). 3. Title-only beyond the index entry.
- **Why it is easy:** the default-workspace setting removes a repeated flag from every later command.
- **Gates:** a key with sufficient scopes; `route: 404` for missing scopes confuses CLI users, worth a clearer message in ours.
- **Sources:** https://docs.roboflow.com/llms.txt (index entry for the CLI install page; page not opened)

---

## Audit and compliance

### F7.38 Audit log table with four filters (RF: *Audit Logs*)
- **What the user does:** answers "who deleted that version" without asking engineering.
- **Flow:** 1. **Settings → Audit logs**, opens on the **Logs** tab. 2. Columns: timestamp (UTC), actor (user / API key / system), action, resource. 3. Filters: **Actor** (person, key, or actor type), **Action** (`member_added`, `project_deleted`, …), **Resource** (or resource type), **Folders**. 4. Folders and Resource are one filter slot: choosing a folder clears the resource, and **All resources** clears it back. 5. Rows load as you scroll. 6. Click a row → detail with the change set, previous and new values. 7. `[empty]` no matching events for the filter combination. 8. Queryable for 365 days by default.
- **Why it is easy:** the row expands in place to show before/after values, so a compliance question is answered without leaving the table or exporting.
- **Gates:** premium feature; SIEM export is a further Enterprise add-on.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/audit-logs-and-siem-export.md
- **LabelDesk hook points:** `apps/backend/app/routers/audit.py`, `apps/backend/app/routers/workspaces.py` (`/audit`)

### F7.39 Audit coverage that spans admin, data and agent changes (RF: *What's recorded*)
- **What the user does:** relies on the log for the categories auditors ask about.
- **Flow:** covered categories — team members (added, removed, invite sent/cancelled, role changed, default role changed, folder access), custom roles, folders, projects, datasets and images (uploaded, deleted, approved, split assigned, version deleted/restored), workflows (created, published, deleted, restored, block allowed/blocked), training and exports (run started/stopped, dataset exported, search exported, weights downloaded), devices and streams, vision events deletion including operator feedback, API keys (created, updated, revoked, rolled — including renames, permission and metadata changes, default assignment, enable/disable), OAuth apps, and SIEM config changes.
- **Why it is easy:** the category list itself is a spec for what our own audit writer must emit — label approvals and dataset exports included, not just admin CRUD.
- **Gates:** premium; some categories belong to features we may not have yet.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/audit-logs-and-siem-export.md

### F7.40 SIEM streaming with a real test event (RF: *SIEM Integration*)
- **What the user does:** pipes audit events into Splunk / Elastic / Datadog / an OTel collector.
- **Flow:** 1. **Settings → Audit logs → SIEM integration** tab → **Enable SIEM integration**. 2. Enter **OTLP endpoint URL**; choose protocol gRPC (port 4317, base URL) or HTTP/Protobuf (4318, full `/v1/logs` path). 3. Optional **Headers** as JSON, typically a bearer token. 4. **Test connection** sends a real OTLP record using the unsaved form values, then appears in the SIEM within seconds (search `audit.action = test_connection`). 5. **Save**. 6. `[error: connection refused / timeout]`, `[401/403 from collector]`, `[TLS error — collector must present a publicly trusted certificate]`, `[HTTP path mismatch — include /v1/logs]` each have a named cause in the docs. 7. Config changes themselves log as `siem_config_updated`.
- **Why it is easy:** test-without-saving plus an event you can hunt for on the SIEM side turns a two-team debugging session into a 30-second check.
- **Gates:** select Enterprise customers.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/audit-logs-and-siem-export.md

### F7.41 Directory-group sync, workspace gating and auto-join (RF: *AD group sync*)
- **What the user does:** lets the IdP decide who is in which workspace and which role.
- **Flow:** 1. Attributes from the SSO profile map to authorization groups at sign-in. 2. Per workspace: **required groups** (only members of at least one) and **auto-join** (on → matching users are added at sign-in without an invite). 3. Four stated combinations: neither (manual invite), auto-join only (all SSO users added), required only (non-matching members removed, new users still need an invite), both (matching added, non-matching removed). 4. Custom roles mapped to IdP groups are reconciled every sign-in: matching roles assigned, non-matching removed, manually assigned roles preserved; losing all mapped roles falls back to the default role. 5. `[error: not in a required group]` the user loses access on next sign-in. 6. Admins are exempt from gating; the environment's default workspace is never gated.
- **Why it is easy:** the four-row behaviour table makes an otherwise invisible sync rule auditable before it removes someone.
- **Gates:** Enterprise; configured by sales/account rep, not self-serve.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/single-sign-on-sso.md

### F7.42 Custom branding of login and navigation (RF: *Custom Branding*)
- **What the user does:** makes the product look like their own.
- **Flow:** 1. **Settings → Branding** (Enterprise SSO environments). 2. Editable: login screen (org logo, logo size, accent colour, card background and border, button colour, wordmark colour), sidebar (hover background, selected/unselected text and icon colours, logo border), loading image (PNG/JPEG/GIF/WebP up to 2 MB, no SVG). 3. **Save changes** applies immediately to everyone in the SSO environment; **Discard changes** reverts to saved. 4. `[error: SVG not supported]`, `[error: file too large]`.
- **Why it is easy:** save/discard with an explicit "only your SSO environment" scope means a half-finished theme never leaks to other tenants.
- **Gates:** Enterprise; enabled through the account rep.
- **Sources:** https://docs.roboflow.com/platform/enterprise-features/single-sign-on-sso.md

### F7.43 30-day workspace trash with permanent delete kept in the UI only (RF: *Trash*)
- **What the user does:** undoes an accidental project, version, training or workflow deletion.
- **Flow:** 1. **Settings → Trash**. Items grouped by type with who deleted it, when, and days remaining. 2. **Restore** on a row, or checkbox-select several → **Restore**; **Restore all** for the whole trash. 3. `[error: restore the parent project first]` for versions and trainings. 4. **Delete permanently** per row or in bulk, **Empty trash** for everything — with a confirm. 5. Deleting hides the item from the app and API, cancels in-flight training so credits stop, stops serving models, and keeps storage counted against the plan until cleanup. 6. An amber marker on a row shows that images belonging only to that project will also go at cleanup; images shared with other projects survive.
- **Why it is easy:** the retention window, the storage-charging nuance and the "shared images survive" rule are all shown on the row that will act on them. Permanent deletion is deliberately absent from API/SDK/CLI so a script cannot destroy data.
- **Gates:** trash permissions are granular per role (`view_trash`, `trash_dataset`, `restore_version`, `trash_training`, …); permanent delete is web-app only.
- **Sources:** https://docs.roboflow.com/platform/workspaces/trash.md
- **LabelDesk hook points:** `apps/frontend/src/features/settings/Settings.tsx` (Trash tab), `apps/backend/app/routers/workspaces.py` (`/trash`)

### F7.44 Private-data licensing opt-out, scoped and reversible (RF: *Data Licensing and Model Training*)
- **What the user does:** stops private-project data being used to improve vendor products or licensed datasets.
- **Flow:** 1. **Settings → Project settings** → **Data licensing and model training** switch. 2. Turning it off → **Turn off** confirm. 3. Effects are stated precisely: it applies to private projects only, does not publish anything, stops future collection, and does not delete already-collected data or change project visibility. 4. `[error: setting locked by plan, compliance policy or region]` — contact support.
- **Why it is easy:** the copy separates "future collection", "already collected" and "visibility" into three sentences, which is exactly the three questions a buyer asks.
- **Gates:** on by default for new workspaces, off for auto-migrated ones; Enterprise data is never included; opt-out free on any plan.
- **Sources:** https://docs.roboflow.com/platform/billing-and-plans.md, https://roboflow.com/pricing

### F7.45 Contractual and regional controls (RF: Enterprise add-ons)
- **What the user does:** satisfies procurement: DPA/MSA, security review, region choice, HIPAA BAA, SLA.
- **Flow:** stated on the pricing page as Enterprise add-ons grouped under "custom contracting and billing": customised MSA and DPA, enterprise security review, procurement services and invoicing, HIPAA compliance and BAA, multi-year pricing, self-hosted weights commercial licensing. **Data sovereignty** offers United States or EU. Uptime SLA and email/ticket/chat support are Enterprise. 2. `[empty]` none of this is self-serve in the app — it is a sales motion.
- **Why it is easy:** procurement items are listed with the same weight as features, which is what an enterprise buyer needs to see; but nothing is clickable, so treat as a spec for a Trust/legal page rather than a UI flow.
- **Gates:** Enterprise only; EU region noted as excluding the Teams add-on.
- **Sources:** https://roboflow.com/pricing, https://docs.roboflow.com/platform/billing-and-plans.md

---

## Integrations

### F7.46 A named credential store for external providers (RF: *Credentials*)
- **What the user does:** saves bucket access once and reuses it across datasources.
- **Flow:** 1. **Settings → Credentials** → **Add credential**. 2. Provider-specific form; stored encrypted and reusable. 3. `[error: cannot list bucket — check the key policy]` appears on save/validate. 4. `[empty]` no credentials → the datasource form's credential dropdown offers **+** to add one without leaving.
- **Why it is easy:** the "+" beside the dropdown is the difference between one form and two forms plus a lost draft.
- **Gates:** Admin-ish; least-privilege guidance per provider.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md

### F7.47 Bucket mirror datasource with two-tab setup (RF: *Datasources*)
- **What the user does:** keeps a cloud bucket and the workspace in sync continuously instead of re-uploading.
- **Flow:** 1. **Settings → Datasources → Create datasource**. 2. **Connection** tab: name, provider, bucket, region, credential. Bucket takes a name only (`my-bucket`, `s3://my-bucket`); a path after the name is rejected. 3. **Mirror configuration** tab: **Import destination** (Workspace, optionally into a project; or a folder on plans with folder permissions), **File filters** (glob or `.txt` list in the bucket, or explicit path whitelist), naming strategy (full path / filename / ETag / metadata key), image update and metadata sync behaviour, orphan removal. 4. **Scheduling** section → **Run automatically on a daily schedule** (off by default). 5. `[error: endpoint points to localhost or a private address]` for S3-compatible endpoints; wrong path-style setting fails the connection test with a message telling you to switch it. 6. `[empty]` before any sync, the eye icon into the asset library is disabled.
- **Why it is easy:** connection and mirror policy are separate tabs — credentials do not have to be re-entered to change a glob — and the connection test tells you which toggle is wrong.
- **Gates:** folder destination needs folder permissions; video mirrored to the asset library only (no frame extraction).
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md

### F7.48 Mirror trigger guards that prevent cost surprises (RF: *manual trigger guards*)
- **What the user does:** re-runs a sync on purpose, without stampeding the bucket.
- **Flow:** 1. **Datasources** list → play icon on a row. 2. `[error: a sync is already running]`. 3. After completion, re-trigger is blocked for 15 minutes; the tooltip shows minutes remaining. 4. Cooldown is skipped if the last run found nothing new, the config changed since, or the last run errored. 5. Hard cap of 10 manual syncs per rolling hour, even when a cooldown skip applies. 6. Scheduled runs bypass both.
- **Why it is easy:** the tooltip carries the countdown, so a blocked button explains itself; and the skip conditions mean the guard never blocks a legitimate retry after a failure.
- **Gates:** plan-dependent; orphan removal is opt-in and warns before it deletes.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md

### F7.49 Webhook push from a processing pipeline (RF: *Webhook Sink*)
- **What the user does:** posts results (or an annotated image) to their own endpoint.
- **Flow:** 1. In the pipeline editor add the webhook step; set URL, method (GET/POST/PUT), query parameters, headers, JSON body, multipart file parts, per-field transform operations, request timeout. 2. **Fire and forget** runs the request in the background but then `error_status` is always false — the docs recommend synchronous for debugging. 3. **Cooldown** defaults to 5 s and suppresses bursts, emitting a throttling flag instead of sending; it only applies to local pipeline execution, not stateless HTTP runtimes. 4. A runtime input can disable the sink for one caller. 5. `[error: destination not public / redirect rejected / proxy refused]` under the hardened transport mode, which also blocks loopback, private, link-local, CGNAT and metadata addresses.
- **Why it is easy:** the failure semantics are documented per mode (sync vs fire-and-forget), which stops the "why is error_status always false" trap.
- **Gates:** internet required (not air-gapped); hardened transport is an env flag on self-hosted.
- **Sources:** https://docs.roboflow.com/workflows/blocks/blocks/data-storage/webhook-sink.md

### F7.50 Third-party AI billed through the workspace (RF: *3rd-party blocks / managed keys*)
- **What the user does:** uses OpenAI / Claude / Gemini / Grok / OpenRouter / OCR inside a pipeline without holding each vendor's key.
- **Flow:** 1. Add a third-party model step; it runs on a workspace-managed key. 2. Cost is converted from vendor tokens to workspace credits at published per-model rates (e.g. 1 credit buys 1,000,000 input / 200,000 output tokens on one mid-tier Claude model; $2.00 of OpenRouter usage; 1,000 OCR images). 3. `[error: out of credits]` the step fails with the credit path (F7.21). 4. `[empty]` vendors without a configured workspace key are absent from the picker.
- **Why it is easy:** one bill and one quota for five vendors removes the "who owns the OpenAI key" problem; the token-to-credit rate table makes the markup inspectable.
- **Gates:** credits; some requests cost more (EU processing +10%, an ultrafast tier at 6×); certain regions excluded for SMS.
- **Sources:** https://roboflow.com/credits, https://docs.roboflow.com/platform/billing-and-plans.md

### F7.51 Notification sinks and their per-message credit cost (RF: *notification blocks*)
- **What the user does:** has a pipeline send an email, Slack message or SMS when a condition fires.
- **Flow:** 1. Add the email / chat / SMS notification step to a pipeline. 2. Cost per credit: 100 emails, 30 SMS/MMS in US/Canada, 10 international. 3. `[error: vendor unavailable in this country]` for high-cost destinations. 4. Slack-specific setup steps were not opened — see Title-only.
- **Why it is easy:** metering notifications in the same currency as compute keeps one burn-down honest; a Slack alert costing 0.01 credit is easy to reason about.
- **Gates:** credits; Twilio restrictions.
- **Sources:** https://roboflow.com/credits

### F7.52 Handoff to external training platforms (RF: *Azure Vision / Google Cloud training*)
- **What the user does:** trains on a partner platform and pulls the resulting weights back to the workspace.
- **Flow:** title-only. Index entries exist for "Train from Azure Vision" and third-party training integrations; steps, credentials and failure states were not read.
- **Gates:** unknown.
- **Sources:** https://docs.roboflow.com/llms.txt (index entries only; pages not opened)

---

## Public dataset sharing (Universe)

### F7.53 Publish a project publicly with an explicit licence choice (RF: *Make a Project Public*)
- **What the user does:** releases a dataset and its models to the public catalogue.
- **Flow:** 1. **Projects** page → `⋯` on a project → **Make public**. 2. Licence picker dialog. 3. A pre-publish warning names what must never be published: copyrighted images, proprietary data, NSFW/NSFL, personal data — with "use a private workspace" as the alternative. 4. Confirm → the project gains a public page. 5. **Make private** reverses it from the same menu; a private project is unlisted. 6. `[error: public projects are disabled for this workspace]`.
- **Why it is easy:** the licence decision is a required dialog step rather than a settings field, so the choice is made before the data is out, not after.
- **Gates:** a workspace-level **Public projects** switch can forbid it; Enterprise has it off by default; plan, compliance policy or EU region can lock the switch; already-public projects stay public until someone unpublishes.
- **Sources:** https://docs.roboflow.com/datasets/manage/make-a-project-public.md
- **LabelDesk hook points:** `apps/backend/app/routers/privacy.py` (privacy surface router), `apps/frontend/src/features/settings/Settings.tsx` (Privacy tab)

### F7.54 Public project page: description, badges, sharing stats (RF: *Project Overview / Sharing Statistics*)
- **What the user does:** polishes the public listing and measures interest.
- **Flow:** 1. Project → `⋯` → **Project overview**. 2. **Set description** gives the public page its copy. 3. Scroll to **Sharing statistics**: stars, views (30 days and all time), dataset downloads (30 days and all time). 4. Share badges with a copy icon yielding HTML to paste into a README or site. 5. `[empty]` before any traffic, the chart renders flat and the badge card is the only actionable element.
- **Why it is easy:** embeddable badges are generated in the same place the numbers are read, which is the moment a maintainer wants them.
- **Gates:** project must be public.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/view-project-analytics.md

### F7.55 Fork a public dataset into your workspace (RF: *Fork Project*)
- **What the user does:** starts a project from someone else's public data.
- **Flow:** 1. On a public dataset page → **Use this dataset** → **Fork project**. 2. Requires sign-in. 3. Images and annotations are copied into a new project in your workspace; the fork starts with fresh versions and export settings, so your own preprocessing and augmentation choices apply. 4. You land on a page offering to generate a dataset version. 5. API equivalent is an async task: request returns 202 with a task id and polling URL; poll until done then read the project from the task result. 6. `[error: 402 not enough credits or image quota]`, `[403 source is not public]`, `[404 not found / missing scope / wrong workspace]`, `[409 you already own this project]`, `[422 missing parameter or no project slug in the URL]`. 7. Web-app `[loading]` copy progress.
- **Why it is easy:** quota and permission failures have distinct codes with distinct fixes, and the arrival state is "make a version" rather than an empty project shell.
- **Gates:** `project:create` scope for API; credits and image quota for large forks; signed-in account.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/fork-a-universe-dataset.md

### F7.56 Star and reuse a public model as a training start point (RF: *Star / Universe checkpoint*)
- **What the user does:** keeps track of public projects and starts training from one.
- **Flow:** 1. Star a public project; the star count feeds the owner's **Sharing statistics** (F7.54). 2. When training, choose a public project as the checkpoint source (detection only per earlier repo research). 3. `[empty]` no stars on a new public project.
- **Why it is easy:** one gesture (star) does double duty as bookmark and as social proof on the owner's page.
- **Gates:** checkpoint option limited by task type.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/view-project-analytics.md, https://docs.roboflow.com/llms.txt

---

## Workspace settings surfaces

### F7.57 Create a workspace from a first-run screen (RF: *Create a Workspace*)
- **What the user does:** makes a second workspace for a client or a separate product.
- **Flow:** 1. Workspace switcher → **New workspace** (or first sign-in with no membership). 2. Single name field; creating it makes the user its creator/admin. 3. `[error: name taken]`. 4. `[empty]` first-run card explaining that a workspace holds projects, data and team.
- **Why it is easy:** one field, no wizard; the workspace is created in a usable state and the plan defaults to Free.
- **Gates:** none beyond being signed in.
- **Sources:** https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md, https://docs.roboflow.com/llms.txt

### F7.58 Rename a workspace with a URL-breakage warning (RF: *Rename a Workspace*)
- **What the user does:** fixes a typo in the workspace slug.
- **Flow:** 1. **Settings → Plan & Billing** (where the docs put it — an odd home worth moving) → **Rename workspace** in the top-right. 2. Type the new name → **Rename workspace**. 3. Applied immediately and irrevocably. 4. A warning states that the workspace URL changes, so every workflow endpoint and API/Inference reference must be updated; old-URL scripts stop working.
- **Why it is easy:** the warning names the exact breakage (endpoints, scripts) rather than saying "this may affect integrations".
- **Gates:** Admin; irreversible; no redirect from the old slug is documented.
- **Sources:** https://docs.roboflow.com/platform/workspaces/rename-a-workspace.md

### F7.59 Delete a workspace, or the whole account (RF: *Delete a Workspace / Account Deletion*)
- **What the user does:** closes a client workspace or leaves the product entirely.
- **Flow:** 1. **Settings → Delete workspace**. 2. The default workspace cannot be deleted; Enterprise workspaces cannot be deleted from Settings at all (button hidden, API returns 403, support must do it). 3. Account deletion lives at **Settings → Account** and removes the account plus its default workspace. 4. `[error: 403 for Enterprise]`.
- **Why it is easy:** the danger zone explains which of the two things (workspace vs account) the button destroys, and hides itself when policy forbids it instead of failing after the click.
- **Gates:** Admin; non-default only; Enterprise by support only.
- **Sources:** https://docs.roboflow.com/platform/workspaces/delete-a-workspace.md, https://docs.roboflow.com/llms.txt

### F7.60 Workspace-level policy switches that gate member actions (RF: *Project Settings*)
- **What the user does:** sets defaults once so members cannot publish or license data by accident.
- **Flow:** 1. **Settings → Project settings** holds workspace policy: **Public projects** (blocks new public projects), **Data licensing and model training**. 2. Each switch shows a lock state when plan or policy forbids changing it. 3. `[error: locked by your plan or region — contact support]`.
- **Why it is easy:** policy lives one level above the project, at the place an admin already visits, and the locked state is visible rather than a failed toggle.
- **Gates:** Admin; lockable by plan, compliance policy, region.
- **Sources:** https://docs.roboflow.com/datasets/manage/make-a-project-public.md, https://docs.roboflow.com/platform/billing-and-plans.md

### F7.61 Cross-workspace rollup for multi-workspace customers (RF: *Organizations / Billing Folders*)
- **What the user does:** compares spend and activity across several workspaces, or attributes spend to a department.
- **Flow:** title-only. Index entries describe an organization dashboard for comparing team activity, deployment volume and credit usage across workspaces, and billing folders for folder-level billable usage; the pages were not opened. The credit-usage page confirms folder-level attribution and folder roll-up inside a single workspace.
- **Gates:** Enterprise.
- **Sources:** https://docs.roboflow.com/llms.txt, https://docs.roboflow.com/platform/billing-and-plans/view-credit-usage.md

---

## Title-only / unverified

- Workspace Announcements (scheduled banner to all members) — index entry only.
- Recommended Access Setup (role + group + folder recipe) — referenced repeatedly, not opened.
- Organizations dashboard — title only (F7.61).
- Billing Folders detail beyond what the credit-usage page states — page not opened.
- Purchase a Plan, Purchase Prepaid Credits, Usage Projection — only summarised through the parent billing page and the usage page.
- Slack notification block setup, Twilio block, email block — not opened; only the credit rates from roboflow.com/credits are confirmed.
- Share a Workspace with Support, Support request template, Status page, Research credits — not opened.
- Trust Center claims (MFA, audit logging, data erasure, AES-256) — from earlier repo research, not re-fetched today.
- Notification preferences (email digest / per-event opt-out) — no page found; assume it exists but do not present as confirmed.
- Change Project Owner — index entry only.
- Whether *any* Core (non-Teams) workspace has a numeric seat cap: the pricing page says "Unlimited Admin Team Members" and "Custom" on Enterprise, the Teams page says unlimited admins + up to 10 non-admins. No number is stated for a plain Core workspace, so treat "seat limit" as plan-specific and unverified below Teams.
- The exact price of the Teams add-on — not stated on any page fetched.
- Audit log retention beyond "365 days by default" (whether it can be raised) — not stated.
- Whether data-region choice (US/EU) is visible anywhere in-app — pricing page only.

## Coverage gaps and what to check next

1. **In-product out-of-credits moment.** F7.21 is documented at plan level (banner, cap notices) but no page shows what the annotate screen, the train button or the deploy screen say when the wallet is empty. Needs an authenticated walkthrough or a changelog entry.
2. **Seat semantics for plain Core.** Resolve before designing our own seat UI: are non-admin seats purchasable outside Teams, and what happens to a 12th member when Teams expires (the docs say everyone becomes Admin, which quietly raises the seat count).
3. **Invite link revocation.** The docs state the link is static and unchangeable; confirm there is truly no rotate, since that is a security gap we should not copy.
4. **Audit-log export to file.** SIEM streaming is documented; a CSV/JSON download is not. Our redesign should offer both.
5. **Slack and MLOps integrations.** Only the webhook sink and the credit-rate table were read. Read the Slack block, the S3/warehouse sinks, and any W&B/MLflow pages before writing the integrations matrix.
6. **Failure and retry semantics for webhooks.** Only cooldown and fire-and-forget are documented; retry/backoff and dead-letter behaviour are unknown.
7. **Ownership transfer.** Project-owner transfer is an index entry; workspace-owner transfer is only implied by the "creator role is honorific and cannot be reassigned" note. Confirm what an owner does when they leave.
8. **Notification preferences.** No page found; check the app's account settings surface if a screenshot or changelog entry surfaces.
9. **DPA and privacy surfaces.** Pricing lists DPA/MSA as an Enterprise contracting item; no in-app DPA page was found. LabelDesk already links a DPA route from Settings, so we are ahead here — verify the content rather than the presence.
10. **Deletion guarantees.** Trash is 30 days for projects/versions/trainings/workflows; account deletion is documented as a button, but no page states the retention period after account deletion. Needed for a PDPA-facing promise.
