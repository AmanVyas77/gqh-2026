"""Synthetic reporting test: pre-holdout trades cannot leak into turnover."""
from types import SimpleNamespace
import pandas as pd
import run_oos


def test_turnover_uses_only_holdout_trades_and_preserves_h2_value(monkeypatch):
    dates=pd.to_datetime(['2024-09-30','2024-10-01','2026-10-02'])
    daily=pd.DataFrame({'date':dates,'net':[0.,0.,0.]})
    trades=pd.DataFrame({'date':dates,'notional':[1000000.,20.,30.]})
    result=SimpleNamespace(daily=daily,trades=trades)
    monkeypatch.setattr(run_oos.signals,'month_end_signals',lambda **kw: None)
    monkeypatch.setattr(run_oos.backtest,'Market',lambda *a,**kw: None)
    monkeypatch.setattr(run_oos.backtest,'backtest_variant',lambda *a,**kw: (result,{}))
    monkeypatch.setattr(run_oos.analysis,'metrics',lambda *a: {})
    perf={k:0. for k in ['ann_return','ann_vol','sharpe','max_drawdown_from_peak','mean_monthly','nw_t_monthly','worst_month']}
    perf['worst_month_label']='2024-10'
    out={'performance':{col:perf for col in ['net','gross','net2x']},'daily':daily.iloc[1:],
         'daily_all':daily,'exposure':{'turnover_per_year':7.5}}
    monkeypatch.setattr(run_oos.h2,'evaluate',lambda **kw:out)
    rows,_=run_oos.evaluate_holdout({'capital_base':100.})
    expected=50./100./((dates[-1]-dates[1]).days/365.25)
    assert (rows.loc[rows.hypothesis=='H1','turnover']==expected).all()
    assert (rows.loc[rows.hypothesis=='H2','turnover']==7.5).all()
