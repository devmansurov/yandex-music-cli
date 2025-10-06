"""Track filtering utilities for Yandex Music tracks.

This module provides filtering functionality for music tracks based on various criteria
such as year, country, genre, and explicit content.

Following SOLID principles:
- Single Responsibility: Handles only track filtering logic
- Open/Closed: Can be extended with new filters without modification
- Interface Segregation: Focused interface for filtering operations
- Dependency Inversion: Works with any track objects that follow Yandex Music structure
"""

import logging
from typing import List, Optional, Any


logger = logging.getLogger(__name__)


class TrackFilter:
    """Filter for music tracks based on various criteria.

    Provides filtering methods for tracks based on:
    - Release year or year range
    - Country/region
    - Genre
    - Explicit content flag
    """

    def apply_filters(self, tracks: List[Any], **kwargs) -> List[Any]:
        """Apply all specified filters to track list.

        Args:
            tracks: List of track objects from Yandex Music API
            **kwargs: Filter criteria:
                - years: str - Single year or year range (e.g., "2020" or "2018-2022")
                - countries: str - Comma-separated list of country codes
                - genres: str - Comma-separated list of genres
                - no_explicit: bool - Filter out explicit tracks

        Returns:
            Filtered list of tracks
        """
        filtered_tracks = tracks.copy()

        # Year filter
        years = kwargs.get('years')
        if years:
            filtered_tracks = self._filter_by_year(filtered_tracks, years)

        # Country filter
        countries = kwargs.get('countries')
        if countries:
            filtered_tracks = self._filter_by_country(filtered_tracks, countries)

        # Genre filter
        genres = kwargs.get('genres')
        if genres:
            filtered_tracks = self._filter_by_genre(filtered_tracks, genres)

        # Explicit content filter
        if kwargs.get('no_explicit'):
            filtered_tracks = self._filter_explicit(filtered_tracks)

        return filtered_tracks

    def _filter_by_year(self, tracks: List[Any], years: str) -> List[Any]:
        """Filter tracks by release year or year range.

        Args:
            tracks: List of track objects
            years: Year string (e.g., "2020" or "2018-2022")

        Returns:
            Filtered tracks matching the year criteria
        """
        try:
            if '-' in years:
                # Year range
                start_year, end_year = map(int, years.split('-'))
            else:
                # Single year
                start_year = end_year = int(years)

            filtered = []
            for track in tracks:
                track_year = self._get_track_year(track)
                if track_year and start_year <= track_year <= end_year:
                    filtered.append(track)

            logger.debug(f"Year filter ({years}): {len(filtered)}/{len(tracks)} tracks")
            return filtered

        except Exception as e:
            logger.error(f"Error applying year filter: {e}")
            return tracks

    def _filter_by_country(self, tracks: List[Any], countries: str) -> List[Any]:
        """Filter tracks by artist/album country.

        Args:
            tracks: List of track objects
            countries: Comma-separated list of country codes

        Returns:
            Filtered tracks from specified countries
        """
        country_list = [c.strip().upper() for c in countries.split(',')]

        filtered = []
        for track in tracks:
            if self._track_matches_countries(track, country_list):
                filtered.append(track)

        logger.info(f"Country filter ({countries}): {len(filtered)}/{len(tracks)} tracks")
        return filtered

    def _filter_by_genre(self, tracks: List[Any], genres: str) -> List[Any]:
        """Filter tracks by genre.

        Args:
            tracks: List of track objects
            genres: Comma-separated list of genres

        Returns:
            Filtered tracks matching specified genres
        """
        genre_list = [g.strip().lower() for g in genres.split(',')]

        filtered = []
        for track in tracks:
            track_genres = self._get_track_genres(track)
            if any(genre in track_genres for genre in genre_list):
                filtered.append(track)

        logger.info(f"Genre filter ({genres}): {len(filtered)}/{len(tracks)} tracks")
        return filtered

    def _filter_explicit(self, tracks: List[Any]) -> List[Any]:
        """Filter out explicit tracks.

        Args:
            tracks: List of track objects

        Returns:
            Tracks without explicit content
        """
        filtered = [track for track in tracks if not getattr(track, 'explicit', False)]
        logger.info(f"Explicit filter: {len(filtered)}/{len(tracks)} tracks")
        return filtered

    def _get_track_year(self, track) -> Optional[int]:
        """Extract year from track metadata.

        Args:
            track: Track object from Yandex Music API

        Returns:
            Release year or None if not found
        """
        try:
            # Try to get year from albums
            if hasattr(track, 'albums') and track.albums:
                for album in track.albums:
                    if hasattr(album, 'year') and album.year:
                        return album.year
                    if hasattr(album, 'release_date') and album.release_date:
                        return album.release_date.year

            # Try to get from meta_data
            if hasattr(track, 'meta_data') and track.meta_data:
                year = getattr(track.meta_data, 'year', None)
                if year:
                    return int(year)

            return None
        except:
            return None

    def _track_matches_countries(self, track, countries: List[str]) -> bool:
        """Check if track matches any of the specified countries.

        Args:
            track: Track object from Yandex Music API
            countries: List of country codes in uppercase

        Returns:
            True if track matches any country, False otherwise
        """
        try:
            # Check album regions
            if hasattr(track, 'albums') and track.albums:
                for album in track.albums:
                    if hasattr(album, 'regions') and album.regions:
                        for region in album.regions:
                            if region.upper() in countries:
                                return True

            # Check artists (if they have country info)
            if hasattr(track, 'artists') and track.artists:
                for artist in track.artists:
                    if hasattr(artist, 'countries') and artist.countries:
                        for country in artist.countries:
                            if country.upper() in countries:
                                return True

            # If no country info available, include the track
            return True

        except:
            return True

    def _get_track_genres(self, track) -> List[str]:
        """Get genres for a track.

        Args:
            track: Track object from Yandex Music API

        Returns:
            List of genre names in lowercase
        """
        genres = []
        try:
            if hasattr(track, 'albums') and track.albums:
                for album in track.albums:
                    if hasattr(album, 'genre') and album.genre:
                        genres.append(album.genre.lower())

            if hasattr(track, 'meta_data') and track.meta_data:
                genre = getattr(track.meta_data, 'genre', None)
                if genre:
                    genres.append(genre.lower())
        except:
            pass

        return genres
