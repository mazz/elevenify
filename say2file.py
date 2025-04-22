import argparse
import os
from pathlib import Path
import re
from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings
from dotenv import load_dotenv

def load_api_key(args):
    """Load ElevenLabs API key from .env file or command-line argument."""
    load_dotenv()
    api_key = args.key or os.getenv("LABSKEY")
    if not api_key:
        raise ValueError("API key must be provided via --key or LABSKEY in .env file")
    return api_key

def list_voices(client):
    """List available ElevenLabs voices with their IDs."""
    voices = client.voices.get_all().voices
    print("Available ElevenLabs voices:")
    for voice in voices:
        print(f" - {voice.name} (ID: {voice.voice_id})")
    return voices

def check_credits(client):
    """Display remaining ElevenLabs character credits."""
    try:
        subscription = client.user.get_subscription()
        credits_used = subscription.character_count
        credits_limit = subscription.character_limit
        credits_remaining = credits_limit - credits_used
        print(f"Credits used: {credits_used:,} characters")
        print(f"Credits limit: {credits_limit:,} characters")
        print(f"Credits remaining: {credits_remaining:,} characters")
    except Exception as e:
        print(f"Error fetching credits: {str(e)}")

def split_text(text, start_line):
    """Split text into segments with sequential sample numbers, skipping comment lines and stripping trailing comments."""
    # Split on newlines and track sample numbers
    lines = text.strip().split('\n')
    segments = []
    sample_number = 0
    line_number = 0
    for line in lines:
        line_number += 1
        # Strip trailing comments
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        if line_number < start_line:
            sample_number += 1
            continue
        sample_number += 1
        segments.append((sample_number, line))
    # If no segments, try sentence splitting on non-comment text
    if not segments:
        non_comment_text = '\n'.join(line.split('#', 1)[0].strip() for i, line in enumerate(lines, 1) if i >= start_line and line.split('#', 1)[0].strip())
        sentences = re.split(r'(?<=[.!?])\s+', non_comment_text.strip())
        segments = [(sample_number + i + 1, s) for i, s in enumerate(sentences) if s.strip()]
    return segments

def slugify(text):
    """Normalize text to a URL-friendly slug."""
    # Convert to lowercase, replace non-alphanumeric (except hyphens and dots) with hyphen
    slug = re.sub(r'[^a-z0-9.-]', '-', text.lower())
    # Replace multiple hyphens with a single hyphen
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    return slug.strip('-')

def get_unique_filename(voice_name, khz_rate, bit_rate, extension, prefix=None, sample_number=None):
    """Generate unique filename with optional prefix and sample number."""
    voice_name = re.sub(r'[^a-zA-Z0-9\s]', '_', voice_name)  # Sanitize voice name
    index = 0
    while True:
        # Construct base filename
        if sample_number is not None:
            base = f"{sample_number:05d}-{voice_name}-{khz_rate:.2f}-{bit_rate}"
        else:
            base = f"{voice_name}-{khz_rate:.2f}-{bit_rate}-{index:05d}"
        # Add prefix if provided
        if prefix:
            base = f"{prefix}-{base}"
        filename = f"{base}.{extension}"
        filename = slugify(filename)
        if not os.path.exists(filename):
            return filename
        # Only increment index if no sample number (for non-split or direct text)
        if sample_number is None:
            index += 1
        else:
            # For split with sample number, append index for existing files
            base = f"{base}-{index:05d}"
            filename = f"{base}.{extension}"
            filename = slugify(filename)
            if not os.path.exists(filename):
                return filename
            index += 1

