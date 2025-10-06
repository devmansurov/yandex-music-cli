# 🤖 Claude Code Development Guidelines

## Overview

This document provides comprehensive guidelines for developing and maintaining the Yandex Music CLI using Claude Code. Follow these guidelines to ensure consistent, maintainable, and high-quality code.

## 📋 Project Structure

```
yandex-music-cli/
├── ymusic_cli/              # Main package
│   ├── cli.py              # CLI entry point
│   ├── config/             # Configuration management
│   ├── core/               # Core models and interfaces
│   ├── services/           # Business logic services
│   └── utils/              # Utility functions
├── docs/                   # Documentation
├── scripts/                # Installation scripts
├── requirements.txt        # Dependencies
├── setup.py               # Package installer
└── .env.example           # Configuration template
```

## 🎯 Code Standards

### Python Code Quality

#### Type Hints
- **MANDATORY**: Use type hints for all function parameters and return values
- **Format**: Use modern type hint syntax (e.g., `list[str]` instead of `List[str]` for Python 3.9+)
- **Imports**: Import types from `typing` when needed

```python
# ✅ Good
async def download_tracks(self, tracks: list[Track], options: DownloadOptions) -> list[Path]:
    pass

# ❌ Bad
async def download_tracks(self, tracks, options):
    pass
```

#### Docstrings
- **Required**: All public methods, classes, and modules must have docstrings
- **Format**: Use Google-style docstrings
- **Content**: Include purpose, parameters, return values, and exceptions

```python
# ✅ Good
async def get_artist_tracks(self, artist_id: str, options: DownloadOptions) -> list[Track]:
    """Get tracks for an artist with filtering options.

    Args:
        artist_id: Yandex Music artist ID
        options: Download filtering and selection options

    Returns:
        List of tracks matching the criteria

    Raises:
        ServiceError: If the API request fails
        NotFoundError: If the artist doesn't exist
    """
    pass
```

#### Code Formatting
- **Line Length**: Maximum 100 characters
- **Indentation**: 4 spaces (no tabs)
- **Imports**: Group imports (standard library, third-party, local)
- **Naming**: Use snake_case for functions/variables, PascalCase for classes

### Async/Await Usage

#### Always Use Async for I/O
- **Database operations**: Always async
- **Network requests**: Always async
- **File operations**: Use `aiofiles`
- **Sleep operations**: Use `asyncio.sleep()`

```python
# ✅ Good
async def save_file(self, data: bytes, path: Path) -> None:
    async with aiofiles.open(path, 'wb') as f:
        await f.write(data)

# ❌ Bad
def save_file(self, data: bytes, path: Path) -> None:
    with open(path, 'wb') as f:
        f.write(data)
```

## 🏗️ Architecture Rules

### SOLID Principles Compliance

#### Single Responsibility Principle (SRP)
- **One purpose**: Each class should have one reason to change
- **Clear focus**: Services should handle one domain (downloads, discovery, etc.)
- **Separation**: CLI logic separate from business logic

#### Dependency Injection
- **Constructor injection**: Inject dependencies through constructors
- **Interface injection**: Inject abstract interfaces, not concrete classes

```python
# ✅ Good
class DownloadOrchestrator:
    def __init__(
        self,
        music_service: MusicService,
        file_manager: FileManager,
        cache_service: CacheService
    ):
        self.music_service = music_service
        self.file_manager = file_manager
        self.cache_service = cache_service
```

## 📝 CLI Development Guidelines

### Parameter Design

#### Short and Long Options
- **Always provide both**: Short (`-a`) and long (`--artist-id`) options
- **POSIX Standard**: Follow standard conventions
- **Metavar**: Use clear metavar names (ID, DIR, N, etc.)

```python
# ✅ Good
parser.add_argument(
    '-a', '--artist-id',
    type=str,
    required=True,
    metavar='ID',
    help='Yandex Music artist ID'
)
```

#### Parameter Validation
- **Validate early**: Check parameters before processing
- **Clear errors**: Provide helpful error messages
- **Logical consistency**: Validate parameter combinations

```python
# ✅ Good
if args.depth > 0 and args.similar == 0:
    parser.error("--depth > 0 requires --similar > 0 (recursive discovery needs similar artists)")
```

### User Experience

#### Progress Tracking
- **Use tqdm**: Show progress bars for long operations
- **Informative messages**: Log what's happening
- **Statistics**: Show summary at the end

#### Error Handling
- **User-friendly**: Don't expose internal details
- **Actionable**: Tell users what to do
- **Verbose mode**: Provide detailed logs with `-v`

```python
# ✅ Good
try:
    await external_api.call()
except ExternalAPIError as e:
    self.logger.error(f"API call failed: {e}")  # Log for debugging
    raise ServiceError("External service unavailable. Please try again later.")  # User message
```

## 🔧 Development Workflow

### Before Making Changes

1. **Read the code**: Understand existing patterns
2. **Check interfaces**: See if changes require interface updates
3. **Consider tests**: Think about how to test your changes
4. **Plan the approach**: Consider the cleanest implementation

### When Adding Features

1. **Start with interfaces**: Define interfaces first
2. **Implement incrementally**: Start with core functionality
3. **Add error handling**: Handle all edge cases
4. **Update documentation**: Update README.md and other docs
5. **Test thoroughly**: Test with various parameters

### When Fixing Bugs

1. **Reproduce**: First reproduce the bug with a test
2. **Fix minimally**: Make the smallest change that fixes the issue
3. **Verify**: Ensure the fix doesn't break other functionality
4. **Document**: Update documentation if needed

