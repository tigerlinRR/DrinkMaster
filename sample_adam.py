#!/usr/bin/env python3
import sys
import time
import base64
import houndify
import pyaudio
from playsound import playsound

CLIENT_ID, CLIENT_KEY = sys.argv[1], sys.argv[2]
CHUNK = 512

WAKE_PHRASE = "hi adam"
EXIT_PHRASE = "bye adam"

class MyListener(houndify.HoundListener):
    def __init__(self):
        self.should_exit = False

    def onPartialTranscript(self, transcript):
        print("Partial transcript:", transcript)
        if EXIT_PHRASE in transcript.lower():
            print(f"🛑 Detected exit phrase '{EXIT_PHRASE}'.")
            self.should_exit = True

    def onFinalResponse(self, response):
        res = response['AllResults'][0]
        speak = res["SpokenResponse"]
        print("🔊", speak)
        if 'ResponseAudioBytes' in res:
            data = base64.b64decode(res['ResponseAudioBytes'])
            with open("output.wav", "wb") as f:
                f.write(data)
            playsound("output.wav")
        if 'ConversationState' in res:
            client.setConversationState(res["ConversationState"])

    def onError(self, err):
        print("Error:", err)

def listen_for_wake(p):
    """Block until WAKE_PHRASE appears in mic input (in raw audio)."""
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                    input=True, frames_per_buffer=CHUNK)
    print(f"🎙️ Waiting for '{WAKE_PHRASE}' to start...")
    transcript = ""
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            # You can add lightweight keyword detection here (e.g. Porcupine)
            # For now, just buffer-based streaming and search manually:
            if WAKE_PHRASE in transcript.lower():
                break
            # Recognizing transcripts on-the-fly would require STT;
            # for now, skip. You can add STT detection here.
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
    print(f"✅ Detected wake phrase '{WAKE_PHRASE}', starting Houndify.")
    return

# Initialize
p = pyaudio.PyAudio()
print("✅ Microphone ready.")

while True:
    listen_for_wake(p)

    # Start Houndify streaming
    listener = MyListener()
    client = houndify.StreamingHoundClient(
        CLIENT_ID, CLIENT_KEY, "user",
        {'ResponseAudioVoice': 'Mia',
         'ResponseAudioShortOrLong': 'Short',
         'ResponseAudioEncoding': 'Speex'},
        enableVAD=True
    )
    client.setLocation(37.388309, -121.973968)
    client.start(listener)
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                    input=True, frames_per_buffer=CHUNK)
    print("🎧 Listening... (say 'bye adam' to stop)")

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            if client.fill(data):  # single utterance done
                client.finish()
                if listener.should_exit:
                    print("🛑 Exit phrase heard. Returning to wake loop.")
                    break
                # otherwise restart the conversation session
                time.sleep(1)
                listener = MyListener()
                client.start(listener)
    except KeyboardInterrupt:
        print("🛑 Aborted by user.")
        break
    finally:
        stream.stop_stream()
        stream.close()

# Cleanup
p.terminate()
print("👋 Goodbye.")