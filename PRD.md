# USQuery — Product Requirements Document

**Version:** 1.02
**Date:** 2026-04-17 
**Author:** Jeremy Lazo  
**Status:** Draft

---

## 1. Overview

USQuery is a web and mobile platform that makes U.S. congressional data accessible and understandable to the general public. It surfaces bill data, congressional votes, member information, and AI-powered insights in an approachable way — without requiring users to have a policy or legal background.

The web app is built on Django with a PostgreSQL backend, Redis caching, a RESTful internal API, and a public-facing GraphQL API. A companion mobile app exists and shares the same backend (GraphQL layer). Future AI features will be integrated into both platforms.

---

## 2. Goals

- Make U.S. legislative data searchable, filterable, and readable for everyday citizens.
- Drive user retention through personalization (starred bills/members, notifications).
- Monetize via a tiered subscription model (Free → Plus → Premium).
- Expand reach by supporting OAuth login (Google/Apple) on both web and mobile.
- Differentiate from government sites via AI-powered features (vote predictions, chatbot).

---

## 3. Target Audience

**Primary:** General public — citizens who want to follow legislation, track their representatives, or stay informed about congressional activity.

**Secondary:** Students, researchers, and journalists who need structured access to legislative data via the public GraphQL API.

---

## 4. Current Features (Shipped)

| Feature | Web | Mobile |
|---|---|---|
| Search bills by subject and time frame | Y | N (need to add timeframe filtering) |
| Search votes by subject and time frame | Y | N (need to add timeframe filtering) |
| Congress member profiles (votes, term history, general info) | Y | Y |
| Vote predictions for bills | Y | N (need to add gql query and UI)|
| Starred bills / starred members | Y | Y |
| User accounts (email/password) | Y | Y |
| Push notifications for starred content | N/A | Y |
| Public GraphQL API (unauthenticated queries) | Y | Y |
| AI-generated bill summaries | Y | Y |

---

## 5. Subscription Tiers

| Feature | Free | Plus | Premium |
|---|---|---|---|
| Starred members | 3 | 10 | 20 |
| Starred bills | 10 | 50 | 100 |
| Vote predictions | 3/day | 100/day | Y |
| AI chatbot access (in development) | N | 3/day | A lot |
| Price | $0 | TBD | TBD |

Access control is enforced via the `UserProfile` model's subscription tier field. Feature gating is the primary mechanism; the chatbot additionally uses rate limiting for the Plus tier.

---

## 6. Prioritized Roadmap

### Note
The scope of edits in this repo should only be for the web frontend and web/mobile backend, a separate repo contains all code for the mobile server.

### Phase 1 — End of April 2026 (Current Sprint)

#### 6.1 [Completed Google Oauth]OAuth Login (Google & Apple)
**Scope:** Web + Mobile  
**Goal:** Reduce friction for new user registration and login.
**Estimated Difficulty:** 4

**Requirements:**
- X | Users can sign in with their Google account via OAuth 2.0.
- Users can sign in with their Apple ID via Sign in with Apple. (wip)
- X | On first OAuth login, a `User` and `UserProfile` are created automatically with Free tier defaults.
- X | If an email from an OAuth provider matches an existing email/password account, the accounts are linked (or the user is prompted to link them).
- X | JWT tokens are issued on successful OAuth login, consistent with the existing `simplejwt` flow.
- X |  OAuth login must work on both the web app and mobile (shared backend endpoint).
- X |Password reset and email verification flows are not applicable to OAuth-only accounts.

**Out of scope:** OAuth login for admin/staff accounts.

**Progress:** Created the backend for creating an account with oauth. Need to edit code so it works for multiple GOOGLE_CLIENT_IDs (since google has us separate web Client ID and mobile Client IDs) 
**Update(4/17):** Added web frontend and support for multiple google client ids
**Update(4/18):** Mobile frontend made, just waiting for google client id to be available in production to fix bugs, rn we get unauthorized even after multiple steps made to correct this.
**		- Correctly defined Javascript Origins in cloud console.
		- ids are correct.
		- Wait for production access, maybe this will fix our issue...**
