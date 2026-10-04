# Economic Hypothesis — written before any backtest

**Proposed edge source:** Compensation for absorbing temporary price pressure and bearing convergence risk.

**Hypothesis.** US large-cap stocks with similar estimated statistical factor exposures, identified through formation-window PCA and clustering, exhibit stable relative-price relationships. Among pairs that pass a cointegration screen over approximately six months, unusually large spread deviations partially reverse over days to a few weeks. Clustering improves pair selection relative to simple correlation and sector-based selection.

**Who is on the other side.** Fund flows, index and portfolio rebalances, and investors demanding immediate liquidity temporarily move one stock relative to a comparable stock. Taking the opposite position earns compensation as that pressure fades. This is a proposed mechanism: price data alone cannot identify the counterparties or distinguish informational from non-informational trading.

**Why the edge persists.** Borrow costs, recall risk, interim losses, and permanent relationship breaks make convergence trades costly and risky, which limits the arbitrage capital competing for this premium.

**Testable predictions.**
1. Cluster-selected pairs outperform correlation-selected and sector-selected pairs after modeled costs in chronological forward testing, under identical spread filters, execution rules, and exposure limits.
2. Previously identified spreads exhibit subsequent convergence. Portfolio returns are not predominantly explained by market and sector exposures.
3. Performance remains economically positive under doubled modeled costs and is reasonably stable across a small, predeclared set of nearby parameters.
4. Results are not dominated by one period or a small number of pairs.

**What would weaken or reject the hypothesis.**
- Forward spreads fail to converge reliably.
- Clustering fails to improve on both selection baselines.
- Net profitability disappears under the predeclared cost stress.
- Returns are predominantly factor exposure or concentrated in a few outcomes.

Insufficient observations or wide uncertainty intervals produce an inconclusive result. Numerical definitions of outperformance, robustness, and concentration are frozen in `config.yaml` before testing.

**Prior work and contribution.** Gatev, Goetzmann & Rouwenhorst (2006); Avellaneda & Lee (2010); Sarmento & Horta (2020). Our contribution is a reproducible, controlled evaluation of PCA-based clustering against correlation and sector selection for daily US large-cap pairs, with identical downstream rules, explicit cost assumptions, chronological validation, and a locked final holdout. We do not claim that PCA-based pair selection is new.
