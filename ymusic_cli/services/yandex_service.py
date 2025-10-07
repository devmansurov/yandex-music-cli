"""Yandex Music service implementation."""

import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

# Add parent directory to path for existing modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from yandex_music import Client
except ImportError as e:
    logging.error(f"Failed to import Yandex Music modules: {e}")
    raise

from ymusic_cli.core.interfaces import MusicService, CacheService
from ymusic_cli.core.models import Artist, Track, Album, DownloadOptions, Quality
from ymusic_cli.core.exceptions import ServiceError, NotFoundError, NetworkError
from ymusic_cli.services.artist_service import ArtistService
from ymusic_cli.services.chart_service import ChartService
from ymusic_cli.utils.track_filters import TrackFilter


class YandexMusicService(MusicService):
    """Yandex Music service implementation."""
    
    def __init__(self, token: str, cache_service: Optional[CacheService] = None):
        self.token = token
        self.cache = cache_service
        self.client: Optional[Client] = None
        self.artist_service: Optional[ArtistService] = None
        self.chart_service: Optional[ChartService] = None
        self.track_filter = TrackFilter()
        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> None:
        """Initialize the Yandex Music client and services."""
        try:
            self.logger.info("Initializing Yandex Music client...")
            self.client = Client(self.token)
            await asyncio.to_thread(self.client.init)

            # Initialize simplified services (following SOLID principles)
            self.artist_service = ArtistService(self.client)
            self.chart_service = ChartService(self.client)

            self.logger.info("✅ Yandex Music service initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Yandex Music service: {e}")
            raise ServiceError(f"Failed to initialize Yandex Music: {e}", "yandex_music")
    
    async def search_artist(self, query: str) -> List[Artist]:
        """Search for artists by name."""
        if not self.client:
            raise ServiceError("Client not initialized", "yandex_music")
        
        cache_key = f"search_artist:{query.lower()}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        
        try:
            search_result = await asyncio.to_thread(
                self.client.search, query, type_="artist"
            )
            
            artists = []
            if search_result and search_result.artists:
                for ya_artist in search_result.artists.results[:10]:  # Limit results
                    artist = Artist(
                        id=str(ya_artist.id),
                        name=ya_artist.name,
                        country=self._extract_country(ya_artist),
                        genres=self._extract_genres(ya_artist),
                        track_count=getattr(ya_artist.counts, 'tracks', 0) if hasattr(ya_artist, 'counts') and ya_artist.counts else 0
                    )
                    artists.append(artist)
            
            if self.cache:
                await self.cache.set(cache_key, artists, ttl_seconds=3600)
            
            return artists
            
        except Exception as e:
            self.logger.error(f"Error searching for artist '{query}': {e}")
            raise ServiceError(f"Search failed: {e}", "yandex_music")
    
    async def get_artist(self, artist_id: str) -> Optional[Artist]:
        """Get artist information by ID."""
        if not self.client:
            raise ServiceError("Client not initialized", "yandex_music")
        
        cache_key = f"artist:{artist_id}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        
        try:
            artists_result = await asyncio.to_thread(self.client.artists, artist_id)
            if not artists_result or len(artists_result) == 0:
                return None
            
            ya_artist = artists_result[0]
            # Get track count safely from Counts object
            track_count = 0
            if hasattr(ya_artist, 'counts') and ya_artist.counts:
                track_count = getattr(ya_artist.counts, 'tracks', 0) or 0
            
            artist = Artist(
                id=str(ya_artist.id),
                name=ya_artist.name,
                country=self._extract_country(ya_artist),
                genres=self._extract_genres(ya_artist),
                track_count=track_count
            )
            
            if self.cache:
                await self.cache.set(cache_key, artist, ttl_seconds=3600)
            
            return artist
            
        except Exception as e:
            self.logger.error(f"Error getting artist {artist_id}: {e}")
            raise ServiceError(f"Failed to get artist: {e}", "yandex_music")
    
    async def get_artist_tracks(self, artist_id: str, options: DownloadOptions) -> List[Track]:
        """Get tracks for an artist with filtering and caching optimization."""
        if not self.artist_service:
            raise ServiceError("Artist service not initialized", "yandex_music")

        try:
            # OPTIMIZATION: Check cache for --in-top filtered results
            if (options.in_top_n or options.in_top_percent) and options.years and self.cache:
                # Create cache key based on filter criteria
                in_top_key = f"{options.in_top_n}" if options.in_top_n else f"{options.in_top_percent}%"
                cache_key = f"top_tracks:{artist_id}:{in_top_key}:{options.years[0]}-{options.years[1]}"

                cached_tracks = await self.cache.get(cache_key)
                if cached_tracks:
                    self.logger.debug(f"✓ Cache hit for {cache_key} (saved API calls)")
                    return cached_tracks

            # OPTIMIZATION: Calculate max tracks needed for early pagination exit
            # For --in-top numeric mode, we know exactly how many tracks to fetch
            # For --in-top percentage mode, we need to fetch at least one page to know total
            max_tracks_needed = options.get_max_tracks_needed() if options.in_top_n else None

            # Get tracks using artist service with optimization
            # Note: Yandex API already returns tracks sorted by popularity
            all_tracks = await self.artist_service.get_artist_tracks(artist_id, max_tracks=max_tracks_needed)

            if not all_tracks:
                return []

            # NEW LOGIC: --in-top filter (works only with year filter)
            if (options.in_top_n or options.in_top_percent) and options.years:
                # Calculate how many top tracks to check
                if options.in_top_percent:
                    # Percentage mode: calculate position from percentage
                    import math
                    top_count = math.ceil(len(all_tracks) * options.in_top_percent / 100)
                    self.logger.debug(
                        f"--in-top {options.in_top_percent}%: "
                        f"Checking top {top_count} tracks out of {len(all_tracks)} total "
                        f"({options.in_top_percent}% of {len(all_tracks)})"
                    )
                else:
                    # Numeric mode: use exact position
                    top_count = min(options.in_top_n, len(all_tracks))
                    self.logger.debug(
                        f"--in-top {options.in_top_n}: "
                        f"Checking top {top_count} tracks out of {len(all_tracks)} total"
                    )

                # Take only the top N most popular tracks
                top_n_tracks = all_tracks[:top_count]

                # Apply year filter to ONLY these top tracks
                filtered_tracks = self.track_filter.apply_filters(
                    top_n_tracks,
                    **self._convert_options_to_kwargs(options)
                )

                self.logger.debug(
                    f"Year filter ({options.years[0]}-{options.years[1]}): "
                    f"{len(filtered_tracks)} tracks from top {top_count} match year criteria"
                )

                # Select up to top_n from filtered results (strict mode)
                selected_tracks = self._select_top_tracks(filtered_tracks, options)

            else:
                # EXISTING LOGIC: Normal mode (no --in-top filter)
                # Apply filters using track filter utility (SOLID: Separation of Concerns)
                filtered_tracks = self.track_filter.apply_filters(
                    all_tracks,
                    **self._convert_options_to_kwargs(options)
                )

                # Apply top selection (tracks are already sorted by Yandex by popularity)
                selected_tracks = self._select_top_tracks(filtered_tracks, options)

            # Convert to our Track model
            tracks = []
            for ya_track in selected_tracks:
                track = await self._convert_yandex_track(ya_track)
                if track:
                    tracks.append(track)

            # OPTIMIZATION: Cache --in-top filtered results for reuse
            if (options.in_top_n or options.in_top_percent) and options.years and self.cache and tracks:
                in_top_key = f"{options.in_top_n}" if options.in_top_n else f"{options.in_top_percent}%"
                cache_key = f"top_tracks:{artist_id}:{in_top_key}:{options.years[0]}-{options.years[1]}"
                # Cache for 1 hour (tracks in year range don't change frequently)
                await self.cache.set(cache_key, tracks, ttl_seconds=3600)
                self.logger.debug(f"Cached result for {cache_key}")

            return tracks

        except Exception as e:
            self.logger.error(f"Error getting tracks for artist {artist_id}: {e}")
            raise ServiceError(f"Failed to get tracks: {e}", "yandex_music")

    async def check_artist_has_content_in_years(self, artist_id: str, years: tuple[int, int]) -> bool:
        """Lightweight check if artist has content in specified year range without fetching all tracks."""
        if not self.client:
            return True  # Default to True if we can't check

        cache_key = f"year_check:{artist_id}:{years[0]}-{years[1]}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Retry logic for API calls
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Try to get artist's albums/singles for year filtering (much faster than all tracks)
                client = self.client

                # Add timeout and retry with exponential backoff
                try:
                    artist = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: client.artists_brief_info(artist_id)
                        ),
                        timeout=10.0  # 10 second timeout
                    )
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        self.logger.debug(f"Timeout checking artist {artist_id}, retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        self.logger.warning(f"Final timeout for artist {artist_id}, including in results")
                        return True  # Include artist on timeout

                if not artist:
                    # Cache negative result but include artist (artist exists but no info available)
                    if self.cache:
                        await self.cache.set(cache_key, True, ttl_seconds=1800)  # Cache for 30 minutes
                    return True

                # Check albums for year range
                if hasattr(artist, 'albums') and artist.albums:
                    for album in artist.albums:
                        try:
                            if hasattr(album, 'year') and album.year:
                                if years[0] <= album.year <= years[1]:
                                    if self.cache:
                                        await self.cache.set(cache_key, True, ttl_seconds=3600)  # Cache for 1 hour
                                    return True
                        except Exception as e:
                            # Handle album data issues (like Description.__init__ errors)
                            error_str = str(e)
                            if "Description.__init__()" in error_str and "uri" in error_str:
                                self.logger.debug(f"Album data issue for artist {artist_id}: {e}")
                            else:
                                self.logger.debug(f"Unexpected album error for artist {artist_id}: {e}")
                            # Continue checking other albums
                            continue

                # No content found in specified years, but cache result and exclude artist
                if self.cache:
                    await self.cache.set(cache_key, False, ttl_seconds=3600)
                return False

            except Exception as e:
                error_str = str(e)
                # Check for network-related errors that should trigger retry
                is_network_error = any(err in error_str.lower() for err in [
                    'network is unreachable', 'connection', 'timeout', 'max retries exceeded'
                ])

                if is_network_error and attempt < max_retries - 1:
                    self.logger.debug(f"Network error for artist {artist_id}, retrying in {retry_delay}s: {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    # On final attempt or non-network error, include the artist
                    error_str = str(e)
                    # Downgrade known API data issues to DEBUG
                    if "Description.__init__()" in error_str and "uri" in error_str:
                        self.logger.debug(f"Malformed album data for artist {artist_id} (Yandex API issue), including artist anyway")
                    else:
                        self.logger.warning(f"Error checking year content for artist {artist_id}: {e}")

                    if self.cache:
                        # Cache as True to avoid repeated failed checks for this artist
                        await self.cache.set(cache_key, True, ttl_seconds=1800)  # Cache for 30 minutes
                    return True  # Default to True on error to avoid filtering out potentially valid artists

        # Fallback (shouldn't reach here)
        return True

    async def batch_check_artists_year_content(
        self,
        artist_ids: List[str],
        years: tuple[int, int],
        max_concurrent: int = 10
    ) -> Dict[str, bool]:
        """
        Check multiple artists for year content in parallel (OPTIMIZATION).

        This method significantly reduces discovery time by checking multiple artists
        concurrently instead of sequentially. For 50 artists, this reduces checking
        time from ~50 seconds to ~5 seconds.

        Args:
            artist_ids: List of artist IDs to check
            years: Tuple of (start_year, end_year) to filter by
            max_concurrent: Maximum number of concurrent API calls (default: 10)

        Returns:
            Dictionary mapping artist_id -> bool (True if has content in year range)
        """
        if not artist_ids:
            return {}

        # Use semaphore to limit concurrent API calls (respect rate limits)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_with_semaphore(artist_id: str) -> tuple[str, bool]:
            """Check artist with rate limiting"""
            async with semaphore:
                has_content = await self.check_artist_has_content_in_years(artist_id, years)
                return (artist_id, has_content)

        # Execute all checks concurrently
        tasks = [check_with_semaphore(aid) for aid in artist_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary
        year_content_map = {}
        for i, result in enumerate(results):
            artist_id = artist_ids[i]
            if isinstance(result, Exception):
                self.logger.warning(f"Error checking year content for {artist_id}: {result}")
                year_content_map[artist_id] = True  # Default to True on error
            else:
                year_content_map[artist_id] = result[1]

        self.logger.info(
            f"Batch year check: {len(artist_ids)} artists checked, "
            f"{sum(year_content_map.values())} have content in {years[0]}-{years[1]}"
        )

        return year_content_map

    async def get_similar_artists(self, artist_id: str, limit: int = 50) -> List[Artist]:
        """Get similar artists for a given artist."""
        self.logger.debug(f"get_similar_artists called: artist_id={artist_id}, limit={limit}")

        if not self.client:
            self.logger.error("Downloader not initialized")
            raise ServiceError("Downloader not initialized", "yandex_music")

        cache_key = f"similar_artists:{artist_id}:{limit}"
        if self.cache:
            self.logger.debug(f"Checking cache for key: {cache_key}")
            cached = await self.cache.get(cache_key)
            if cached:
                self.logger.debug(f"Found cached result: {len(cached)} artists")
                return cached
            else:
                self.logger.debug("No cached result found")

        try:
            self.logger.debug(f"Making API call to get_all_similar_artists for artist {artist_id}")
            # Use enhanced similar artists method from the downloader
            similar_artists_raw = await self.artist_service.get_all_similar_artists(artist_id)

            self.logger.debug(f"API call returned {len(similar_artists_raw) if similar_artists_raw else 0} raw similar artists")
            
            if not similar_artists_raw:
                self.logger.warning(f"No raw similar artists returned for artist {artist_id}")
                return []
            
            artists = []
            for i, ya_artist in enumerate(similar_artists_raw[:limit]):
                # Get track count from artist's counts
                track_count = 0
                if hasattr(ya_artist, 'counts') and ya_artist.counts:
                    track_count = getattr(ya_artist.counts, 'tracks', 0) or 0
                
                self.logger.debug(f"Processing similar artist {i+1}: {ya_artist.name} (ID: {ya_artist.id}, tracks: {track_count})")

                artist = Artist(
                    id=str(ya_artist.id),
                    name=ya_artist.name,
                    country=self._extract_country(ya_artist),  # Use existing data instead of API call
                    genres=self._extract_genres(ya_artist),
                    track_count=track_count,
                    similarity_score=(1.0 - (i / len(similar_artists_raw))) if similar_artists_raw else 0.0
                )
                artists.append(artist)
            
            self.logger.debug(f"Successfully processed {len(artists)} similar artists")

            if self.cache:
                self.logger.debug(f"Caching result for key: {cache_key}")
                await self.cache.set(cache_key, artists, ttl_seconds=86400)  # 24 hours
            
            return artists
            
        except Exception as e:
            self.logger.error(f"Error getting similar artists for {artist_id}: {e}", exc_info=True)
            raise ServiceError(f"Failed to get similar artists: {e}", "yandex_music")
    
    async def get_track_download_info(self, track: Track) -> Optional[str]:
        """Get download URL for a track."""
        if not self.client:
            raise ServiceError("Client not initialized", "yandex_music")
        
        try:
            # Get track object
            ya_track = await asyncio.to_thread(self.client.tracks, track.id)
            if not ya_track or len(ya_track) == 0:
                return None
            
            track_obj = ya_track[0]
            
            # Get download info
            download_info = await asyncio.to_thread(track_obj.get_download_info)
            if not download_info:
                return None
            
            # Select best quality
            best_quality = self._get_best_quality(download_info, track.quality)
            if not best_quality:
                return None
            
            return best_quality.get_direct_link()
            
        except Exception as e:
            self.logger.error(f"Error getting download info for track {track.id}: {e}")
            return None
    
    async def get_chart_tracks(self, chart_type: str, options: DownloadOptions) -> List[Track]:
        """Get tracks from a chart."""
        if not self.client:
            raise ServiceError("Downloader not initialized", "yandex_music")
        
        try:
            # Use chart downloader from the advanced downloader
            tracks_result = await self.chart_service.get_chart_tracks(chart_type)
            
            if not tracks_result:
                return []
            
            # Apply filters
            filtered_tracks = self.track_filter.apply_filters(
                tracks_result,
                **self._convert_options_to_kwargs(options)
            )
            
            # Apply quantity limit
            quantity = options.top_n or len(filtered_tracks)
            selected_tracks = filtered_tracks[:quantity]
            
            # Convert to our Track model
            tracks = []
            for ya_track in selected_tracks:
                track = await self._convert_yandex_track(ya_track)
                if track:
                    tracks.append(track)
            
            return tracks
            
        except Exception as e:
            self.logger.error(f"Error getting chart tracks for {chart_type}: {e}")
            raise ServiceError(f"Failed to get chart tracks: {e}", "yandex_music")
    
    # Helper methods
    
    async def _convert_yandex_track(self, ya_track) -> Optional[Track]:
        """Convert Yandex track object to our Track model."""
        try:
            # Handle TrackShort objects (from charts) vs regular Track objects
            # TrackShort has a nested track property with the actual track data
            if hasattr(ya_track, 'track') and ya_track.track:
                # This is a TrackShort object from chart
                actual_track = ya_track.track
            else:
                # This is a regular Track object
                actual_track = ya_track

            # Get track ID
            track_id = str(actual_track.id) if hasattr(actual_track, 'id') else None
            if not track_id:
                return None

            # Get title
            title = None
            if hasattr(actual_track, 'title'):
                title = actual_track.title
            elif hasattr(actual_track, 'name'):
                title = actual_track.name

            if not title:
                title = "Unknown Title"

            # Get artist names and IDs
            artist_ids = []
            artist_names = []
            if hasattr(actual_track, 'artists') and actual_track.artists:
                for artist in actual_track.artists:
                    if hasattr(artist, 'id'):
                        artist_ids.append(str(artist.id))
                    if hasattr(artist, 'name'):
                        artist_names.append(artist.name)

            # Get album info
            album_id = None
            album_name = None
            year = None
            if hasattr(actual_track, 'albums') and actual_track.albums:
                album = actual_track.albums[0]
                if hasattr(album, 'id'):
                    album_id = str(album.id)
                if hasattr(album, 'title'):
                    album_name = album.title
                if hasattr(album, 'year'):
                    year = album.year

            track = Track(
                id=track_id,
                title=title,
                artist_ids=artist_ids,
                album_id=album_id,
                duration_ms=getattr(actual_track, 'duration_ms', 0) or 0,
                explicit=getattr(actual_track, 'explicit', False),
                year=year,
                artist_names=artist_names,
                album_name=album_name
            )

            return track

        except Exception as e:
            self.logger.error(f"Error converting track: {e}")
            return None
    
    def _convert_options_to_kwargs(self, options: DownloadOptions) -> Dict[str, Any]:
        """Convert DownloadOptions to kwargs for the downloader."""
        kwargs = {}
        
        if options.years:
            start_year, end_year = options.years
            if start_year == end_year:
                kwargs['years'] = str(start_year)
            else:
                kwargs['years'] = f"{start_year}-{end_year}"
        
        if options.countries:
            kwargs['countries'] = ','.join(options.countries)
        
        if options.genres:
            kwargs['genres'] = ','.join(options.genres)
        
        if options.exclude_explicit:
            kwargs['no_explicit'] = True
        
        kwargs['quality'] = options.quality.value
        kwargs['skip_existing'] = options.skip_existing
        
        return kwargs
    
    def _select_top_tracks(self, tracks: List[Any], options: DownloadOptions) -> List[Any]:
        """Select top N tracks or top N percentage."""
        if not options.top_n and not options.top_percent:
            return tracks

        if options.top_percent:
            count = max(1, int(len(tracks) * options.top_percent / 100))
        else:
            count = min(options.top_n or len(tracks), len(tracks))

        return tracks[:count]

    def _get_best_quality(self, download_info, quality: Quality):
        """Select the best available quality."""
        if not download_info:
            return None
        
        # Quality preference mapping
        quality_preference = {
            Quality.HIGH: ["lossless", "hq", "mp3"],
            Quality.MEDIUM: ["hq", "mp3"],
            Quality.LOW: ["mp3"]
        }
        
        preferred_codecs = quality_preference.get(quality, ["mp3"])
        
        # Sort by bitrate (highest first)
        sorted_info = sorted(download_info, key=lambda x: x.bitrate_in_kbps, reverse=True)
        
        # Try to find preferred codec with highest bitrate
        for codec in preferred_codecs:
            for info in sorted_info:
                if info.codec == codec:
                    return info
        
        # Fallback to highest bitrate available
        return sorted_info[0] if sorted_info else None
    
    def _extract_country(self, ya_artist) -> Optional[str]:
        """Extract country from Yandex artist object."""
        try:
            if hasattr(ya_artist, 'countries') and ya_artist.countries:
                return ya_artist.countries[0].upper()
            if hasattr(ya_artist, 'regions') and ya_artist.regions:
                return ya_artist.regions[0].upper()
            return None
        except:
            return None
    
    def _extract_genres(self, ya_artist) -> List[str]:
        """Extract genres from Yandex artist object."""
        try:
            if hasattr(ya_artist, 'genres') and ya_artist.genres:
                return [genre.lower() for genre in ya_artist.genres]
            return []
        except:
            return []
    
    async def _get_artist_country(self, artist_id: str) -> Optional[str]:
        """Get artist country using the downloader."""
        if not self.client:
            return None

        try:
            return await self.artist_service.get_artist_country(artist_id)
        except:
            return None

    def _build_image_url(self, uri: str, size: str = "1000x1000") -> str:
        """Build full image URL from Yandex URI."""
        if not uri:
            return None

        # Handle URI that already has https://
        if uri.startswith('https://'):
            return uri.replace('%%', size)

        # Add https:// prefix and replace %% with size
        return f"https://{uri.replace('%%', size)}"

    async def get_artist_basic_info(self, artist_id: str) -> Optional[Dict[str, Any]]:
        """Get basic artist information without similar artists (for faster search results)."""
        if not self.client:
            raise ServiceError("Client not initialized", "yandex_music")

        cache_key = f"artist_basic_info:{artist_id}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        try:
            # Get basic artist info
            artists_result = await asyncio.to_thread(self.client.artists, artist_id)
            if not artists_result or len(artists_result) == 0:
                return None

            ya_artist = artists_result[0]

            # Get brief info for additional data
            brief_info = await asyncio.to_thread(self.client.artists_brief_info, artist_id)

            # Extract all available information
            artist_info = {
                # Basic info
                'id': str(ya_artist.id),
                'name': ya_artist.name,
                'available': getattr(ya_artist, 'available', True),
                'various': getattr(ya_artist, 'various', False),
                'composer': getattr(ya_artist, 'composer', False),
                'tickets_available': getattr(ya_artist, 'tickets_available', False),

                # Counts and statistics
                'counts': {},
                'ratings': {},

                # Content
                'genres': self._extract_genres(ya_artist),
                'countries': self._extract_country(ya_artist),

                # Media
                'cover': None,
                'og_image': getattr(ya_artist, 'og_image', None),

                # Links and social
                'links': [],

                # Related content (empty for basic info)
                'similar_artists': [],
                'popular_tracks': [],
                'albums': [],
                'playlists': [],
                'concerts': []
            }

            # Extract counts
            if hasattr(ya_artist, 'counts') and ya_artist.counts:
                counts = ya_artist.counts
                artist_info['counts'] = {
                    'tracks': getattr(counts, 'tracks', 0) or 0,
                    'direct_albums': getattr(counts, 'direct_albums', 0) or 0,
                    'also_albums': getattr(counts, 'also_albums', 0) or 0,
                    'also_tracks': getattr(counts, 'also_tracks', 0) or 0
                }

            # Extract ratings
            if hasattr(ya_artist, 'ratings') and ya_artist.ratings:
                ratings = ya_artist.ratings
                artist_info['ratings'] = {
                    'month': getattr(ratings, 'month', 0) or 0,
                    'week': getattr(ratings, 'week', 0) or 0,
                    'day': getattr(ratings, 'day', 0) or 0
                }

            # Extract cover information
            if hasattr(ya_artist, 'cover') and ya_artist.cover:
                cover = ya_artist.cover
                artist_info['cover'] = {
                    'type': getattr(cover, 'type', None),
                    'uri': getattr(cover, 'uri', None),
                    'items_uri': getattr(cover, 'items_uri', None)
                }

            # Extract links
            if hasattr(ya_artist, 'links') and ya_artist.links:
                for link in ya_artist.links:
                    if hasattr(link, 'type') and hasattr(link, 'href'):
                        artist_info['links'].append({
                            'type': link.type,
                            'href': link.href
                        })

            # Extract brief info data (but skip similar artists!)
            if brief_info:

                # Popular tracks
                if hasattr(brief_info, 'popular_tracks') and brief_info.popular_tracks:
                    for track in brief_info.popular_tracks[:10]:  # Top 10
                        if hasattr(track, 'id') and hasattr(track, 'title'):
                            artist_info['popular_tracks'].append({
                                'id': str(track.id),
                                'title': track.title,
                                'duration_ms': getattr(track, 'duration_ms', 0) or 0
                            })

                # Albums
                if hasattr(brief_info, 'albums') and brief_info.albums:
                    for album in brief_info.albums[:10]:  # Top 10
                        if hasattr(album, 'id') and hasattr(album, 'title'):
                            artist_info['albums'].append({
                                'id': str(album.id),
                                'title': album.title,
                                'year': getattr(album, 'year', None),
                                'track_count': getattr(album, 'track_count', 0) or 0,
                                'genre': getattr(album, 'genre', None)
                            })

                # Playlists
                if hasattr(brief_info, 'playlists') and brief_info.playlists:
                    for playlist in brief_info.playlists[:5]:  # Top 5
                        if hasattr(playlist, 'title'):
                            # Safely extract description - might be a complex object
                            description = None
                            try:
                                if hasattr(playlist, 'description'):
                                    desc = playlist.description
                                    if hasattr(desc, 'text'):
                                        description = desc.text
                                    elif isinstance(desc, str):
                                        description = desc
                            except:
                                description = None

                            artist_info['playlists'].append({
                                'title': playlist.title,
                                'description': description
                            })

                # Concerts
                if hasattr(brief_info, 'concerts') and brief_info.concerts:
                    for concert in brief_info.concerts[:5]:  # Top 5
                        artist_info['concerts'].append({
                            'title': getattr(concert, 'title', None),
                            'date': getattr(concert, 'date', None),
                            'city': getattr(concert, 'city', None)
                        })

            if self.cache:
                await self.cache.set(cache_key, artist_info, ttl_seconds=3600)

            return artist_info

        except Exception as e:
            self.logger.error(f"Error getting basic artist info for {artist_id}: {e}")
            raise ServiceError(f"Failed to get artist info: {e}", "yandex_music")

    async def get_artist_full_info(self, artist_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive artist information with all available data."""
        if not self.client:
            raise ServiceError("Client not initialized", "yandex_music")

        cache_key = f"artist_full_info:{artist_id}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        try:
            # Get basic artist info
            artists_result = await asyncio.to_thread(self.client.artists, artist_id)
            if not artists_result or len(artists_result) == 0:
                return None

            ya_artist = artists_result[0]

            # Get brief info for additional data
            brief_info = await asyncio.to_thread(self.client.artists_brief_info, artist_id)

            # Extract all available information
            artist_info = {
                # Basic info
                'id': str(ya_artist.id),
                'name': ya_artist.name,
                'available': getattr(ya_artist, 'available', True),
                'various': getattr(ya_artist, 'various', False),
                'composer': getattr(ya_artist, 'composer', False),
                'tickets_available': getattr(ya_artist, 'tickets_available', False),

                # Counts and statistics
                'counts': {},
                'ratings': {},

                # Content
                'genres': self._extract_genres(ya_artist),
                'countries': self._extract_country(ya_artist),

                # Media
                'cover': None,
                'og_image': getattr(ya_artist, 'og_image', None),

                # Links and social
                'links': [],

                # Related content
                'similar_artists': [],
                'popular_tracks': [],
                'albums': [],
                'videos': [],
                'playlists': [],
                'concerts': [],

                # Additional info
                'description': getattr(ya_artist, 'description', None),
                'aliases': getattr(ya_artist, 'aliases', None),
                'full_names': getattr(ya_artist, 'full_names', None),
            }

            # Extract counts
            if hasattr(ya_artist, 'counts') and ya_artist.counts:
                counts = ya_artist.counts
                artist_info['counts'] = {
                    'tracks': getattr(counts, 'tracks', 0) or 0,
                    'albums': getattr(counts, 'albums', 0) or 0,
                    'also_albums': getattr(counts, 'also_albums', 0) or 0,
                    'direct_albums': getattr(counts, 'direct_albums', 0) or 0,
                }

            # Extract ratings
            if hasattr(ya_artist, 'ratings') and ya_artist.ratings:
                ratings = ya_artist.ratings
                artist_info['ratings'] = {
                    'day': getattr(ratings, 'day', None),
                    'week': getattr(ratings, 'week', None),
                    'month': getattr(ratings, 'month', None),
                }

            # Extract cover info
            if hasattr(ya_artist, 'cover') and ya_artist.cover:
                cover = ya_artist.cover
                artist_info['cover'] = {
                    'type': getattr(cover, 'type', None),
                    'uri': getattr(cover, 'uri', None),
                }

            # Extract links
            if hasattr(ya_artist, 'links') and ya_artist.links:
                for link in ya_artist.links:
                    if hasattr(link, 'type') and hasattr(link, 'href'):
                        artist_info['links'].append({
                            'type': link.type,
                            'href': link.href
                        })

            # Get all similar artists using our existing working method (gets all 50)
            try:
                self.logger.info(f"Fetching all similar artists for artist {artist_id}")
                # Use the existing get_similar_artists method that already works with /similar command
                similar_artists = await self.get_similar_artists(artist_id, limit=50)

                if similar_artists:
                    self.logger.info(f"Got {len(similar_artists)} similar artists")
                    for similar_artist in similar_artists:
                        artist_info['similar_artists'].append({
                            'id': similar_artist.id,
                            'name': similar_artist.name,
                            'track_count': similar_artist.track_count if hasattr(similar_artist, 'track_count') else 0
                        })
                    self.logger.info(f"Added all {len(artist_info['similar_artists'])} similar artists to artist_info")
                else:
                    self.logger.info("No similar artists found")

            except Exception as e:
                self.logger.warning(f"Could not fetch similar artists: {e}")
                # Fallback to brief_info if our method fails
                if brief_info and hasattr(brief_info, 'similar_artists') and brief_info.similar_artists:
                    self.logger.info(f"Falling back to brief_info with {len(brief_info.similar_artists)} similar artists")
                    for similar in brief_info.similar_artists:
                        if hasattr(similar, 'id') and hasattr(similar, 'name'):
                            artist_info['similar_artists'].append({
                                'id': str(similar.id),
                                'name': similar.name,
                                'track_count': getattr(similar.counts, 'tracks', 0) if hasattr(similar, 'counts') and similar.counts else 0
                            })
                    self.logger.info(f"Added {len(artist_info['similar_artists'])} similar artists from brief_info")

            # Extract other brief info data
            if brief_info:

                # Popular tracks
                if hasattr(brief_info, 'popular_tracks') and brief_info.popular_tracks:
                    for track in brief_info.popular_tracks[:10]:  # Top 10
                        if hasattr(track, 'id') and hasattr(track, 'title'):
                            artist_info['popular_tracks'].append({
                                'id': str(track.id),
                                'title': track.title,
                                'duration_ms': getattr(track, 'duration_ms', 0) or 0
                            })

                # Albums
                if hasattr(brief_info, 'albums') and brief_info.albums:
                    for album in brief_info.albums[:10]:  # Top 10
                        if hasattr(album, 'id') and hasattr(album, 'title'):
                            artist_info['albums'].append({
                                'id': str(album.id),
                                'title': album.title,
                                'year': getattr(album, 'year', None),
                                'track_count': getattr(album, 'track_count', 0) or 0,
                                'genre': getattr(album, 'genre', None)
                            })

                # Videos
                if hasattr(brief_info, 'videos') and brief_info.videos:
                    for video in brief_info.videos[:10]:  # Top 10
                        if hasattr(video, 'title'):
                            artist_info['videos'].append({
                                'title': video.title,
                                'duration': getattr(video, 'duration', None)
                            })

                # Playlists
                if hasattr(brief_info, 'playlists') and brief_info.playlists:
                    for playlist in brief_info.playlists[:5]:  # Top 5
                        if hasattr(playlist, 'title'):
                            artist_info['playlists'].append({
                                'title': playlist.title,
                                'description': getattr(playlist, 'description', None)
                            })

                # Concerts
                if hasattr(brief_info, 'concerts') and brief_info.concerts:
                    for concert in brief_info.concerts[:5]:  # Top 5
                        artist_info['concerts'].append({
                            'title': getattr(concert, 'title', None),
                            'date': getattr(concert, 'date', None),
                            'city': getattr(concert, 'city', None)
                        })

            if self.cache:
                await self.cache.set(cache_key, artist_info, ttl_seconds=3600)

            return artist_info

        except Exception as e:
            self.logger.error(f"Error getting full artist info for {artist_id}: {e}")
            raise ServiceError(f"Failed to get artist info: {e}", "yandex_music")

    async def get_track_full_info(self, track_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive track information with all available data."""
        if not self.client:
            raise ServiceError("Client not initialized", "yandex_music")

        cache_key = f"track_full_info:{track_id}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        try:
            # Get track info
            tracks_result = await asyncio.to_thread(self.client.tracks, [track_id])
            if not tracks_result or len(tracks_result) == 0:
                return None

            ya_track = tracks_result[0]

            # Extract all available information
            track_info = {
                # Basic info
                'id': str(ya_track.id),
                'track_id': getattr(ya_track, 'track_id', str(ya_track.id)),
                'real_id': getattr(ya_track, 'real_id', str(ya_track.id)),
                'title': ya_track.title or "Unknown Title",
                'available': getattr(ya_track, 'available', True),
                'available_for_premium_users': getattr(ya_track, 'available_for_premium_users', True),
                'available_full_without_permission': getattr(ya_track, 'available_full_without_permission', False),

                # Duration and file info
                'duration_ms': getattr(ya_track, 'duration_ms', 0) or 0,
                'preview_duration_ms': getattr(ya_track, 'preview_duration_ms', 0) or 0,
                'file_size': getattr(ya_track, 'file_size', 0) or 0,
                'storage_dir': getattr(ya_track, 'storage_dir', None),

                # Content flags
                'explicit': getattr(ya_track, 'explicit', False),
                'is_suitable_for_children': getattr(ya_track, 'is_suitable_for_children', None),
                'lyrics_available': getattr(ya_track, 'lyrics_available', False),
                'remember_position': getattr(ya_track, 'remember_position', False),

                # Media
                'cover_uri': getattr(ya_track, 'cover_uri', None),
                'og_image': getattr(ya_track, 'og_image', None),

                # Additional metadata
                'track_sharing_flag': getattr(ya_track, 'track_sharing_flag', None),
                'track_source': getattr(ya_track, 'track_source', None),
                'type': getattr(ya_track, 'type', 'music'),
                'regions': getattr(ya_track, 'regions', None),
                'version': getattr(ya_track, 'version', None),

                # Related objects
                'artists': [],
                'albums': [],
                'download_formats': [],
                'lyrics_info': {},
                'major': {},
                'normalization': {},
                'r128': {}
            }

            # Extract artists
            if hasattr(ya_track, 'artists') and ya_track.artists:
                for artist in ya_track.artists:
                    if hasattr(artist, 'id') and hasattr(artist, 'name'):
                        artist_data = {
                            'id': str(artist.id),
                            'name': artist.name,
                            'has_cover': hasattr(artist, 'cover') and artist.cover is not None
                        }
                        track_info['artists'].append(artist_data)

            # Extract albums
            if hasattr(ya_track, 'albums') and ya_track.albums:
                for album in ya_track.albums:
                    if hasattr(album, 'id') and hasattr(album, 'title'):
                        album_data = {
                            'id': str(album.id),
                            'title': album.title,
                            'year': getattr(album, 'year', None),
                            'genre': getattr(album, 'genre', None),
                            'track_count': getattr(album, 'track_count', 0) or 0,
                            'track_position': getattr(album, 'track_position', None)
                        }
                        track_info['albums'].append(album_data)

            # Extract download info
            try:
                download_info = await asyncio.to_thread(ya_track.get_download_info)
                if download_info:
                    for info in download_info:
                        format_data = {
                            'codec': getattr(info, 'codec', None),
                            'bitrate_in_kbps': getattr(info, 'bitrate_in_kbps', 0),
                            'gain': getattr(info, 'gain', False),
                            'preview': getattr(info, 'preview', False)
                        }
                        track_info['download_formats'].append(format_data)
            except Exception as e:
                self.logger.debug(f"Could not get download info for track {track_id}: {e}")

            # Extract lyrics info
            if hasattr(ya_track, 'lyrics_info') and ya_track.lyrics_info:
                lyrics = ya_track.lyrics_info
                track_info['lyrics_info'] = {
                    'has_lyrics': getattr(lyrics, 'has_lyrics', False),
                    'show_translation': getattr(lyrics, 'show_translation', False)
                }

            # Extract major label info
            if hasattr(ya_track, 'major') and ya_track.major:
                major = ya_track.major
                track_info['major'] = {
                    'id': getattr(major, 'id', None),
                    'name': getattr(major, 'name', None)
                }

            # Extract normalization data
            if hasattr(ya_track, 'normalization') and ya_track.normalization:
                norm = ya_track.normalization
                track_info['normalization'] = {
                    'gain': getattr(norm, 'gain', None),
                    'peak': getattr(norm, 'peak', None)
                }

            # Extract R128 data
            if hasattr(ya_track, 'r128') and ya_track.r128:
                r128 = ya_track.r128
                track_info['r128'] = {
                    'i': getattr(r128, 'i', None),
                    'tp': getattr(r128, 'tp', None)
                }

            if self.cache:
                await self.cache.set(cache_key, track_info, ttl_seconds=3600)

            return track_info

        except Exception as e:
            self.logger.error(f"Error getting full track info for {track_id}: {e}")
            raise ServiceError(f"Failed to get track info: {e}", "yandex_music")

    async def download_artist_photo(self, artist_id: str, size: str = '300x300') -> Optional[bytes]:
        """Download artist photo bytes."""
        if not self.client:
            raise ServiceError("Client not initialized", "yandex_music")

        try:
            # Get the artist object
            artists_result = await asyncio.to_thread(self.client.artists, artist_id)
            if not artists_result or len(artists_result) == 0:
                return None

            ya_artist = artists_result[0]

            # Check if artist has an image
            if not hasattr(ya_artist, 'og_image') or not ya_artist.og_image:
                return None

            # Download the image
            photo_bytes = await asyncio.to_thread(ya_artist.download_og_image_bytes, size)
            return photo_bytes

        except Exception as e:
            self.logger.warning(f"Error downloading artist photo for {artist_id}: {e}")
            return None