**Update(4/23):** Resubmitted for prod verification...
---

#### 6.2 [Completed] Starred Bills & Members on Web
**Scope:** Web frontend  
**Goal:** Port the existing mobile starred content feature to the web app.
**Estimated Difficulty:** 2

**Requirements:**
- X | Authenticated web users can star/unstar a bill from the bill detail page.
- X | Authenticated web users can star/unstar a member from the member profile page.
- X | A dedicated "My Starred" page (or dashboard section) lists the user's starred bills and starred members.
- X | Starring is blocked with an upsell prompt when the user's tier limit is reached (e.g., Free user at 10 starred bills).
- X | Starred state is synced with the existing `StarredBill` and `StarredMembership` models — no schema changes required.
- X | The existing GraphQL API calls used by mobile should be reused or minimally refactored for the web frontend. (Refactored it)
- X | Unauthenticated users are prompted to log in when attempting to star content.

---

#### 6.3 Vote Predictions on Mobile + Update on web
**Scope:** Mobile
**Goal:** Enable users to see vote predictions in the mobile app.
**Estimated Difficulty:** 2

**Requirements:**
- A REST API/graphQL query that returns "Yea" vote probabilities of each current congress-person for a bill.
- Unauthenticated users are denied access, must provide a valid access token and free tier is limited to only 3 unique predictions a day.
- Update Web REST API to return a list of "Yea" vote probabilities for each congress-person.
- Use a Javascript/Typescript distribution plot library to present a sample of predictions (1000 sample full votes for both senate and house).
- Remove old pandas made vote distribution predictions and make user device create prediction, also add list showing "Yea" vote probabilities for each member.

#### 6.4 [Completed, need to enable after adding promised features]Paid Membership / Subscription Feature
**Scope:** Web + Mobile
**Goal:** Enable users to upgrade from Free to Plus or Premium, unlocking gated features.
**Estimated Difficulty:** 7

**Requirements:**
- A "Plans & Pricing" page clearly presents Free, Plus, and Premium tiers with feature comparisons.
- Users can initiate an upgrade from within the app (from the plans page or from a feature gate prompt) or on a page in the web app.
- Payment processing is integrated (provider TBD — e.g., Stripe). PCI scope must be minimized by using a hosted payment page or embedded SDK (never handling raw card data server-side).
- On successful payment, the user's `UserProfile.subscription_tier` is updated to the purchased tier.
- Subscription management (cancel, view billing) is accessible from the user's account settings.
- Downgrades/cancellations take effect at end of billing period; starred item counts that exceed the lower tier's limits are soft-capped (user can view but not add more, but eventually after downgrade a monthly maintainance command removes latest starred items to match limit).
- Webhooks from the payment provider update subscription state server-side.

---

### Phase 2 — Near Term (~1 Month Out)

#### 6.5 Rebuilt Vote Prediction Model
**Scope:** Web + Mobile
**Goal:** Replace the current prediction model with one that ingests full bill text for higher accuracy.
**Estimated Difficulty:** 8

**Requirements:**
- New model accepts bill text as input (not just metadata) and outputs a predicted vote outcome.
- Predictions are stored in the existing `BillPrediction` model (or an updated version of it).
- Prediction generation is an async background task (no blocking the request cycle).
- Results are accessible via the existing prediction UI; no new UI surface required.
- New UI shows the likelihood of specific members voting "yea" in a list for both mobile and web.
- Model accuracy benchmarks are tracked internally before replacing the production model.
- Access to predictions remains gated to Plus and Premium tiers.

**Notes:**
- Currently testing base case of predicting vote solely by member's party, will use this model to compare future models.

---

### Phase 3 — Future

#### 6.6 Keyword Search for Bills & Votes
**Scope:** Web + Mobile
**Goal:** Allow users to search by keywords found in bill titles.
**Estimated Difficulty:** 5

