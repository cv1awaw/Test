from http.server import BaseHTTPRequestHandler
import json
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import urllib.parse
import re

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data.decode('utf-8'))
            url = body.get('url')
            target_lang = body.get('lang', 'en') # Default to English if not specified
            
            if not url:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing 'url' in request body"}).encode('utf-8'))
                return

            # Robust Video ID Extraction
            video_id = None
            patterns = [
                r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", 
                r"(?:embed\/|v\/|youtu.be\/)([0-9A-Za-z_-]{11})", 
                r"^([0-9A-Za-z_-]{11})$" 
            ]

            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    break

            if not video_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Could not extract Video ID from URL"}).encode('utf-8'))
                return

            # Fetch transcript lists
            try:
                transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Gather available languages for frontend
                available_langs = []
                for t in transcript_list_obj:
                    available_langs.append({
                        "code": t.language_code,
                        "name": t.language,
                        "is_generated": t.is_generated
                    })
                
                # Try to find target language or translate
                transcript = None
                
                try:
                    # 1. Try exact match
                     transcript = transcript_list_obj.find_transcript([target_lang])
                except NoTranscriptFound:
                    # 2. If not found, try to find one that can be translated
                    # Taking the first available (usually the primary one) and translating it
                    try:
                        first_transcript = next(iter(transcript_list_obj))
                        if first_transcript.is_translatable:
                            transcript = first_transcript.translate(target_lang)
                        else:
                            # Fallback: Just return the first one if translation fails/impossible
                            transcript = first_transcript
                    except Exception:
                         # Last resort: just try to get anything 'en' or generated 'en'
                         try:
                             transcript = transcript_list_obj.find_transcript(['en']) 
                         except:
                             transcript = next(iter(transcript_list_obj))

                
                final_data = transcript.fetch()
                
                response_data = {
                    "success": True,
                    "video_id": video_id,
                    "language_code": transcript.language_code,
                    "language_name": transcript.language, 
                    "is_generated": transcript.is_generated,
                    "available_languages": available_langs,
                    "transcript": final_data
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))

            except (TranscriptsDisabled, NoTranscriptFound) as e:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False, 
                    "error": "Transcripts are disabled or not available for this video."
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False, 
                    "error": str(e)
                }).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Server Error: {str(e)}"}).encode('utf-8'))
