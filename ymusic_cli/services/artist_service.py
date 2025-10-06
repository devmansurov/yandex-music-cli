"""Artist-related operations for Yandex Music API.

This module provides functionality to fetch artist tracks, similar artists,
and artist information from the Yandex Music API.

Following SOLID principles:
- Single Responsibility: Handles only artist-related API operations
- Open/Closed: Can be extended without modification
- Liskov Substitution: Can replace any artist data source interface
- Interface Segregation: Focused on artist operations only
- Dependency Inversion: Depends on yandex_music.Client abstraction
"""

import asyncio
import logging
from typing import List, Optional, Any

from yandex_music import Client, Artist


logger = logging.getLogger(__name__)


class ArtistService:
    """Service for fetching artist data from Yandex Music API.

    Handles all artist-related operations including track retrieval,
    similar artist discovery, and artist metadata fetching.
    """

    def __init__(self, client: Client):
        """Initialize artist service.

        Args:
            client: Initialized Yandex Music API client
        """
        self.client = client

    async def get_artist_tracks(self, artist_id: str, max_tracks: Optional[int] = None) -> List[Any]:
        """Get tracks from an artist with pagination and early exit optimization.

        Performance optimization: When max_tracks is specified (e.g., for --in-top filter),
        pagination stops once we have enough tracks instead of fetching all tracks.

        Args:
            artist_id: Yandex Music artist ID
            max_tracks: Maximum number of tracks to fetch (None = fetch all)
                       Enables early pagination exit for --in-top optimization

        Returns:
            List of track objects from Yandex Music API (up to max_tracks if specified)

        Examples:
            >>> # Fetch all tracks (old behavior)
            >>> tracks = await service.get_artist_tracks("123456")
            >>> len(tracks)  # e.g., 243 tracks

            >>> # Fetch only top 10 tracks (optimized for --in-top 10)
            >>> tracks = await service.get_artist_tracks("123456", max_tracks=10)
            >>> len(tracks)  # 10 tracks (1 API call instead of 13)
        """
        all_tracks = []
        page = 0
        # Increased from 20 to 50 for better performance (fewer API calls)
        page_size = 50

        try:
            while True:
                logger.debug(f"Fetching artist tracks page {page} (max_tracks={max_tracks})")
                tracks_result = await asyncio.to_thread(
                    self.client.artists_tracks,
                    artist_id,
                    page=page,
                    page_size=page_size
                )

                if not tracks_result or not tracks_result.tracks:
                    break

                all_tracks.extend(tracks_result.tracks)

                # OPTIMIZATION: Early exit if we have enough tracks for --in-top filter
                if max_tracks and len(all_tracks) >= max_tracks:
                    logger.debug(
                        f"Early exit: fetched {len(all_tracks)} tracks "
                        f"(needed {max_tracks}) - saved API calls"
                    )
                    break

                # Check if we have more pages
                if len(tracks_result.tracks) < page_size:
                    break

                page += 1

                # Safety limit to prevent infinite loops
                if page > 100:
                    logger.warning("Reached page limit of 100, stopping")
                    break

            logger.info(
                f"Retrieved {len(all_tracks)} tracks from artist {artist_id}"
                + (f" (requested max_tracks={max_tracks})" if max_tracks else "")
            )
            return all_tracks

        except Exception as e:
            logger.error(f"Error fetching artist tracks: {e}")
            return []

    async def get_all_similar_artists(self, artist_id: str) -> List[Any]:
        """Get ALL similar artists (up to 50) using direct API endpoint.

        Args:
            artist_id: Yandex Music artist ID

        Returns:
            List of similar artist objects (up to 50)
        """
        try:
            logger.debug(f"Getting all similar artists for artist {artist_id}")

            # Use direct API endpoint to get all 50 similar artists
            url = f'{self.client.base_url}/artists/{artist_id}/similar'
            logger.debug(f"Making request to URL: {url}")

            result = await asyncio.to_thread(self.client._request.get, url)
            logger.debug(f"API response keys: {list(result.keys()) if result else 'None'}")

            if not result or 'similar_artists' not in result:
                logger.warning(f"No similar_artists key in API response for artist {artist_id}")
                # Fallback to brief info method
                return await self._get_similar_artists_fallback(artist_id)

            similar_data = result.get('similar_artists', [])
            if not similar_data:
                logger.warning(f"Empty similar_artists list for artist {artist_id}")
                return await self._get_similar_artists_fallback(artist_id)

            # Convert dict objects to Artist objects
            similar_artists = []
            logger.debug(f"Processing {len(similar_data)} similar artists from API")

            conversion_errors = 0
            for i, artist_dict in enumerate(similar_data):
                try:
                    artist_obj = Artist.de_json(artist_dict, self.client)
                    if artist_obj:
                        similar_artists.append(artist_obj)
                        logger.debug(f"✓ Converted artist {i+1}: {artist_dict.get('name', 'Unknown')}")
                    else:
                        logger.warning(f"✗ Artist.de_json returned None for {artist_dict.get('name', 'Unknown')}")
                        conversion_errors += 1
                except Exception as e:
                    logger.error(f"✗ Exception converting artist {i+1}: {e}")
                    logger.debug(f"Artist dict: {artist_dict}")
                    conversion_errors += 1
                    continue

            logger.debug(f"Converted {len(similar_artists)}/{len(similar_data)} similar artists (errors: {conversion_errors})")

            if len(similar_artists) == 0:
                logger.warning(f"All conversions failed, using fallback for artist {artist_id}")
                return await self._get_similar_artists_fallback(artist_id)

            return similar_artists

        except Exception as e:
            logger.error(f"Unexpected error in get_all_similar_artists for {artist_id}: {e}")
            return await self._get_similar_artists_fallback(artist_id)

    async def _get_similar_artists_fallback(self, artist_id: str) -> List[Any]:
        """Fallback method to get similar artists using brief info.

        Args:
            artist_id: Yandex Music artist ID

        Returns:
            List of similar artist objects (fewer than direct API method)
        """
        try:
            logger.info(f"Using fallback method for similar artists of {artist_id}")
            brief_info = await asyncio.to_thread(self.client.artists_brief_info, artist_id)

            if not brief_info:
                logger.warning(f"No brief info found for artist {artist_id}")
                return []

            similar_artists = []
            if hasattr(brief_info, 'similar_artists') and brief_info.similar_artists:
                similar_artists = brief_info.similar_artists

            logger.info(f"Found {len(similar_artists)} similar artists via fallback")
            return similar_artists

        except Exception as e:
            logger.error(f"Error in fallback similar artists for {artist_id}: {e}")
            return []

    async def get_artist_info(self, artist_id: str) -> Optional[Any]:
        """Get detailed artist information.

        Args:
            artist_id: Yandex Music artist ID

        Returns:
            Artist object or None if not found
        """
        try:
            artists = await asyncio.to_thread(self.client.artists, artist_id)
            if artists and len(artists) > 0:
                return artists[0]
            return None
        except Exception as e:
            logger.error(f"Error getting artist info for {artist_id}: {e}")
            return None

    async def get_artist_country(self, artist_id: str) -> Optional[str]:
        """Get artist's country/region.

        Args:
            artist_id: Yandex Music artist ID

        Returns:
            Country code in uppercase or None if not found
        """
        try:
            artist = await self.get_artist_info(artist_id)
            if not artist:
                return None

            # Try different ways to get country information
            # Method 1: Direct countries attribute
            if hasattr(artist, 'countries') and artist.countries:
                return artist.countries[0].upper()

            # Method 2: Check regions
            if hasattr(artist, 'regions') and artist.regions:
                return artist.regions[0].upper()

            # Method 3: Try to infer from artist's albums
            try:
                albums_info = await asyncio.to_thread(
                    self.client.artists_direct_albums,
                    artist_id,
                    page_size=5
                )
                if albums_info and albums_info.albums:
                    for album in albums_info.albums[:3]:
                        if hasattr(album, 'regions') and album.regions:
                            return album.regions[0].upper()
            except Exception:
                pass

            logger.debug(f"No country information found for artist {artist_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting country for artist {artist_id}: {e}")
            return None