**Requirements:**
- Full-text or substring search on bill titles (and optionally, summaries).
- Search is accessible from the main search interface alongside existing subject/date filters.
- Results are paginated and ranked by relevance.

**Notes:**
- GraphQL endpoint already has a query that searches bills by keyword relevance, need to ensure everything works optimally and that any necessary db changes are made in db server.

---

#### 6.7 AI Chatbot
**Scope:** Web + Mobile
**Goal:** Let users ask natural language questions about bills and their potential impact.
**Estimated Difficulty:** 6

**Requirements:**
- Users can open a chat interface and ask questions like "How would this bill affect small businesses?", or "How would this affect me as a single mother?"
- The chatbot is grounded in bill data from the database (RAG or structured context injection).
- Free tier: no access (hard gate with upsell prompt).
- Plus tier: rate-limited access (specific message cap per day/month — TBD, maybe 3 per day).
- Premium tier: unlimited access.
- Conversation history is stored per user session (duration TBD).
- The chatbot must not present speculative or fabricated legislative information; it should cite the source bill/section when making claims.

---

#### 6.8 Sponsored & Cosponsored Legislation per Member
**Scope:** Web + Mobile
**Goal:** Show which bills a member has sponsored or cosponsored on their profile page.
**Estimated Difficulty:** 5

**Requirements:**
- Member profile page includes a "Sponsored" and "Cosponsored" bills tab.
- Data is ideally sourced from existing bill/membership data or supplemented via the Congress.gov API.
- Lists are paginated and filterable by congress session and subject.

---

#### 6.9 Committee Data
**Scope:** Web + Mobile
**Goal:** Surface committee membership and committee actions for bills.

**Requirements:**
- Bills show which committee(s) they were referred to and any committee actions taken.
- Committee detail pages list member assignments.
- Data model additions required (committees, committee memberships, committee actions(maybe access these through Congress API rather than saved in db)).

---

## 7. Technical Scope

| Layer | Technology |
|---|---|
| Backend framework | Django |
| Databases | PostgreSQL |
| Caching | Redis (`django_redis`) |
| REST API | Django REST Framework (internal use only) |
| GraphQL API | Strawberry (public; auth-gated queries require JWT) |
| Authentication | Email/password + JWT (`simplejwt`); OAuth to be added |
| Frontend | Django templates + JavaScript (not a SPA) |
| Visualization | Custom JS: bar, choropleth, donut, sunburst plots |
| Containerization | Docker Compose (dev/test only) |
| Mobile backend | Shared PostgreSQL + GraphQL layer |

---

## 8. Non-Goals (Explicit Exclusions)

- The REST API will not be made public; it remains an internal implementation detail.
- No SPA rewrite — the Django template approach is retained.
- The Docker setup will not be promoted to a production deployment path at this time.
- No admin/staff-facing OAuth login.

---

## 9. Open Questions

| # | Question | Answer |
|---|---|---|
| 1 | What payment provider will be used for subscriptions (Stripe, etc.)? |
| 2 | What are the Plus and Premium monthly/annual price points? |
| 3 | What is the Plus tier's chatbot rate limit (messages/day or messages/month)? |
| 4 | Should downgraded users lose access to predictions immediately or at period end? | A maintenance that runs monthly will find downgraded users and delete the latest overflowing starred items.
| 5 | Will the chatbot be built on the Anthropic API or another LLM provider? | 
| 6 | What data source feeds the prediction model's bill text (Congress.gov API, bulk data)? |

---

## 10. Success Metrics 

- Phase 1 shipped by end of April 2026.
- OAuth login reduces new user drop-off rate vs. email/password baseline.
- Starred content on web reaches parity engagement with mobile within 30 days of launch.
- At least one paid subscriber within 30 days of subscription feature going live.
- Prediction model v2 accuracy exceeds current model on a held-out test set.
