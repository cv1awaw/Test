from http.server import BaseHTTPRequestHandler
import json
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import urllib.parse

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data.decode('utf-8'))
            url = body.get('url')
            
            if not url:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing 'url' in request body"}).encode('utf-8'))
                return

            # Extract Video ID
            # Simple regex to catch standard v= parameter or short links
            # We can use a simplified approach or regex similar to the JS one
            video_id = None
            if "v=" in url:
                parsed = urllib.parse.urlparse(url)
                params = urllib.parse.parse_qs(parsed.query)
                if 'v' in params:
                    video_id = params['v'][0]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
            
            # Fallback regex just in case
            if not video_id:
                # Basic extraction for typical YouTube URLs if the above fails
                import re
                match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
                if match:
                    video_id = match.group(1)

            if not video_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid YouTube URL"}).encode('utf-8'))
                return

            # Fetch transcript
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                full_text = " ".join([item['text'] for item in transcript_list])
                
                response_data = {
                    "success": True,
                    "transcript": full_text
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
