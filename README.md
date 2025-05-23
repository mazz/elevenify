# Elevenify: Text-to-Audio Conversion with ElevenLabs

`elevenify.py` is a Python script that converts text to audio using the ElevenLabs API. It is designed for generating high-quality audio from text files or direct input, with flexible options for processing line ranges, adding pauses, and customizing output formats. Ideal for applications like generating audio for Bible verses (e.g., `kjv.txt`), audiobooks, or narration, it offers robust features for both single-file and split-file outputs.

## Features

- **Text-to-Audio Conversion**:
  - Converts text from a file or command-line input to audio using ElevenLabs voices.
  - Supports models like `eleven_turbo_v2` and `eleven_multilingual_v2`.
- **File Processing**:
  - Processes text files with optional line range selection (`--start-line`, `--last-line`).
  - Skips empty lines and comments (lines starting with `#` or inline comments).
  - Supports large files like `kjv.txt` (~31,102 lines of Bible verses).
- **Pause Insertion**:
  - Adds precise silent pauses between lines in non-split mode (`--pause`, 0.0–30.0 seconds).
  - Uses `pydub` for accurate pause durations (e.g., 10-second pause between verses).
- **Split Mode**:
  - Generates separate audio files for each non-comment line (`--split`).
  - Useful for creating individual audio clips (e.g., one file per verse).
- **Flexible Output Formats**:
  - Supports MP3, PCM, uLaw, aLaw, and Opus formats with configurable bitrates/sample rates.
  - Default: MP3, 128 kbps, 44.1 kHz.
- **Filename Customization**:
  - Generates unique filenames with prefixes (from input file), sample numbers, voice name, and audio settings.
  - Non-split: `<prefix>-<start_sample>-<end_sample>-<voice>-<khz>-<bitrate>.mp3` (e.g., `kjv-31101-31102-knightley-dapper-and-deep-narrator-44.10-128.mp3`).
  - Split: `<prefix>-<sample>-<voice>-<khz>-<bitrate>.mp3`.
- **Credit Management**:
  - Estimates ElevenLabs character credits needed for file processing (`--estimate-credits`).
  - Displays remaining credits (`--credits`).
- **Voice Selection**:
  - Supports all ElevenLabs voices by name or ID (list via `--list`).
  - Default voice: Adam.
- **Error Handling**:
  - Validates inputs (e.g., line ranges, pause values, API key).
  - Handles filename collisions with indexed suffixes.
- **Unicode Support**:
  - Processes UTF-8 encoded text files for multilingual compatibility.
- **Custom API URL**:
  - Supports custom ElevenLabs API endpoints via `LABSURL` in `.env` (defaults to `https://api.elevenlabs.io`).

## Installation

1. **Clone or Download**:
   - Copy the `Elevenify` directory, including `elevenify.py`, `requirements.txt`, `.env-example`, and `sample.txt`, to your project directory.

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   This installs:
   - `elevenlabs>=0.3.0`
   - `python-dotenv>=1.0.0`
   - `pydub>=0.25.1`
   Verify:
   ```bash
   pip show elevenlabs python-dotenv pydub
   ```

