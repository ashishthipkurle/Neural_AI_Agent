"""
Daily Report Generator — HTML Summary Reports.

Generates comprehensive daily HTML reports with:
    - Today's trades (entries + exits) with P&L
    - Portfolio snapshot: equity, drawdown, risk mode
    - Strategy performance breakdown
    - Learning engine insights
    - Embedded equity curve chart (matplotlib → base64 PNG)

Output: agent_data/reports/YYYY-MM-DD.html
"""
import logging
import time
import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class ReportGenerator:
    """
    Generates daily HTML trading reports.
    """

    def __init__(self, database=None, learning_engine=None) -> None:
        self.logger = logging.getLogger("ReportGenerator")
        self.database = database
        self.learning_engine = learning_engine

        self.reports_dir = Path(__file__).resolve().parent.parent.parent / "agent_data" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_report(self, date_str: str = None) -> Optional[str]:
        """
        Generate the daily HTML report.

        Returns:
            Path to the generated HTML file, or None on error.
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            # Gather data
            portfolio = self._get_portfolio_data()
            trades = self._get_todays_trades(date_str)
            trade_stats = self._get_trade_stats()
            strategy_stats = self._get_strategy_stats()
            insights = self._get_insights()
            equity_chart_b64 = self._generate_equity_chart()

            # Build HTML
            html = self._build_html(
                date_str=date_str,
                portfolio=portfolio,
                trades=trades,
                trade_stats=trade_stats,
                strategy_stats=strategy_stats,
                insights=insights,
                equity_chart_b64=equity_chart_b64,
            )

            # Save
            filepath = self.reports_dir / f"{date_str}.html"
            filepath.write_text(html, encoding="utf-8")

            self.logger.info(f"Daily report generated: {filepath}")
            return str(filepath)

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return None

    def _get_portfolio_data(self) -> Dict[str, Any]:
        if self.database:
            state = self.database.get_portfolio_state()
            return state or {}
        return {}

    def _get_todays_trades(self, date_str: str) -> List[Dict[str, Any]]:
        if not self.database:
            return []
        trades = self.database.get_trade_history(limit=50)
        # Filter to today's trades
        today_trades = []
        for t in trades:
            closed_at = t.get("closed_at", 0)
            if closed_at:
                trade_date = datetime.fromtimestamp(closed_at, tz=timezone.utc).strftime("%Y-%m-%d")
                if trade_date == date_str:
                    today_trades.append(t)
        return today_trades

    def _get_trade_stats(self) -> Dict[str, Any]:
        if self.database:
            return self.database.get_trade_stats()
        return {}

    def _get_strategy_stats(self) -> List[Dict[str, Any]]:
        if self.learning_engine:
            return self.learning_engine.get_strategy_regime_stats_list()
        return []

    def _get_insights(self) -> List[str]:
        if self.learning_engine:
            return self.learning_engine.get_insights()
        return ["No learning data available yet."]

    def _generate_equity_chart(self) -> str:
        """Generate equity curve chart as base64 PNG."""
        if not self.database:
            return ""

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io

            snapshots = self.database.get_equity_curve(limit=500)
            if not snapshots or len(snapshots) < 2:
                return ""

            timestamps = [s["timestamp"] for s in snapshots]
            equities = [s["equity"] for s in snapshots]
            drawdowns = [s.get("drawdown_pct", 0) for s in snapshots]

            dates = [datetime.fromtimestamp(t, tz=timezone.utc) for t in timestamps]

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6),
                                            gridspec_kw={"height_ratios": [3, 1]},
                                            sharex=True)

            # Equity curve
            ax1.fill_between(dates, equities, alpha=0.3, color="#00c853")
            ax1.plot(dates, equities, color="#00c853", linewidth=1.5)
            ax1.set_ylabel("Equity ($)")
            ax1.set_title("Portfolio Equity Curve")
            ax1.grid(True, alpha=0.3)

            # Drawdown
            ax2.fill_between(dates, [-d * 100 for d in drawdowns],
                            alpha=0.4, color="#ff1744")
            ax2.set_ylabel("Drawdown (%)")
            ax2.set_xlabel("Date")
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            return base64.b64encode(buf.read()).decode("utf-8")

        except ImportError:
            self.logger.debug("matplotlib not available — skipping chart")
            return ""
        except Exception as e:
            self.logger.warning(f"Chart generation failed: {e}")
            return ""

    def _build_html(self, date_str, portfolio, trades, trade_stats,
                    strategy_stats, insights, equity_chart_b64) -> str:
        """Build the complete HTML report."""
        equity = portfolio.get("equity", 0)
        cash = portfolio.get("cash", 0)
        drawdown = portfolio.get("drawdown_pct", 0) * 100
        risk_mode = portfolio.get("risk_mode", "UNKNOWN")
        positions = portfolio.get("open_positions_count", 0)

        total_trades = trade_stats.get("total", 0)
        win_rate = trade_stats.get("win_rate", 0)
        total_pnl = trade_stats.get("total_net_pnl", 0)

        # Build trades table rows
        trades_rows = ""
        for t in trades:
            pnl = t.get("net_pnl", 0)
            pnl_class = "win" if pnl > 0 else "loss"
            trades_rows += f"""
            <tr class="{pnl_class}">
                <td>{t.get('symbol', '')}</td>
                <td>{t.get('direction', '')}</td>
                <td>{t.get('strategy_name', '')}</td>
                <td>${t.get('entry_price', 0):.2f}</td>
                <td>${t.get('exit_price', 0):.2f}</td>
                <td>${pnl:.2f}</td>
                <td>{t.get('pnl_pct', 0) * 100:.2f}%</td>
            </tr>"""

        if not trades_rows:
            trades_rows = '<tr><td colspan="7" style="text-align:center;color:#888;">No trades today</td></tr>'

        # Strategy stats rows
        strategy_rows = ""
        for s in strategy_stats:
            total = s.get("total_trades", 0)
            wins = s.get("wins", 0)
            wr = (wins / total * 100) if total > 0 else 0
            wr_class = "win" if wr > 55 else ("loss" if wr < 40 else "")
            strategy_rows += f"""
            <tr class="{wr_class}">
                <td>{s.get('strategy', '')}</td>
                <td>{s.get('regime', '')}</td>
                <td>{total}</td>
                <td>{wins}</td>
                <td>{s.get('losses', 0)}</td>
                <td>{wr:.1f}%</td>
                <td>{s.get('avg_pnl', 0) * 100:.2f}%</td>
            </tr>"""

        # Insights list
        insights_html = "".join(f"<li>{i}</li>" for i in insights)

        # Equity chart
        chart_html = ""
        if equity_chart_b64:
            chart_html = f'<img src="data:image/png;base64,{equity_chart_b64}" style="width:100%;max-width:800px;border-radius:8px;">'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Trading Report — {date_str}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #0a0a0a; color: #e0e0e0; padding: 24px; }}
        h1 {{ color: #fff; margin-bottom: 8px; }}
        h2 {{ color: #90caf9; margin: 24px 0 12px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        .subtitle {{ color: #888; margin-bottom: 24px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .card {{ background: #1a1a2e; border-radius: 12px; padding: 16px; border: 1px solid #333; }}
        .card .label {{ font-size: 12px; color: #888; text-transform: uppercase; }}
        .card .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
        .card .value.green {{ color: #00e676; }}
        .card .value.red {{ color: #ff5252; }}
        .card .value.blue {{ color: #448aff; }}
        table {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
        th {{ background: #1a1a2e; padding: 10px 12px; text-align: left; font-size: 12px;
              text-transform: uppercase; color: #90caf9; border-bottom: 2px solid #333; }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #222; }}
        tr.win td {{ color: #00e676; }}
        tr.loss td {{ color: #ff5252; }}
        .insights {{ background: #1a1a2e; border-radius: 12px; padding: 16px; margin-top: 16px; }}
        .insights li {{ margin: 8px 0; padding-left: 8px; }}
        .chart {{ text-align: center; margin: 16px 0; }}
    </style>
</head>
<body>
    <h1>Trading Report</h1>
    <p class="subtitle">{date_str} | Intelligent Trading Agent v3.0</p>

    <div class="cards">
        <div class="card">
            <div class="label">Equity</div>
            <div class="value green">${equity:,.2f}</div>
        </div>
        <div class="card">
            <div class="label">Cash</div>
            <div class="value blue">${cash:,.2f}</div>
        </div>
        <div class="card">
            <div class="label">Drawdown</div>
            <div class="value {'red' if drawdown > 5 else 'green'}">{drawdown:.1f}%</div>
        </div>
        <div class="card">
            <div class="label">Risk Mode</div>
            <div class="value">{risk_mode}</div>
        </div>
        <div class="card">
            <div class="label">Open Positions</div>
            <div class="value blue">{positions}</div>
        </div>
        <div class="card">
            <div class="label">Total Trades</div>
            <div class="value">{total_trades}</div>
        </div>
        <div class="card">
            <div class="label">Win Rate</div>
            <div class="value {'green' if win_rate > 50 else 'red'}">{win_rate:.1f}%</div>
        </div>
        <div class="card">
            <div class="label">Total P&L</div>
            <div class="value {'green' if total_pnl >= 0 else 'red'}">${total_pnl:,.2f}</div>
        </div>
    </div>

    <h2>Equity Curve</h2>
    <div class="chart">{chart_html if chart_html else '<p style="color:#888;">Insufficient data for chart</p>'}</div>

    <h2>Today's Trades</h2>
    <table>
        <thead>
            <tr><th>Symbol</th><th>Direction</th><th>Strategy</th><th>Entry</th><th>Exit</th><th>P&L ($)</th><th>P&L (%)</th></tr>
        </thead>
        <tbody>{trades_rows}</tbody>
    </table>

    <h2>Strategy × Regime Performance</h2>
    <table>
        <thead>
            <tr><th>Strategy</th><th>Regime</th><th>Trades</th><th>Wins</th><th>Losses</th><th>Win Rate</th><th>Avg P&L</th></tr>
        </thead>
        <tbody>{strategy_rows if strategy_rows else '<tr><td colspan="7" style="text-align:center;color:#888;">No data yet</td></tr>'}</tbody>
    </table>

    <h2>Learning Engine Insights</h2>
    <div class="insights">
        <ul>{insights_html}</ul>
    </div>

    <p style="margin-top:32px;color:#555;font-size:12px;">
        Generated by Intelligent Trading Agent v3.0 at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
    </p>
</body>
</html>"""

    def get_report_summary_text(self, date_str: str = None) -> str:
        """Get a plain-text summary for Telegram notifications."""
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        portfolio = self._get_portfolio_data()
        trades = self._get_todays_trades(date_str)
        trade_stats = self._get_trade_stats()
        insights = self._get_insights()

        equity = portfolio.get("equity", 0)
        drawdown = portfolio.get("drawdown_pct", 0) * 100
        risk_mode = portfolio.get("risk_mode", "?")

        lines = [
            f"📊 Daily Report — {date_str}",
            f"💰 Equity: ${equity:,.2f}",
            f"📉 Drawdown: {drawdown:.1f}%",
            f"🛡️ Risk: {risk_mode}",
            f"📈 Today's trades: {len(trades)}",
            f"🏆 All-time: {trade_stats.get('total', 0)} trades, "
            f"{trade_stats.get('win_rate', 0):.1f}% win rate",
        ]

        if insights:
            lines.append("\n💡 Insights:")
            for i in insights[:3]:
                lines.append(f"  {i}")

        return "\n".join(lines)