## 📚 Documentation Standards

### README.md
- **Keep updated**: Always reflect current features
- **Clear examples**: Provide working examples
- **Installation**: Keep installation instructions accurate

### Code Comments
- **Why, not what**: Explain why, not what the code does
- **Complex logic**: Comment complex algorithms
- **TODOs**: Use TODO comments for future improvements

```python
# ✅ Good
# Use semaphore to limit concurrent downloads and prevent API rate limiting
semaphore = asyncio.Semaphore(5)

# ❌ Bad
# Create a semaphore with value 5
semaphore = asyncio.Semaphore(5)
```

## 🔍 Code Review Checklist

### Functionality
- [ ] Does the code solve the intended problem?
- [ ] Are all edge cases handled?
- [ ] Is error handling comprehensive?
- [ ] Are there any obvious bugs?

### Quality
- [ ] Are there type hints on all functions?
- [ ] Are there docstrings on public methods?
- [ ] Is the code readable and well-structured?
- [ ] Are variable names descriptive?

### Performance
- [ ] Are async/await used correctly?
- [ ] Are there any blocking operations?
- [ ] Is memory usage reasonable?
- [ ] Are there appropriate limits and timeouts?

### Documentation
- [ ] Is README.md updated?
- [ ] Are examples working?
- [ ] Is CHANGELOG updated?
- [ ] Are comments helpful?

## 🛠️ Tools and Commands

### Running the CLI

```bash
# Activate virtual environment
source venv/bin/activate

# Run CLI
python -m ymusic_cli -a 9045812 -n 10 -o ./downloads

# Run with verbose logging
python -m ymusic_cli -a 9045812 -n 10 -o ./downloads -v
```

### Testing

```bash
# Test installation
bash scripts/install.sh

# Test CLI help
python -m ymusic_cli --help

# Test basic download
python -m ymusic_cli -a 9045812 -n 1 -o ./test -v
```

### Code Quality

```bash
# Type checking (if mypy installed)
mypy ymusic_cli/

# Code formatting (if black installed)
black ymusic_cli/

# Linting (if flake8 installed)
flake8 ymusic_cli/
```

## 📦 Dependency Management

### Adding New Dependencies

1. **Evaluate necessity**: Is the dependency really needed?
2. **Check size**: Keep dependencies minimal
3. **Update requirements.txt**: Add with version constraint
4. **Update documentation**: Note new dependency in README

### Current Dependencies

- `yandex-music>=2.1.1` - Yandex Music API
- `aiohttp==3.9.1` - Async HTTP
- `aiofiles==23.2.1` - Async file operations
- `mutagen==1.47.0` - Audio metadata
- `tqdm==4.66.1` - Progress bars
- `python-dotenv==1.0.0` - Configuration
- `python-dateutil==2.8.2` - Date utilities

## 🔒 Security Guidelines

### Input Validation
- **Always validate**: All user inputs must be validated
- **Sanitize**: Sanitize file names and paths
- **Limits**: Enforce reasonable limits

### Token Handling
- **Never log**: Don't log tokens or credentials
- **Environment**: Store in `.env`, never in code
- **Documentation**: Remind users to keep tokens private

## 🚀 Release Process

### Version Updates

1. **Update version**: In `ymusic_cli/__init__.py` and `setup.py`
2. **Update CHANGELOG**: Document changes
3. **Test thoroughly**: Test all features
4. **Commit**: `git commit -m "Release v1.x.x"`
5. **Tag**: `git tag v1.x.x`
6. **Push**: `git push && git push --tags`

### Documentation Updates

Before release:
- [ ] README.md is accurate
- [ ] INSTALL.md is updated
- [ ] Examples are working
- [ ] CHANGELOG is updated
- [ ] Version numbers are consistent

## 💡 Best Practices

### Do's

✅ **DO** use type hints everywhere
✅ **DO** write descriptive commit messages
✅ **DO** keep functions small and focused
✅ **DO** use async/await for I/O operations
✅ **DO** validate user input
✅ **DO** provide helpful error messages
✅ **DO** update documentation with code changes
✅ **DO** test with real API calls occasionally

### Don'ts

❌ **DON'T** commit `.env` files
❌ **DON'T** hardcode credentials
❌ **DON'T** use blocking I/O in async functions
❌ **DON'T** catch exceptions without logging
❌ **DON'T** leave TODO comments without issues
❌ **DON'T** break backward compatibility without major version bump
❌ **DON'T** add dependencies without justification

## 🎯 Project Goals

### Primary Goals
1. **Easy to use**: Simple, intuitive CLI interface
2. **Well documented**: Clear documentation and examples
3. **Reliable**: Handle errors gracefully
4. **Performant**: Efficient downloads with progress tracking
5. **Maintainable**: Clean, well-structured code

### Non-Goals
- GUI interface (CLI only)
- Support for other music platforms (Yandex Music only)
- Real-time streaming (downloads only)

## 📞 Getting Help

### Resources
- **GitHub Issues**: https://github.com/devmansurov/yandex-music-cli/issues
- **Documentation**: See `docs/` directory
- **Examples**: See README.md and QUICK_START.md

### When Stuck
1. Check existing documentation
2. Look at similar implementations in codebase
3. Search GitHub issues
4. Create new issue if needed

---

## 🎯 Remember

> **"Code is read more often than it's written"** - Always prioritize readability and maintainability over cleverness.

Follow these guidelines consistently to maintain a high-quality, maintainable codebase that's easy for others (including future you) to understand and extend.

---

**Happy coding! 🎵**
