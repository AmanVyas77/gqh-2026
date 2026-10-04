# Economic Hypothesis — written before any backtest

**Edge source:** Liquidity provision / behavioral (temporary non-informational price pressure)

**Hypothesis.** We expect pairs of US large-cap stocks that share common statistical
factor exposure (identified by PCA-based clustering of returns) and are cointegrated
over a ~6-month formation window to mean-revert after their spread diverges
unusually far, over horizons of days to a few weeks.

**Who is on the other side.** Traders whose orders move one stock without new
information about its fundamental value: fund flows, index and portfolio
rebalances, and investors demanding immediate liquidity. We are paid for
absorbing that price pressure until it fades.

**Why it persists.** Arbitrage capital is limited. Shorting costs money (borrow fees,
recall risk), spreads can widen further before converging, and some pair
relationships break permanently. These risks deter enough capital to leave a
residual premium.

**Testable predictions.**
1. Cluster-selected pairs earn higher net-of-cost risk-adjusted returns than
   pairs chosen by correlation alone or by same-sector membership alone,
   under identical trading rules.
2. Returns come from spread convergence, not market beta: the strategy's
   market exposure should be near zero and unexplained by standard factors.
3. Results hold across nearby parameter values, not at one tuned setting.

**It fails if.**
- Cluster-selected pairs do not beat both baselines out of sample, or
- the edge disappears when transaction costs are doubled, or
- profits come from a single period or a single small group of pairs.

**Prior work.** Gatev, Goetzmann & Rouwenhorst (2006); Avellaneda & Lee (2010);
Sarmento & Horta (2020). Our extension: a controlled head-to-head test of
clustering against correlation and sector selection, with identical rules,
realistic costs, and a locked out-of-sample period.
