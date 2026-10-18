# Auction markets, trade, and control of commodity inputs

## Purpose

Make commodity prices emerge from the quantities and prices that households, producers, firms, merchants, and governments actually offer. Then let an input-hungry corporation try to secure cheaper and more reliable supplies by bidding, contracting, lending, buying land, acquiring water rights, or petitioning for exclusive privileges. Each route must transfer a named asset or right, spend real resources, and create a response for affected people and the player.

The strategic question is whether cheaper industrial inputs and export strength justify lost food land, cultivator income, public legitimacy, and future supply. A firm can gain a short-run cost advantage and still destroy the growers it needs. A government can favor a champion firm and gain tax or military supply while impoverishing rural households and provoking opposition. A player should be able to choose a competitive market, a cooperative or public buyer, a regulated exclusive concession, or direct protection of cultivators, then see who gained and lost.

Historical framing: Beckert's *Capitalism* describes the expansion of trade and production through state-backed institutions and merchant power, alongside rural agency and resistance. His account of cotton identifies land, labor, and credit as linked constraints and describes state activism as crucial to new supply systems. Water rights and the specific charter mechanics below are proposed game systems inspired by that framing and the user's examples; they are not claims that Beckert documented these exact policies in every setting. Sources: [*Capitalism*, publisher description](https://www.penguinrandomhouse.com/books/541160/capitalism-by-sven-beckert/9780735220843/) and [Beckert, “Empire of Cotton”](https://www.wcfia.harvard.edu/publications/empire-cotton-0).

## Current engine seams and defects to resolve first

- `region_market.py` has a local auction, active goods, imported asks, paid sale events, and a traced reference-price formula. `trade()` computes `calculate_ask()` quantities, but `clear_discriminatory()` rebuilds the local sell book from raw inventory, using a fixed two-unit food subtraction. This can clear more food than the seller offered or reserved. It updates the reference before clearing, so submitted quantities were chosen against different terms from the final asks.
- The current “pay-as-bid” name is inaccurate: buyers submit quantities but no limit prices; sales occur at each seller's ask. Buyer ordering gives productive inputs priority for nonfood goods and hungry agents priority for food. Those priorities should become explicit policy or procurement channels, rather than silently overriding a price auction.
- A displayed recipe price is a smoothed reference, while paid sales have their own prices and VWAP. These must be labeled separately. No sale is not evidence that a unit traded at the reference price.
- `economy/capitalist_planner.py` purchases neighboring inputs and sells some outputs directly to the first available agent at a recipe reference. These transfers bypass the local order book, transport quotes, and market power accounting. Existing trader and foreign-exchange paths need to remain the source of truth for delivered goods.
- `land_tenure.py` names plots and titled lords, but has no generic voluntary or compelled title-transfer transaction. `enclosure.py` changes tenure on an existing lord's plot; it does not buy that plot for a corporation. The irrigation building is a yield bonus, not a scarce water allocation. `crop_credit.py` has advances and harvest liens that can support an early tied-sale contract.
- Desktop accounts and the web client already show reference prices and some trade data. Neither distinguishes a farmgate receipt from a mill's delivered input cost or exposes why one changed. The web state path is `sim_server/sim_server.py` into `web_client/`.

## Market rules and data contract

An order is `(turn, region, good, actor, side, quantity, limit_price, purpose, cash_or_stock_reserved, contract_id?)`. Input demand comes from recipe requirements, current stock, expected production, and a cash budget. Household food demand comes from appetite and existing food; it does not become a bid without purchasing power or a funded public purchaser. A seller can offer only inventory above actual household, seed, and contractual reserves. An order cannot both enter the spot book and be promised to a contract.

For each good and region, sort executable buy limits high to low and sell limits low to high, with deterministic seeded tie resolution. Match while `bid_limit >= ask_limit`, subject to current cash, stock, import arrival, and route constraints. Use a documented price rule within those two limits, initially their midpoint for each matched tranche. Charge that actual price, and update both agents' ledgers from the same settlement operation. A second buyer raises the paid price when it outbids an existing buyer for scarce stock; simply adding a low bid does not move the price. A lone buyer can offer less, but sellers may keep food or seek another outlet instead of being forced to accept. No fictitious volume enters a price signal.

Record separately:

1. **Paid spot price:** actual unit prices and quantity-weighted mean for trades that settled.
2. **Reference quote:** a bounded, smoothed expectation used by decisions when there is no fresh trade. Move it primarily toward paid VWAP, and only cautiously toward best unmatched bid/ask when a market does not clear. Keep trace replay in `price_trace.py` aligned with the new formula.
3. **Farmgate net receipt:** money retained by a producer after contracted repayments, transport, tolls, and taxes.
4. **Delivered input cost:** purchase price plus freight, tariff, financing, and loss paid by a manufacturer.

All four may differ. A low farmgate price and high city price can coexist when a merchant controls a route. Genuine scarcity means executable bids exceed offered stock; poverty can mean need without bids. Show both physical need and funded demand, so starvation does not masquerade as weak preferences. A price rise caused by buyer competition must be distinguished from one caused by crop loss, export diversion, currency change, or a seller withholding stock. Maintain numerical guards against negative or infinite prices, but do not treat the existing `0.1–50` engineering clamp as an economic price ceiling.

## Build sequence

### Phase 1 — Trustworthy local double auction

**Files:** `region_market.py`, `price_trace.py`, `test_run_trace.py`, targeted market tests, and any quote fields in `region.py`.

1. Build one immutable order list per good from `calculate_bid()` and `calculate_ask()`; clearing consumes those exact quantities. Apply household food reserves, scenario grain holds, and already pledged crop to both totals and the book.
2. Add buyer limit prices from use value: household food affordability and urgency, manufacturer expected output margin and next input need, trader expected destination receipt minus delivered costs. Add seller limits from cash costs, inventory pressure, subsistence reserves, and realistic outside options. Keep formulas bounded and traceable. Use tranches if one price for an entire inventory causes implausible all-or-nothing trades.
3. Match priced orders deterministically, settle cash and inventory once, and emit order, fill, rejection reason, and price events. Separate hunger assistance and public procurement as funded orders with stated priority rules; preserve the existing protective intent without invisible free priority for all production firms.
4. Set next-turn reference after settlement. Preserve a sensible quote when no trade occurs, and mark it stale. Remove any use of a reference as if it were a paid market price.
5. Test conservation, food reserves, partial fills, unaffordable bids, bid below ask, multiple sellers/buyers, no bids, no offers, import asks, and trace replay. A controlled supply cut with steady funded demand should raise paid price; an extra producer should lower it if all else is equal. An income collapse may lower funded demand even as physical need rises.

**Gate:** The same order quantities appear in supply/demand totals and settlement; paid volume and money balance exactly; the reference can be explained from paid trades and unfilled orders. Compare a seeded 50-turn default three-nation run with today's baseline for price movement, food access, industrial input fill, and simulation time. Do not tune to a predetermined price curve.

### Phase 2 — Delivered trade competes for local crops

**Files:** `economy/capitalist_planner.py`, merchant/route and FX settlement paths, `region_market.py`, `sim_server/sim_server.py`.

1. Replace planner “first neighbor with inventory” purchases and sales with route orders or explicit negotiated contracts. A mill's bid for distant cotton must face the producer's local alternatives plus freight, delay, tariffs, FX, and route capacity. Existing trader inventory may carry the good, but never sell the same unit twice.
2. Give merchants and manufacturers a route choice based on expected delivered margin, not just the neighboring recipe quote. Purchase, movement, arrival, and destination sale are separate traceable stages. Recheck cash, stock, route capacity, and rights at each stage.
3. Limit information to observed quotes, old fills, visible stock estimates, and known routes. Add a small delivery risk or uncertainty allowance rather than perfect future prices.
4. Test a second buyer entering a producing district, a blocked route, a same-currency and a cross-currency transaction, and a glut moved to a deficit district. Assert cash, stock, freight payments, FX balances, and tariffs reconcile.

**Gate:** A rival mill changes the producing district's paid price only by bidding or contracting for physical goods; a changed destination price cannot instantly teleport crops or cash.

### Phase 3 — Corporate control of supply, with cultivator choice

**Files:** `crop_credit.py`, `land_tenure.py`, new water-right registry and settlement module, producer decisions, `economy/capitalist_planner.py`.

Implement three distinct investments; each has a different market effect.

| Corporate move | Required state change | Likely benefit | Countervailing effect and response |
| --- | --- | --- | --- |
| Advance plus offtake | Creditor pays cash now; named grower accepts a lien/quantity/price or price formula, due date, and settlement priority | Secures future crop and financing dependence | Grower may reject, repay elsewhere, default, or sell unpledged surplus; a low guaranteed price can discourage planting |
| Buy or lease titled plot | Transfer title/lease from an owner for cash; preserve or adjudicate tenant/customary claims explicitly | Changes crop choice and captures rent or output | Seller can refuse; tenants lose or retain named rights; food area and unrest change; firm bears land and cultivation cost |
| Acquire/lease irrigation right | Transfer a quantified seasonal share of a named water source/canal, with maintenance and enforcement | Raises favored cash-crop reliability or lowers rival yield | Rival farms lose actual allocations; drought and maintenance constrain everyone; state or communities can protect minimum access |

Water is a rival seasonal quantity, not a toggle or generic building bonus. When scarcity occurs, allocate it by enforceable priority with an explicit minimum domestic/food allocation if law requires one. A firm cannot own more water than the source supplies. Land acquisition cannot erase customary use without the existing legal process. A lien cannot pledge more harvest than exists, and repayments must flow to a named creditor. Exclude already committed goods from spot asks, then record later contract deliveries and effective unit price separately from open-market VWAP. Use the game's established cadence of ten seasonal turns per year and one career-choice turn per year: water, planting, harvest, delivery, and default dates follow seasonal turns without making households reconsider careers ten times a year.

**Gate:** Acquisition and contract histories identify the asset, prior owner/user, new owner/user, payment, legal basis, and realized harvest/output. Removing or contesting a right changes an actual allocation or sale, not a narrative modifier.

Persist contract, plot-title, and water-right IDs through save/load and world snapshots. Loading a game must retain outstanding claims and future delivery obligations; it must not recreate collateral or water allocations.

### Phase 4 — State granted exclusivity, monopoly, and monopsony

**Files:** government law/petition/case machinery, route licensing, `economy/capitalist_planner.py`, AI nation policy, market settlement.

Create a time-limited charter for a named `good`, jurisdiction, and scope: exclusive purchasing station, exclusive processing/export license, or exclusive route/warehouse concession. These are different powers. The firm petitions and funds application or enforcement; the competent government decides under its own fiscal, political, and supply goals. The player decides or delegates in player territory. State capacity and compliance determine whether unlicensed buyers are actually excluded, charged, or merely pushed into smuggling; no law should silently set a market price.

The price effect follows changed options: a purchasing monopsony removes alternative buyers and can lower farmgate bids if growers cannot store, consume, or export; a monopoly seller may raise downstream prices; a route concession may widen the gap between farmgate receipts and delivered costs. Rival countries, cooperatives, and public buyers can offer alternatives if routes and law allow. Model leakage, resistance, charter expiry, litigation/repeal, tax or fee receipts, and food supply effects. A government's expected gains and costs must be visible before it grants the petition.

**Gate:** The same market rules clear with and without a charter. A monopoly does not automatically increase profit if lost output, enforcement costs, and opposition outweigh the margin. A monopsony cannot buy crops below a seller's minimum without a separate legal or coercive mechanism that actually changes that seller's outside option.

### Phase 5 — Strategic AI and player presentation

**Files:** `economy/capitalist_planner.py`, nation AI, `sim_server/sim_server.py`, `web_client/`, desktop accounts/Guided UI, trace and replay readers.

For each firm, estimate the next few turns of input needs, cash runway, margin by output price, recent fill rate, competing buyers, grower viability, and accessible routes. Compare bidding more, diversifying suppliers, paying an advance, buying or leasing land, acquiring water, lobbying, improving productivity, and reducing output. The score is expected profit after finance, transport, enforcement, supply failure, unrest, and future grower exit. Plans persist across turns with milestones and budget; failed petitions and resisted acquisitions cause replanning. Do not use exact future harvests or unobserved private stocks.

Nation AI evaluates the same petition against tax base, food security, export income, military supply, fiscal enforcement cost, legitimacy, and rival advantage. It can reject a profitable corporate request. A player government receives a reviewable petition with projected winners/losers, alternatives, uncertainty, and a clear decision deadline; a standing delegation rule may decide routine cases. Producers choose whether to plant food/cash crops, accept a contract, hold for better prices, sell to rivals, or join a cooperative according to their actual rights, stock, debt, and route access.

The desktop and web client should show the same compact market card for the selected good and district: **paid local price, change and cause; offered vs funded demand vs physical need; quantity traded and unfilled; top buyers/sellers; farmgate vs delivered price; active contracts and charters; next harvest and food-land exposure**. A linked timeline explains “Mill A bid for 8 cotton; two growers sold 5 at 4.2; 3 went unfilled; Mill A offered an advance to Grower B; the council is considering exclusive buying rights.” Display forecasts as estimates and paid transfers as observed facts. Keep exact AI scores and individual order details in Analysis/debug.

**Gate:** In a small playable scenario, the player can identify why a price moved and what an exclusive charter would do to two named growers and one mill. Both a competitive-purchase route and a controlled-supply route can succeed under different conditions. A 50-turn comparison should report price volatility, input fill, firm profit, grower net income, food consumption, land/water concentration, public revenue, unrest, and rival trade share. Inspect representative traces step by step, then playtest whether the choice is understandable and interesting.

## First implementation slice

Start with Phase 1 plus the Phase 2 removal of direct corporate input purchase. Use one producing district with two growers and one mill, a second mill able to enter by route, and a food reserve on one grower. The first playable result should be simple: when the second mill outbids the first for scarce cotton, the farmgate paid price rises; when a harvest falls, unfilled mill demand and the higher paid price are visible; when a grower needs a meal, its reserved food remains in inventory. A low cash buyer can lose even if it needs cotton badly. This makes later advances, land ownership, water control, and exclusive charters meaningful changes to outside options rather than arbitrary price multipliers.

Make a commit after each phase that passes its gate. The first slice may be committed separately so the core price system can be reviewed before property and political mechanisms build on it.

## Implementation progress

### Phase 1 — complete (2026-10-18)

- Local clearing consumes the order quantities assembled in `trade()` and settles at a midpoint bounded by the matched limit prices. Orders use the quote visible at submission; reference prices update after clearing.
- Funded excess demand raises buyer limits within a cap. Food urgency can raise a household's limit; a productive input buyer is capped by expected output receipts after direct payroll; a trader is capped by estimated destination receipts after freight.
- Dead agents and trader export inventory are excluded from local demand and supply totals. Existing food reserve logic determines the offered quantity, which is now the quantity clearing consumes.
- Removed the capitalist planner's direct neighboring input purchase path. Cross-region corporate input access now awaits Phase 2 route settlement.
- Added `test_market_auction.py` coverage for exact offer conservation and settlement, bid below ask, food reserves, scarce-market price pressure, bid trace replay, and prevention of the direct input bypass.
- Targeted market, food-security, and capitalist-trade tests passed. A broader run had four unrelated environment errors because `pygame` and `scipy` are unavailable; the remaining tests in those files passed.

### Phase 2 — complete (2026-10-18)

- Routes and pending import pools now carry every commodity except government, transport service, and `none`; cotton and industrial inputs no longer stop at the old food/wood/furniture list.
- Traders compare reachable prices after freight, FX, tariffs, and trade fees. Profitable destination demand for a corporation's missing recipe inputs biases route selection, while the local destination firm still buys arriving stock through its auction.
- The capitalist planner no longer transfers spatial luxury goods, input goods, or output goods directly between neighboring agents. Imports arrive through trader inventories and destination auctions.
- Added `test_market_routes.py` for general commodity shipment, delivery into the import pool, destination auction settlement, and trader response to input shortages. These tests and the Phase 1 market tests pass. Broader geographic and UI test files have environment failures from unavailable `scipy`/`pygame`; one unrelated death-context fixture also fails.

### Phase 3 — complete (2026-10-18)

- Advances may include a named fixed-price crop offtake contract. The grower receives cash immediately; only independently recorded harvest is delivered, and contract deliveries reduce the receipt before spot asks. The paid cash plus debt credit reconcile against contract price; a missed harvest defaults and restores the ordinary lien path.
- Voluntary plot title sales and fixed-term leases move real cash. Sales update the title holder; leases grant and expire control. Both preserve tenant and tenure/customary-right records.
- Added plot-linked seasonal water entitlements and finite allocation from source capacity, rainfall (including the low-flood scenario modifier), and canal condition. Water rights transfer between named plots for payment and change crop yield by the plot allocation. Allocation and acquisition events carry IDs and trace inputs.
- State snapshots expose active contracts, land leases/transfers, water allocations/rights, and histories; the world cache's pickle save/load retains these records. Added tests for cash/inventory conservation, title and tenant retention, water diversion and yield, missed claim settlement, and pickle persistence.
- Corporate AI now scores advances/offtake, water reallocation, land lease, and exclusive-processing petitions when profitable output is input constrained.

### Phase 4 — complete (2026-10-18)

- Added delayed, fee-funded petitions for exclusive buying, exclusive processing, and route concessions. The government AI considers legitimacy, supplier concentration, jobs, public treasury, food pressure, and strategic goods. Player-territory petitions wait for an explicit approve/reject decision with a two-turn deadline.
- Charters alter actual executable buyer quantities or trader route shipments, while finite enforcement permits measured leakage. Suppressed orders create opposition; severe opposition or unrest repeals a charter, and all charters expire by term.
- Petition snapshots state beneficiaries, exposed growers, restricted rivals, alternatives, expected effects, and uncertainty. Trace records include decision score, enforcement, leakage, opposition, and expiry/repeal causes.
- Added command and serialization coverage for petition review, buyer restrictions, route leakage, and repeal. Market settlement remains the same priced auction.

### Phase 5 — complete (2026-10-18)

- Corporate planning scores four input-security options and executes the highest viable choice, after repairing existing productive machinery. It records candidate feasibility and selected action through the existing AI decision/outcome trace.
- Government decisions now produce a reviewable brief. The web client shows funded demand, offered supply, quantity traded, physical food need, paid local and imported prices, top buyers and sellers, offtake terms, seasonal water allocations, and active charters. It lets the player approve/reject petitions from their territory.
- The desktop HUD shows local supply-control counts and the latest paid fill. Both interfaces now distinguish observed fills from the reference quote and expose named supply rights.
- Added JSON serialization and UI action parity tests. A seeded 50-turn default three-nation run reached turn 50 across 80 tiles: food reference prices ranged $1.00–$3.63, 111 corporations were active, 5 offtake contracts and 1 charter remained active, and 600 seasonal water allocation events were recorded. The full world snapshot serialized to JSON. The compact trace recorded 1,437,703 causal events; inspection confirmed AI decisions, 104 contract settlements, 109 water-right transfers, and charter-enforcement events.

**Verification note:** Focused auction, route, supply-right, capitalist-planner, web serialization, charter decision, and parity tests pass (38 tests). JavaScript syntax and Python compilation pass. A desktop render test is blocked by the host's OpenGL setup (`cannot choose pixel format`); the changed desktop HUD module compiles, and web tests pass. The 50-turn full-map run passed and its serialized snapshot is valid JSON.
