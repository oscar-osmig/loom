# Speech Processing

## Overview

The speech module handles audio-to-text conversion with pluggable ASR (Automatic Speech Recognition) backends and tracks speech provenance for all extracted knowledge. Multiple backends allow flexibility:

- **Whisper Local** — OpenAI's Whisper model running locally (best accuracy, requires GPU/CPU)
- **Whisper API** — OpenAI Whisper via HTTP API (requires OPENAI_API_KEY)
- **Vosk** — Offline speech recognition (lightweight, lower accuracy)
- **Google** — Google Cloud Speech-to-Text (placeholder, not implemented)
- **Azure** — Azure Speech Services (placeholder, not implemented)
- **Mock** — Testing without actual ASR

Transcribed speech is processed through the parser with full provenance tracking: transcript ID, segment timing, confidence score, and speaker ID.

## Key Concepts

### Backends & ASRBackendBase
Each backend implements `transcribe()` and optionally `transcribe_stream()`:
- Loads models lazily (Whisper/Vosk)
- Returns `Transcript` object with segments
- Handles timing and confidence scores

### Transcript & TranscriptSegment
- **Transcript**: Complete audio transcription with metadata
  - `segments`: List of TranscriptSegment
  - `full_text`: Complete transcribed text
  - `audio_duration`: Length of audio in seconds
  - `backend_used`: Which ASR backend produced this
  - `metadata`: Custom fields (transcript_id, audio_source, etc.)

- **TranscriptSegment**: A chunk of transcribed speech
  - `text`: The actual words
  - `start_time`, `end_time`: Timing in seconds
  - `confidence`: ASR confidence (0.0–1.0)
  - `speaker_id`: Optional speaker identifier
  - `language`: ISO language code

### Speech Provenance
Metadata attached to facts derived from speech:
- `transcript_id`: Which transcript this came from
- `segment_index`: Which segment in the transcript
- `segment_text`: The actual spoken words
- `start_time`, `end_time`: Timing within audio
- `confidence`: ASR confidence score (affects fact confidence)
- `speaker_id`: Who said this
- `audio_source`: Filename or stream identifier

## API / Public Interface

### SpeechProcessor

```python
__init__(loom, backend: ASRBackend = ASRBackend.MOCK)

# Transcription
transcribe_file(audio_path: str) -> Transcript
transcribe_stream(audio_stream, chunk_callback: Callable = None) -> Iterator[TranscriptSegment]

# Processing & Knowledge Extraction
process_transcript(transcript: Transcript, process_immediately: bool = True) -> Dict[str, Any]
process_audio_file(audio_path: str) -> Dict[str, Any]  # Convenience: transcribe + process

# Querying
get_speech_facts() -> List[dict]  # All facts with speech provenance
```

Returns from `process_transcript()`:
```python
{
    "transcript_id": str,
    "segments_processed": int,
    "facts_extracted": int,
    "responses": List[dict]  # {segment, text, response}
}
```

### Transcript (dataclass)

```python
segments: List[TranscriptSegment]
full_text: str
audio_duration: float
language: str = "en"
backend_used: str  # Which ASR backend
created_at: datetime
metadata: Dict[str, Any]

# Methods
to_dict() -> dict  # Serialize for storage
```

### TranscriptSegment (dataclass)

```python
text: str
start_time: float = 0.0     # seconds
end_time: float = 0.0
confidence: float = 1.0     # ASR confidence 0–1
speaker_id: Optional[str] = None
language: str = "en"
```

### SpeechProvenance (dataclass)

```python
transcript_id: str
segment_index: int
segment_text: str
start_time: float
end_time: float
confidence: float
speaker_id: Optional[str]
audio_source: Optional[str] = None

# Methods
to_dict() -> dict  # Serialize to storage format
```

### ASRBackendBase (abstract)

```python
transcribe(audio_path: str) -> Transcript  # Abstract
transcribe_stream(audio_stream) -> Iterator[TranscriptSegment]  # Optional
```

### Backend Implementations

#### WhisperLocalBackend
```python
__init__(model_size: str = "base")  # base, small, medium, large
transcribe(audio_path: str) -> Transcript
# Supports: MP3, WAV, M4A, FLAC, OGG, etc.
```

#### WhisperAPIBackend
```python
__init__(api_key: str = None)  # Defaults to OPENAI_API_KEY env
transcribe(audio_path: str) -> Transcript
# Requires: openai library, valid API key
```

#### VoskBackend
```python
__init__(model_path: str = None)  # Path to Vosk model, or use default
transcribe(audio_path: str) -> Transcript
transcribe_stream(audio_stream) -> Iterator[TranscriptSegment]
# Lightweight, offline; lower accuracy than Whisper
```

#### MockBackend
```python
transcribe(audio_path: str) -> Transcript
# Returns hardcoded test data for testing
```

## How It Works

### Single File Transcription

