"""
Speech Ingestion Module for Loom.
Handles audio-to-text conversion and speech-aware knowledge extraction.

Supports multiple ASR backends:
- OpenAI Whisper (local or API)
- Google Speech-to-Text
- Azure Speech Services
- Vosk (offline)

Speech provenance is tracked for all extracted knowledge.
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ASRBackend(Enum):
    """Available speech recognition backends."""
    WHISPER_LOCAL = "whisper_local"
    WHISPER_API = "whisper_api"
    GOOGLE = "google"
    AZURE = "azure"
    VOSK = "vosk"
    MOCK = "mock"  # For testing


@dataclass
class TranscriptSegment:
    """A segment of transcribed speech."""
    text: str
    start_time: float = 0.0  # seconds
    end_time: float = 0.0
    confidence: float = 1.0
    speaker_id: Optional[str] = None
    language: str = "en"


@dataclass
class Transcript:
    """Complete transcript of an audio file or stream."""
    segments: List[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""
    audio_duration: float = 0.0
    language: str = "en"
    backend_used: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "segments": [
                {
                    "text": s.text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "confidence": s.confidence,
                    "speaker_id": s.speaker_id,
                    "language": s.language,
                }
                for s in self.segments
            ],
            "full_text": self.full_text,
            "audio_duration": self.audio_duration,
            "language": self.language,
            "backend_used": self.backend_used,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SpeechProvenance:
    """Provenance information for speech-derived facts."""
    transcript_id: str
    segment_index: int
    segment_text: str
    start_time: float
    end_time: float
    confidence: float
    speaker_id: Optional[str]
    audio_source: Optional[str] = None  # filename or stream ID

    def to_dict(self) -> dict:
        return {
            "source_type": "speech",
            "transcript_id": self.transcript_id,
            "segment_index": self.segment_index,
            "segment_text": self.segment_text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
            "speaker_id": self.speaker_id,
            "audio_source": self.audio_source,
            "created_at": datetime.utcnow().isoformat(),
            "premises": [],
            "rule_id": None,
            "derivation_id": None,
        }


class SpeechProcessor:
    """
    Main class for speech ingestion and processing.

    Handles:
    - Audio transcription via multiple backends
    - Transcript chunking and parsing
    - Speech provenance tracking
    - Streaming support
    """

    def __init__(self, loom, backend: ASRBackend = ASRBackend.MOCK):
        """
        Initialize the speech processor.

        Args:
            loom: The Loom instance for knowledge storage
            backend: Which ASR backend to use
        """
        self.loom = loom
        self.backend = backend
        self._backend_instance = None
        self._transcript_counter = 0

        # Initialize the ASR backend
        self._init_backend()

    def _init_backend(self):
        """Initialize the selected ASR backend."""
        if self.backend == ASRBackend.WHISPER_LOCAL:
            self._backend_instance = WhisperLocalBackend()
        elif self.backend == ASRBackend.WHISPER_API:
            self._backend_instance = WhisperAPIBackend()
        elif self.backend == ASRBackend.VOSK:
            self._backend_instance = VoskBackend()
        elif self.backend == ASRBackend.MOCK:
            self._backend_instance = MockBackend()
        else:
            logger.warning(f"Backend {self.backend} not yet implemented, using mock")
            self._backend_instance = MockBackend()

    def transcribe_file(self, audio_path: str) -> Transcript:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to the audio file (WAV, MP3, etc.)

        Returns:
            Transcript object with segments and full text
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self._transcript_counter += 1
        transcript_id = f"transcript_{self._transcript_counter}_{int(time.time())}"

        # Use the backend to transcribe
        transcript = self._backend_instance.transcribe(audio_path)
        transcript.metadata["transcript_id"] = transcript_id
        transcript.metadata["audio_source"] = audio_path

        return transcript

    def transcribe_stream(self, audio_stream, chunk_callback: Callable = None):
        """
        Transcribe a streaming audio source.

        Args:
            audio_stream: Audio stream (e.g., microphone input)
            chunk_callback: Optional callback for each transcribed chunk

        Yields:
            TranscriptSegment objects as they are transcribed
        """
        if hasattr(self._backend_instance, 'transcribe_stream'):
            for segment in self._backend_instance.transcribe_stream(audio_stream):
                if chunk_callback:
                    chunk_callback(segment)
                yield segment
        else:
            logger.warning(f"Backend {self.backend} does not support streaming")

    def process_transcript(self, transcript: Transcript,
                          process_immediately: bool = True) -> Dict[str, Any]:
        """
        Process a transcript through Loom to extract knowledge.

        Args:
            transcript: The transcript to process
            process_immediately: Whether to process through Loom immediately

        Returns:
            Dict with processing results including extracted facts
        """
        results = {
            "transcript_id": transcript.metadata.get("transcript_id"),
            "segments_processed": 0,
            "facts_extracted": 0,
            "responses": [],
        }

        for i, segment in enumerate(transcript.segments):
            if not segment.text.strip():
                continue

            # Create speech provenance for this segment
            provenance = SpeechProvenance(
                transcript_id=transcript.metadata.get("transcript_id", ""),
                segment_index=i,
                segment_text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                confidence=segment.confidence,
                speaker_id=segment.speaker_id,
                audio_source=transcript.metadata.get("audio_source"),
            )

            if process_immediately:
                # Process through Loom parser with speech provenance
                response = self._process_segment(segment.text, provenance)
                results["responses"].append({
                    "segment": i,
                    "text": segment.text,
                    "response": response,
                })
                results["segments_processed"] += 1

        return results

    def _process_segment(self, text: str, provenance: SpeechProvenance) -> str:
        """
        Process a single transcript segment through Loom.

        Args:
            text: The text to process
            provenance: Speech provenance information

        Returns:
            Loom's response
        """
        # Store provenance context for this processing
        # The parser will use this when adding facts
        self.loom._current_speech_provenance = provenance.to_dict()

        try:
            response = self.loom.process(text)
        finally:
            # Clear provenance context
            self.loom._current_speech_provenance = None

        return response

    def process_audio_file(self, audio_path: str) -> Dict[str, Any]:
        """
        Convenience method: transcribe and process an audio file.

        Args:
            audio_path: Path to the audio file

        Returns:
            Dict with transcript and processing results
        """
        transcript = self.transcribe_file(audio_path)
        results = self.process_transcript(transcript)
        results["transcript"] = transcript.to_dict()
        return results

    def get_speech_facts(self) -> List[dict]:
        """
        Get all facts that were derived from speech input.

        Returns:
            List of facts with speech provenance
        """
        speech_facts = []

        # Query storage for facts with speech provenance
        if hasattr(self.loom.storage, 'get_facts_by_source_type'):
            speech_facts = self.loom.storage.get_facts_by_source_type("speech")

        return speech_facts


# ==================== ASR BACKENDS ====================

class ASRBackendBase:
    """Base class for ASR backends."""

    def transcribe(self, audio_path: str) -> Transcript:
        """Transcribe an audio file."""
        raise NotImplementedError

    def transcribe_stream(self, audio_stream):
        """Transcribe streaming audio."""
        raise NotImplementedError


class MockBackend(ASRBackendBase):
    """Mock backend for testing without actual ASR."""

    def transcribe(self, audio_path: str) -> Transcript:
        """Return a mock transcript."""
        # For testing, just return placeholder
        return Transcript(
            segments=[
                TranscriptSegment(
                    text="This is a mock transcript.",
                    start_time=0.0,
                    end_time=2.0,
                    confidence=1.0,
                ),
                TranscriptSegment(
                    text="Dogs are mammals.",
                    start_time=2.0,
                    end_time=4.0,
                    confidence=0.95,
                ),
            ],
            full_text="This is a mock transcript. Dogs are mammals.",
            audio_duration=4.0,
            backend_used="mock",
        )


class WhisperLocalBackend(ASRBackendBase):
    """OpenAI Whisper running locally."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None

    def _load_model(self):
        """Lazy load the Whisper model."""
        if self.model is None:
            try:
                import whisper
                self.model = whisper.load_model(self.model_size)
                logger.info(f"Loaded Whisper model: {self.model_size}")
            except ImportError:
                raise ImportError("whisper not installed. Install with: pip install openai-whisper")

    def transcribe(self, audio_path: str) -> Transcript:
        """Transcribe using local Whisper."""
        self._load_model()

        result = self.model.transcribe(audio_path)

        segments = []
        for seg in result.get("segments", []):
            segments.append(TranscriptSegment(
                text=seg["text"].strip(),
                start_time=seg["start"],
                end_time=seg["end"],
                confidence=seg.get("avg_logprob", 0.0),
                language=result.get("language", "en"),
            ))

        return Transcript(
            segments=segments,
            full_text=result["text"],
            audio_duration=segments[-1].end_time if segments else 0.0,
            language=result.get("language", "en"),
            backend_used="whisper_local",
        )