3. **Install FFmpeg** (for `pydub` pause insertion):
   - macOS:
     ```bash
     brew install ffmpeg
     ```
   - Linux:
     ```bash
     sudo apt-get install ffmpeg
     ```
   - Windows:
     - Download from [FFmpeg website](https://ffmpeg.org/download.html).
     - Add to PATH or place in script directory.
     Verify:
     ```bash
     ffmpeg -version
     ```

4. **Set Up Environment Variables**:
   - Copy `.env-example` to `.env`:
     ```bash
     cp .env-example .env
     ```
   - Edit `.env` to include your ElevenLabs API key and optional custom API URL:
     ```
     LABSURL=https://api.elevenlabs.io
     LABSKEY=your_elevenlabs_api_key
     ```
   - Alternatively, use `--key your_elevenlabs_api_key` in commands. `LABSURL` can only be set via `.env`.

5. **Optional: Virtual Environment**:
   ```bash
   python -m venv elevenify_venv
   source elevenify_venv/bin/activate  # macOS/Linux
   elevenify_venv\Scripts\activate     # Windows
   ```

## Usage

Run `elevenify.py` with command-line arguments to generate audio. The included `sample.txt` file can be used for testing:

```
This is line one.
This is line two.

# comment
after comment
# comment on last line
```

### Basic Examples

- **Convert a Single Text String**:
  ```bash
  python elevenify.py "Hello, world!" --voice TJIZFyULEXGaeHXEFtw7 --model eleven_turbo_v2
  ```
  Output: `knightley-dapper-and-deep-narrator-44.10-128-00000.mp3`

- **Convert a File (Single Audio File)**:
  ```bash
  python elevenify.py --file sample.txt --model eleven_turbo_v2 --start-line 1 --voice TJIZFyULEXGaeHXEFtw7
  ```
  Output: `sample-00001-00003-knightley-dapper-and-deep-narrator-44.10-128.mp3` (lines 1, 2, 5)

- **Add a 10-Second Pause Between Lines**:
  ```bash
  python elevenify.py --file sample.txt --model eleven_turbo_v2 --start-line 1 --last-line 2 --pause 10 --voice TJIZFyULEXGaeHXEFtw7
  ```
  Output: `sample-00001-00002-knightley-dapper-and-deep-narrator-44.10-128.mp3` with 10-second pause between lines 1 and 2.

- **Split File into Multiple Audio Files**:
  ```bash
  python elevenify.py --file sample.txt --split --start-line 1 --last-line 5 --voice TJIZFyULEXGaeHXEFtw7
  ```
  Outputs:
  - `sample-00001-knightley-dapper-and-deep-narrator-44.10-128.mp3` (line 1)
  - `sample-00002-knightley-dapper-and-deep-narrator-44.10-128.mp3` (line 2)
  - `sample-00003-knightley-dapper-and-deep-narrator-44.10-128.mp3` (line 5)

### Advanced Examples

- **Process Bible Verses**:
  ```bash
  python elevenify.py --file kjv.txt --model eleven_turbo_v2 --start-line 31101 --pause 10 --voice TJIZFyULEXGaeHXEFtw7
  ```
  Output: `kjv-31101-31102-knightley-dapper-and-deep-narrator-44.10-128.mp3` (Revelation 22:20–21 with 10-second pause).

- **Estimate Credits**:
  ```bash
  python elevenify.py --file sample.txt --estimate-credits --start-line 1
  ```
  Shows credits needed and lines convertible.

- **List Available Voices**:
  ```bash
  python elevenify.py --list
  ```

- **Check Remaining Credits**:
  ```bash
  python elevenify.py --credits
  ```

- **Custom Audio Format**:
  ```bash
  python elevenify.py --file sample.txt --type pcm --rate 44100 --voice TJIZFyULEXGaeHXEFtw7
  ```
  Output: `sample-00001-00003-knightley-dapper-and-deep-narrator-44.10-44100.wav`

## Notes

- **File Format**: Input files must be UTF-8 encoded. Comments (`#`) and empty lines are skipped.
- **Pause Feature**: Requires `pydub` and `ffmpeg`. Pauses are precise (e.g., 10 seconds) but increase API calls for multiple lines.
- **Credit Usage**: `eleven_turbo_v2` uses 0.5 credits per character. Check credits before processing large files.
- **Filename Collisions**: Automatically appends an index (e.g., `-00001`) if a file exists.
- **Custom API URL**: Set `LABSURL` in `.env` to use a custom ElevenLabs API endpoint. Defaults to `https://api.elevenlabs.io` if not specified.
- **Use Case**: Optimized for generating audio for Bible verses (e.g., `kjv.txt` with 31,102 verses) or smaller files like `sample.txt`, with support for verse ranges and pauses for clarity.

## Limitations

- Requires an ElevenLabs API key and internet connection.
- Pause feature increases processing time for large line ranges due to multiple API calls.
- FFmpeg dependency needed for pause insertion.

## Contributing

Feel free to submit issues or pull requests for enhancements like additional audio formats, performance optimizations, or GUI wrappers.

## License
MIT License. See [LICENSE](LICENSE) for details.

```
Elevenify/
├── elevenify.py
├── README.md
├── requirements.txt
├── .env-example
├── sample.txt
```