# instantiate the pipeline
from pyannote.audio import Pipeline
from pyannote.audio.pipelines import SpeakerDiarization


pipeline = Pipeline.from_pretrained(
  "pyannote/speaker-diarization-3.1",
  use_auth_token="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")


print(pipeline._models)
print(pipeline._inferences)

# run the pipeline on an audio file
diarization = pipeline("audio.mp3")


# dump the diarization output to disk using RTTM format
with open("audio2.rttm", "w") as rttm:
    diarization.write_rttm(rttm)
