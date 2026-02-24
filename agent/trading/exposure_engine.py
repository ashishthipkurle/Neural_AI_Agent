"""
Correlation & Exposure Control Engine.

Rolling correlation matrix. Cluster assets by correlation > 0.75.
Block additional trades in over-exposed clusters.
Enforce sector, asset class, and leverage caps.

No LLM. Fully deterministic.
"""
import math
import logging
from typing import List, Dict, Any, Optional, Set, Tuple


class ExposureEngine:
    """
    Portfolio-level exposure and correlation management.
    """

    def __init__(
        self,
        correlation_threshold: float = 0.75,
        max_cluster_exposure_pct: float = 0.25,
        max_sector_exposure_pct: float = 0.30,
        max_single_asset_pct: float = 0.15,
        max_leverage: float = 1.0,
    ) -> None:
        self.logger = logging.getLogger("ExposureEngine")
        self.correlation_threshold = correlation_threshold
        self.max_cluster_exposure_pct = max_cluster_exposure_pct
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.max_single_asset_pct = max_single_asset_pct
        self.max_leverage = max_leverage

        # Active positions tracking
        self._positions: Dict[str, Dict[str, Any]] = {}
        # Correlation cache
        self._correlation_matrix: Dict[Tuple[str, str], float] = {}

    def compute_correlation(
        self, returns_a: List[float], returns_b: List[float]
    ) -> float:
        """
        Pearson correlation between two return series.
        Returns: float in [-1.0, +1.0]
        """
        n = min(len(returns_a), len(returns_b))
        if n < 10:
            return 0.0

        a = returns_a[-n:]
        b = returns_b[-n:]

        mean_a = sum(a) / n
        mean_b = sum(b) / n

        cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
        std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / n)
        std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b) / n)

        if std_a == 0 or std_b == 0:
            return 0.0

        return max(-1.0, min(1.0, cov / (std_a * std_b)))

    def build_correlation_matrix(
        self, asset_returns: Dict[str, List[float]]
    ) -> Dict[Tuple[str, str], float]:
        """
        Build pairwise correlation matrix for all tracked assets.

        Args:
            asset_returns: Dict mapping asset name to list of returns

        Returns:
            Dict mapping (asset_a, asset_b) to correlation value
        """
        assets = list(asset_returns.keys())
        matrix = {}

        for i in range(len(assets)):
            for j in range(i + 1, len(assets)):
                corr = self.compute_correlation(
                    asset_returns[assets[i]],
                    asset_returns[assets[j]]
                )
                pair = (assets[i], assets[j])
                matrix[pair] = corr
                matrix[(assets[j], assets[i])] = corr

        self._correlation_matrix = matrix
        return matrix

    def find_correlated_clusters(self) -> List[Set[str]]:
        """
        Group assets into clusters where intra-cluster correlation > threshold.
        Simple single-linkage clustering.
        """
        if not self._correlation_matrix:
            return []

        # Extract unique assets
        assets = set()
        for (a, b) in self._correlation_matrix:
            assets.add(a)
            assets.add(b)

        visited = set()
        clusters = []

        for asset in assets:
            if asset in visited:
                continue
            cluster = {asset}
            queue = [asset]
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                visited.add(current)
                for other in assets:
                    if other in visited:
                        continue
                    pair = (current, other)
                    corr = self._correlation_matrix.get(pair, 0.0)
                    if abs(corr) >= self.correlation_threshold:
                        cluster.add(other)
                        queue.append(other)
            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters

    def register_position(
        self, asset: str, size_pct: float, sector: str = "GENERAL"
    ) -> None:
        """Register an active position for exposure tracking."""
        self._positions[asset] = {
            "size_pct": size_pct,
            "sector": sector,
        }

    def remove_position(self, asset: str) -> None:
        """Remove a closed position."""
        self._positions.pop(asset, None)

    def check_exposure(
        self, new_asset: str, new_size_pct: float, sector: str = "GENERAL"
    ) -> Dict[str, Any]:
        """
        Check if adding a new position would violate exposure limits.

        Returns:
            dict with allowed (bool), violations (list), current_exposure details
        """
        violations = []

        # ── Single asset limit ─────────────────────────────────
        current_asset_exposure = self._positions.get(new_asset, {}).get("size_pct", 0.0)
        if current_asset_exposure + new_size_pct > self.max_single_asset_pct:
            violations.append(
                f"Single asset '{new_asset}' exposure "
                f"{current_asset_exposure + new_size_pct:.2%} > limit {self.max_single_asset_pct:.2%}"
            )

        # ── Sector limit ───────────────────────────────────────
        sector_total = sum(
            p["size_pct"] for p in self._positions.values()
            if p["sector"] == sector
        ) + new_size_pct
        if sector_total > self.max_sector_exposure_pct:
            violations.append(
                f"Sector '{sector}' exposure {sector_total:.2%} > limit {self.max_sector_exposure_pct:.2%}"
            )

        # ── Cluster correlation limit ──────────────────────────
        clusters = self.find_correlated_clusters()
        for cluster in clusters:
            if new_asset in cluster:
                cluster_exposure = sum(
                    self._positions.get(a, {}).get("size_pct", 0.0)
                    for a in cluster
                ) + new_size_pct
                if cluster_exposure > self.max_cluster_exposure_pct:
                    violations.append(
                        f"Correlated cluster {cluster} exposure "
                        f"{cluster_exposure:.2%} > limit {self.max_cluster_exposure_pct:.2%}"
                    )

        # ── Total leverage limit ───────────────────────────────
        total_exposure = sum(p["size_pct"] for p in self._positions.values()) + new_size_pct
        if total_exposure > self.max_leverage:
            violations.append(
                f"Total leverage {total_exposure:.2%} > limit {self.max_leverage:.2%}"
            )

        allowed = len(violations) == 0
        return {
            "allowed": allowed,
            "violations": violations,
            "total_exposure": round(total_exposure, 4),
            "position_count": len(self._positions) + 1,
        }

    def get_state(self) -> Dict[str, Any]:
        """Serialize current exposure state for API/frontend."""
        return {
            "positions": dict(self._positions),
            "total_exposure": round(
                sum(p["size_pct"] for p in self._positions.values()), 4
            ),
            "cluster_count": len(self.find_correlated_clusters()),
            "max_leverage": self.max_leverage,
        }
