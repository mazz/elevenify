import argparse
import os
from pathlib import Path
import re
from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings
from dotenv import load_dotenv
from pydub import AudioSegment
import io

def load_api_key_and_url(args):
    """Load ElevenLabs API key and URL from .env file or command-line argument."""
    load_dotenv()
    api_key = args.key or os.getenv("LABSKEY")
    if not api_key:
        raise ValueError("API key must be provided via --key or LABSKEY in .env file")
    api_url = os.getenv("LABSURL", "https://api.elevenlabs.io")
    return api_key, api_url

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

def get_model_credit_cost(model):
    """Return the credit cost per character for the specified model."""
    if model == "eleven_turbo_v2":
        return 0.5
    return 1.0

def estimate_convertible_lines(client, text, start_line, last_line, model):
    """Estimate lines convertible with remaining credits and for the full file within the specified range."""
    try:
        subscription = client.user.get_subscription()
        credits_remaining = subscription.character_limit - subscription.character_count
        credit_cost = get_model_credit_cost(model)
        
        lines = text.strip().split('\n')
        line_count = 0
        total_chars = 0
        total_credits = 0
        full_file_lines = 0
        full_file_chars = 0
        full_file_credits = 0
        line_number = 0
        
        for line in lines:
            line_number += 1
            if line_number < start_line or line_number > last_line:
                continue
            # Strip trailing comments and whitespace
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            chars = len(line)
            line_credits = chars * credit_cost
            # Full file estimate
            full_file_lines += 1
            full_file_chars += chars
            full_file_credits += line_credits
            # Current credits estimate
            if total_credits + line_credits <= credits_remaining:
                line_count += 1
                total_chars += chars
                total_credits += line_credits
        
        return {
            'credits_remaining': credits_remaining,
            'credit_cost': credit_cost,
            'lines': line_count,
            'characters': total_chars,
            'credits_required': total_credits,
            'full_file_lines': full_file_lines,
            'full_file_characters': full_file_chars,
            'full_file_credits': full_file_credits
        }
    except Exception as e:
        print(f"Error estimating credits: {str(e)}")
        return None

def split_text(text, start_line, last_line):
    """Split text into segments with sequential sample numbers, skipping comment lines and stripping trailing comments within the specified range."""
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
        sample_number += 1
        if line_number < start_line or line_number > last_line:
            continue
        segments.append((sample_number, line))
    # If no segments, try sentence splitting on non-comment text
    if not segments:
        non_comment_text = '\n'.join(line.split('#', 1)[0].strip() for i, line in enumerate(lines, 1) if i >= start_line and i <= last_line and line.split('#', 1)[0].strip())
        sentences = re.split(r'(?<=[.!?])\s+', non_comment_text.strip())
        segments = [(sample_number + i + 1, s) for i, s in enumerate(sentences) if s.strip()]
    return segments

def slugify(text):
    """Normalize text to a URL-friendly slug."""
    slug = re.sub(r'[^a-z0-9.-]', '-', text.lower())
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')

def get_unique_filename(voice_name, khz_rate, bit_rate, extension, prefix=None, start_sample_number=None, end_sample_number=None):
    """Generate unique filename with optional prefix and sample number range."""
    voice_name = re.sub(r'[^a-zA-Z0-9\s]', '_', voice_name)
    max_attempts = 1000  # Prevent infinite loops
    for index in range(max_attempts):
        if start_sample_number is not None and end_sample_number is not None:
            # Non-split mode with range
            base = f"{start_sample_number:05d}-{end_sample_number:05d}-{voice_name}-{khz_rate:.2f}-{bit_rate}"
            if index > 0:
                base += f"-{index:05d}"
        elif start_sample_number is not None:
            # Split mode
            base = f"{start_sample_number:05d}-{voice_name}-{khz_rate:.2f}-{bit_rate}"
            if index > 0:
                base += f"-{index:05d}"
        else:
            # Direct text input
            base = f"{voice_name}-{khz_rate:.2f}-{bit_rate}-{index:05d}"
        if prefix:
            base = f"{prefix}-{base}"
        filename = f"{base}.{extension}"
        filename = slugify(filename)
        if not os.path.exists(filename):
            return filename
    raise ValueError(f"Could not generate unique filename after {max_attempts} attempts")

