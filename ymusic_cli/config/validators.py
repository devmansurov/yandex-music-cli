"""Input validation utilities for the bot."""

import re
from typing import List, Optional, Tuple, Union
from urllib.parse import urlparse, parse_qs

from core.exceptions import ValidationError


class CommandValidator:
    """Validates bot commands and parameters."""
    
    # Regex patterns
    ARTIST_ID_PATTERN = re.compile(r'^\d+$')
    YEAR_PATTERN = re.compile(r'^(\d{4})(-(\d{4}))?$')
    COUNTRY_PATTERN = re.compile(r'^[A-Z]{2}$')
    GENRE_PATTERN = re.compile(r'^[a-zA-Z\s\-]+$')
    QUALITY_PATTERN = re.compile(r'^(low|medium|high)$')
    
    # Yandex Music URL patterns
    YANDEX_ARTIST_URL = re.compile(r'https?://music\.yandex\.[a-z]{2,3}/artist/(\d+)')
    YANDEX_ALBUM_URL = re.compile(r'https?://music\.yandex\.[a-z]{2,3}/album/(\d+)')
    YANDEX_TRACK_URL = re.compile(r'https?://music\.yandex\.[a-z]{2,3}/album/(\d+)/track/(\d+)')

    @classmethod
    def validate_artist_id(cls, value: Union[str, int]) -> int:
        """Validate and extract artist ID from string or URL."""
        if isinstance(value, int):
            if value <= 0:
                raise ValidationError("Artist ID must be positive")
            return value
            
        value = str(value).strip()
        
        # Try to extract from Yandex Music URL
        url_match = cls.YANDEX_ARTIST_URL.match(value)
        if url_match:
            return int(url_match.group(1))
        
        # Validate as direct ID
        if not cls.ARTIST_ID_PATTERN.match(value):
            raise ValidationError(
                "Invalid artist ID. Use numeric ID or Yandex Music artist URL."
            )
        
        artist_id = int(value)
        if artist_id <= 0:
            raise ValidationError("Artist ID must be positive")
        
        return artist_id

    @classmethod
    def validate_years(cls, value: str) -> Tuple[Optional[int], Optional[int]]:
        """Validate year or year range."""
        if not value:
            return None, None
            
        match = cls.YEAR_PATTERN.match(value.strip())
        if not match:
            raise ValidationError(
                "Invalid year format. Use YYYY or YYYY-YYYY."
            )
        
        start_year = int(match.group(1))
        end_year = int(match.group(3)) if match.group(3) else start_year
        
        # Basic validation
        current_year = 2025  # Update this as needed
        if start_year < 1900 or start_year > current_year:
            raise ValidationError(f"Start year must be between 1900 and {current_year}")
        if end_year < 1900 or end_year > current_year:
            raise ValidationError(f"End year must be between 1900 and {current_year}")
        if start_year > end_year:
            raise ValidationError("Start year cannot be greater than end year")
        
        return start_year, end_year

    @classmethod
    def validate_countries(cls, value: str) -> List[str]:
        """Validate country codes."""
        if not value:
            return []
        
        countries = [c.strip().upper() for c in value.split(',')]
        invalid_countries = [c for c in countries if not cls.COUNTRY_PATTERN.match(c)]
        
        if invalid_countries:
            raise ValidationError(
                f"Invalid country codes: {', '.join(invalid_countries)}. "
                "Use 2-letter ISO codes (e.g., RU, UZ, US)."
            )
        
        return countries

    @classmethod
    def validate_genres(cls, value: str) -> List[str]:
        """Validate genre names."""
        if not value:
            return []
        
        genres = [g.strip().lower() for g in value.split(',')]
        invalid_genres = [g for g in genres if not cls.GENRE_PATTERN.match(g)]
        
        if invalid_genres:
            raise ValidationError(
                f"Invalid genre names: {', '.join(invalid_genres)}. "
                "Use letters, spaces, and hyphens only."
            )
        
        return genres

    @classmethod
    def validate_positive_int(cls, value: Union[str, int], name: str, max_value: Optional[int] = None) -> int:
        """Validate positive integer."""
        try:
            result = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{name} must be a number")
        
        if result <= 0:
            raise ValidationError(f"{name} must be positive")
        
        if max_value and result > max_value:
            raise ValidationError(f"{name} cannot exceed {max_value}")
        
        return result

    @classmethod
    def validate_quality(cls, value: str) -> str:
        """Validate audio quality."""
        if not value:
            return "high"  # default
        
        value = value.lower().strip()
        if not cls.QUALITY_PATTERN.match(value):
            raise ValidationError(
                "Invalid quality. Use 'low', 'medium', or 'high'."
            )
        
        return value

    @classmethod
    def validate_chart_type(cls, value: str) -> str:
        """Validate chart type."""
        if not value:
            return "world"  # default
        
        valid_charts = ["world", "russia", "ukraine", "belarus", "kazakhstan", "global"]
        value = value.lower().strip()
        
        if value not in valid_charts:
            raise ValidationError(
                f"Invalid chart type. Use one of: {', '.join(valid_charts)}"
            )
        
        return value


class ParameterParser:
    """Parses command parameters from text."""
    
    # Parameter patterns
    PARAM_PATTERNS = {
        'artist': re.compile(r'artist[:\s=](\S+)', re.IGNORECASE),
        'track': re.compile(r'track[:\s=](\S+)', re.IGNORECASE),
        'top': re.compile(r'top[:\s=](\d+)', re.IGNORECASE),
        'years': re.compile(r'years?[:\s=]([0-9\-]+)', re.IGNORECASE),
        'countries': re.compile(r'countr(?:y|ies)[:\s=]([A-Z,\s]+)', re.IGNORECASE),
        'genres': re.compile(r'genres?[:\s=]([a-zA-Z,\s\-]+)', re.IGNORECASE),
        'quality': re.compile(r'quality[:\s=](low|medium|high)', re.IGNORECASE),
        'depth': re.compile(r'depth[:\s=](\d+)', re.IGNORECASE),
        'limit': re.compile(r'limit[:\s=](\d+)', re.IGNORECASE),
        'songs': re.compile(r'songs?[:\s=](\d+)', re.IGNORECASE),
        'max': re.compile(r'max[:\s=](\d+)', re.IGNORECASE),
        'chart': re.compile(r'chart[:\s=](\w+)', re.IGNORECASE),
    }

    @classmethod
    def parse_parameters(cls, text: str) -> dict:
        """Parse parameters from command text."""
        params = {}
        
        # Check if first parameter after command is a number (artist ID)
        parts = text.split()
        if len(parts) > 1:
            # Check if first arg after command is numeric (artist ID without prefix)
            first_param = parts[1]
            if first_param.isdigit():
                params['artist'] = first_param
        
        # Parse other parameters with patterns
        for param_name, pattern in cls.PARAM_PATTERNS.items():
            match = pattern.search(text)
            if match:
                params[param_name] = match.group(1).strip()
        
        return params

    @classmethod
    def extract_artist_from_url(cls, text: str) -> Optional[str]:
        """Extract artist ID from Yandex Music URL in text."""
        match = CommandValidator.YANDEX_ARTIST_URL.search(text)
        return match.group(1) if match else None