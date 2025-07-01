#!/usr/bin/env python3
import houndify
import sys
import pyttsx3
from playsound import playsound
import base64
import time
import pyaudio
import wave
import io
from google.cloud import speech
from google.oauth2 import service_account

# ========== Google STT Setup ==========
credentials = service_account.Credentials.from_service_account_file('./Credentials.json')
client_stt = speech.SpeechClient(credentials=credentials)

# ========== Config ==========
BUFFER_SIZE = 1024
WAKEWORD = "hello adam"
EXIT_PHRASE = "bye adam"

CLIENT_ID = sys.argv[1]
CLIENT_KEY = sys.argv[2]

MODE_EXIT_ON_BYE = True   # True = exit whole program; False = return to Google STT

# ========== Google STT Recording ==========
def record_audio():
    print("🎙️ Listening for wakeword...")

    RATE = 16000
    CHANNELS = 1
    CHUNK = 1024
    RECORD_SECONDS = 5

    p = pyaudio.PyAudio()
    stream_stt = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream_stt.read(CHUNK)
        frames.append(data)

    stream_stt.stop_stream()
    stream_stt.close()
    p.terminate()

    wav_buffer = io.BytesIO()
    wf = wave.open(wav_buffer, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    wav_buffer.seek(0)
    return wav_buffer.read()

# ========== Google STT Recognize ==========
def recognize_audio(audio_bytes):
    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        model="command_and_search",
        speech_contexts=[
            speech.SpeechContext(phrases=[WAKEWORD], boost=20.0)
        ]
    )

    response = client_stt.recognize(config=config, audio=audio)

    if not response.results:
        return "", 0.0

    result = response.results[0].alternatives[0]
    return result.transcript.lower(), result.confidence

# ========== Houndify Listener ==========
class MyListener(houndify.HoundListener):
    def __init__(self, stream):
        self.should_exit = False
        self.stream = stream

    def onPartialTranscript(self, transcript):
        print("Partial transcript: " + transcript)
        if EXIT_PHRASE in transcript.lower():
            print("🛑 Detected exit phrase '{}', exiting...".format(EXIT_PHRASE))
            self.should_exit = True

    def onFinalResponse(self, response):
        res = response['AllResults'][0]
        speak = res["SpokenResponse"]
        print("🔊 " + speak)

        if 'ResponseAudioBytes' in res:
            aud = res['ResponseAudioBytes']
            decode_string = base64.b64decode(aud)
            with open("output.wav", "wb") as wav_file:
                wav_file.write(decode_string)

            # Pause PyAudio stream to prevent echo
            self.stream.stop_stream()

            playsound('output.wav')

            # Resume PyAudio stream
            self.stream.start_stream()

        if 'ConversationState' in res:
            conversationState = res["ConversationState"]
            client_houndify.setConversationState(conversationState)

    def onError(self, err):
        print("Error: " + str(err))

# ========== Houndify Client Setup ==========
requestInfo = {
    'ResponseAudioVoice': 'Mia',
    'ResponseAudioShortOrLong': 'Short',
    'ResponseAudioEncoding': 'Speex'
}

client_houndify = houndify.StreamingHoundClient(CLIENT_ID, CLIENT_KEY, "test_user", requestInfo, enableVAD=True)
client_houndify.setLocation(37.388309, -121.973968)

# ========== Main ==========
def main():
    print("🛑 Say 'Hello Adam' to start Houndify...")

    while True:
        # Google STT wakeword detection
        audio_bytes = record_audio()
        transcript, confidence = recognize_audio(audio_bytes)

        print(f"📝 Transcript: {transcript}")
        print(f"📊 Confidence: {confidence:.2f}")

        if "adam" in transcript and ("hello" in transcript or "hi" in transcript) and confidence > 0.6:
            print("✅ Wakeword detected! Starting Houndify...")
            run_houndify_session()

            if MODE_EXIT_ON_BYE:
                print("🚪 Program exiting after bye adam.")
                sys.exit(0)
            else:
                print("🔁 Returning to Google STT listening...\n")
        else:
            print("🔁 Wakeword not detected. Listening again...\n")

# ========== Houndify Session ==========
def run_houndify_session():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=BUFFER_SIZE)

    listener = MyListener(stream)
    client_houndify.start(listener)

    print("🎙️ Listening with Houndify... (say 'bye adam' to exit)")

    try:
        while True:
            samples = stream.read(BUFFER_SIZE, exception_on_overflow=False)
            if client_houndify.fill(samples):
                client_houndify.finish()
                if listener.should_exit:
                    print("✅ Exiting Houndify session.")
                    break
                time.sleep(1)
                listener = MyListener(stream)
                client_houndify.start(listener)

    except KeyboardInterrupt:
        print("🛑 Keyboard interrupt, exiting Houndify.")

    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

# ========== Entry ==========
if __name__ == "__main__":
    main()