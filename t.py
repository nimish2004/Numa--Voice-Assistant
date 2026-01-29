import pyttsx3

engine = pyttsx3.init('sapi5')
engine.say("This is a test. If you hear this, text to speech is working.")
engine.runAndWait()
