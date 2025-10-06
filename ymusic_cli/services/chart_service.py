"""Chart operations for Yandex Music API.

This module provides functionality to fetch music charts from Yandex Music.

Following SOLID principles:
- Single Responsibility: Handles only chart-related API operations
- Open/Closed: Can be extended without modification
- Dependency Inversion: Depends on yandex_music.Client abstraction
"""

import asyncio
import logging
from typing import List, Any

from yandex_music import Client


logger = logging.getLogger(__name__)


class ChartService:
    """Service for fetching chart data from Yandex Music API.

    Handles chart track retrieval using multiple fallback methods
    to ensure reliability across different API versions.
    """

    def __init__(self, client: Client):
        """Initialize chart service.

        Args:
            client: Initialized Yandex Music API client
        """
        self.client = client

    async def get_chart_tracks(self, chart_id: str) -> List[Any]:
        """Get tracks from a chart.

        Tries multiple methods to fetch chart data:
        1. Direct chart() method
        2. Landing page charts
        3. Popular tracks fallback

        Args:
            chart_id: Chart identifier (e.g., 'world', 'russia', 'global')

        Returns:
            List of track objects from the chart
        """
        try:
            logger.info(f"Fetching chart: {chart_id}")

            # Method 1: Try chart() method
            tracks = await self._try_chart_method(chart_id)
            if tracks:
                return tracks

            # Method 2: Try landing page charts
            tracks = await self._try_landing_charts()
            if tracks:
                return tracks

            # Method 3: Try specific chart playlists fallback
            if chart_id.lower() in ['world', 'russia', 'global']:
                tracks = await self._try_popular_tracks_fallback()
                if tracks:
                    return tracks

            logger.error(f"Chart {chart_id} not found or no tracks available")
            return []

        except Exception as e:
            logger.error(f"Error fetching chart tracks: {e}")
            return []

    async def _try_chart_method(self, chart_id: str) -> List[Any]:
        """Try to fetch chart using direct chart() method.

        Args:
            chart_id: Chart identifier

        Returns:
            List of tracks or empty list if method fails
        """
        try:
            chart_info = await asyncio.to_thread(self.client.chart, chart_id)
            if not chart_info or not hasattr(chart_info, 'chart') or not chart_info.chart:
                return []

            tracks = []

            # Check if it has items (old structure)
            if hasattr(chart_info.chart, 'items') and chart_info.chart.items:
                for chart_item in chart_info.chart.items:
                    if hasattr(chart_item, 'track') and chart_item.track:
                        tracks.append(chart_item.track)

            # Check if it has tracks directly (new structure)
            elif hasattr(chart_info.chart, 'tracks') and chart_info.chart.tracks:
                tracks.extend(chart_info.chart.tracks)

            if tracks:
                logger.info(f"Retrieved {len(tracks)} tracks from chart {chart_id}")
                return tracks

            return []

        except Exception as e:
            logger.debug(f"Chart method failed: {e}")
            return []

    async def _try_landing_charts(self) -> List[Any]:
        """Try to fetch chart from landing page.

        Returns:
            List of tracks or empty list if method fails
        """
        try:
            landing = await asyncio.to_thread(self.client.landing, blocks=['chart'])
            if not landing or not landing.blocks:
                return []

            for block in landing.blocks:
                if block.type != 'chart' or not block.data:
                    continue

                chart_tracks = []
                if hasattr(block.data, 'chart') and block.data.chart:
                    if hasattr(block.data.chart, 'tracks') and block.data.chart.tracks:
                        chart_tracks.extend(block.data.chart.tracks)
                    elif hasattr(block.data.chart, 'items') and block.data.chart.items:
                        for item in block.data.chart.items:
                            if hasattr(item, 'track') and item.track:
                                chart_tracks.append(item.track)

                if chart_tracks:
                    logger.info(f"Retrieved {len(chart_tracks)} tracks from landing chart")
                    return chart_tracks

            return []

        except Exception as e:
            logger.debug(f"Landing chart method failed: {e}")
            return []

    async def _try_popular_tracks_fallback(self) -> List[Any]:
        """Try to fetch popular tracks as fallback.

        Returns:
            List of up to 50 popular tracks or empty list if method fails
        """
        try:
            landing = await asyncio.to_thread(self.client.landing)
            if not landing or not landing.blocks:
                return []

            for block in landing.blocks:
                if block.type not in ['chart', 'popular-tracks'] or not block.data:
                    continue

                if hasattr(block.data, 'tracks') and block.data.tracks:
                    tracks = block.data.tracks[:50]  # Limit to reasonable number
                    logger.info(f"Retrieved {len(tracks)} tracks from {block.type} block")
                    return tracks

            return []

        except Exception as e:
            logger.debug(f"Popular tracks method failed: {e}")
            return []