def process_text_to_audio(client, text, voice_id, voice_name, model, audio_type, rate, prefix=None, start_sample_number=None, end_sample_number=None, pause=None, lines=None):
    """Convert text to audio using ElevenLabs API with custom filename, adding pauses between lines if specified."""
    try:
        output_format, khz_rate, bit_rate, extension = get_output_format(audio_type, rate)
        output_file = get_unique_filename(voice_name, khz_rate, bit_rate, extension, prefix, start_sample_number, end_sample_number)
        
        if pause is not None and lines and len(lines) > 1:
            # Generate audio for each line and concatenate with silence
            audio_segments = []
            for line in lines:
                audio = client.generate(
                    text=line,
                    voice=voice_id,
                    model=model,
                    output_format=output_format
                )
                # Convert audio stream to AudioSegment
                audio_data = b''.join(audio)
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format='mp3')
                audio_segments.append(audio_segment)
            
            # Combine segments with silence
            combined_audio = audio_segments[0]
            silence = AudioSegment.silent(duration=int(pause * 1000))  # Pause in milliseconds
            for segment in audio_segments[1:]:
                combined_audio += silence + segment
            
            # Export combined audio
            combined_audio.export(output_file, format=extension, bitrate=f"{bit_rate}k")
        else:
            # Single API call for no pause or single line
            audio = client.generate(
                text=text,
                voice=voice_id,
                model=model,
                output_format=output_format
            )
            with open(output_file, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
        
        print(f"Generated audio file: {output_file}")
    except Exception as e:
        print(f"Error generating audio: {str(e)}")

def get_file_prefix(filename):
    """Extract and slugify filename prefix, truncated to 10 characters."""
    base = os.path.splitext(os.path.basename(filename))[0]
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
    parser.add_argument("--last-line", type=int, help="Last line number to process (requires --file)")
    parser.add_argument("--estimate-credits", action="store_true", help="Estimate lines convertible with remaining credits (requires --file)")
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
    parser.add_argument("--pause", type=float, help="Pause duration in seconds between lines in non-split mode (requires --file, not --split, 0.0 to 30.0)")
    
    args = parser.parse_args()

    # Validate start-line, last-line, estimate-credits, and pause
    if args.start_line < 1:
        parser.error("--start-line must be a positive integer")
    if args.start_line > 1 and not args.file:
        parser.error("--start-line requires --file")
    if args.last_line is not None:
        if not args.file:
            parser.error("--last-line requires --file")
        if args.last_line < args.start_line:
            parser.error("--last-line must not be less than --start-line")
        if args.last_line < 1:
            parser.error("--last-line must be a positive integer")
    if args.estimate_credits and not args.file:
        parser.error("--estimate-credits requires --file")
    if args.pause is not None:
        if not args.file:
            parser.error("--pause requires --file")
        if args.split:
            parser.error("--pause cannot be used with --split")
        if args.pause < 0.0 or args.pause > 30.0:
            parser.error("--pause must be between 0.0 and 30.0 seconds")

    # Load API key and URL, then initialize client
    api_key, api_url = load_api_key_and_url(args)
    client = ElevenLabs(api_key=api_key, base_url=api_url)

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
        
        # Validate start-line and last-line against file size
        line_count = len(text.strip().split('\n'))
        if args.start_line > line_count:
            print(f"Error: --start-line {args.start_line} exceeds file line count ({line_count})")
            return
        if args.last_line is not None and args.last_line > line_count:
            print(f"Error: --last-line {args.last_line} exceeds file line count ({line_count})")
            return

        # Set last_line to end of file if not specified
        last_line = args.last_line if args.last_line is not None else line_count

        if args.estimate_credits:
            result = estimate_convertible_lines(client, text, args.start_line, last_line, args.model)
            if result:
                print(f"Remaining credits: {result['credits_remaining']:,}")
                print(f"Model: {args.model} ({result['credit_cost']} credits per character)")
                print(f"Lines that can be converted with current credits: {result['lines']}")
                print(f"Characters for convertible lines: {result['characters']:,}")
                print(f"Credits required for convertible lines: {result['credits_required']:,}")
                estimate_label = "Full file estimate"
                if args.start_line > 1 or args.last_line is not None:
                    estimate_label += f" (from line {args.start_line}"
                    if args.last_line is not None:
                        estimate_label += f" to line {args.last_line}"
                    estimate_label += ")"
                print(f"{estimate_label}:")
                print(f"  Total lines: {result['full_file_lines']}")
                print(f"  Total characters: {result['full_file_characters']:,}")
                print(f"  Total credits required: {result['full_file_credits']:,}")
            return

        if args.split:
            segments = split_text(text, args.start_line, last_line)
            for sample_number, sentence in segments:
                process_text_to_audio(client, sentence, voice_id, voice_name, args.model, args.type, args.rate, prefix, start_sample_number=sample_number)
        else:
            # Filter out comment lines and lines outside start_line to last_line for non-split mode
            lines = text.strip().split('\n')
            non_comment_lines = []
            sample_number = 0
            first_sample_number = None
            last_sample_number = None
            line_number = 0
            for line in lines:
                line_number += 1
                # Strip trailing comments
                line = line.split('#', 1)[0].strip()
                if not line:
                    continue
                sample_number += 1
                if line_number < args.start_line or line_number > last_line:
                    continue
                if first_sample_number is None:
                    first_sample_number = sample_number
                last_sample_number = sample_number
                non_comment_lines.append(line)
            
            if non_comment_lines:
                # Use pydub for pause if specified, otherwise join with space
                if args.pause is not None and len(non_comment_lines) > 1:
                    process_text_to_audio(client, None, voice_id, voice_name, args.model, args.type, args.rate, prefix, first_sample_number, last_sample_number, pause=args.pause, lines=non_comment_lines)
                else:
                    combined_text = ' '.join(non_comment_lines)
                    process_text_to_audio(client, combined_text, voice_id, voice_name, args.model, args.type, args.rate, prefix, first_sample_number, last_sample_number)
            else:
                print("No non-comment lines to process in the specified line range.")
    else:
        process_text_to_audio(client, args.text, voice_id, voice_name, args.model, args.type, args.rate)

if __name__ == "__main__":
    main()