```
Audio file ("speech.wav")
    │
    ├─ transcribe_file(path)
    │   └─ Backend.transcribe(path) → Transcript
    │       ├─ Load audio
    │       ├─ Segment & transcribe
    │       └─ Return with timings & confidence
    │
    ├─ process_transcript(transcript)
    │   └─ For each segment:
    │       ├─ Create SpeechProvenance
    │       ├─ Set loom._current_speech_provenance
    │       ├─ Call parser.parse(segment_text)
    │       └─ Parser adds facts with speech provenance
    │
    └─ Return results {segments_processed, facts_extracted, responses}
```

### Backend Selection & Lazy Loading

1. `__init__` calls `_init_backend()` which sets `self._backend_instance`
2. Whisper/Vosk models are **lazy-loaded** on first transcribe call
3. Missing dependencies raise ImportError with installation instructions
4. Mock backend is always available (testing fallback)

### Provenance Tracking in Parser

When processing a transcript segment:

```python
# SpeechProcessor._process_segment()
self.loom._current_speech_provenance = provenance.to_dict()
response = self.loom.process(text)  # Parser sees _current_speech_provenance
self.loom._current_speech_provenance = None
```

Parser should use `_current_speech_provenance` when calling `add_fact()` so that facts include:
```python
{
    "source_type": "speech",
    "transcript_id": "transcript_1_1234567890",
    "segment_index": 0,
    "segment_text": "Dogs are mammals",
    "start_time": 0.0,
    "end_time": 2.5,
    "confidence": 0.95,
    "speaker_id": None,
    "audio_source": "speech.wav"
}
```

### Streaming (Vosk)

```python
# Vosk supports streaming for live input
for segment in processor.transcribe_stream(mic_input):
    print(f"Heard: {segment.text} (confidence {segment.confidence:.2f})")
    # Could process each segment as it arrives
```

## Dependencies

**Imports from:**
- `brain.Loom` — knowledge system for processing
- Standard library: `os`, `time`, `logging`, `datetime`, `json`
- Optional backends: `openai`, `whisper`, `vosk`, `google.cloud.speech`, `azure.cognitiveservices`

**Used by:**
- CLI (potential future: `speech <audio_file>` command)
- Web API (potential future: audio upload endpoint)
- Parser (when `_current_speech_provenance` is set)

**Data sources:**
- Audio files on disk or streaming input
- ASR backend models (Whisper/Vosk downloaded on first use)

## Examples

### Local Whisper Transcription

```python
from loom import Loom
from loom.speech import SpeechProcessor, ASRBackend

loom = Loom("speech_example")
processor = SpeechProcessor(loom, backend=ASRBackend.WHISPER_LOCAL)

# Transcribe a file
transcript = processor.transcribe_file("sample.wav")
print(f"Full text: {transcript.full_text}")

# Process each segment with provenance
results = processor.process_transcript(transcript)
print(f"Processed {results['segments_processed']} segments")
print(f"Extracted {results['facts_extracted']} facts")

# Each fact now has speech provenance
speech_facts = processor.get_speech_facts()
for fact in speech_facts:
    print(f"From {fact['audio_source']} at {fact['start_time']}s: {fact['segment_text']}")
```

### Whisper API with OpenAI

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-..."

processor = SpeechProcessor(loom, backend=ASRBackend.WHISPER_API)
results = processor.process_audio_file("meeting.mp3")
# Uses OpenAI API to transcribe, then processes through Loom
```

### Vosk Streaming from Microphone

```python
# Hypothetical: streaming from microphone
processor = SpeechProcessor(loom, backend=ASRBackend.VOSK)

mic_input = get_mic_stream()  # Some audio stream
for segment in processor.transcribe_stream(mic_input):
    if segment.confidence > 0.8:  # High confidence
        loom.process(segment.text)
        print(f"✓ Learned from: {segment.text}")
```

### Multi-speaker Meeting Transcription

```python
transcript = processor.transcribe_file("meeting.wav")

# Segments may have speaker_id if backend supports it
for segment in transcript.segments:
    if segment.speaker_id:
        print(f"Speaker {segment.speaker_id}: {segment.text}")
    
# Process with speaker context
results = processor.process_transcript(transcript)
# Facts include speaker_id for multi-party learning
```

### Testing with Mock Backend

```python
# Unit tests don't need actual audio or ASR
processor = SpeechProcessor(loom, backend=ASRBackend.MOCK)
transcript = processor.transcribe_file("fake.wav")
# Returns hardcoded test data:
# "This is a mock transcript. Dogs are mammals."

results = processor.process_transcript(transcript)
# Process runs through parser; no external API calls
```

## Integration Notes

### Wiring into CLI
Currently skeleton; potential integration:
```bash
> speech samples/dogs.wav
```

### Wiring into Web API
Potential endpoint:
```
POST /api/speech
- Body: audio/wav (multipart)
- Returns: {transcript, facts_extracted, responses}
```

### Parser Integration
Parser needs to check `_current_speech_provenance` during `add_fact()`:
```python
# In parser.add_fact() or similar
provenance_context = getattr(self.loom, '_current_speech_provenance', None)
if provenance_context:
    # Merge provenance_context into fact properties
    fact.properties.update(provenance_context)
```

Without this, facts extracted from speech will lose provenance info.
