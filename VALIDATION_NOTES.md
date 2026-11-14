# MIDI Input Validation Specification

## Overview
To ensure reliable sorting inside `organizer/`, input files must pass basic integrity checks before metadata extraction.

## Validation Rules
- **Supported Extensions:** `.mid`, `.midi` (case-insensitive)
- **Minimum File Size:** Reject `0-byte` empty files
- **Header Check:** Must start with valid Standard MIDI File (SMF) header chunk (`MThd`)
