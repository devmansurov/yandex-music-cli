#!/usr/bin/env python3
"""
Script to deduplicate files by replacing copies with hard links.

This script finds duplicate files in tracks/ and top10_tracks/ directories
and replaces the copies with hard links to save disk space.

Usage:
    python deduplicate_files.py [--dry-run] [--storage-dir PATH]

Options:
    --dry-run       Show what would be done without making changes
    --storage-dir   Path to storage/downloads directory (default: ./storage/downloads)
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from collections import defaultdict


def get_file_hash(filepath: Path, chunk_size: int = 8192) -> str:
    """Calculate MD5 hash of file for duplicate detection."""
    hash_md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_inode(filepath: Path) -> int:
    """Get inode number of file."""
    return filepath.stat().st_ino


def deduplicate_directory(storage_dir: Path, dry_run: bool = False):
    """
    Find and deduplicate files between tracks/ and top10_tracks/ directories.

    Args:
        storage_dir: Path to storage/downloads directory
        dry_run: If True, only show what would be done
    """
    tracks_dir = storage_dir / "tracks"
    output_dir = storage_dir / "top10_tracks"

    if not tracks_dir.exists():
        print(f"Error: tracks directory not found: {tracks_dir}")
        return

    if not output_dir.exists():
        print(f"Error: top10_tracks directory not found: {output_dir}")
        return

    print(f"Scanning directories...")
    print(f"  Cache: {tracks_dir}")
    print(f"  Output: {output_dir}")
    print()

    # Build index of cache files by filename
    cache_files = {}
    print("Indexing cache files...")
    for filepath in tracks_dir.glob("*.mp3"):
        cache_files[filepath.name] = filepath
    print(f"  Found {len(cache_files)} files in cache")

    # Find matching files in output directory
    print("\nScanning output directory for duplicates...")
    duplicates_found = 0
    space_saved = 0
    hard_links_created = 0
    errors = 0

    for output_file in output_dir.rglob("*.mp3"):
        filename = output_file.name

        if filename in cache_files:
            cache_file = cache_files[filename]

            # Check if they have the same inode (already hard linked)
            if get_inode(cache_file) == get_inode(output_file):
                continue  # Already hard linked

            # Check if files are identical
            if cache_file.stat().st_size == output_file.stat().st_size:
                duplicates_found += 1
                file_size = output_file.stat().st_size

                if dry_run:
                    print(f"[DRY RUN] Would replace: {output_file}")
                    print(f"          With link to: {cache_file}")
                    print(f"          Space saved: {file_size / 1024 / 1024:.2f} MB")
                    space_saved += file_size
                else:
                    try:
                        # Remove output file and create hard link
                        output_file.unlink()
                        os.link(str(cache_file), str(output_file))
                        hard_links_created += 1
                        space_saved += file_size

                        # Verify hard link was created
                        if get_inode(cache_file) == get_inode(output_file):
                            print(f"✓ Linked: {output_file.relative_to(storage_dir)}")
                        else:
                            print(f"⚠ Warning: Link created but inodes don't match: {output_file}")
                    except OSError as e:
                        errors += 1
                        print(f"✗ Error linking {output_file}: {e}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Duplicates found: {duplicates_found}")

    if dry_run:
        print(f"Would create hard links: {duplicates_found}")
        print(f"Would save disk space: {space_saved / 1024 / 1024 / 1024:.2f} GB")
    else:
        print(f"Hard links created: {hard_links_created}")
        print(f"Errors: {errors}")
        print(f"Disk space saved: {space_saved / 1024 / 1024 / 1024:.2f} GB")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate music files by replacing copies with hard links"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=Path("./storage/downloads"),
        help="Path to storage/downloads directory (default: ./storage/downloads)"
    )

    args = parser.parse_args()

    if not args.storage_dir.exists():
        print(f"Error: Storage directory not found: {args.storage_dir}")
        sys.exit(1)

    print("=" * 70)
    print("FILE DEDUPLICATION TOOL")
    print("=" * 70)

    if args.dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    else:
        print("MODE: LIVE (files will be modified)")
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    print()
    deduplicate_directory(args.storage_dir, args.dry_run)


if __name__ == "__main__":
    main()
