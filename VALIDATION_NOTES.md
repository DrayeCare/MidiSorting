# MIDI Input Validation Specification

## Overview
To ensure reliable sorting inside `organizer/`, input files must pass basic integrity checks before metadata extraction.

## Validation Rules
- **Supported Extensions:** `.mid`, `.midi` (case-insensitive)
- **Minimum File Size:** Reject `0-byte` or truncated files (< 14 bytes)
- **Header Check:** Require a complete 14-byte SMF header: `MThd` chunk identifier, big-endian header-length field of `6`, and valid format (`0`, `1`, or `2`), track-count, and division fields. 