def process_text_to_audio(client, text, voice_id, voice_name, model, audio_type, rate, prefix=None, sample_number=None):
    """Convert text to audio using ElevenLabs API with custom filename."""
    try:
        output_format, khz_rate, bit_rate, extension = get_output_format(audio_type, rate)
        output_file = get_unique_filename(voice_name, khz_rate, bit_rate, extension, prefix, sample_number)
        audio = client.generate(
            text=text,
            voice=voice_id,
            model=model,
            output_format=output_format
        )
        # Save the audio stream to file
        with open(output_file, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        print(f"Generated audio file: {output_file}")
    except Exception as e:
        print(f"Error generating audio: {str(e)}")

def get_file_prefix(filename):
    """Extract and slugify filename prefix, truncated to 10 characters."""
    # Get filename without extension
    base = os.path.splitext(os.path.basename(filename))[0]
    # Slugify and truncate
    slug = slugify(base)
    return slug[:10]

def get_output_format(audio_type, rate):
    """Map audio type and rate to valid ElevenLabs output format and extract khz/bitrate."""
    valid_formats = {
        'mp3': {
            32: ('mp3_22050_32', 22.05, 32, 'mp3'),
            64: ('mp3_44100_64', 44.1, 64, 'mp3'),
            96: ('mp3_44100_96', 44.1, 96, 'mp3'),
            128: ('mp3_44100_128', 44.1, 128, 'mp3'),
            192: ('mp3_44100_192', 44.1, 192, 'mp3')
        },
        'pcm': {
            8000: ('pcm_8000', 8.0, 8000, 'wav'),
            16000: ('pcm_16000', 16.0, 16000, 'wav'),
            22050: ('pcm_22050', 22.05, 22050, 'wav'),
            24000: ('pcm_24000', 24.0, 24000, 'wav'),
            44100: ('pcm_44100', 44.1, 44100, 'wav')
        },
        'ulaw': {
            8000: ('ulaw_8000', 8.0, 8000, 'ulaw')
        },
        'alaw': {
            8000: ('alaw_8000', 8.0, 8000, 'alaw')
        },
        'opus': {
            32: ('opus_48000_32', 48.0, 32, 'oga'),
            64: ('opus_48000_64', 48.0, 64, 'oga'),
            96: ('opus_48000_96', 48.0, 96, 'oga'),
            128: ('opus_48000_128', 48.0, 128, 'oga'),
            192: ('opus_48000_192', 48.0, 192, 'oga')
        }
    }
    if audio_type not in valid_formats or rate not in valid_formats[audio_type]:
        raise ValueError(f"Invalid {audio_type} rate {rate}. Valid options: {list(valid_formats[audio_type].keys())}")
    return valid_formats[audio_type][rate]

def main():
    parser = argparse.ArgumentParser(description="Convert text to audio using ElevenLabs API")
    parser.add_argument("text", nargs="?", help="Text to convert to audio")
    parser.add_argument("--file", "-f", help="Input text file")
    parser.add_argument("--split", "-s", action="store_true", help="Split input text file into multiple output files")
    parser.add_argument("--start-line", type=int, default=1, help="Line number to start processing from (requires --file)")
    parser.add_argument("--voice", "-w", default="Adam", help="Voice name or ID (default: Adam)")
    parser.add_argument("--model", "-m", default="eleven_multilingual_v2", 
                       choices=["eleven_monolingual_v1", "eleven_multilingual_v1", "eleven_multilingual_v2", "eleven_turbo_v2"], 
                       help="Model to use")
    parser.add_argument("--type", "-t", default="mp3", 
                       choices=["mp3", "pcm", "ulaw", "alaw", "opus"], 
                       help="Audio output type")
    parser.add_argument("--rate", "-r", type=int, 
                       choices=[32, 64, 96, 128, 192, 8000, 16000, 22050, 24000, 44100], 
                       default=128, help="Bitrate for mp3/opus or sample rate for pcm/ulaw/alaw")
    parser.add_argument("--key", "-k", help="ElevenLabs API key")
    parser.add_argument("--list", "-l", action="store_true", help="List available voices")
    parser.add_argument("--credits", "-c", action="store_true", help="Show remaining character credits")
    
    args = parser.parse_args()

    # Validate start-line
    if args.start_line < 1:
        parser.error("--start-line must be a positive integer")
    if args.start_line > 1 and not args.file:
        parser.error("--start-line requires --file")

    # Load API key and initialize client
    api_key = load_api_key(args)
    client = ElevenLabs(api_key=api_key)

    # Check credits if requested
    if args.credits:
        check_credits(client)
        return

    # List voices if requested
    if args.list:
        list_voices(client)
        return

    # Validate input
    if not args.text and not args.file:
        parser.error("Either text or --file must be provided")

    # Get voice ID and name
    voices_by_name = {v.name: (v.voice_id, v.name) for v in client.voices.get_all().voices}
    voices_by_id = {v.voice_id: (v.voice_id, v.name) for v in client.voices.get_all().voices}
    
    if args.voice in voices_by_name:
        voice_id, voice_name = voices_by_name[args.voice]
    elif args.voice in voices_by_id:
        voice_id, voice_name = voices_by_id[args.voice]
    else:
        raise ValueError(f"Voice '{args.voice}' not found. Use --list to see available voices.")

    # Get prefix if using a file
    prefix = None
    if args.file:
        prefix = get_file_prefix(args.file)

    # Process input
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Validate start-line against file size
        line_count = len(text.strip().split('\n'))
        if args.start_line > line_count:
            print(f"Error: --start-line {args.start_line} exceeds file line count ({line_count})")
            return

        if args.split:
            segments = split_text(text, args.start_line)
            for sample_number, sentence in segments:
                process_text_to_audio(client, sentence, voice_id, voice_name, args.model, args.type, args.rate, prefix, sample_number)
        else:
            # Filter out comment lines and lines before start_line for non-split mode
            lines = text.strip().split('\n')
            non_comment_lines = [line.split('#', 1)[0].strip() for i, line in enumerate(lines, 1) if i >= args.start_line and line.split('#', 1)[0].strip()]
            if non_comment_lines:
                combined_text = ' '.join(non_comment_lines)
                process_text_to_audio(client, combined_text, voice_id, voice_name, args.model, args.type, args.rate, prefix)
            else:
                print("No non-comment lines to process from the specified start line.")
    else:
        process_text_to_audio(client, args.text, voice_id, voice_name, args.model, args.type, args.rate)

if __name__ == "__main__":
    main()
