import sys
import json
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

def get_transcript(video_id):
    try:
        # Fetch the transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Combine text
        full_text = " ".join([item['text'] for item in transcript_list])
        
        # Print JSON result
        print(json.dumps({
            "success": True,
            "transcript": full_text
        }))
        
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(json.dumps({
            "success": False,
            "error": "Transcripts are disabled or not available for this video."
        }))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e)
        }))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No video ID provided"}))
        sys.exit(1)
        
    video_id = sys.argv[1]
    get_transcript(video_id)
