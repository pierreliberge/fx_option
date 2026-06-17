from pathlib import Path

from fx_backtester import BacktestConfig, MarketData, OptionBacktester, StrategyFactory, performance_report
from fx_backtester.plots import plot_backtest


def main() -> None:
    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    output_dir.mkdir(exist_ok=True)

    market = MarketData.from_folder(root)
    config = BacktestConfig(
        start="2024-01-02",
        end="2025-12-31",
        roll_frequency="monthly",
        notional=1_000_000,
        signal_mode="always",
    )

    strategy = StrategyFactory.straddle(tenor_months=1)
    results = OptionBacktester(market, config).run(strategy)
    report = performance_report(results)

    results.to_csv(output_dir / "straddle_backtest_results.csv")
    report.to_csv(output_dir / "straddle_performance_report.csv", header=["value"])
    fig = plot_backtest(results)
    fig.savefig(output_dir / "straddle_backtest_charts.png", dpi=150)

    print(report.round(4).to_string())
    print(f"\nSaved outputs in: {output_dir}")


if __name__ == "__main__":
    main()
