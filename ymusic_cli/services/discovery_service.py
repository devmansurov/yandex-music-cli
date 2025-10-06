"""Artist discovery service for recursive and similar artist functionality."""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional, Set, Dict, Any
from collections import defaultdict

from ymusic_cli.core.interfaces import DiscoveryService, MusicService, CacheService
from ymusic_cli.core.models import Artist, DownloadOptions, DiscoveryResult
from ymusic_cli.core.exceptions import ServiceError, NotFoundError
from ymusic_cli.config.settings import get_settings
from ymusic_cli.utils.language_detector import detect_artist_language


class ArtistDiscoveryService(DiscoveryService):
    """Service for discovering similar and related artists."""
    
    def __init__(
        self,
        music_service: MusicService,
        cache_service: Optional[CacheService] = None
    ):
        self.music_service = music_service
        self.cache = cache_service
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
    
    async def discover_similar_artists(
        self,
        artist_id: str,
        options: DownloadOptions
    ) -> DiscoveryResult:
        """Discover similar artists with filtering."""
        start_time = time.time()
        
        try:
            # Get base artist info
            base_artist = await self.music_service.get_artist(artist_id)
            if not base_artist:
                raise NotFoundError(f"Artist {artist_id} not found", "artist")
            
            self.logger.info(f"Discovering similar artists for: {base_artist.name}")
            
            # Get similar artists
            self.logger.info(f"Calling music_service.get_similar_artists with limit={options.similar_limit}")
            similar_artists = await self.music_service.get_similar_artists(
                artist_id,
                limit=options.similar_limit
            )
            
            self.logger.info(f"Music service returned {len(similar_artists)} similar artists")
            
            # Apply country filtering if specified
            if options.similar_country_filter:
                self.logger.info(f"Applying country filter: {options.similar_country_filter}")
                similar_artists = await self._apply_country_filter(
                    similar_artists,
                    base_artist,
                    options.similar_country_filter
                )
                self.logger.info(f"After country filtering: {len(similar_artists)} artists")
            
            # Apply priority countries
            if options.priority_countries:
                self.logger.info(f"Applying priority countries: {options.priority_countries}")
                similar_artists = await self._apply_priority_countries(
                    similar_artists,
                    options.priority_countries
                )
                self.logger.info(f"After priority countries: {len(similar_artists)} artists")
            
            # Filter by minimum track count
            self.logger.info(f"Filtering by minimum track count: {options.min_tracks_per_artist}")
            filtered_artists = []
            for artist in similar_artists:
                self.logger.debug(f"Artist {artist.name}: {artist.track_count} tracks (min required: {options.min_tracks_per_artist})")
                if artist.track_count >= options.min_tracks_per_artist:
                    filtered_artists.append(artist)
                    self.logger.debug(f"  ✓ Added {artist.name}")
                else:
                    self.logger.debug(f"  ✗ Filtered out {artist.name} (insufficient tracks)")
            
            self.logger.info(f"After track count filtering: {len(filtered_artists)} artists")
            
            discovery_time = time.time() - start_time
            
            # Create discovery result
            result = DiscoveryResult(
                base_artist=base_artist,
                discovered_artists=filtered_artists,
                discovery_tree={artist_id: [a.id for a in filtered_artists]},
                total_discovered=len(filtered_artists) + 1,  # +1 for base artist
                max_depth_reached=1,
                countries_found=set(a.country for a in filtered_artists if a.country),
                discovery_time_seconds=discovery_time,
                discovery_params={
                    'similar_limit': options.similar_limit,
                    'similar_country_filter': options.similar_country_filter,
                    'min_tracks_per_artist': options.min_tracks_per_artist,
                    'priority_countries': options.priority_countries
                }
            )
            
            self.logger.info(
                f"Discovered {len(filtered_artists)} similar artists for {base_artist.name} "
                f"in {discovery_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error discovering similar artists for {artist_id}: {e}")
            raise ServiceError(f"Discovery failed: {e}", "discovery")
    
    async def discover_recursive(
        self,
        artist_id: str,
        options: DownloadOptions,
        progress_callback: Optional[callable] = None
    ) -> DiscoveryResult:
        """Discover artists recursively with progress updates."""
        start_time = time.time()
        
        try:
            # Get base artist info
            base_artist = await self.music_service.get_artist(artist_id)
            if not base_artist:
                raise NotFoundError(f"Artist {artist_id} not found", "artist")
            
            self.logger.info(
                f"Starting recursive discovery for: {base_artist.name} "
                f"(depth={options.max_depth}, max_artists={options.max_total_artists})"
            )
            
            # Initialize discovery state
            discovered_artists: Dict[str, Artist] = {artist_id: base_artist}
            visited_artists: Set[str] = {artist_id}
            discovery_tree: Dict[str, List[str]] = {artist_id: []}
            countries_found: Set[str] = set()
            
            if base_artist.country:
                countries_found.add(base_artist.country)
            
            # Start recursive discovery
            current_level = [artist_id]
            
            for depth in range(1, options.max_depth + 1):
                if len(discovered_artists) >= options.max_total_artists:
                    self.logger.info(f"Reached maximum artist limit ({options.max_total_artists})")
                    break
                
                if not current_level:
                    self.logger.info(f"No more artists to discover at depth {depth}")
                    break
                
                self.logger.info(
                    f"Processing level {depth}/{options.max_depth}: {len(current_level)} artists"
                )
                
                next_level = []
                level_added = 0
                level_skipped = 0

                for i, current_artist_id in enumerate(current_level):
                    if len(discovered_artists) >= options.max_total_artists:
                        break

                    current_artist = discovered_artists[current_artist_id]

                    # Log progress for current artist at this level
                    self.logger.info(
                        f"  [{i + 1}/{len(current_level)}] Checking similar artists for: {current_artist.name}"
                    )

                    # Send progress update
                    if progress_callback:
                        await progress_callback({
                            'type': 'discovery',
                            'current_depth': depth,
                            'max_depth': options.max_depth,
                            'current_artist': current_artist.name,
                            'discovered_count': len(discovered_artists),
                            'target_count': options.max_total_artists,
                            'level_progress': f"{i + 1}/{len(current_level)}"
                        })

                    # Get similar artists for current artist
                    try:
                        similar_artists = await self.music_service.get_similar_artists(
                            current_artist_id,
                            limit=50  # Get more to have better selection
                        )

                        # Filter and select candidates
                        candidates = await self._select_discovery_candidates(
                            similar_artists,
                            visited_artists,
                            options,
                            depth
                        )

                        # Add selected candidates with year filtering if enabled
                        selected_candidates = []
                        candidates_checked = 0
                        max_attempts = options.max_similar_artist_attempts if options.enable_year_filtering_for_discovery else options.similar_limit

                        for candidate in candidates:
                            if len(discovered_artists) >= options.max_total_artists:
                                break

                            if len(selected_candidates) >= options.similar_limit:
                                break

                            # If year filtering is enabled, check if artist has content in year range
                            if options.enable_year_filtering_for_discovery and options.years:
                                candidates_checked += 1
                                if candidates_checked > max_attempts:
                                    self.logger.debug(
                                        f"Reached max attempts ({max_attempts}) for {current_artist.name}"
                                    )
                                    break

                                has_content = await self.music_service.check_artist_has_content_in_years(
                                    candidate.id, options.years
                                )

                                if not has_content:
                                    self.logger.debug(
                                        f"✗ Skipping {candidate.name} - no content in "
                                        f"{options.years[0]}-{options.years[1]}, checking next similar artist"
                                    )
                                    level_skipped += 1
                                    continue  # Try next similar artist

                            # Artist passed filters, add to selected
                            candidate.depth = depth
                            candidate.discovered_from = current_artist_id
                            discovered_artists[candidate.id] = candidate
                            visited_artists.add(candidate.id)
                            next_level.append(candidate.id)
                            selected_candidates.append(candidate)
                            level_added += 1

                            if candidate.country:
                                countries_found.add(candidate.country)

                        # Update discovery tree
                        discovery_tree[current_artist_id] = [c.id for c in selected_candidates]

                        # Log progress summary for this artist
                        if options.years:
                            skipped_count = candidates_checked - len(selected_candidates) if options.enable_year_filtering_for_discovery else 0
                            self.logger.info(
                                f"    → Added {len(selected_candidates)} artists, "
                                f"skipped {skipped_count} (checked {candidates_checked} total)"
                            )
                        else:
                            self.logger.debug(f"Added {len(selected_candidates)} artists from {current_artist.name}")
                        
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to get similar artists for {current_artist.name}: {e}"
                        )
                        continue
                
                current_level = next_level

                # Enhanced summary with skip count
                if options.years:
                    self.logger.info(
                        f"Level {depth} complete: Added {level_added} artists, "
                        f"Skipped {level_skipped} (no year content), "
                        f"Total: {len(discovered_artists)} artists"
                    )
                else:
                    self.logger.info(
                        f"Level {depth} complete: {len(discovered_artists)} total artists, "
                        f"{len(next_level)} for next level"
                    )
            
            discovery_time = time.time() - start_time
            max_depth_reached = max(a.depth for a in discovered_artists.values())
            
            # Create discovery result
            result = DiscoveryResult(
                base_artist=base_artist,
                discovered_artists=list(discovered_artists.values()),
                discovery_tree=discovery_tree,
                total_discovered=len(discovered_artists),
                max_depth_reached=max_depth_reached,
                countries_found=countries_found,
                discovery_time_seconds=discovery_time,
                discovery_params={
                    'max_depth': options.max_depth,
                    'max_total_artists': options.max_total_artists,
                    'similar_limit': options.similar_limit,
                    'priority_countries': options.priority_countries,
                    'exclude_artists': list(options.exclude_artists)
                }
            )
            
            self.logger.info(
                f"Recursive discovery complete: {len(discovered_artists)} artists "
                f"(max depth {max_depth_reached}) in {discovery_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in recursive discovery for {artist_id}: {e}")
            raise ServiceError(f"Recursive discovery failed: {e}", "discovery")
    
    # Helper methods
    
    async def _apply_country_filter(
        self,
        artists: List[Artist],
        base_artist: Artist,
        country_filter: str
    ) -> List[Artist]:
        """Apply country filtering to artists."""
        if country_filter.lower() == 'same':
            # Filter by base artist's country
            if not base_artist.country:
                self.logger.warning("Base artist has no country, no filtering applied")
                return artists
            
            target_country = base_artist.country
            return [a for a in artists if a.country == target_country]
        
        else:
            # Filter by specified countries
            target_countries = set(c.strip().upper() for c in country_filter.split(','))
            return [a for a in artists if a.country in target_countries]
    
    async def _apply_priority_countries(
        self,
        artists: List[Artist],
        priority_countries: List[str]
    ) -> List[Artist]:
        """Sort artists by priority countries."""
        if not priority_countries:
            return artists
        
        priority_set = set(c.upper() for c in priority_countries)
        
        # Separate priority and non-priority artists
        priority_artists = [a for a in artists if a.country in priority_set]
        other_artists = [a for a in artists if a.country not in priority_set]
        
        # Return priority artists first
        return priority_artists + other_artists
    
    async def _select_discovery_candidates(
        self,
        similar_artists: List[Artist],
        visited_artists: Set[str],
        options: DownloadOptions,
        current_depth: int
    ) -> List[Artist]:
        """Select the best candidates for discovery."""
        candidates = []
        
        for artist in similar_artists:
            # Skip if already visited or excluded
            if (artist.id in visited_artists or 
                artist.id in options.exclude_artists):
                continue
            
            # Skip if insufficient track count
            if artist.track_count < options.min_tracks_per_artist:
                continue
            
            candidates.append(artist)
        
        # Apply priority country sorting
        if options.priority_countries:
            candidates = await self._apply_priority_countries(
                candidates,
                options.priority_countries
            )
        
        # Sort by similarity score and track count
        candidates.sort(
            key=lambda a: (a.similarity_score or 0, a.track_count),
            reverse=True
        )

        return candidates

    async def _process_artists_batch(
        self,
        artist_ids: List[str],
        years: Optional[tuple[int, int]] = None,
        similar_limit: int = 50,
        visited_artists: Set[str] = None,
        depth: int = 1
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Process a batch of artists concurrently for discovery.

        Returns:
            tuple: (included_artists, filtered_out_artists)
        """
        if visited_artists is None:
            visited_artists = set()

        # Create semaphore to limit concurrent operations (reduced to avoid API rate limiting)
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent operations to avoid overwhelming API

        async def process_single_artist(artist_id: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            async with semaphore:
                try:
                    # Get similar artists
                    similar_artists = await self.music_service.get_similar_artists(
                        artist_id, limit=similar_limit
                    )

                    included_results = []
                    filtered_results = []

                    # Process similar artists with concurrent year filtering if needed
                    if years:
                        # Batch year filtering for better performance
                        year_check_tasks = []
                        for artist in similar_artists:
                            if artist.id not in visited_artists:
                                task = self._artist_has_content_in_years(artist.id, years)
                                year_check_tasks.append((artist, task))

                        # Execute year checks concurrently
                        if year_check_tasks:
                            artists_to_check = [item[0] for item in year_check_tasks]
                            tasks = [item[1] for item in year_check_tasks]
                            year_results = await asyncio.gather(*tasks, return_exceptions=True)

                            for artist, has_content in zip(artists_to_check, year_results):
                                artist_data = {
                                    "id": artist.id,
                                    "name": artist.name,
                                    "depth": depth,
                                    "discovered_from": artist_id,
                                    "country": artist.country,
                                    "url": f"https://music.yandex.ru/artist/{artist.id}"
                                }

                                if isinstance(has_content, bool) and has_content:
                                    included_results.append(artist_data)
                                else:
                                    # Track filtered out artist with reason
                                    filtered_data = artist_data.copy()
                                    filtered_data["reason"] = f"no_content_in_years_{years[0]}-{years[1]}"
                                    filtered_results.append(filtered_data)
                    else:
                        # No year filtering needed
                        for artist in similar_artists:
                            if artist.id not in visited_artists:
                                included_results.append({
                                    "id": artist.id,
                                    "name": artist.name,
                                    "depth": depth,
                                    "discovered_from": artist_id,
                                    "country": artist.country,
                                    "url": f"https://music.yandex.ru/artist/{artist.id}"
                                })

                    return (included_results, filtered_results)

                except Exception as e:
                    self.logger.warning(f"Failed to process artist {artist_id}: {e}")
                    return ([], [])

        # Execute all artist processing tasks concurrently
        batch_tasks = [process_single_artist(artist_id) for artist_id in artist_ids]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Flatten results
        all_included = []
        all_filtered = []
        for result in batch_results:
            if isinstance(result, tuple) and len(result) == 2:
                included, filtered = result
                if isinstance(included, list):
                    all_included.extend(included)
                if isinstance(filtered, list):
                    all_filtered.extend(filtered)

        return (all_included, all_filtered)

    async def _artist_has_content_in_years(
        self,
        artist_id: str,
        years: tuple[int, int]
    ) -> bool:
        """Check if an artist has tracks/albums in the specified year range."""
        try:
            # Use the optimized lightweight check method if available
            if hasattr(self.music_service, 'check_artist_has_content_in_years'):
                return await self.music_service.check_artist_has_content_in_years(artist_id, years)

            # Fallback to the original method if optimized version not available
            from ..core.models import DownloadOptions

            options = DownloadOptions(
                years=years,
                top_n=1  # Just need to check if any tracks exist
            )

            tracks = await self.music_service.get_artist_tracks(artist_id, options)
            return len(tracks) > 0

        except Exception as e:
            self.logger.debug(f"Could not check year filter for artist {artist_id}: {e}")
            # If we can't check, include the artist to avoid filtering out valid results
            return True

    async def build_artist_tree(
        self,
        artist_id: str,
        max_depth: int = 999,
        similar_limit: int = 50,
        years: Optional[tuple[int, int]] = None,
        shuffle: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Build a complete artist tree for JSON export.

        Args:
            artist_id: Base artist ID
            max_depth: Maximum depth to traverse (default 999 for unlimited)
            similar_limit: Maximum similar artists per artist
            years: Optional year range filter (start_year, end_year)
            shuffle: Whether to shuffle the final artist list
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with tree structure for JSON export
        """
        start_time = time.time()

        try:
            # Get base artist info
            base_artist = await self.music_service.get_artist(artist_id)
            if not base_artist:
                raise NotFoundError(f"Artist {artist_id} not found", "artist")

            self.logger.info(
                f"Building artist tree for: {base_artist.name} "
                f"(depth={max_depth}, limit={similar_limit})"
            )

            # Initialize discovery state
            unique_artists = []
            filtered_artists = []
            visited_artists = {artist_id}
            artist_map = {}

            # Add base artist
            base_artist_data = {
                "id": artist_id,
                "name": base_artist.name,
                "depth": 0,
                "discovered_from": None,
                "country": base_artist.country,
                "url": f"https://music.yandex.ru/artist/{artist_id}"
            }
            unique_artists.append(base_artist_data)
            artist_map[artist_id] = base_artist_data

            # Start recursive discovery
            current_level = [artist_id]

            for depth in range(1, max_depth + 1):
                if not current_level:
                    self.logger.info(f"No more artists to discover at depth {depth}")
                    break

                self.logger.info(
                    f"Processing level {depth}/{max_depth}: {len(current_level)} artists"
                )

                next_level = []

                for i, current_artist_id in enumerate(current_level):
                    # Send progress update
                    if progress_callback:
                        await progress_callback({
                            'type': 'tree_discovery',
                            'current_depth': depth,
                            'max_depth': max_depth,
                            'discovered_count': len(unique_artists),
                            'level_progress': f"{i + 1}/{len(current_level)}"
                        })

                    # Get similar artists for current artist
                    try:
                        similar_artists = await self.music_service.get_similar_artists(
                            current_artist_id,
                            limit=similar_limit
                        )

                        for artist in similar_artists:
                            if artist.id not in visited_artists:
                                artist_data = {
                                    "id": artist.id,
                                    "name": artist.name,
                                    "depth": depth,
                                    "discovered_from": current_artist_id,
                                    "country": artist.country,
                                    "url": f"https://music.yandex.ru/artist/{artist.id}"
                                }

                                # Apply year filter if specified
                                if years:
                                    has_content_in_years = await self._artist_has_content_in_years(
                                        artist.id, years
                                    )
                                    if not has_content_in_years:
                                        # Track filtered out artist with reason
                                        filtered_data = artist_data.copy()
                                        filtered_data["reason"] = f"no_content_in_years_{years[0]}-{years[1]}"
                                        filtered_artists.append(filtered_data)
                                        continue

                                visited_artists.add(artist.id)
                                unique_artists.append(artist_data)
                                artist_map[artist.id] = artist_data
                                next_level.append(artist.id)

                        self.logger.debug(
                            f"Added {len(similar_artists)} artists from ID {current_artist_id}"
                        )

                    except Exception as e:
                        self.logger.warning(
                            f"Failed to get similar artists for {current_artist_id}: {e}"
                        )
                        continue

                current_level = next_level

                self.logger.info(
                    f"Level {depth} complete: {len(unique_artists)} total artists, "
                    f"{len(next_level)} for next level"
                )

            discovery_time = time.time() - start_time
            max_depth_reached = max(a["depth"] for a in unique_artists)

            # Apply shuffle if requested
            if shuffle:
                import random
                # Shuffle the list but keep the base artist first
                base_artist_data = unique_artists[0]  # First is always the base artist
                rest_artists = unique_artists[1:]
                random.shuffle(rest_artists)
                unique_artists = [base_artist_data] + rest_artists

            # Perform language detection for statistics
            self.logger.info("Analyzing language distribution...")
            language_stats = await self._analyze_language_distribution(unique_artists)

            # Build result structure
            result = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "script_version": "telegram_bot_tree_command",
                    "base_artist": {
                        "id": artist_id,
                        "name": base_artist.name,
                        "url": f"https://music.yandex.ru/artist/{artist_id}"
                    },
                    "filters": {
                        "years": f"{years[0]}-{years[1]}" if years else None,
                        "shuffled": shuffle
                    }
                },
                "stats": {
                    "total_artists_discovered": len(unique_artists) + len(filtered_artists),
                    "filtered_artists_count": len(unique_artists),
                    "filtered_out_count": len(filtered_artists),
                    "max_depth_reached": max_depth_reached,
                    "max_depth_requested": max_depth,
                    "similar_limit_per_artist": similar_limit,
                    "discovery_time_seconds": discovery_time,
                    "year_filter_applied": years is not None,
                    "language_distribution": language_stats
                },
                "unique_artists": unique_artists,
                "filtered_out_artists": filtered_artists
            }

            self.logger.info(
                f"Artist tree complete: {len(unique_artists)} artists "
                f"(max depth {max_depth_reached}) in {discovery_time:.2f}s"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error building artist tree for {artist_id}: {e}")
            raise ServiceError(f"Tree building failed: {e}", "discovery")

    async def build_multi_artist_tree(
        self,
        artist_ids: List[str],
        max_depth: int = 999,
        similar_limit: int = 50,
        years: Optional[tuple[int, int]] = None,
        shuffle: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Build a combined artist tree from multiple base artists with concurrent processing.

        Args:
            artist_ids: List of base artist IDs
            max_depth: Maximum depth to traverse (default 999 for unlimited)
            similar_limit: Maximum similar artists per artist
            years: Optional year range filter (start_year, end_year)
            shuffle: Whether to shuffle the final artist list
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with combined tree structure for JSON export
        """
        start_time = time.time()

        try:
            # Get all base artists info concurrently
            base_artist_tasks = [self.music_service.get_artist(artist_id) for artist_id in artist_ids]
            base_artists_results = await asyncio.gather(*base_artist_tasks, return_exceptions=True)

            base_artists = []
            for i, result in enumerate(base_artists_results):
                if isinstance(result, Exception):
                    raise NotFoundError(f"Artist {artist_ids[i]} not found", "artist")
                if not result:
                    raise NotFoundError(f"Artist {artist_ids[i]} not found", "artist")
                base_artists.append(result)

            self.logger.info(
                f"Building optimized multi-artist tree for {len(artist_ids)} artists: "
                f"{[a.name for a in base_artists]} "
                f"(depth={max_depth}, limit={similar_limit})"
            )

            # Initialize combined discovery state
            all_unique_artists = []
            all_filtered_artists = []
            global_visited_artists = set()
            combined_artist_map = {}

            # Add base artists
            for artist_id, base_artist in zip(artist_ids, base_artists):
                base_artist_data = {
                    "id": artist_id,
                    "name": base_artist.name,
                    "depth": 0,
                    "discovered_from": None,
                    "country": base_artist.country,
                    "url": f"https://music.yandex.ru/artist/{artist_id}"
                }
                all_unique_artists.append(base_artist_data)
                combined_artist_map[artist_id] = base_artist_data
                global_visited_artists.add(artist_id)

            # Start recursive discovery with concurrent processing
            current_level = artist_ids.copy()

            for depth in range(1, max_depth + 1):
                if not current_level:
                    self.logger.info(f"No more artists to discover at depth {depth}")
                    break

                self.logger.info(
                    f"Processing level {depth}/{max_depth}: {len(current_level)} artists concurrently"
                )

                if progress_callback:
                    await progress_callback({
                        'type': 'concurrent_multi_tree_discovery',
                        'current_depth': depth,
                        'max_depth': max_depth,
                        'discovered_count': len(all_unique_artists),
                        'level_size': len(current_level)
                    })

                # Process current level artists in batches concurrently
                batch_size = 10  # Process 10 artists at a time
                next_level = []

                for i in range(0, len(current_level), batch_size):
                    batch_artists = current_level[i:i + batch_size]

                    # Process batch concurrently
                    batch_included, batch_filtered = await self._process_artists_batch(
                        artist_ids=batch_artists,
                        years=years,
                        similar_limit=similar_limit,
                        visited_artists=global_visited_artists,
                        depth=depth
                    )

                    # Add discovered artists, avoiding duplicates
                    for artist_data in batch_included:
                        if artist_data['id'] not in global_visited_artists:
                            global_visited_artists.add(artist_data['id'])
                            combined_artist_map[artist_data['id']] = artist_data
                            all_unique_artists.append(artist_data)
                            next_level.append(artist_data['id'])

                    # Track filtered out artists (always add them to get full picture)
                    all_filtered_artists.extend(batch_filtered)

                    self.logger.debug(f"Batch {i//batch_size + 1}: added {len(batch_included)} new artists, filtered {len(batch_filtered)} artists")

                    # Add small delay between batches to avoid overwhelming the API
                    if i + batch_size < len(current_level):
                        await asyncio.sleep(0.5)

                current_level = next_level

                self.logger.info(
                    f"Level {depth} complete: {len(all_unique_artists)} total artists, "
                    f"{len(next_level)} for next level"
                )

            discovery_time = time.time() - start_time
            max_depth_reached = max(a["depth"] for a in all_unique_artists) if all_unique_artists else 0

            # Apply shuffle if requested
            if shuffle:
                import random
                # Separate base artists from discovered artists
                base_artist_data = [a for a in all_unique_artists if a['id'] in artist_ids]
                discovered_artists = [a for a in all_unique_artists if a['id'] not in artist_ids]
                random.shuffle(discovered_artists)
                all_unique_artists = base_artist_data + discovered_artists

            # Perform language detection for statistics
            self.logger.info("Analyzing language distribution...")
            language_stats = await self._analyze_language_distribution(all_unique_artists)

            # Build combined result structure
            result = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "script_version": "telegram_bot_optimized_multi_tree_command",
                    "base_artists": [
                        {
                            "id": artist.id,
                            "name": artist.name,
                            "url": f"https://music.yandex.ru/artist/{artist.id}"
                        }
                        for artist in base_artists
                    ],
                    "filters": {
                        "years": f"{years[0]}-{years[1]}" if years else None,
                        "shuffled": shuffle
                    }
                },
                "stats": {
                    "total_artists_discovered": len(all_unique_artists) + len(all_filtered_artists),
                    "filtered_artists_count": len(all_unique_artists),
                    "filtered_out_count": len(all_filtered_artists),
                    "base_artist_count": len(artist_ids),
                    "max_depth_reached": max_depth_reached,
                    "max_depth_requested": max_depth,
                    "similar_limit_per_artist": similar_limit,
                    "discovery_time_seconds": discovery_time,
                    "year_filter_applied": years is not None,
                    "optimization_enabled": True,
                    "language_distribution": language_stats
                },
                "unique_artists": all_unique_artists,
                "filtered_out_artists": all_filtered_artists
            }

            self.logger.info(
                f"Optimized multi-artist tree complete: {len(all_unique_artists)} total artists "
                f"from {len(artist_ids)} base artists "
                f"(max depth {max_depth_reached}) in {discovery_time:.2f}s"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error building optimized multi-artist tree: {e}")
            raise ServiceError(f"Multi-artist tree building failed: {e}", "discovery")

    async def _analyze_language_distribution(self, artists: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze language and country distribution among discovered artists."""
        try:
            country_counts = defaultdict(int)
            language_counts = defaultdict(int)
            detection_method_counts = defaultdict(int)
            successful_detections = 0
            total_artists = len(artists)

            # Sample artists for analysis (to avoid hitting API limits on large trees)
            max_sample_size = 100
            if len(artists) > max_sample_size:
                import random
                sample_artists = random.sample(artists, max_sample_size)
                self.logger.info(f"Analyzing language distribution on sample of {max_sample_size} artists")
            else:
                sample_artists = artists

            # Analyze each artist
            for artist_data in sample_artists:
                try:
                    # Get full artist information for language detection
                    artist = await self.music_service.get_artist(artist_data['id'])
                    if not artist:
                        continue

                    # Get some popular tracks for title analysis (if available)
                    track_titles = []
                    if hasattr(artist, 'popular_tracks') and artist.popular_tracks:
                        track_titles = [track.title for track in artist.popular_tracks[:5]
                                      if hasattr(track, 'title') and track.title]

                    # Perform language detection
                    detection = detect_artist_language(
                        artist_name=artist.name,
                        genres=getattr(artist, 'genres', []) or [],
                        track_titles=track_titles
                    )

                    # Count results if confident enough
                    if detection.confidence >= 0.5:  # Only count confident detections
                        successful_detections += 1
                        if detection.country_code:
                            country_counts[detection.country_name or detection.country_code] += 1
                        if detection.language_code:
                            language_counts[detection.language_name or detection.language_code] += 1
                        detection_method_counts[detection.detection_method] += 1

                except Exception as e:
                    self.logger.debug(f"Failed to analyze artist {artist_data.get('name', 'unknown')}: {e}")
                    continue

            # Calculate statistics
            confidence_rate = (successful_detections / len(sample_artists)) * 100 if sample_artists else 0

            # Sort by count and take top entries
            top_countries = dict(sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:10])
            top_languages = dict(sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:10])

            return {
                "total_artists_analyzed": len(sample_artists),
                "successful_detections": successful_detections,
                "confidence_rate_percent": round(confidence_rate, 1),
                "countries": top_countries,
                "languages": top_languages,
                "detection_methods": dict(detection_method_counts),
                "sample_size": len(sample_artists),
                "is_sampled": len(artists) > max_sample_size
            }

        except Exception as e:
            self.logger.error(f"Error analyzing language distribution: {e}")
            return {
                "error": "Language analysis failed",
                "total_artists_analyzed": 0,
                "successful_detections": 0,
                "confidence_rate_percent": 0.0,
                "countries": {},
                "languages": {},
                "detection_methods": {},
                "sample_size": 0,
                "is_sampled": False
            }

    async def _get_artist_stats(self, artists: List[Artist]) -> Dict[str, Any]:
        """Get statistics about discovered artists."""
        if not artists:
            return {}

        # Country distribution
        country_counts = defaultdict(int)
        for artist in artists:
            if artist.country:
                country_counts[artist.country] += 1
        
        # Depth distribution
        depth_counts = defaultdict(int)
        for artist in artists:
            depth_counts[artist.depth] += 1
        
        # Track count statistics
        track_counts = [a.track_count for a in artists if a.track_count > 0]
        
        return {
            'total_artists': len(artists),
            'countries': dict(country_counts),
            'depth_distribution': dict(depth_counts),
            'avg_track_count': sum(track_counts) / len(track_counts) if track_counts else 0,
            'total_tracks': sum(track_counts)
        }