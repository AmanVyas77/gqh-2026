# Risk methodology: prospective scenario assessment

4 October 2026 — post-evaluation supplement

## Purpose and status

This assessment examines whether proposed operating procedures address four risks documented in saved research artifacts. It is a qualitative tabletop assessment, not a simulation of alternative positions, losses or funding requirements. No new numerical thresholds are selected. The procedures below are prospective proposals: they were not implemented in, or credited with protecting, the frozen strategies.

H1 A remains the frozen primary; B/C remain secondary. H2 is a sequential follow-up using TSN/XLP and TXRH/XLY pairs. Both primary hypotheses remain rejected. The evaluated holdout is not a fresh validation sample for these proposals.

## Capital and evidence definitions

- **Initial capital:** the fixed $1 million denominator used for reported arithmetic P&L returns and position sizing. A/C's 2× sizing cap does not establish a continuously enforced 2× current-NAV limit. B has no gross leverage cap.
- **Current NAV:** remaining marked portfolio equity, distinct from initial capital. Saved gross/current-NAV peaks are approximately 2.18× A, 7.49× B and 2.07× C.
- **Modeled initial margin:** supplied current per-contract margin proxies summed without offsets. These are not historical broker requirements or reconstructed margin calls.
- **Modeled free equity:** NAV less modeled initial margin. The saved calculation assumes all NAV is eligible collateral; free equity is not proof of immediately available cash.
- **Five-session funding envelope:** the largest modeled margin plus net P&L loss since a rolling window's start, measured across intermediate days in five observed strategy sessions. Intervening gains count as credits. It is a conditional historical description, not a recommended reserve or forecast.
- **Capacity illustration:** linear scaling of historical actual-order participation, including reversals and roll legs. The 1%-ADV illustrations ($1.28M A, $0.76M B and $1.52M C) establish neither executable nor profitable capacity.

Separate maxima may occur on different dates and positions. They must not be added together and labeled a coherent historical or joint stress event.

## Assessment method

For each scenario, assess whether the proposal (1) recognizes the documented failure mode, (2) specifies a decision and a responsible role, and (3) leaves unsupported claims unresolved. A procedure is inadequate if it assumes an unfilled exit eliminates exposure, treats a historical envelope as sufficient reserves, or permits deployment despite missing essential implementation evidence. These are qualitative review criteria, not new strategy acceptance tests.

Roles below are proposed responsibilities, not existing appointments. Before operational adoption, named people and authority must be assigned. No scenario receives a quantitative effectiveness or funding-sufficiency pass.

## Four-scenario assessment

| Scenario and saved evidence | Proposed decision and responsible role | Assessment and unresolved dependency |
|---|---|---|
| **Limit-locked market.** The saved A/C illustration applies two adverse LE moves of 8.50 and 12.75 cents/lb at 2× initial-capital sizing, producing a 22.9% initial-capital loss. | The risk owner tracks actual remaining exposure and escalates cash needs to the funding owner. The execution owner tracks outstanding orders and confirms fills; an exit instruction never counts as a completed exit. New risk-increasing orders require review. | The procedure recognizes that losses can continue while exits are unavailable. Survival is unverified: the illustration does not combine stressed margins with losses, is not a maximum-loss bound, and does not model further locked sessions or subsequent fills. |
| **Funding pressure.** B's saved maximum five-session envelope is $338,794; peak modeled margin/current-NAV is approximately 41.6%. | Before deployment, the funding owner reconciles eligible collateral and available cash with broker requirements and payment timing, including haircuts and add-ons. Unresolved funding requirements block deployment. An actual shortfall requires immediate broker coordination and escalation to the risk owner; liquidation is not presumed executable. | The procedure distinguishes funding approval from a favorable historical observation. Adequacy is unverified: current margin proxies omit historical and intraday calls, collateral restrictions and broker changes. The saved envelope cannot set a sufficient cash reserve. |
| **Uncertain execution.** Unknown session ranges affect 8/202 A LE order legs. Original executions assume settlement-price fills; an available range does not prove a fill. | The execution owner reviews unverified executability before new risk-increasing orders. Existing exposure remains on the risk record. Risk-reducing orders require confirmed market access and fills; any unresolved position is escalated to the risk owner rather than treated as flat. | The procedure distinguishes stopping new exposure from resolving existing exposure. Its effect on losses is unknown: order deferral can prolong risk. Session data, fill feasibility, market impact and implementable whole-contract sizes remain unresolved. |
| **Incomplete H2 readiness.** Volume-based capacity and historical borrow availability remain unresolved for the TSN/XLP and TXRH/XLY strategy. | Before deployment, execution and funding owners obtain volume/participation evidence and broker borrow terms for intended short legs. The risk owner withholds deployment approval until essential evidence is available and reviewed. | The procedure gives missing evidence an explicit decision consequence. Capacity, stressed funding and borrow continuity remain unquantified. Sector hedges do not eliminate individual-stock events, basis risk or borrow recall risk. |