class WhisperAPIBackend(ASRBackendBase):
    """OpenAI Whisper via API."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def transcribe(self, audio_path: str) -> Transcript:
        """Transcribe using OpenAI Whisper API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed. Install with: pip install openai")

        client = OpenAI(api_key=self.api_key)

        with open(audio_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
            )

        segments = []
        for seg in result.segments:
            segments.append(TranscriptSegment(
                text=seg.text.strip(),
                start_time=seg.start,
                end_time=seg.end,
                confidence=seg.avg_logprob if hasattr(seg, 'avg_logprob') else 1.0,
            ))

        return Transcript(
            segments=segments,
            full_text=result.text,
            audio_duration=result.duration,
            language=result.language,
            backend_used="whisper_api",
        )


class VoskBackend(ASRBackendBase):
    """Vosk offline speech recognition."""

    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.model = None

    def _load_model(self):
        """Lazy load the Vosk model."""
        if self.model is None:
            try:
                from vosk import Model, KaldiRecognizer
                if self.model_path:
                    self.model = Model(self.model_path)
                else:
                    # Try to use default small model
                    self.model = Model(lang="en-us")
                logger.info("Loaded Vosk model")
            except ImportError:
                raise ImportError("vosk not installed. Install with: pip install vosk")

    def transcribe(self, audio_path: str) -> Transcript:
        """Transcribe using Vosk."""
        self._load_model()

        import wave
        from vosk import KaldiRecognizer

        wf = wave.open(audio_path, "rb")
        rec = KaldiRecognizer(self.model, wf.getframerate())
        rec.SetWords(True)

        results = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    results.append(result)

        # Get final result
        final = json.loads(rec.FinalResult())
        if final.get("text"):
            results.append(final)

        segments = []
        for i, r in enumerate(results):
            segments.append(TranscriptSegment(
                text=r["text"],
                start_time=float(i),  # Vosk doesn't always provide timing
                end_time=float(i + 1),
                confidence=r.get("confidence", 1.0),
            ))

        full_text = " ".join(s.text for s in segments)

        return Transcript(
            segments=segments,
            full_text=full_text,
            audio_duration=wf.getnframes() / wf.getframerate(),
            backend_used="vosk",
        )

    def transcribe_stream(self, audio_stream):
        """Streaming transcription with Vosk."""
        self._load_model()

        from vosk import KaldiRecognizer

        rec = KaldiRecognizer(self.model, 16000)
        rec.SetWords(True)

        for data in audio_stream:
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    yield TranscriptSegment(
                        text=result["text"],
                        confidence=result.get("confidence", 1.0),
                    )

        # Final result
        final = json.loads(rec.FinalResult())
        if final.get("text"):
            yield TranscriptSegment(
                text=final["text"],
                confidence=final.get("confidence", 1.0),
            )
