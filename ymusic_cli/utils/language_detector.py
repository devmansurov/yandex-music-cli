#!/usr/bin/env python3
"""
Language and country detection utility for music artists and tracks.
Uses genre analysis, script detection, and other heuristics to determine origin.
"""

import re
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class LanguageDetectionResult:
    """Result of language/country detection."""
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    language_code: Optional[str] = None
    language_name: Optional[str] = None
    confidence: float = 0.0
    detection_method: str = "unknown"
    additional_info: Dict[str, Any] = None

    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


class MusicLanguageDetector:
    """Detects language and country of origin for music artists and tracks."""

    # Genre to country/language mappings
    GENRE_MAPPINGS = {
        # Uzbek
        'uzbekpop': {'country': 'UZ', 'language': 'uz', 'country_name': 'Uzbekistan', 'language_name': 'Uzbek'},
        'uzbekrock': {'country': 'UZ', 'language': 'uz', 'country_name': 'Uzbekistan', 'language_name': 'Uzbek'},
        'uzbekfolk': {'country': 'UZ', 'language': 'uz', 'country_name': 'Uzbekistan', 'language_name': 'Uzbek'},

        # Turkish
        'turkishfolk': {'country': 'TR', 'language': 'tr', 'country_name': 'Turkey', 'language_name': 'Turkish'},
        'turkishpop': {'country': 'TR', 'language': 'tr', 'country_name': 'Turkey', 'language_name': 'Turkish'},
        'arabesquemusic': {'country': 'TR', 'language': 'tr', 'country_name': 'Turkey', 'language_name': 'Turkish'},
        'turkishrock': {'country': 'TR', 'language': 'tr', 'country_name': 'Turkey', 'language_name': 'Turkish'},
        'turkishclassical': {'country': 'TR', 'language': 'tr', 'country_name': 'Turkey', 'language_name': 'Turkish'},

        # Russian
        'russianrock': {'country': 'RU', 'language': 'ru', 'country_name': 'Russia', 'language_name': 'Russian'},
        'rusrap': {'country': 'RU', 'language': 'ru', 'country_name': 'Russia', 'language_name': 'Russian'},
        'russianpop': {'country': 'RU', 'language': 'ru', 'country_name': 'Russia', 'language_name': 'Russian'},
        'chanson': {'country': 'RU', 'language': 'ru', 'country_name': 'Russia', 'language_name': 'Russian'},
        'ruspop': {'country': 'RU', 'language': 'ru', 'country_name': 'Russia', 'language_name': 'Russian'},
        'rusestrada': {'country': 'RU', 'language': 'ru', 'country_name': 'Russia', 'language_name': 'Russian'},

        # Korean
        'kpop': {'country': 'KR', 'language': 'ko', 'country_name': 'South Korea', 'language_name': 'Korean'},
        'koreanrock': {'country': 'KR', 'language': 'ko', 'country_name': 'South Korea', 'language_name': 'Korean'},

        # Japanese
        'jpop': {'country': 'JP', 'language': 'ja', 'country_name': 'Japan', 'language_name': 'Japanese'},
        'japanesepop': {'country': 'JP', 'language': 'ja', 'country_name': 'Japan', 'language_name': 'Japanese'},
        'japaneserock': {'country': 'JP', 'language': 'ja', 'country_name': 'Japan', 'language_name': 'Japanese'},

        # Persian/Iranian
        'persian': {'country': 'IR', 'language': 'fa', 'country_name': 'Iran', 'language_name': 'Persian'},
        'iranianpop': {'country': 'IR', 'language': 'fa', 'country_name': 'Iran', 'language_name': 'Persian'},
        'eastern': {'country': 'IR', 'language': 'fa', 'country_name': 'Iran', 'language_name': 'Persian'},

        # Arabic
        'arabic': {'country': 'AE', 'language': 'ar', 'country_name': 'Arab World', 'language_name': 'Arabic'},
        'arabicpop': {'country': 'AE', 'language': 'ar', 'country_name': 'Arab World', 'language_name': 'Arabic'},
        'tarab': {'country': 'LB', 'language': 'ar', 'country_name': 'Lebanon', 'language_name': 'Arabic'},
        'egyptianpop': {'country': 'EG', 'language': 'ar', 'country_name': 'Egypt', 'language_name': 'Arabic'},
        'khaleejipop': {'country': 'SA', 'language': 'ar', 'country_name': 'Saudi Arabia', 'language_name': 'Arabic'},

        # Tajik
        'tajikpop': {'country': 'TJ', 'language': 'tg', 'country_name': 'Tajikistan', 'language_name': 'Tajik'},
        'tajikfolk': {'country': 'TJ', 'language': 'tg', 'country_name': 'Tajikistan', 'language_name': 'Tajik'},

        # Kazakh
        'kazakhpop': {'country': 'KZ', 'language': 'kk', 'country_name': 'Kazakhstan', 'language_name': 'Kazakh'},
        'kazakhfolk': {'country': 'KZ', 'language': 'kk', 'country_name': 'Kazakhstan', 'language_name': 'Kazakh'},

        # Kyrgyz
        'kyrgyzpop': {'country': 'KG', 'language': 'ky', 'country_name': 'Kyrgyzstan', 'language_name': 'Kyrgyz'},
        'kyrgyzfolk': {'country': 'KG', 'language': 'ky', 'country_name': 'Kyrgyzstan', 'language_name': 'Kyrgyz'},

        # Indian
        'bollywood': {'country': 'IN', 'language': 'hi', 'country_name': 'India', 'language_name': 'Hindi'},
        'indianpop': {'country': 'IN', 'language': 'hi', 'country_name': 'India', 'language_name': 'Hindi'},

        # Chinese/Mandarin/Cantonese
        'cpop': {'country': 'CN', 'language': 'zh', 'country_name': 'China', 'language_name': 'Chinese'},
        'chinesepop': {'country': 'CN', 'language': 'zh', 'country_name': 'China', 'language_name': 'Chinese'},
        'mandopop': {'country': 'TW', 'language': 'zh', 'country_name': 'Taiwan', 'language_name': 'Mandarin'},
        'cantopop': {'country': 'HK', 'language': 'yue', 'country_name': 'Hong Kong', 'language_name': 'Cantonese'},
        'chineseclassical': {'country': 'CN', 'language': 'zh', 'country_name': 'China', 'language_name': 'Chinese'},
        'taiwanesepop': {'country': 'TW', 'language': 'zh', 'country_name': 'Taiwan', 'language_name': 'Mandarin'},

        # Southeast Asian
        'malaypop': {'country': 'MY', 'language': 'ms', 'country_name': 'Malaysia', 'language_name': 'Malay'},
        'thaipop': {'country': 'TH', 'language': 'th', 'country_name': 'Thailand', 'language_name': 'Thai'},
        'vietnamesepop': {'country': 'VN', 'language': 'vi', 'country_name': 'Vietnam', 'language_name': 'Vietnamese'},
        'indonesianpop': {'country': 'ID', 'language': 'id', 'country_name': 'Indonesia', 'language_name': 'Indonesian'},
        'opm': {'country': 'PH', 'language': 'tl', 'country_name': 'Philippines', 'language_name': 'Tagalog'},
        'filipinopop': {'country': 'PH', 'language': 'tl', 'country_name': 'Philippines', 'language_name': 'Tagalog'},
        'vietpop': {'country': 'VN', 'language': 'vi', 'country_name': 'Vietnam', 'language_name': 'Vietnamese'},

        # French
        'chanson française': {'country': 'FR', 'language': 'fr', 'country_name': 'France', 'language_name': 'French'},
        'frenchpop': {'country': 'FR', 'language': 'fr', 'country_name': 'France', 'language_name': 'French'},

        # Spanish/Latin American
        'latino': {'country': 'ES', 'language': 'es', 'country_name': 'Spain', 'language_name': 'Spanish'},
        'spanishpop': {'country': 'ES', 'language': 'es', 'country_name': 'Spain', 'language_name': 'Spanish'},
        'reggaeton': {'country': 'PR', 'language': 'es', 'country_name': 'Puerto Rico', 'language_name': 'Spanish'},
        'latinfolk': {'country': 'ES', 'language': 'es', 'country_name': 'Latin America', 'language_name': 'Spanish'},

        # Portuguese (separate from Spanish)
        'brazilianpop': {'country': 'BR', 'language': 'pt', 'country_name': 'Brazil', 'language_name': 'Portuguese'},
        'lusophone': {'country': 'PT', 'language': 'pt', 'country_name': 'Portugal', 'language_name': 'Portuguese'},
        'bossanova': {'country': 'BR', 'language': 'pt', 'country_name': 'Brazil', 'language_name': 'Portuguese'},
        'samba': {'country': 'BR', 'language': 'pt', 'country_name': 'Brazil', 'language_name': 'Portuguese'},
        'fado': {'country': 'PT', 'language': 'pt', 'country_name': 'Portugal', 'language_name': 'Portuguese'},
        'mpb': {'country': 'BR', 'language': 'pt', 'country_name': 'Brazil', 'language_name': 'Portuguese'},
        'brazilian': {'country': 'BR', 'language': 'pt', 'country_name': 'Brazil', 'language_name': 'Portuguese'},

        # German
        'germanrock': {'country': 'DE', 'language': 'de', 'country_name': 'Germany', 'language_name': 'German'},
        'germanpop': {'country': 'DE', 'language': 'de', 'country_name': 'Germany', 'language_name': 'German'},

        # Italian
        'italianpop': {'country': 'IT', 'language': 'it', 'country_name': 'Italy', 'language_name': 'Italian'},

        # Nordic/Scandinavian
        'swedishpop': {'country': 'SE', 'language': 'sv', 'country_name': 'Sweden', 'language_name': 'Swedish'},
        'norwegianrock': {'country': 'NO', 'language': 'no', 'country_name': 'Norway', 'language_name': 'Norwegian'},
        'finnishfolk': {'country': 'FI', 'language': 'fi', 'country_name': 'Finland', 'language_name': 'Finnish'},
        'danishpop': {'country': 'DK', 'language': 'da', 'country_name': 'Denmark', 'language_name': 'Danish'},
        'icelandicpop': {'country': 'IS', 'language': 'is', 'country_name': 'Iceland', 'language_name': 'Icelandic'},
        'nordicfolk': {'country': 'SE', 'language': 'sv', 'country_name': 'Sweden', 'language_name': 'Swedish'},

        # Caribbean/English-speaking regions
        'reggae': {'country': 'JM', 'language': 'en', 'country_name': 'Jamaica', 'language_name': 'English'},
        'ska': {'country': 'JM', 'language': 'en', 'country_name': 'Jamaica', 'language_name': 'English'},

        # English-speaking genres
        'britpop': {'country': 'GB', 'language': 'en', 'country_name': 'United Kingdom', 'language_name': 'English'},
        'americanpop': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'ukrock': {'country': 'GB', 'language': 'en', 'country_name': 'United Kingdom', 'language_name': 'English'},
        'usrap': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'indierock': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'countrymusic': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'country': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'indie': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},

        # African genres
        'african': {'country': 'NG', 'language': 'en', 'country_name': 'Nigeria', 'language_name': 'English'},
        'afrobeat': {'country': 'NG', 'language': 'en', 'country_name': 'Nigeria', 'language_name': 'English'},

        # Other specific genres from test results
        'conjazz': {'country': 'GE', 'language': 'ka', 'country_name': 'Georgia', 'language_name': 'Georgian'},
        'mizrahi': {'country': 'IL', 'language': 'he', 'country_name': 'Israel', 'language_name': 'Hebrew'},
        'levantpop': {'country': 'SY', 'language': 'ar', 'country_name': 'Syria', 'language_name': 'Arabic'},
        'ukrrock': {'country': 'UA', 'language': 'uk', 'country_name': 'Ukraine', 'language_name': 'Ukrainian'},
        'kazakhrap': {'country': 'KZ', 'language': 'kk', 'country_name': 'Kazakhstan', 'language_name': 'Kazakh'},
        'armenian': {'country': 'AM', 'language': 'hy', 'country_name': 'Armenia', 'language_name': 'Armenian'},
        'azerbaijanpop': {'country': 'AZ', 'language': 'az', 'country_name': 'Azerbaijan', 'language_name': 'Azerbaijani'},

        # Specific Folk Genres (replacing generic 'folk')
        'celticfolk': {'country': 'IE', 'language': 'en', 'country_name': 'Ireland', 'language_name': 'Irish/English'},
        'balkanfolk': {'country': 'RS', 'language': 'sr', 'country_name': 'Serbia', 'language_name': 'Serbian'},
        'anatolianfolk': {'country': 'TR', 'language': 'tr', 'country_name': 'Turkey', 'language_name': 'Turkish'},
        'slavicfolk': {'country': 'PL', 'language': 'pl', 'country_name': 'Poland', 'language_name': 'Polish'},
        'balkan': {'country': 'RS', 'language': 'sr', 'country_name': 'Serbia', 'language_name': 'Serbian'},
        'folkrock': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'newage': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},

        # Additional Regional Variations
        'caucasian': {'country': 'GE', 'language': 'ka', 'country_name': 'Georgia', 'language_name': 'Georgian'},
        'maghreb': {'country': 'MA', 'language': 'ar', 'country_name': 'Morocco', 'language_name': 'Arabic'},
        'afrikaans': {'country': 'ZA', 'language': 'af', 'country_name': 'South Africa', 'language_name': 'Afrikaans'},
        'foreignbard': {'country': 'EU', 'language': 'multi', 'country_name': 'Europe', 'language_name': 'European'},
        'allrock': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'alternative': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'rnb': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'jazz': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'soul': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
        'rap': {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},

        # Multi-country genres (lower confidence)
        'estrada': {'country': 'EU', 'language': 'multi', 'country_name': 'Europe', 'language_name': 'European'},
        'eurofolk': {'country': 'EU', 'language': 'multi', 'country_name': 'Europe', 'language_name': 'European'},
        'folkgenre': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
        'local-indie': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
        'folk': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
        'pop': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
        'dance': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
        'rock': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
        'electronic': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
        'electronics': {'country': 'MIXED', 'language': 'multi', 'country_name': 'Mixed', 'language_name': 'Mixed'},
    }

    # Script detection patterns
    SCRIPT_PATTERNS = {
        'cyrillic': re.compile(r'[\u0400-\u04FF\u0500-\u052F\u2DE0-\u2DFF\uA640-\uA69F]'),  # Expanded Cyrillic
        'arabic': re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'),
        'chinese': re.compile(r'[\u4e00-\u9fff]'),  # Basic CJK only
        'korean': re.compile(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]'),  # Hangul + Jamo
        'japanese_hiragana': re.compile(r'[\u3040-\u309f]'),
        'japanese_katakana': re.compile(r'[\u30a0-\u30ff]'),
        'devanagari': re.compile(r'[\u0900-\u097f]'),  # Hindi, Sanskrit
        'hebrew': re.compile(r'[\u0590-\u05FF]'),  # Hebrew
        'armenian': re.compile(r'[\u0530-\u058F]'),  # Armenian
        'georgian': re.compile(r'[\u10A0-\u10FF]'),  # Georgian
        'thai': re.compile(r'[\u0E00-\u0E7F]'),  # Thai
        'vietnamese': re.compile(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđĐ]'),  # Vietnamese diacritics
        'greek': re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]'),  # Greek
        'latin': re.compile(r'[a-zA-Z\u00C0-\u017F\u0100-\u024F]'),  # Latin + extended
    }

    # Script to possible languages
    SCRIPT_TO_LANGUAGES = {
        'cyrillic': [
            {'country': 'RU', 'language': 'ru', 'country_name': 'Russia', 'language_name': 'Russian'},
            {'country': 'UZ', 'language': 'uz', 'country_name': 'Uzbekistan', 'language_name': 'Uzbek'},
            {'country': 'TJ', 'language': 'tg', 'country_name': 'Tajikistan', 'language_name': 'Tajik'},
            {'country': 'KZ', 'language': 'kk', 'country_name': 'Kazakhstan', 'language_name': 'Kazakh'},
            {'country': 'KG', 'language': 'ky', 'country_name': 'Kyrgyzstan', 'language_name': 'Kyrgyz'},
            {'country': 'UA', 'language': 'uk', 'country_name': 'Ukraine', 'language_name': 'Ukrainian'},
            {'country': 'BY', 'language': 'be', 'country_name': 'Belarus', 'language_name': 'Belarusian'},
        ],
        'arabic': [
            {'country': 'AE', 'language': 'ar', 'country_name': 'Arab World', 'language_name': 'Arabic'},
            {'country': 'IR', 'language': 'fa', 'country_name': 'Iran', 'language_name': 'Persian'},
            {'country': 'AF', 'language': 'fa', 'country_name': 'Afghanistan', 'language_name': 'Persian'},
        ],
        'chinese': [
            {'country': 'CN', 'language': 'zh', 'country_name': 'China', 'language_name': 'Chinese'},
            {'country': 'TW', 'language': 'zh', 'country_name': 'Taiwan', 'language_name': 'Chinese'},
        ],
        'korean': [
            {'country': 'KR', 'language': 'ko', 'country_name': 'South Korea', 'language_name': 'Korean'},
        ],
        'japanese_hiragana': [
            {'country': 'JP', 'language': 'ja', 'country_name': 'Japan', 'language_name': 'Japanese'},
        ],
        'japanese_katakana': [
            {'country': 'JP', 'language': 'ja', 'country_name': 'Japan', 'language_name': 'Japanese'},
        ],
        'devanagari': [
            {'country': 'IN', 'language': 'hi', 'country_name': 'India', 'language_name': 'Hindi'},
        ],
        'hebrew': [
            {'country': 'IL', 'language': 'he', 'country_name': 'Israel', 'language_name': 'Hebrew'},
        ],
        'armenian': [
            {'country': 'AM', 'language': 'hy', 'country_name': 'Armenia', 'language_name': 'Armenian'},
        ],
        'georgian': [
            {'country': 'GE', 'language': 'ka', 'country_name': 'Georgia', 'language_name': 'Georgian'},
        ],
        'thai': [
            {'country': 'TH', 'language': 'th', 'country_name': 'Thailand', 'language_name': 'Thai'},
        ],
        'vietnamese': [
            {'country': 'VN', 'language': 'vi', 'country_name': 'Vietnam', 'language_name': 'Vietnamese'},
        ],
        'greek': [
            {'country': 'GR', 'language': 'el', 'country_name': 'Greece', 'language_name': 'Greek'},
        ],
        'latin': [
            {'country': 'US', 'language': 'en', 'country_name': 'United States', 'language_name': 'English'},
            {'country': 'GB', 'language': 'en', 'country_name': 'United Kingdom', 'language_name': 'English'},
            {'country': 'DE', 'language': 'de', 'country_name': 'Germany', 'language_name': 'German'},
            {'country': 'FR', 'language': 'fr', 'country_name': 'France', 'language_name': 'French'},
            {'country': 'ES', 'language': 'es', 'country_name': 'Spain', 'language_name': 'Spanish'},
            {'country': 'IT', 'language': 'it', 'country_name': 'Italy', 'language_name': 'Italian'},
        ],
    }

    def detect_from_genres(self, genres: List[str]) -> LanguageDetectionResult:
        """Detect language/country from genre information with weighted scoring."""
        if not genres:
            return LanguageDetectionResult(confidence=0.0, detection_method="no_genres")

        # Collect all possible matches with scores
        matches = []

        # Check each genre against mappings
        for genre in genres:
            genre_lower = genre.lower().strip()

            # Direct match
            if genre_lower in self.GENRE_MAPPINGS:
                mapping = self.GENRE_MAPPINGS[genre_lower]
                # Higher score for specific language genres, lower for multi-language
                score = 0.9 if mapping['language'] != 'multi' else 0.5
                matches.append({
                    'mapping': mapping,
                    'score': score,
                    'method': 'direct_genre_match',
                    'matched_genre': genre
                })

            # Partial matches (more strict)
            else:
                for genre_key, mapping in self.GENRE_MAPPINGS.items():
                    # Only match if the genre is a significant part of the key or vice versa
                    if (len(genre_lower) >= 4 and genre_lower in genre_key and len(genre_lower) / len(genre_key) > 0.6) or \
                       (len(genre_key) >= 4 and genre_key in genre_lower and len(genre_key) / len(genre_lower) > 0.6):
                        score = 0.6 if mapping['language'] != 'multi' else 0.3
                        matches.append({
                            'mapping': mapping,
                            'score': score,
                            'method': 'partial_genre_match',
                            'matched_genre': genre,
                            'genre_key': genre_key
                        })

        if not matches:
            return LanguageDetectionResult(confidence=0.0, detection_method="no_genre_match")

        # Sort by score and take the best match
        best_match = max(matches, key=lambda x: x['score'])
        mapping = best_match['mapping']

        # If we have multiple good matches for the same language, increase confidence
        same_language_matches = [m for m in matches if m['mapping']['language'] == mapping['language'] and m['score'] >= 0.5]
        confidence_boost = min(0.1 * (len(same_language_matches) - 1), 0.2)  # Max boost of 0.2
        final_confidence = min(best_match['score'] + confidence_boost, 1.0)

        additional_info = {
            'matched_genre': best_match['matched_genre'],
            'all_matches': matches[:5],  # Keep top 5 matches for debugging
            'confidence_boost': confidence_boost
        }
        if 'genre_key' in best_match:
            additional_info['genre_key'] = best_match['genre_key']

        return LanguageDetectionResult(
            country_code=mapping['country'],
            country_name=mapping['country_name'],
            language_code=mapping['language'],
            language_name=mapping['language_name'],
            confidence=final_confidence,
            detection_method=best_match['method'],
            additional_info=additional_info
        )

    def detect_script_from_text(self, text: str) -> Dict[str, float]:
        """Detect script composition in text."""
        if not text:
            return {}

        script_counts = {}
        total_chars = len(text)

        for script_name, pattern in self.SCRIPT_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                script_counts[script_name] = len(matches) / total_chars

        return script_counts

    def detect_from_track_titles(self, track_titles: List[str]) -> LanguageDetectionResult:
        """Detect language from track title analysis."""
        if not track_titles:
            return LanguageDetectionResult(confidence=0.0, detection_method="no_titles")

        # Analyze all titles
        all_scripts = {}
        for title in track_titles:
            scripts = self.detect_script_from_text(title)
            for script, ratio in scripts.items():
                all_scripts[script] = all_scripts.get(script, 0) + ratio

        if not all_scripts:
            return LanguageDetectionResult(confidence=0.0, detection_method="no_script_detected")

        # Find dominant script
        dominant_script = max(all_scripts.keys(), key=lambda k: all_scripts[k])
        dominant_ratio = all_scripts[dominant_script] / len(track_titles)

        # Map script to languages
        if dominant_script in self.SCRIPT_TO_LANGUAGES:
            # For now, take the first (most common) language for the script
            mapping = self.SCRIPT_TO_LANGUAGES[dominant_script][0]

            # Adjust confidence based on ratio and number of titles
            # Lower confidence for script analysis to prioritize genre detection
            base_confidence = 0.3 if dominant_script == 'latin' else 0.6
            confidence = min(base_confidence, dominant_ratio * (len(track_titles) / 10))

            return LanguageDetectionResult(
                country_code=mapping['country'],
                country_name=mapping['country_name'],
                language_code=mapping['language'],
                language_name=mapping['language_name'],
                confidence=confidence,
                detection_method="script_analysis",
                additional_info={
                    'dominant_script': dominant_script,
                    'script_ratio': dominant_ratio,
                    'all_scripts': all_scripts,
                    'titles_analyzed': len(track_titles)
                }
            )

        return LanguageDetectionResult(
            confidence=0.3,
            detection_method="script_detected_unmapped",
            additional_info={
                'dominant_script': dominant_script,
                'script_ratio': dominant_ratio,
                'all_scripts': all_scripts
            }
        )

    def detect_from_artist_name(self, artist_name: str) -> LanguageDetectionResult:
        """Detect language from artist name."""
        scripts = self.detect_script_from_text(artist_name)

        if not scripts:
            return LanguageDetectionResult(confidence=0.0, detection_method="no_script_in_name")

        # Find dominant script in name
        dominant_script = max(scripts.keys(), key=lambda k: scripts[k])

        if dominant_script in self.SCRIPT_TO_LANGUAGES:
            mapping = self.SCRIPT_TO_LANGUAGES[dominant_script][0]

            return LanguageDetectionResult(
                country_code=mapping['country'],
                country_name=mapping['country_name'],
                language_code=mapping['language'],
                language_name=mapping['language_name'],
                confidence=0.4,  # Lower confidence for name-only detection
                detection_method="artist_name_script",
                additional_info={
                    'artist_name': artist_name,
                    'dominant_script': dominant_script,
                    'scripts': scripts
                }
            )

        return LanguageDetectionResult(
            confidence=0.2,
            detection_method="name_script_unmapped",
            additional_info={
                'artist_name': artist_name,
                'dominant_script': dominant_script,
                'scripts': scripts
            }
        )

    def detect_comprehensive(
        self,
        artist_name: str = None,
        genres: List[str] = None,
        track_titles: List[str] = None
    ) -> LanguageDetectionResult:
        """Comprehensive detection using all available methods."""

        results = []

        # Try genre-based detection first (highest confidence)
        if genres:
            genre_result = self.detect_from_genres(genres)
            if genre_result.confidence > 0:
                results.append(genre_result)

        # Try track title analysis
        if track_titles:
            title_result = self.detect_from_track_titles(track_titles)
            if title_result.confidence > 0:
                results.append(title_result)

        # Try artist name analysis
        if artist_name:
            name_result = self.detect_from_artist_name(artist_name)
            if name_result.confidence > 0:
                results.append(name_result)

        if not results:
            return LanguageDetectionResult(confidence=0.0, detection_method="no_detection_possible")

        # Return the result with highest confidence
        best_result = max(results, key=lambda r: r.confidence)

        # Add information about other methods
        best_result.additional_info['all_results'] = [
            {
                'method': r.detection_method,
                'confidence': r.confidence,
                'country': r.country_code,
                'language': r.language_code
            }
            for r in results
        ]

        return best_result


# Global instance
detector = MusicLanguageDetector()


def detect_artist_language(
    artist_name: str = None,
    genres: List[str] = None,
    track_titles: List[str] = None
) -> LanguageDetectionResult:
    """Convenience function for artist language detection."""
    return detector.detect_comprehensive(
        artist_name=artist_name,
        genres=genres,
        track_titles=track_titles
    )