## Findings and boundaries

The proposed procedures address the four failure modes at the level of decision logic, provided responsible people and authority are assigned. They expose unresolved dependencies rather than establish readiness to trade. In particular, the existing evidence cannot demonstrate sufficient stressed funding, timely exits or acceptable H2 capacity.

Existing controls retain their original status. The supplemental H1 drawdown overlay halves size at month-end drawdown above 15%, restores within 7.5% of peak, and executes next day; it is excluded from the frozen primary. This assessment neither retunes that overlay nor credits it with protecting against intraday or locked-market losses. Missing GF cash finals, fractional futures, historical funding and borrow uncertainty, and uncalibrated impact remain limitations.

Measuring hypothetical changes to losses and funding needs would require a separate, precisely specified counterfactual model of positions, execution, collateral and margin. Any analysis on already-seen records would be labeled exploratory and post-evaluation. No such analysis was performed here, and no new approval of that work is implied.

## Exploratory funding sensitivity added after the scenario assessment

This post-hoc, post-evaluation check is separate from the qualitative governance assessment. The all-date comparison was proposed after observing results at selected snapshots; both A and B findings have that status. It does not validate any control or change frozen results.

The joint qualitative finding can be independently established from the already-packaged `extension/tables/funding_envelopes.csv`, without distributing private dated holdings, prices or NAV detail. Let N be current NAV, I the modeled initial-margin proxy, m the margin multiplier and h the collateral haircut. Modeled headroom is H = (1 - h)N - mI. For I > 0, nonnegative headroom requires N/I >= m/(1 - h). At m = 2 and h = 0.20, that boundary is 2.5.

The saved minimum N/I is 7.698403335860274 for A and 2.4063160548357345 for B. Therefore A remains above this hypothetical boundary on the saved development positions with positive modeled margin, whereas B crosses below it on at least one date. A's saved minimum free equity is also positive, covering any zero-margin positions. This establishes the joint qualitative statement; these aggregate minima alone do not establish the number, dates or dollar amounts of B shortfalls, which are not published here.

The supplied current maintenance-margin schedule is multiplied by 1.10 to obtain the baseline initial-margin proxy, then doubled in this scenario. All NAV is assumed eligible before the arbitrary 20% haircut; there are no spread offsets. Haircuts reduce collateral eligibility, not economic NAV. Margin encumbers collateral and is not a P&L loss. This is a hypothetical end-of-day comparison, not a reconstruction of historical margin calls, a cash-payment schedule, a sufficient funding reserve or evidence of control effectiveness. There is no new simultaneous price shock in this comparison.

No dated private scratch artifacts were copied into the package. The previously saved funding-summary evidence is unchanged. Both primary hypotheses remain rejected.

## Suggested paper passage

**Prospective governance assessment (post-evaluation).** We assessed proposed operating procedures against four documented scenarios: adverse limit moves, funding pressure, uncertain execution and incomplete H2 capacity/borrow evidence. The procedures require explicit funding approval, confirmed execution, escalation of unresolved positions and deployment restrictions where essential evidence is missing. This qualitative assessment identifies dependencies and proposed responsibilities; it does not demonstrate reduced losses, adequate stressed liquidity or improved performance. The procedures were not implemented in the frozen strategies, and both primary hypotheses remain rejected.

## Evidence used

All numeric statements above report saved evidence; no new strategy calculations were performed.

- [Current paper source](../paper/research_note_edited.html), Section 4: reported leverage, funding, execution and capacity summaries.
- [Editorial notes](editorial_revision/EDITORIAL_NOTES.md): reporting qualifications and chronology.
- [Extension report](extension/REPORT.md): definitions, funding assumptions and execution limitations.
- [Funding envelopes](extension/tables/funding_envelopes.csv): $338,793.993852771 B five-session envelope.
- [Order capacity](extension/tables/order_capacity.csv): actual-order participation illustrations.
- [Execution sessions](extension/tables/execution_session_summary.csv): 194 A LE legs with ranges and 8 unknown.
- [Limit shock](../results/tables/stress_limit_shock.csv): A/C two-day loss fraction 0.22867904223836427.
- [Stress episodes](../results/tables/stress_episodes.csv) and [original capital table](../results/tables/capital.csv): retained historical context; original capital-table margin ratios must not be relabeled as current-NAV ratios.
- [H1 specification](../HYPOTHESIS.md), [H2 specification](../HYPOTHESIS_H2.md) and [submission freeze](../SUBMISSION_FREEZE.md): frozen rules and historical status. Their pre-holdout statements describe their creation dates, not the present evaluation status.

The paper summarizes this assessment in Section 4; this file preserves its methodology and limitations. References resolve within the submission package.
