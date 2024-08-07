# Standard imports
import logging
from io import BytesIO
from typing import Any, Optional

# Third-party imports
import simpleaudio
import sounddevice  # suppress ALSA warnings # noqa: F401
from gtts import gTTS
from overrides import override
from pydub import AudioSegment

# Local imports
from ..base import AbstractTextToSpeech

# Create the default logger
logging.basicConfig(level=logging.INFO)
DEFAULT_LOGGER = logging.getLogger(__name__)


class GTTSTextToSpeech(AbstractTextToSpeech):
    """
    Text-to-speech engine using gTTS.
    """

    @override  # inherit the docstring from the parent class
    def __init__(self, logger: logging.Logger = DEFAULT_LOGGER):
        super().__init__(logger)
        self._can_say_async = True

        # Initialize the voices.
        # https://gtts.readthedocs.io/en/latest/module.html#gtts.lang.tts_langs
        self._voice_ids = [
            "com",  # Default
            "us",  # United States
            "com.au",  # Australia
            "co.uk",  # United Kingdom
            "ca",  # Canada
            "co.in",  # India
            "ie",  # Ireland
            "co.za",  # South Africa
            "com.ng",  # Nigeria
        ]
        self.voice_id = "com"
        self._playback: Optional[simpleaudio.PlayObject] = None

    def __synthesize_and_play_text(self, text: str) -> simpleaudio.PlayObject:
        """
        Get the playback object for the given text.

        Parameters
        ----------
        text : str
            The text to speak.

        Returns
        -------
        simpleaudio.PlayObject
            The playback object.
        """
        tts = gTTS(text=text, lang="en", tld=self.voice_id, slow=self.is_slow)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio = AudioSegment.from_file(fp, format="mp3")
        self._playback = simpleaudio.play_buffer(
            audio.raw_data, audio.channels, audio.sample_width, audio.frame_rate
        )

    @override  # inherit the docstring from the parent class
    def say_async(self, text: str) -> None:
        self.__synthesize_and_play_text(text)

    @override  # inherit the docstring from the parent class
    def is_speaking(self) -> bool:
        if self._playback is None:
            return False
        if not self._playback.is_playing():
            self._playback = None
            return False
        return True

    @override  # inherit the docstring from the parent class
    def say(self, text: str) -> None:
        self.__synthesize_and_play_text(text)
        self._playback.wait_done()
        self._playback = None

    @override  # inherit the docstring from the parent class
    def stop(self):
        if self._playback is not None:
            self._playback.stop()
            self._playback = None

    @override  # inherit the docstring from the parent class
    def save_to_file(self, text: str, filepath: str, **kwargs: Any) -> None:
        if not self.is_file_type_supported(filepath):
            return
        tts = gTTS(text=text, lang="en", tld=self.voice_id, slow=self.is_slow)
        tts.save(filepath)
